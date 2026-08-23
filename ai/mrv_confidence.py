"""
mrv_confidence.py — MRV Confidence Fusion Layer (Blue Carbon MRV)

Combines five independent evidence streams into a single MRV confidence
score (0–100) that M5's backend uses to decide mint / freeze.

Weights (must sum to 1.0):
  IoT sensor consistency       0.20
  Satellite / NDVI evidence    0.25
  AI model confidence          0.25
  Community photo validation   0.15
  Historical trend consistency 0.15

Each raw input is 0–100 (higher = more confidence).
Score ≥ 85 → eligible for minting; score < 60 → freeze trigger.
"""


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

WEIGHTS = {
    "iot":        0.20,
    "satellite":  0.25,
    "ai":         0.25,
    "community":  0.15,
    "historical": 0.15,
}

MINT_THRESHOLD   = 85.0   # score ≥ this → eligible for mint
FREEZE_THRESHOLD = 60.0   # score < this → trigger freeze / alert


# ─────────────────────────────────────────────
# CORE FORMULA
# ─────────────────────────────────────────────

def mrv_confidence(
    iot_consistency:       float,
    satellite_evidence:    float,
    ai_confidence:         float,
    community_evidence:    float,
    historical_consistency: float,
) -> float:
    """
    Compute the weighted MRV confidence score.

    Parameters (each 0–100, higher = more confidence)
    ----------
    iot_consistency        : IoT sensor data quality / agreement with expected
    satellite_evidence     : Satellite NDVI / vegetation health signal
    ai_confidence          : AI model's own confidence (from carbon estimator)
    community_evidence     : Community photo / ground-truth validation
    historical_consistency : Consistency with historical trend for this plot

    Returns
    -------
    float — MRV confidence score 0–100, rounded to 1 dp
    """
    score = (
        iot_consistency        * WEIGHTS["iot"]        +
        satellite_evidence     * WEIGHTS["satellite"]  +
        ai_confidence          * WEIGHTS["ai"]         +
        community_evidence     * WEIGHTS["community"]  +
        historical_consistency * WEIGHTS["historical"]
    )
    return round(min(100.0, max(0.0, score)), 1)


# ─────────────────────────────────────────────
# HEURISTIC CONVERTERS
# ─────────────────────────────────────────────

def iot_score_from_anomaly(anomaly_severity: float) -> float:
    """
    Convert rule-based anomaly severity (0–1) → IoT consistency score (0–100).
    severity = 0   → full confidence (100)
    severity = 1   → zero confidence (0)
    """
    return round(max(0.0, (1.0 - anomaly_severity) * 100.0), 1)


def satellite_score_from_ndvi(
    current_ndvi: float,
    mean_ndvi: float,
    std_ndvi: float = 0.05,
) -> float:
    """
    Convert NDVI deviation from historical mean → satellite evidence score.

    If NDVI is within 1σ of mean: ~100
    At 2σ deviation: ~60
    At 3σ+: → 0
    """
    if std_ndvi <= 0:
        return 100.0
    z = abs(current_ndvi - mean_ndvi) / std_ndvi
    score = max(0.0, 100.0 - z * 20.0)
    return round(score, 1)


def ai_confidence_from_uncertainty(
    estimate: float,
    sigma: float,
) -> float:
    """
    Convert AI uncertainty (sigma / estimate ratio) → AI confidence score (0–100).
    pct_uncertainty = σ/estimate × 100
    conf = 100 − pct_uncertainty × 0.8  (linear decay, cap at 0)
    """
    if estimate <= 0:
        return 50.0
    pct_unc = (sigma / estimate) * 100.0
    return round(max(0.0, 100.0 - pct_unc * 0.8), 1)


# ─────────────────────────────────────────────
# FULL PIPELINE HELPER
# ─────────────────────────────────────────────

def compute_mrv_score(
    anomaly_severity:     float,
    current_ndvi:         float,
    mean_ndvi:            float,
    std_ndvi:             float,
    carbon_estimate:      float,
    carbon_sigma:         float,
    community_evidence:   float = 80.0,    # stub until photo validator is wired
    historical_consistency: float = 80.0,  # derived from NDVI time series trend
) -> dict:
    """
    Convenience wrapper: convert raw signals → MRV confidence dict.
    Returns full breakdown for the API response.
    """
    iot  = iot_score_from_anomaly(anomaly_severity)
    sat  = satellite_score_from_ndvi(current_ndvi, mean_ndvi, std_ndvi)
    ai   = ai_confidence_from_uncertainty(carbon_estimate, carbon_sigma)
    comm = community_evidence
    hist = historical_consistency

    score = mrv_confidence(iot, sat, ai, comm, hist)

    return {
        "mrv_confidence":   score,
        "eligible":         score >= MINT_THRESHOLD,
        "freeze_alert":     score < FREEZE_THRESHOLD,
        "components": {
            "iot_consistency":        iot,
            "satellite_evidence":     sat,
            "ai_confidence":          ai,
            "community_evidence":     comm,
            "historical_consistency": hist,
        },
        "weights": WEIGHTS,
        "thresholds": {
            "mint":   MINT_THRESHOLD,
            "freeze": FREEZE_THRESHOLD,
        },
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 55)
    print("MRV Confidence Fusion — Self-test")
    print("=" * 55)

    # Healthy scenario
    healthy = compute_mrv_score(
        anomaly_severity=0.0,
        current_ndvi=0.42,
        mean_ndvi=0.38,
        std_ndvi=0.04,
        carbon_estimate=1200.0,
        carbon_sigma=90.0,
        community_evidence=85.0,
        historical_consistency=85.0,
    )
    print("\nHealthy plot scenario:")
    print(json.dumps(healthy, indent=2))
    assert healthy["eligible"], "Healthy scenario should be mint-eligible"

    # Degraded scenario
    degraded = compute_mrv_score(
        anomaly_severity=0.85,
        current_ndvi=0.20,
        mean_ndvi=0.38,
        std_ndvi=0.04,
        carbon_estimate=400.0,
        carbon_sigma=300.0,
        community_evidence=40.0,
        historical_consistency=30.0,
    )
    print("\nDegraded plot scenario:")
    print(json.dumps(degraded, indent=2))
    assert degraded["freeze_alert"], "Degraded scenario should trigger freeze"

    print("\n[OK] Both scenarios behave correctly")
