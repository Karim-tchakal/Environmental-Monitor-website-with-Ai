import json
import os
import csv
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional, List, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Path Configuration ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENSORS_FILE = os.path.join(BASE_DIR, "data", "sensors.json")
NODES_FILE   = os.path.join(BASE_DIR, "data", "nodes.json")
USER_FILE    = os.path.join(BASE_DIR, "data", "user.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "data", "settings.json")
ALERT_FILE   = os.path.join(BASE_DIR, "data", "alerts.json")
LOG_FILE     = os.path.join(BASE_DIR, "data", "log.json")
READINGS_DIR = os.path.join(BASE_DIR, "data", "readings")

# Static and Template mounting
app.mount("/frontend", StaticFiles(directory=os.path.join(BASE_DIR, "..", "frontend")), name="frontend")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "..", "frontend"))

# ── Data Helpers ───────────────────────────────────────────────────────────

def read_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def read_sensor_readings(sensor_id):
    path = os.path.join(READINGS_DIR, f"{sensor_id}.csv")
    timestamps = []
    readings = []
    if os.path.exists(path):
        with open(path, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    timestamps.append(row[0])
                    try:
                        readings.append(float(row[1]))
                    except ValueError:
                        readings.append(0.0)
    return timestamps, readings

def get_sensor_graph_color(stype, last_val, thresholds):
    """Visualization ONLY color based on thresholds"""
    t = thresholds.get(stype)
    if not t: return "blue"
    if stype == "moisture":
        if last_val <= t["alert"]: return "red"
        if last_val <= t["warning"]: return "yellow"
    else:
        if last_val >= t["alert"]: return "red"
        if last_val >= t["warning"]: return "yellow"
    return "blue"

def sync_alerts():
    """
    Refined Alert Sync:
    - Uses last_reported_status to detect transitions.
    - Alert/Warning persistent in alerts.json.
    - Normal status is ignored.
    - End time updated only if status remains the same non-normal state.
    """
    sensors = read_json(SENSORS_FILE)
    alerts = read_json(ALERT_FILE)
    
    updated_sensors = False
    updated_alerts = False
    
    for s in sensors:
        current_status = s.get("status", "normal").lower()
        prev_status = s.get("last_reported_status", "normal").lower()
        current_ts = s.get("last_sync") or datetime.now().isoformat()
        
        if current_status == prev_status:
            # Status hasn't changed. If it's non-normal, update the end time of the LATEST alert for this sensor.
            if current_status != "normal":
                sensor_alerts = [a for a in alerts if a.get("sensor_id") == s["id"]]
                if sensor_alerts:
                    latest = sensor_alerts[-1]
                    if latest.get("status") == current_status:
                        if current_ts > latest.get("end_timestamp", ""):
                            latest["end_timestamp"] = current_ts
                            updated_alerts = True
                else:
                    # Fallback: create if it somehow doesn't exist
                    new_alert = {
                        "id": int(datetime.now().timestamp() * 1000) + len(alerts),
                        "sensor_id": s["id"],
                        "type": s["type"],
                        "sensor": s["name"],
                        "status": current_status,
                        "start_timestamp": current_ts,
                        "end_timestamp": current_ts,
                        "area": s["node"]
                    }
                    alerts.append(new_alert)
                    updated_alerts = True
        else:
            # Status HAS changed.
            if current_status != "normal":
                # Entered a new non-normal state (Warning -> Alert or Normal -> Warning, etc.)
                new_alert = {
                    "id": int(datetime.now().timestamp() * 1000) + len(alerts),
                    "sensor_id": s["id"],
                    "type": s["type"],
                    "sensor": s["name"],
                    "status": current_status,
                    "start_timestamp": current_ts,
                    "end_timestamp": current_ts,
                    "area": s["node"]
                }
                alerts.append(new_alert)
                updated_alerts = True
            
            s["last_reported_status"] = current_status
            updated_sensors = True
            
    if updated_alerts:
        write_json(ALERT_FILE, alerts)
    if updated_sensors:
        write_json(SENSORS_FILE, sensors)
        
    return alerts

def get_computed_nodes():
    nodes = read_json(NODES_FILE)
    sensors = read_json(SENSORS_FILE)
    
    # Status hierarchy from SENSORS.JSON status field
    RANK = {"alert": 4, "warning": 3, "incident": 2, "normal": 1}
    
    for n in nodes:
        node_sensors = [s for s in sensors if s.get("node") == n.get("name")]
        max_rank = 1
        max_status = "normal"
        for s in node_sensors:
            s_status = s.get("status", "normal").lower()
            if RANK.get(s_status, 0) > max_rank:
                max_rank = RANK.get(s_status)
                max_status = s_status
        
        n["status"] = max_status
        ICONS = {"alert": "⚠️", "warning": "⚡", "incident": "❗", "normal": "✅"}
        n["icon"] = ICONS.get(n["status"], "📍")
    return nodes

def get_ai_summary_text(context="global"):
    summaries = {
        "global": "Neural analysis suggests consistent patterns. Mitidja sensor array reports humidity fluctuations within historical alert margins.",
        "default": "Station telemetry is stable. No immediate actions required. Battery levels at 85% average."
    }
    return summaries.get(context.lower(), summaries["default"])

# ── Pydantic Models ────────────────────────────────────────────────────────

class NodeModel(BaseModel):
    id: Optional[int] = None
    name: str
    lat: float
    lng: float
    status: Optional[str] = "normal"
    icon: Optional[str] = "📍"

class SensorModel(BaseModel):
    id: str
    status: str
    battery: str
    name: str
    node: str
    type: str
    unit: str

class SettingsModel(BaseModel):
    thresholds: dict[str, Any]

# ── HTML Routes ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/maps", response_class=HTMLResponse)
async def maps(request: Request):
    return templates.TemplateResponse("maps.html", {"request": request})

@app.get("/sensors", response_class=HTMLResponse)
async def sensors_page(request: Request):
    return templates.TemplateResponse("sensors.html", {"request": request})

@app.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request):
    return templates.TemplateResponse("sense_dashboard.html", {"request": request})

@app.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/ai", response_class=HTMLResponse)
async def ai(request: Request):
    return templates.TemplateResponse("ai.html", {"request": request})

@app.get("/sense_dashboard", response_class=HTMLResponse)
async def sense(request: Request):
    return templates.TemplateResponse("sense_dashboard.html", {"request": request})

@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard/{station_id}", response_class=HTMLResponse)
async def station_dashboard(request: Request, station_id: int):
    nodes = get_computed_nodes()
    node  = next((n for n in nodes if str(n.get("id")) == str(station_id)), None)
    if not node:
        raise HTTPException(status_code=404, detail="Station not found")
    return templates.TemplateResponse("station.html", {"request": request, "station": node})

# ── API Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/ai/summary")
def api_ai_summary(node: Optional[str] = None):
    return {"summary": get_ai_summary_text(node or "global")}

@app.get("/api/reports")
def api_reports():
    nodes = get_computed_nodes()
    sensors = read_json(SENSORS_FILE)
    report_data = []
    RANK = {"alert": 4, "warning": 3, "incident": 2, "normal": 1}
    for n in nodes:
        node_sensors = [s for s in sensors if s.get("node") == n.get("name")]
        report_data.append({
            "id": n["id"],
            "area": n["name"],
            "status": n["status"],
            "rank": RANK.get(n["status"], 0),
            "summary": get_ai_summary_text(n["name"]),
            "sensors_count": len(node_sensors)
        })
    return sorted(report_data, key=lambda x: x["rank"], reverse=True)

@app.get("/api/settings")
def get_settings():
    settings = read_json(SETTINGS_FILE)
    if not settings or "thresholds" not in settings:
        settings = {
            "thresholds": {
                "temperature": {"warning": 25.0, "alert": 35.0},
                "humidity": {"warning": 70.0, "alert": 85.0},
                "moisture": {"warning": 20.0, "alert": 10.0},
                "smoke": {"warning": 50.0, "alert": 150.0}
            }
        }
        write_json(SETTINGS_FILE, settings)
    return settings

@app.post("/api/settings")
def update_settings(settings: SettingsModel):
    write_json(SETTINGS_FILE, settings.dict())
    return {"status": "success", "settings": settings}

@app.get("/api/user")
def get_user():
    user_data = read_json(USER_FILE)
    if not user_data:
        user_data = {"name": "Admin", "avatar": "https://i.pravatar.cc/32"}
        write_json(USER_FILE, user_data)
    sync_alerts()
    alerts = read_json(ALERT_FILE)
    if alerts:
        sorted_alerts = sorted(alerts, key=lambda x: x.get('end_timestamp', ''), reverse=True)
        user_data["last_alert"] = sorted_alerts[0].get('end_timestamp')
    else:
        user_data["last_alert"] = "No events"
    return user_data

@app.get("/api/stats")
def get_stats():
    sensors = read_json(SENSORS_FILE)
    nodes = get_computed_nodes()
    sync_alerts()
    alerts = read_json(ALERT_FILE)
    counts = Counter([a.get("status", "").lower() for a in alerts])
    return [
        {"title": "Alerts",    "value": counts['alert'],    "change": "", "color": "red"},
        {"title": "Incidents", "value": counts['incident'], "change": "", "color": "orange"},
        {"title": "Warnings",  "value": counts['warning'],  "change": "", "color": "yellow"},
        {"title": "Active Sensors", "value": len(sensors), "change": "", "color": "blue"},
        {"title": "Maps", "value": len(nodes), "change": "", "color": "green"},
    ]

@app.get("/api/sensors")
def get_sensors(area: Optional[str] = None):
    sensors = read_json(SENSORS_FILE)
    settings = get_settings()
    thresholds = settings.get("thresholds", {})
    if area:
        sensors = [s for s in sensors if s.get("node") == area]
    for s in sensors:
        ts, rd = read_sensor_readings(s["id"])
        s["timestamps"] = ts
        s["readings"] = rd
        if rd:
            s["current_value"] = rd[-1]
            s["last_sync"] = ts[-1]
            s["graph_color"] = get_sensor_graph_color(s["type"], rd[-1], thresholds)
    return sensors

@app.post("/api/sensors")
def add_sensor(sensor: SensorModel):
    sensors = read_json(SENSORS_FILE)
    if any(s["id"] == sensor.id for s in sensors):
        raise HTTPException(status_code=400, detail="Sensor ID already exists")
    sensors.append(sensor.dict())
    write_json(SENSORS_FILE, sensors)
    csv_path = os.path.join(READINGS_DIR, f"{sensor.id}.csv")
    if not os.path.exists(csv_path):
        with open(csv_path, "w") as f: pass
    return {"status": "success", "sensor": sensor}

@app.get("/api/alerts")
def get_alerts_api():
    return sync_alerts()

@app.get("/api/alerts/active")
def get_active_alerts():
    sensors = read_json(SENSORS_FILE)
    active = []
    for s in sensors:
        status = s.get("status", "normal").lower()
        if status != "normal":
            ts, rd = read_sensor_readings(s["id"])
            val = rd[-1] if rd else "N/A"
            active.append({
                "id": s["id"], "name": s["name"], "node": s["node"],
                "type": s["type"], "value": val, "unit": s["unit"],
                "status": status, "timestamp": s.get("last_sync")
            })
    return active

@app.delete("/api/alerts/{item_id}")
def delete_alert(item_id: int):
    alerts = read_json(ALERT_FILE)
    logs = read_json(LOG_FILE)
    deleted = [a for a in alerts if a.get("id") == item_id]
    if deleted:
        log_entry = deleted[0]
        log_entry["log_type"] = "alert_deleted"
        log_entry["deleted_at"] = datetime.now().isoformat()
        logs.append(log_entry)
        write_json(LOG_FILE, logs)
    new_alerts = [a for a in alerts if a.get("id") != item_id]
    write_json(ALERT_FILE, new_alerts)
    return {"status": "deleted"}

@app.delete("/api/sensors/{item_id}")
def delete_sensor(item_id: str):
    data = read_json(SENSORS_FILE)
    logs = read_json(LOG_FILE)
    deleted = [s for s in data if str(s.get("id")) == item_id]
    if deleted:
        log_entry = deleted[0]
        log_entry["log_type"] = "sensor_deleted"
        log_entry["deleted_at"] = datetime.now().isoformat()
        logs.append(log_entry)
        write_json(LOG_FILE, logs)
    new_data = [i for i in data if str(i.get("id")) != item_id]
    write_json(SENSORS_FILE, new_data)
    csv_path = os.path.join(READINGS_DIR, f"{item_id}.csv")
    if os.path.exists(csv_path): os.remove(csv_path)
    return {"status": "deleted"}

@app.get("/api/nodes")
def get_nodes_api():
    return get_computed_nodes()

@app.post("/api/nodes")
def add_node(node: NodeModel):
    nodes = read_json(NODES_FILE)
    if node.id is None:
        node.id = max([n.get("id", 0) for n in nodes] + [0]) + 1
    if any(n.get("id") == node.id for n in nodes):
        raise HTTPException(status_code=400, detail="Node ID already exists")
    nodes.append(node.dict())
    write_json(NODES_FILE, nodes)
    return {"status": "success", "node": node}

@app.put("/api/nodes/{item_id}")
def update_node(item_id: int, node_update: NodeModel):
    nodes = read_json(NODES_FILE)
    for i, n in enumerate(nodes):
        if n.get("id") == item_id:
            updated = n.copy()
            updated.update(node_update.dict(exclude_unset=True))
            nodes[i] = updated
            write_json(NODES_FILE, nodes)
            return {"status": "success", "node": updated}
    raise HTTPException(status_code=404, detail="Node not found")

@app.delete("/api/nodes/{item_id}")
def delete_node(item_id: str):
    data = read_json(NODES_FILE)
    new_data = [i for i in data if str(i.get("id")) != str(item_id)]
    write_json(NODES_FILE, new_data)
    return {"status": "deleted"}

@app.get("/api/station/{station_id}")
def get_station_data(station_id: int):
    nodes = get_computed_nodes()
    node = next((n for n in nodes if str(n.get("id")) == str(station_id)), None)
    if not node: raise HTTPException(status_code=404, detail="Station not found")
    sensors = get_sensors()
    node_sensors = [s for s in sensors if s.get("node") == node.get("name")]
    return {"info": node, "sensors": node_sensors}
