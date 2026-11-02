import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).parent / "data"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")


def sample_value(sensor: dict[str, Any], previous: float, rng: random.Random) -> float:
    sensor_type = sensor.get("type", "general").lower()
    unit = sensor.get("unit", "").lower()

    if sensor_type == "temperature":
        baseline, spread, step = 22.0, 7.0, 0.8
    elif sensor_type == "humidity":
        baseline, spread, step = 58.0, 20.0, 2.0
    elif sensor_type == "moisture":
        baseline, spread, step = 38.0, 22.0, 1.8
    elif sensor_type == "smoke":
        baseline, spread, step = 18.0, 16.0, 1.4
    elif sensor_type == "co2":
        baseline, spread, step = 520.0, 180.0, 14.0
    elif sensor_type == "pm25":
        baseline, spread, step = 18.0, 14.0, 1.5
    elif unit == "ph":
        baseline, spread, step = 6.8, 0.8, 0.08
    elif unit in {"m/s", "km/h"}:
        baseline, spread, step = 5.0, 5.0, 0.6
    elif unit == "lx":
        baseline, spread, step = 9000.0, 6000.0, 350.0
    else:
        baseline, spread, step = 45.0, 30.0, 2.5

    if previous == 0:
        previous = rng.uniform(max(0, baseline - spread / 2), baseline + spread / 2)
    value = previous + rng.uniform(-step, step)
    return round(min(baseline + spread, max(0, baseline - spread, value)), 2)


def generate_huge_dataset(data_dir: Path = DATA_DIR, seed: int = 42) -> int:
    """Refresh synthetic telemetry for the existing project inventory."""
    sensors_path = data_dir / "sensors.json"
    alerts_path = data_dir / "alerts.json"
    readings_dir = data_dir / "readings"
    sensors = read_json(sensors_path)
    alerts = read_json(alerts_path)

    if not isinstance(sensors, list):
        raise ValueError(f"Expected a sensor list in {sensors_path}")

    rng = random.Random(seed)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now - timedelta(hours=24)
    timestamps = [
        (start + timedelta(minutes=15 * index)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for index in range(97)
    ]
    latest_timestamp = timestamps[-1]
    alerts_by_sensor = {str(alert.get("sensor_id")): alert for alert in alerts}
    refreshed_alerts = []
    readings_dir.mkdir(parents=True, exist_ok=True)

    for index, sensor in enumerate(sensors):
        sensor_id = str(sensor["id"])
        status = rng.choices(
            ("normal", "warning", "alert", "incident"),
            weights=(92, 4, 3, 1),
            k=1,
        )[0]
        sensor["status"] = status
        sensor["last_reported_status"] = status
        sensor["comment"] = {
            "normal": "System nominal.",
            "warning": "Warning: Sensor readings need attention.",
            "alert": "Alert: Sensor readings exceeded the normal range.",
            "incident": "Incident: Critical sensor condition reported.",
        }[status]
        current_value = 0.0
        path = readings_dir / f"{sensor_id}.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, lineterminator="\n")
            for timestamp in timestamps:
                current_value = sample_value(sensor, current_value, rng)
                writer.writerow((timestamp, current_value))

        sensor["last_sync"] = latest_timestamp
        if status != "normal":
            alert = alerts_by_sensor.get(sensor_id, {})
            started = now - timedelta(minutes=rng.randint(30, 7 * 24 * 60))
            refreshed_alerts.append({
                **alert,
                "id": alert.get("id", int(now.timestamp() * 1000) + index),
                "sensor_id": sensor_id,
                "type": sensor.get("type", "general"),
                "sensor": sensor.get("name", sensor_id),
                "status": status,
                "start_timestamp": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_timestamp": latest_timestamp,
                "area": sensor.get("node", ""),
            })

    write_json(sensors_path, sensors)
    write_json(alerts_path, refreshed_alerts)
    return len(sensors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh the dashboard's synthetic sensor telemetry.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible readings.")
    args = parser.parse_args()
    count = generate_huge_dataset(seed=args.seed)
    print(f"Refreshed 97 readings for each of {count} sensors.")
