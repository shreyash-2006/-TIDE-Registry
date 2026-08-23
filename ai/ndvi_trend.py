"""
ndvi_trend.py -- NDVI Trend Analysis for Blue Carbon MRV (MNG-001 Pichavaram)

Analyses the GEE-derived NDVI time series to:
  1. Detect trend direction (improving / degrading / stable)
  2. Identify anomalous months (for historical_consistency in MRV fusion)
  3. Compute a health score (0-100) used by the MRV confidence layer

Used by:
  - api.py  GET /api/ai/ndvi-trend
  - mrv_confidence.py  historical_consistency input
"""

import os
import numpy as np
import pandas as pd

_TS_PATH = os.path.join(os.path.dirname(__file__), "data", "ndvi_timeseries.csv")


def _load_series() -> pd.DataFrame:
    df = pd.read_csv(_TS_PATH, parse_dates=["date"])
    df = df.dropna(subset=["ndvi"]).sort_values("date")
    return df


def get_ndvi_trend() -> dict:
    """
    Analyse the Pichavaram NDVI time series and return:

    Returns
    -------
    dict with keys:
        n               : number of observations
        mean_ndvi       : overall mean
        std_ndvi        : standard deviation
        min_ndvi        : minimum observed
        max_ndvi        : maximum observed
        last_ndvi       : most recent value
        last_date       : date of most recent observation
        trend_slope     : NDVI/day linear trend (positive = improving)
        trend_direction : "improving" | "degrading" | "stable"
        anomaly_months  : list of date strings where NDVI is > 2 sigma from mean
        health_score    : 0-100 score for historical_consistency input to MRV fusion
        series          : list of {date, ndvi} dicts (full time series)
    """
    try:
        df = _load_series()
    except Exception as e:
        # Fallback if file not found
        return {
            "error":       str(e),
            "n":           0,
            "mean_ndvi":   0.36,
            "std_ndvi":    0.05,
            "last_ndvi":   0.36,
            "last_date":   "unknown",
            "trend_slope": 0.0,
            "trend_direction": "stable",
            "anomaly_months": [],
            "health_score":   75.0,
            "series": [],
        }

    vals  = df["ndvi"].values
    dates = df["date"].values  # numpy datetime64
    n     = len(df)

    mean_ndvi = float(np.mean(vals))
    std_ndvi  = float(np.std(vals))
    min_ndvi  = float(np.min(vals))
    max_ndvi  = float(np.max(vals))
    last_ndvi = float(vals[-1])
    last_date = str(df["date"].iloc[-1].date())

    # Linear trend via least-squares on days-since-start
    days = (df["date"] - df["date"].iloc[0]).dt.days.values.astype(float)
    if len(days) >= 3:
        slope, _ = np.polyfit(days, vals, 1)  # NDVI per day
        slope = float(slope)
    else:
        slope = 0.0

    # Trend direction: slope * 365 days gives annual NDVI change
    annual_change = slope * 365
    if annual_change > 0.02:
        trend_direction = "improving"
    elif annual_change < -0.02:
        trend_direction = "degrading"
    else:
        trend_direction = "stable"

    # Anomalous months: NDVI more than 2 sigma from mean (indicates disturbance)
    anomaly_threshold_lo = mean_ndvi - 2.0 * std_ndvi
    anomaly_threshold_hi = mean_ndvi + 2.0 * std_ndvi
    anomaly_mask = (vals < anomaly_threshold_lo) | (vals > anomaly_threshold_hi)
    anomaly_months = [
        str(pd.Timestamp(d).date())
        for d in dates[anomaly_mask]
    ]

    # Health score (0-100) for historical_consistency input
    #   Start at 100, penalise:
    #     - downward trend: up to -30
    #     - anomaly rate > 10%: up to -25
    #     - current NDVI below mean-1sigma: -20
    score = 100.0
    if annual_change < 0:
        score += max(-30.0, annual_change * 500)   # -0.06/yr -> -30
    anomaly_rate = len(anomaly_months) / max(n, 1)
    score -= min(25.0, anomaly_rate * 250)
    if last_ndvi < mean_ndvi - std_ndvi:
        score -= 20.0
    health_score = round(max(0.0, min(100.0, score)), 1)

    series = df[["date", "ndvi"]].copy()
    series["date"] = series["date"].astype(str)
    series = series.to_dict(orient="records")

    return {
        "n":               n,
        "mean_ndvi":       round(mean_ndvi, 4),
        "std_ndvi":        round(std_ndvi, 4),
        "min_ndvi":        round(min_ndvi, 4),
        "max_ndvi":        round(max_ndvi, 4),
        "last_ndvi":       round(last_ndvi, 4),
        "last_date":       last_date,
        "trend_slope":     round(slope * 1000, 6),   # NDVI per 1000 days (easier to read)
        "annual_ndvi_change": round(annual_change, 4),
        "trend_direction": trend_direction,
        "anomaly_months":  anomaly_months,
        "n_anomalies":     len(anomaly_months),
        "health_score":    health_score,
        "series":          series,
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import json
    result = get_ndvi_trend()
    # Don't print full series to keep it readable
    display = {k: v for k, v in result.items() if k != "series"}
    display["series_length"] = len(result.get("series", []))
    print(json.dumps(display, indent=2))
    print(f"\nTrend: {result['trend_direction']}  "
          f"(annual NDVI change: {result['annual_ndvi_change']:+.4f})")
    print(f"Health score: {result['health_score']}")
    print(f"Anomaly months ({result['n_anomalies']}): {result['anomaly_months']}")
