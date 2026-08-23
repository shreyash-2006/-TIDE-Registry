"""
simulator.py — IoT Sensor Data Generator for MNG-001 (Pichavaram)

Generates realistic sensor readings in normal and anomaly modes.
Used to:
  1. Train the IsolationForest (generate_normal_dataset)
  2. Produce live readings for the demo (generate_reading)
  3. Trigger controlled anomaly events during the demo (anomaly=True)

Normal ranges derived from:
  - Bay of Bengal coastal mangrove salinity: 10–18 ppt
  - Tropical coastal water temperature: 26–30 °C
  - Mangrove creek pH: 7.4–8.1
  - Mangrove soil moisture: 55–75 %
  - Tidal water level Pichavaram: 0.8–1.5 m
"""

import time
import json
import numpy as np
import pandas as pd
import os

# ─────────────────────────────────────────────
# NORMAL SENSOR RANGES
# ─────────────────────────────────────────────

NORMAL_RANGES: dict[str, tuple[float, float]] = {
    "salinity":      (10.0, 18.0),   # ppt
    "temperature":   (26.0, 30.0),   # °C
    "ph":            (7.4,  8.1),    # unitless
    "soil_moisture": (55.0, 75.0),   # %
    "water_level":   (0.8,  1.5),    # m
}

ANOMALY_SENSORS = ("salinity", "soil_moisture", "temperature")


# ─────────────────────────────────────────────
# CORE GENERATOR
# ─────────────────────────────────────────────

def generate_reading(
    anomaly: bool = False,
    rng: np.random.Generator | None = None,
) -> dict:
    """
    Return one sensor reading dict.

    Normal mode : all values drawn uniformly from NORMAL_RANGES.
    Anomaly mode: salinity, soil_moisture, temperature are pushed
                  out of range by a random factor (×0.45 or ×1.85).

    Fields:
        plot_id, timestamp, salinity, temperature, ph,
        soil_moisture, water_level, anomaly_injected
    """
    if rng is None:
        rng = np.random.default_rng()

    reading: dict = {"plot_id": "MNG-001"}

    for key, (low, high) in NORMAL_RANGES.items():
        val = rng.uniform(low, high)
        if anomaly and key in ANOMALY_SENSORS:
            val = val * rng.choice([0.45, 1.85])
        reading[key] = round(float(val), 3)

    reading["timestamp"]        = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reading["anomaly_injected"] = anomaly
    return reading


# ─────────────────────────────────────────────
# BATCH GENERATOR (for IsolationForest training)
# ─────────────────────────────────────────────

def generate_normal_dataset(
    n: int = 500,
    seed: int = 42,
    save_path: str | None = None,
) -> pd.DataFrame:
    """
    Generate n normal readings, optionally save as CSV, return DataFrame.
    Used to fit the IsolationForest model in anomaly_model.py.
    """
    rng = np.random.default_rng(seed)
    rows = [generate_reading(anomaly=False, rng=rng) for _ in range(n)]
    df   = pd.DataFrame(rows)

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        df.to_csv(save_path, index=False)
        print(f"Normal dataset ({n} rows) saved -> {save_path}")

    return df


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IoT sensor simulator for MNG-001")
    parser.add_argument("--anomaly",  action="store_true", help="Inject an anomaly")
    parser.add_argument("--generate", type=int, metavar="N",
                        help="Generate N normal training rows and save to data/iot_normal.csv")
    parser.add_argument("--stream",   type=int, default=0, metavar="COUNT",
                        help="Stream COUNT readings to stdout (1 per second)")
    args = parser.parse_args()

    if args.generate:
        data_dir  = os.path.join(os.path.dirname(__file__), "data")
        save_path = os.path.join(data_dir, "iot_normal.csv")
        df = generate_normal_dataset(n=args.generate, save_path=save_path)
        print(df.describe())

    elif args.stream:
        rng = np.random.default_rng()
        for i in range(args.stream):
            reading = generate_reading(anomaly=args.anomaly, rng=rng)
            print(json.dumps(reading))
            time.sleep(1)

    else:
        # Default: print one reading
        reading = generate_reading(anomaly=args.anomaly)
        print(json.dumps(reading, indent=2))
