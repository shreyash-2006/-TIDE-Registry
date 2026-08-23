"""
anomaly_model.py — Blue Carbon MRV (Plot: MNG-001, Pichavaram)

Two-layer anomaly detection:

  Layer A — Rule-based (primary)
      Deterministic, highly explainable.
      Checks NDVI drop, IoT sensor out-of-range, and biomass deviation.
      Binary anomaly flag used for the live demo trigger.

  Layer B — Statistical, IsolationForest (secondary signal)
      Multivariate outlier score on the 5 IoT sensor dimensions.
      Trained on 500 synthetic normal readings from simulator.py.
      Provides a continuous score the MRV confidence fusion consumes.

  Combined score:
      final_score = 0.7 × rule_severity + 0.3 × statistical_score
      (rule-based drives the binary flag; blended score feeds fusion layer)
"""

import os
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest

from simulator import NORMAL_RANGES, generate_normal_dataset

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
MODEL_PATH   = os.path.join(os.path.dirname(__file__), "models", "iso_forest.pkl")
IOT_CSV_PATH = os.path.join(os.path.dirname(__file__), "data",   "iot_normal.csv")

SENSOR_COLS = ["salinity", "temperature", "ph", "soil_moisture", "water_level"]


# ─────────────────────────────────────────────
# LAYER A — RULE-BASED
# ─────────────────────────────────────────────

def rule_based_anomaly(
    current: dict,
    previous: dict,
    expected_range: dict | None = None,
) -> dict:
    """
    Evaluate current reading against previous and expected ranges.

    Parameters
    ----------
    current : dict
        Latest sensor reading (salinity, temperature, ph,
        soil_moisture, water_level, ndvi).
    previous : dict
        Reading immediately before current (same fields).
    expected_range : dict, optional
        Override of NORMAL_RANGES. If not provided, NORMAL_RANGES is used.

    Returns
    -------
    dict with keys:
        anomaly (bool), severity (float 0–1), reasons (list[str])
    """
    if expected_range is None:
        expected_range = {k: list(v) for k, v in NORMAL_RANGES.items()}

    flags: list[str] = []

    # ── 1. NDVI drop ──────────────────────────────────────────────────
    curr_ndvi = current.get("ndvi")
    prev_ndvi = previous.get("ndvi")

    ndvi_drop_fraction = 0.0
    if curr_ndvi is not None and prev_ndvi is not None and prev_ndvi > 0:
        ndvi_drop_fraction = (prev_ndvi - curr_ndvi) / prev_ndvi
        if ndvi_drop_fraction > 0.20:
            flags.append(
                f"NDVI dropped {ndvi_drop_fraction:.1%} "
                f"(from {prev_ndvi:.3f} -> {curr_ndvi:.3f})"
            )

    # ── 2. IoT sensor out-of-range ────────────────────────────────────
    for sensor in SENSOR_COLS:
        val = current.get(sensor)
        if val is None:
            continue
        rng = expected_range.get(sensor)
        if rng is None:
            continue
        lo, hi = rng[0], rng[1]
        if not (lo <= val <= hi):
            flags.append(
                f"{sensor} out of expected range "
                f"[{lo}, {hi}]: got {val}"
            )

    # ── 3. Reported vs modelled biomass mismatch ──────────────────────
    reported_biomass = current.get("reported_biomass")
    model_biomass    = current.get("model_biomass_estimate")

    if reported_biomass is not None and model_biomass and model_biomass > 0:
        deviation = abs(reported_biomass - model_biomass) / model_biomass
        if deviation > 0.20:
            flags.append(
                f"Reported vs modelled biomass deviates "
                f"{deviation:.1%} "
                f"(reported={reported_biomass:.1f}, model={model_biomass:.1f})"
            )

    # ── Severity score ─────────────────────────────────────────────────
    # Each flag contributes 0.3; NDVI drop adds its fractional magnitude on top.
    ndvi_component = ndvi_drop_fraction if ndvi_drop_fraction > 0 else 0.0
    severity = min(1.0, len(flags) * 0.3 + ndvi_component)

    return {
        "anomaly":  len(flags) > 0,
        "severity": round(severity, 3),
        "reasons":  flags,
    }


# ─────────────────────────────────────────────
# LAYER B — ISOLATION FOREST
# ─────────────────────────────────────────────

def train_isolation_forest(
    n_normal: int = 500,
    contamination: float = 0.05,
    seed: int = 42,
) -> IsolationForest:
    """
    Train IsolationForest on synthetic normal readings and save the model.
    """
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    df = generate_normal_dataset(n=n_normal, seed=seed, save_path=IOT_CSV_PATH)
    X  = df[SENSOR_COLS].values

    iso = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=seed,
    )
    iso.fit(X)

    joblib.dump(iso, MODEL_PATH)
    print(f"IsolationForest trained on {n_normal} normal readings -> {MODEL_PATH}")

    # Quick false-positive check on training data
    preds    = iso.predict(X)
    fp_rate  = (preds == -1).mean()
    print(f"False-positive rate on training set: {fp_rate:.2%}  "
          f"(target ~= contamination={contamination:.2%})")

    return iso


_iso_model: IsolationForest | None = None

def _load_iso() -> IsolationForest:
    global _iso_model
    if _iso_model is None:
        if not os.path.exists(MODEL_PATH):
            print("IsolationForest model not found — training now …")
            train_isolation_forest()
        _iso_model = joblib.load(MODEL_PATH)
    return _iso_model


def statistical_anomaly_score(reading: dict) -> float:
    """
    Return a non-negative anomaly score for one sensor reading.
    Higher → more anomalous.
    0.0 means the reading is well inside the normal distribution.

    Uses IsolationForest.decision_function(), negated so positive = anomalous.
    The raw range is roughly −0.5 … +0.5; we clip to [0, ∞) and round.
    """
    iso = _load_iso()
    X   = [[
        reading.get("salinity",      14.0),
        reading.get("temperature",   28.0),
        reading.get("ph",             7.7),
        reading.get("soil_moisture", 65.0),
        reading.get("water_level",    1.1),
    ]]
    score = float(-iso.decision_function(X)[0])  # higher → more anomalous
    return round(max(0.0, score), 4)


# ─────────────────────────────────────────────
# COMBINED SCORE
# ─────────────────────────────────────────────

def combined_anomaly(
    current: dict,
    previous: dict,
    expected_range: dict | None = None,
) -> dict:
    """
    Full anomaly assessment combining rule-based and statistical signals.

    Returns all rule-based fields plus:
        statistical_score    : raw IsolationForest anomaly score
        combined_score       : 0.7 × rule_severity + 0.3 × norm_stat
    """
    rule  = rule_based_anomaly(current, previous, expected_range)
    stat  = statistical_anomaly_score(current)

    # Normalise stat score to [0, 1] — typical max is ~0.5 for hard anomalies
    norm_stat     = min(1.0, stat * 2.0)
    combined      = 0.7 * rule["severity"] + 0.3 * norm_stat

    return {
        **rule,
        "statistical_score": stat,
        "combined_score":    round(combined, 3),
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 50)
    print("Training IsolationForest...")
    train_isolation_forest()

    print("\n" + "=" * 50)
    print("Self-test -- healthy reading:")
    healthy = {
        "salinity":      14.0,
        "temperature":   28.0,
        "ph":             7.8,
        "soil_moisture": 65.0,
        "water_level":    1.1,
        "ndvi":           0.45,
    }
    prev = {**healthy, "ndvi": 0.46}
    result_h = combined_anomaly(healthy, prev)
    print(json.dumps(result_h, indent=2))
    assert not result_h["anomaly"], "Healthy reading falsely flagged!"
    print("[OK] Healthy reading correctly NOT flagged")

    print("\n" + "=" * 50)
    print("Self-test -- degraded reading:")
    degraded = {
        "salinity":      28.0,  # out of range
        "temperature":   35.0,  # out of range
        "ph":             7.8,
        "soil_moisture": 22.0,  # out of range
        "water_level":    1.1,
        "ndvi":           0.25,  # sharp drop
    }
    prev_d = {**degraded, "salinity": 14.0, "temperature": 28.0,
              "soil_moisture": 65.0, "ndvi": 0.45}
    result_d = combined_anomaly(degraded, prev_d)
    print(json.dumps(result_d, indent=2))
    assert result_d["anomaly"], "Degraded reading NOT flagged!"
    print("[OK] Degraded reading correctly FLAGGED")
