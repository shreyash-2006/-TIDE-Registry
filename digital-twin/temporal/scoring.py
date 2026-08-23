"""
temporal/scoring.py — Health and permanence composite scores

Two numbers that make the Twin feel intelligent rather than just a data dump
(per the work plan, §4).

health_score    — current vegetation condition, sensor normalcy, anomaly state
permanence_score — likelihood that the carbon stock will persist, based on
                   recent volatility and credit status

Both return 0–100, clamped, single decimal.
"""

import math
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from temporal.snapshot import TwinSnapshot


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH SCORE
# ─────────────────────────────────────────────────────────────────────────────

def health_score(
    ndvi_current:       float,
    ndvi_baseline:      float,
    iot_anomaly_penalty: float = 0.0,
    ai_anomaly_severity: float = 0.0,
) -> float:
    """
    Composite health score (0–100) for a plot snapshot.

    Formula (from work plan §4):
        base    = (ndvi_current / ndvi_baseline) × 100, capped at 100
        penalty = iot_anomaly_penalty + (ai_anomaly_severity × 30)
        score   = max(0, base - penalty)

    Parameters
    ----------
    ndvi_current : float
        Current NDVI reading.
    ndvi_baseline : float
        Historical baseline NDVI (> 0).
    iot_anomaly_penalty : float
        Additional penalty from IoT rule-based anomaly score (0–30 typical).
    ai_anomaly_severity : float
        M1 anomaly severity (0–1). Multiplied by 30 to convert to score penalty.

    Returns
    -------
    float
        Health score, 0.0–100.0.
    """
    if ndvi_baseline <= 0:
        raise ValueError(f"ndvi_baseline must be > 0, got {ndvi_baseline}")

    ndvi_ratio = min(1.0, ndvi_current / ndvi_baseline)
    base       = ndvi_ratio * 100
    penalty    = iot_anomaly_penalty + (ai_anomaly_severity * 30)
    score      = max(0.0, base - penalty)
    return round(score, 1)


# ─────────────────────────────────────────────────────────────────────────────
# PERMANENCE SCORE
# ─────────────────────────────────────────────────────────────────────────────

def permanence_score(
    h_score:           float,
    recent_volatility: float = 0.0,
    credit_status:     Optional[str] = None,
) -> float:
    """
    Carbon permanence score (0–100).

    Permanence isn't just current health — it's stability of that health
    over time (a good talking point for judges).

    Formula (from work plan §4):
        base    = health_score
        penalty = recent_volatility × 20
        if credit_status in (FROZEN, UNDER_REVIEW): penalty += 15
        score   = max(0, base - penalty)

    Parameters
    ----------
    h_score : float
        Current health score (0–100).
    recent_volatility : float
        Std-dev of last N health scores (0–100 scale). Higher → less permanent.
    credit_status : str or None
        Credit chain state. FROZEN or UNDER_REVIEW add a 15-point penalty.

    Returns
    -------
    float
        Permanence score, 0.0–100.0.
    """
    penalty = recent_volatility * 20
    if credit_status in ("FROZEN", "UNDER_REVIEW"):
        penalty += 15
    score = max(0.0, h_score - penalty)
    return round(score, 1)


# ─────────────────────────────────────────────────────────────────────────────
# VOLATILITY HELPER
# ─────────────────────────────────────────────────────────────────────────────

def compute_volatility(snapshots: List["TwinSnapshot"], n: int = 5) -> float:
    """
    Compute recent health-score volatility as std-dev of last N snapshots.

    Normalised to 0–1 range (dividing by 100) so it plugs directly into
    permanence_score's recent_volatility parameter.

    Parameters
    ----------
    snapshots : list of TwinSnapshot
        Full plot history (oldest first).
    n : int
        Number of most-recent snapshots to consider.

    Returns
    -------
    float
        Normalised volatility (0.0 = perfectly stable, 1.0 = max swing).
    """
    if not snapshots:
        return 0.0

    recent_scores = [
        s.health_score for s in snapshots[-n:]
        if s.health_score is not None
    ]

    if len(recent_scores) < 2:
        return 0.0

    mean = sum(recent_scores) / len(recent_scores)
    variance = sum((x - mean) ** 2 for x in recent_scores) / len(recent_scores)
    std_dev = math.sqrt(variance)

    # Normalise: divide by 100 (the max possible swing)
    return round(min(1.0, std_dev / 100), 4)


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE: COMPUTE BOTH SCORES FROM A SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────

def score_snapshot(
    snapshot: "TwinSnapshot",
    ndvi_baseline:      float,
    iot_anomaly_penalty: float = 0.0,
    ai_anomaly_severity: float = 0.0,
    history: Optional[List["TwinSnapshot"]] = None,
) -> dict:
    """
    Compute health and permanence scores for a snapshot and return both.

    Parameters
    ----------
    snapshot : TwinSnapshot
        The snapshot to score (uses its ndvi and credit_status fields).
    ndvi_baseline : float
        Historical NDVI baseline for the plot.
    iot_anomaly_penalty : float
        From M3's IoT anomaly score.
    ai_anomaly_severity : float
        From M1's anomaly severity (0–1).
    history : list, optional
        Full plot history for volatility computation.

    Returns
    -------
    dict
        {health_score, permanence_score, volatility, inputs}
    """
    ndvi = snapshot.ndvi if snapshot.ndvi is not None else ndvi_baseline

    h = health_score(ndvi, ndvi_baseline, iot_anomaly_penalty, ai_anomaly_severity)
    volatility = compute_volatility(history or [], n=5)
    p = permanence_score(h, volatility, snapshot.credit_status)

    return {
        "health_score":     h,
        "permanence_score": p,
        "volatility":       volatility,
        "inputs": {
            "ndvi_current":        ndvi,
            "ndvi_baseline":       ndvi_baseline,
            "iot_anomaly_penalty": iot_anomaly_penalty,
            "ai_anomaly_severity": ai_anomaly_severity,
            "credit_status":       snapshot.credit_status,
        },
    }
