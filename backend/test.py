import json
import random
from datetime import datetime, timedelta

def generate_huge_dataset():
    nodes = ["AgriNode_01", "AgriNode_02", "AgriNode_03"]
    sensor_types = [
        {"name": "Ambient Temperature", "type": "temperature", "unit": "°C", "base": 22.0, "var": 5.0},
        {"name": "Root Zone Moisture", "type": "moisture", "unit": "%", "base": 40.0, "var": 10.0},
        {"name": "Spectral Health Index", "type": "spectral", "unit": "idx", "base": 0.85, "var": 0.1},
        {"name": "Leaf Wetness", "type": "wetness", "unit": "%", "base": 15.0, "var": 5.0},
        {"name": "Solar Radiation", "type": "solar", "unit": "W/m²", "base": 400.0, "var": 200.0},
        {"name": "Soil Conductivity", "type": "ec", "unit": "mS/cm", "base": 1.2, "var": 0.3},
        {"name": "Atmospheric Pressure", "type": "pressure", "unit": "hPa", "base": 1013.0, "var": 2.0},
        {"name": "Wind Speed", "type": "wind", "unit": "km/h", "base": 5.0, "var": 12.0},
        {"name": "CO2 Concentration", "type": "co2", "unit": "ppm", "base": 415.0, "var": 20.0},
        {"name": "Humidity", "type": "humidity", "unit": "%", "base": 60.0, "var": 15.0}
    ]

    data = []
    num_readings = 150  # Over 100 readings per sensor
    start_time = datetime.now() - timedelta(hours=12)

    for i, s_meta in enumerate(sensor_types):
        node = nodes[i % len(nodes)]
        readings = []
        timestamps = []
        
        current_val = s_meta["base"]
        
        for j in range(num_readings):
            # Generate a "random walk" for realistic sensor drift
            change = random.uniform(-s_meta["var"] * 0.1, s_meta["var"] * 0.1)
            current_val = max(0, current_val + change)
            
            readings.append(round(current_val, 2))
            ts = start_time + timedelta(minutes=5 * j)
            timestamps.append(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))

        sensor_obj = {
            "id": f"node-{i:02d}-{s_meta['type']}",
            "name": s_meta["name"],
            "node": node,
            "type": s_meta["type"],
            "area": "Mitidja Plain",
            "unit": s_meta["unit"],
            "current_value": readings[-1],
            "timestamps": timestamps,
            "readings": readings
        }
        data.append(sensor_obj)

    with open('sensor.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Successfully generated sensor.json with {len(data)} sensors and {num_readings} readings each.")

if __name__ == "__main__":
    generate_huge_dataset()