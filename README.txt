# Polaris Dashboard - Hackathon Technical Guide

## 🚀 Launching the System
Local server:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000

---

## 🛠 Under the Hood: How it Works

1. **The "Push" Architecture (`sensor_status.json`)**:
   - External scripts or MCU integrations don't need to call complex APIs. They simply append to `backend/data/sensor_status.json`.
   - The backend runs `sync_from_status_file()` on every key API request. 
   - It reads the status, updates `sensors.json` (for current state), and creates/updates entries in `alerts.json` (for the historical log).
   - Once processed, the backend clears `sensor_status.json`.

2. **Smart Alert Tracking (`alerts.json`)**:
   - When a sensor enters a non-normal state (alert/warning), a new entry is created with a `start_timestamp`.
   - If the same sensor reports the same error again, the backend simply updates the `end_timestamp` of that existing entry.
   - If the status changes (e.g., Warning -> Alert), a new entry is created.
   - "Normal" statuses are never logged as alerts but are updated in the sensor's metadata.

3. **Node Status Inheritance**:
   - Nodes (Areas) do not have a fixed status. They automatically inherit the "Highest Danger Level" from all sensors assigned to them.
   - Priority: Alert (Red) > Warning (Yellow) > Incident (Orange) > Normal (Green).

4. **Telemetry Storage (CSV)**:
   - High-frequency data (readings) is NOT stored in JSON to keep things fast.
   - Each sensor has its own file: `backend/data/readings/<sensor_id>.csv`.
   - Format: `timestamp,value` (no headers).

5. **AI Analysis (`node_report.json`)**:
   - The "AI Summary" boxes are driven by this file. Team members can push text summaries here, and the backend maps them to specific areas or the "global" dashboard.

---

## 📊 Data Structures

### 1. `sensors.json` (Metadata & Current State)
```json
{
  "id": "node-15",
  "name": "Ambient Temp",
  "node": "Mitidja Plain",
  "type": "temperature",
  "unit": "°C",
  "battery": "85",
  "status": "alert",
  "last_sync": "2026-03-04T12:00:00Z",
  "last_reported_status": "alert"
}
```

### 2. `sensor_status.json` (The Team Input File)
**PUSH DATA HERE TO TEST TRANSITIONS**
```json
[
  {
    "id": "node-15",
    "status": "warning",
    "timestamp": "2026-03-04T14:30:00Z"
  }
]
```

### 3. `alerts.json` (The Persistence Log)
```json
{
  "id": 1741100000000,
  "sensor_id": "node-15",
  "status": "warning",
  "start_timestamp": "2026-03-04T14:30:00Z",
  "end_timestamp": "2026-03-04T15:00:00Z",
  "area": "Mitidja Plain"
}
```

### 4. `node_report.json` (AI Summaries)
```json
[
  { "name": "global", "report": "System is stable." },
  { "name": "Mitidja Plain", "report": "Extreme heat detected." }
]
```

### 5. `settings.json` (Thresholds)
```json
{
  "thresholds": {
    "temperature": { "warning": 25.0, "alert": 35.0 }
  }
}
```

### 6. `log.json` (Archives)
- Stores entries deleted from the dashboard table for legal/audit review.
