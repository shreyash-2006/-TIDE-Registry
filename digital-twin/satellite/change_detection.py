"""
satellite/change_detection.py — NDVI-based change detection for MNG-001

Computes percentage NDVI change between two periods and determines whether
the change crosses the "significant degradation" threshold.

Threshold is coordinated with M1's anomaly detector (SIGNIFICANCE_THRESHOLD_PCT)
so both modules agree on what counts as "significant" during the demo.
"""

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import SIGNIFICANCE_THRESHOLD_PCT
from satellite.composites import get_both_composites


def compute_change(ndvi_before: float, ndvi_after: float) -> dict:
    """
    Compute NDVI percentage change and significance flag.

    Parameters
    ----------
    ndvi_before : float
        Mean NDVI for the baseline period.
    ndvi_after : float
        Mean NDVI for the comparison period.

    Returns
    -------
    dict with keys:
        ndvi_before, ndvi_after, absolute_change, pct_change,
        significant_degradation, direction, threshold_used
    """
    if ndvi_before <= 0:
        raise ValueError(f"ndvi_before must be > 0, got {ndvi_before}")

    absolute_change = ndvi_after - ndvi_before
    pct_change      = (absolute_change / ndvi_before) * 100
    significant     = abs(pct_change) > SIGNIFICANCE_THRESHOLD_PCT

    if pct_change > 5:
        direction = "improving"
    elif pct_change < -5:
        direction = "degrading"
    else:
        direction = "stable"

    return {
        "ndvi_before":             round(ndvi_before, 4),
        "ndvi_after":              round(ndvi_after, 4),
        "absolute_change":         round(absolute_change, 4),
        "pct_change":              round(pct_change, 2),
        "significant_degradation": significant and pct_change < 0,
        "significant_improvement": significant and pct_change > 0,
        "direction":               direction,
        "threshold_used":          SIGNIFICANCE_THRESHOLD_PCT,
    }


def get_satellite_change_report(plot_id: str = "MNG-001") -> dict:
    """
    Full change report using the composites module's before/after values.

    This is the canonical data returned by the /satellite-change API endpoint.
    Attaches period metadata from the composites alongside change statistics.
    """
    composites = get_both_composites()
    before = composites["before"]
    after  = composites["after"]

    change = compute_change(before["ndvi_mean"], after["ndvi_mean"])

    return {
        "plot_id":      plot_id,
        "period_before": {
            "label":      before["label"],
            "date_start": before["date_start"],
            "date_end":   before["date_end"],
            "ndvi_mean":  before["ndvi_mean"],
            "source":     before["source"],
        },
        "period_after": {
            "label":      after["label"],
            "date_start": after["date_start"],
            "date_end":   after["date_end"],
            "ndvi_mean":  after["ndvi_mean"],
            "source":     after["source"],
        },
        "change": change,
    }
