"""
api.py — Blue Carbon MRV AI Service

Exposes three REST endpoints consumed by M5's backend and M4's oracle:

  POST /api/ai/estimate          → Carbon estimation
  POST /api/ai/detect-anomaly    → Anomaly detection (rule + statistical)
  POST /api/ai/mrv-confidence    → MRV confidence fusion score

  GET  /api/ai/health            → Model metadata + liveness check
  GET  /api/ai/simulate          → One sensor reading (normal or anomaly mode)
  GET  /docs                     → Auto-generated Swagger UI

Run:
  cd ai/
  uvicorn api:app --reload --port 8001

Or from any directory:
  uvicorn ai.api:app --reload --port 8001
"""

import os
import sys
import numpy as np
import pandas as pd
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Make sure imports work whether we're inside ai/ or at project root ──
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from carbon_model  import estimate_carbon, get_model_meta
from anomaly_model import rule_based_anomaly, statistical_anomaly_score, combined_anomaly
from uncertainity  import creditable_carbon, uncertainty_breakdown
from mrv_confidence import (
    mrv_confidence,
    compute_mrv_score,
    MINT_THRESHOLD,
    FREEZE_THRESHOLD,
    WEIGHTS,
)
from simulator     import generate_reading, NORMAL_RANGES
from config        import PLOT_ID, SITE_NAME, PLOT_BOUNDS
from ndvi_trend    import get_ndvi_trend


# ─────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "Blue Carbon MRV — AI Service",
    description = (
        "AI/ML endpoints for carbon estimation, anomaly detection, "
        "and MRV confidence scoring for the TIDE Hackathon Blue Carbon Registry. "
        f"Demo plot: {SITE_NAME} (MNG-001)."
    ),
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ─────────────────────────────────────────────────────────────────────
# CACHED NDVI STATS  (from real time-series data)
# ─────────────────────────────────────────────────────────────────────

def _load_ndvi_stats() -> dict:
    ts_path = os.path.join(_HERE, "data", "ndvi_timeseries.csv")
    try:
        df = pd.read_csv(ts_path)
        vals = df["ndvi"].dropna().values
        return {
            "mean": float(np.mean(vals)),
            "std":  float(np.std(vals)),
            "min":  float(np.min(vals)),
            "max":  float(np.max(vals)),
            "last": float(vals[-1]),
            "n":    len(vals),
        }
    except Exception:
        return {"mean": 0.38, "std": 0.05, "min": 0.25, "max": 0.45,
                "last": 0.38, "n": 0}

_NDVI_STATS = _load_ndvi_stats()


# ─────────────────────────────────────────────────────────────────────
# MODELS — loaded at startup (not on every request)
# ─────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup():
    """Pre-load models so first request isn't slow."""
    try:
        get_model_meta()          # triggers carbon model load / fit
    except Exception as e:
        print(f"[startup] Carbon model load warning: {e}")

    try:
        from anomaly_model import _load_iso
        _load_iso()               # triggers IsolationForest load / train
    except Exception as e:
        print(f"[startup] IsolationForest load warning: {e}")

    print("[startup] AI Service ready [OK]")


# ─────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────

class EstimateRequest(BaseModel):
    plot_id: str  = Field(default="MNG-001", example="MNG-001")
    ndvi:    float = Field(..., ge=-1.0, le=1.0, example=0.42,
                           description="Normalised Difference Vegetation Index (−1 to 1)")
    area_ha: float = Field(..., gt=0.0,  example=280.0,
                           description="Plot area in hectares")

class EstimateResponse(BaseModel):
    plot_id:            str
    ndvi_input:         float
    area_ha:            float
    carbon_estimate:    float = Field(description="Central CO2e estimate (t)")
    standard_deviation: float = Field(description="1-sigma uncertainty (t)")
    creditable_carbon:  float = Field(description="Conservative lower bound, 90% CI (t)")
    confidence_level:   float = Field(default=0.90)
    carbon_fraction:    float = Field(description="Biomass carbon fraction used")
    co2_per_ha:         float = Field(description="CO2e per hectare")


class SensorReading(BaseModel):
    ndvi:             Optional[float] = Field(None, example=0.42)
    salinity:         Optional[float] = Field(None, example=14.0)
    temperature:      Optional[float] = Field(None, example=28.0)
    ph:               Optional[float] = Field(None, example=7.8)
    soil_moisture:    Optional[float] = Field(None, example=65.0)
    water_level:      Optional[float] = Field(None, example=1.1)
    reported_biomass: Optional[float] = Field(None)
    model_biomass_estimate: Optional[float] = Field(None)
    timestamp:        Optional[str]   = Field(None)

class AnomalyRequest(BaseModel):
    plot_id:        str            = Field(default="MNG-001")
    current:        SensorReading
    previous:       SensorReading
    expected_range: Optional[dict] = Field(
        None,
        description="Override of sensor normal ranges. "
                    "Each key maps to [lo, hi]. If absent, default ranges are used.",
        example={"salinity": [10, 18], "temperature": [26, 30]}
    )

class AnomalyResponse(BaseModel):
    plot_id:           str
    anomaly:           bool
    severity:          float
    reasons:           list[str]
    statistical_score: float
    combined_score:    float


class ConfidenceRequest(BaseModel):
    iot_consistency:        float = Field(..., ge=0.0, le=100.0, example=90.0)
    satellite_evidence:     float = Field(..., ge=0.0, le=100.0, example=85.0)
    ai_confidence:          float = Field(..., ge=0.0, le=100.0, example=88.0)
    community_evidence:     float = Field(..., ge=0.0, le=100.0, example=80.0)
    historical_consistency: float = Field(..., ge=0.0, le=100.0, example=82.0)

class ConfidenceResponse(BaseModel):
    mrv_confidence: float
    eligible:       bool  = Field(description=f"True if score ≥ {MINT_THRESHOLD} (mint-eligible)")
    freeze_alert:   bool  = Field(description=f"True if score < {FREEZE_THRESHOLD} (freeze trigger)")
    components:     dict
    weights:        dict
    thresholds:     dict


class FullMRVRequest(BaseModel):
    """
    All-in-one request: provide raw signals and let the AI layer
    compute confidence components automatically.
    """
    plot_id:              str   = Field(default="MNG-001")
    current:              SensorReading
    previous:             SensorReading
    current_ndvi:         float = Field(..., ge=-1.0, le=1.0, example=0.38)
    area_ha:              float = Field(..., gt=0.0, example=280.0)
    community_evidence:   float = Field(default=80.0, ge=0.0, le=100.0)
    historical_consistency: float = Field(default=80.0, ge=0.0, le=100.0)
    expected_range:       Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

@app.get("/api/ai/health", tags=["Utility"])
def health():
    """Liveness + model metadata."""
    try:
        meta = get_model_meta()
    except Exception as e:
        meta = {"error": str(e)}
    return {
        "status":      "ok",
        "service":     "Blue Carbon MRV — AI Service",
        "plot_id":     PLOT_ID,
        "site":        SITE_NAME,
        "plot_bounds": PLOT_BOUNDS,
        "ndvi_stats":  _NDVI_STATS,
        "carbon_model_meta": meta,
        "normal_ranges": {k: list(v) for k, v in NORMAL_RANGES.items()},
        "thresholds": {
            "mint":   MINT_THRESHOLD,
            "freeze": FREEZE_THRESHOLD,
        },
    }


@app.post(
    "/api/ai/estimate",
    response_model=EstimateResponse,
    tags=["Carbon Estimation"],
    summary="Estimate CO2e carbon for a plot given NDVI and area",
)
def estimate(req: EstimateRequest):
    """
    Estimates aboveground carbon (t CO2e) using the NDVI → AGB polynomial
    regression calibrated on NASA Simard et al. mangrove AGB data +
    Sentinel-2 NDVI for MNG-001 (Pichavaram).

    Returns the central estimate, 1-sigma uncertainty, and the conservative
    creditable amount (lower bound of 90% one-sided confidence interval,
    per Verra VM0007).
    """
    try:
        co2e, sigma = estimate_carbon(req.ndvi, req.area_ha)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Carbon model error: {e}")

    lower = creditable_carbon(co2e, sigma)

    return EstimateResponse(
        plot_id            = req.plot_id,
        ndvi_input         = req.ndvi,
        area_ha            = req.area_ha,
        carbon_estimate    = round(co2e, 1),
        standard_deviation = round(sigma, 1),
        creditable_carbon  = lower,
        confidence_level   = 0.90,
        carbon_fraction    = 0.47,
        co2_per_ha         = round(co2e / req.area_ha, 2) if req.area_ha > 0 else 0.0,
    )


@app.post(
    "/api/ai/detect-anomaly",
    response_model=AnomalyResponse,
    tags=["Anomaly Detection"],
    summary="Detect anomalies in IoT sensor + NDVI readings",
)
def detect_anomaly(req: AnomalyRequest):
    """
    Two-layer anomaly detection:

    **Layer A (rule-based)** — checks NDVI drop, sensor out-of-range,
    and biomass deviation. Drives the binary `anomaly` flag.

    **Layer B (IsolationForest)** — multivariate statistical score
    trained on 500 normal synthetic readings.

    `combined_score = 0.7 × rule_severity + 0.3 × norm_statistical`

    The `combined_score` (0–1) is what the MRV confidence fusion consumes.
    """
    current  = req.current.dict(exclude_none=False)
    previous = req.previous.dict(exclude_none=False)

    # Use provided expected_range or fall back to defaults
    expected_range = req.expected_range

    try:
        result = combined_anomaly(current, previous, expected_range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anomaly model error: {e}")

    return AnomalyResponse(
        plot_id           = req.plot_id,
        anomaly           = result["anomaly"],
        severity          = result["severity"],
        reasons           = result["reasons"],
        statistical_score = result["statistical_score"],
        combined_score    = result["combined_score"],
    )


@app.post(
    "/api/ai/mrv-confidence",
    response_model=ConfidenceResponse,
    tags=["MRV Confidence"],
    summary="Compute weighted MRV confidence score (0–100)",
)
def mrv_confidence_endpoint(req: ConfidenceRequest):
    """
    Combines five independent evidence streams into a single MRV confidence
    score (0–100).

    | Signal                | Weight |
    |---|---|
    | IoT sensor consistency        | 0.20 |
    | Satellite / NDVI evidence     | 0.25 |
    | AI model confidence           | 0.25 |
    | Community photo validation    | 0.15 |
    | Historical trend consistency  | 0.15 |

    Score ≥ **85** → `eligible: true` (mint trigger)
    Score < **60** → `freeze_alert: true` (freeze trigger)
    """
    score = mrv_confidence(**req.dict())
    return ConfidenceResponse(
        mrv_confidence = score,
        eligible       = score >= MINT_THRESHOLD,
        freeze_alert   = score < FREEZE_THRESHOLD,
        components     = req.dict(),
        weights        = WEIGHTS,
        thresholds     = {"mint": MINT_THRESHOLD, "freeze": FREEZE_THRESHOLD},
    )


@app.post(
    "/api/ai/mrv-full",
    tags=["MRV Confidence"],
    summary="All-in-one MRV pipeline: raw signals → confidence + carbon + anomaly",
)
def mrv_full(req: FullMRVRequest):
    """
    Convenience endpoint: provide raw sensor readings and NDVI once,
    get carbon estimate + anomaly assessment + MRV confidence in one call.

    Useful for M5's backend to make a single call and get everything it needs
    to decide mint / freeze.
    """
    current  = req.current.dict(exclude_none=False)
    previous = req.previous.dict(exclude_none=False)

    # Carbon estimate
    try:
        co2e, sigma = estimate_carbon(req.current_ndvi, req.area_ha)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Carbon model error: {e}")
    lower = creditable_carbon(co2e, sigma)

    # Anomaly
    try:
        anom = combined_anomaly(current, previous, req.expected_range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anomaly model error: {e}")

    # MRV confidence (heuristic converters)
    # Auto-populate historical_consistency from real NDVI trend if not overridden
    hist_consistency = req.historical_consistency
    if hist_consistency == 80.0:  # default sentinel value -- replace with real data
        try:
            trend = get_ndvi_trend()
            hist_consistency = trend["health_score"]
        except Exception:
            pass  # keep default

    mrv_result = compute_mrv_score(
        anomaly_severity      = anom["severity"],
        current_ndvi          = req.current_ndvi,
        mean_ndvi             = _NDVI_STATS["mean"],
        std_ndvi              = max(_NDVI_STATS["std"], 0.01),
        carbon_estimate       = co2e,
        carbon_sigma          = sigma,
        community_evidence    = req.community_evidence,
        historical_consistency= hist_consistency,
    )

    return {
        "plot_id": req.plot_id,
        "carbon": {
            "ndvi_input":         req.current_ndvi,
            "area_ha":            req.area_ha,
            "carbon_estimate":    round(co2e, 1),
            "standard_deviation": round(sigma, 1),
            "creditable_carbon":  lower,
            "co2_per_ha":         round(co2e / req.area_ha, 2),
        },
        "anomaly": {
            "anomaly":           anom["anomaly"],
            "severity":          anom["severity"],
            "reasons":           anom["reasons"],
            "statistical_score": anom["statistical_score"],
            "combined_score":    anom["combined_score"],
        },
        "mrv": mrv_result,
    }


@app.get(
    "/api/ai/simulate",
    tags=["Utility"],
    summary="Generate one simulated IoT sensor reading",
)
def simulate(anomaly: bool = False):
    """
    Returns one simulated sensor reading for MNG-001.
    Use `?anomaly=true` to inject an out-of-range event for demo purposes.
    """
    reading = generate_reading(anomaly=anomaly)
    # Add a plausible NDVI so rule-based anomaly can evaluate it too
    ndvi_base = _NDVI_STATS["last"] if not anomaly else _NDVI_STATS["last"] * 0.55
    reading["ndvi"] = round(float(ndvi_base), 4)
    return reading


@app.get(
    "/api/ai/ndvi-trend",
    tags=["Utility"],
    summary="NDVI trend analysis — direction, anomalies, health score",
)
def ndvi_trend_endpoint():
    """
    Analyses the 24-month Sentinel-2 NDVI time series for MNG-001 and returns:

    - **trend_direction**: improving / degrading / stable
    - **health_score**: 0-100, used as `historical_consistency` input to MRV fusion
    - **anomaly_months**: dates where NDVI was > 2-sigma from the historical mean
    - **annual_ndvi_change**: estimated annual NDVI delta from linear regression
    - **series**: full time series (date, ndvi) for the dashboard chart
    """
    try:
        return get_ndvi_trend()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/ai/ndvi-timeseries",
    tags=["Utility"],
    summary="Return historical NDVI time series for MNG-001",
)
def ndvi_timeseries():
    """Returns the full NDVI time series pulled from Sentinel-2 via GEE."""
    ts_path = os.path.join(_HERE, "data", "ndvi_timeseries.csv")
    try:
        df = pd.read_csv(ts_path)
        return {
            "plot_id": PLOT_ID,
            "site":    SITE_NAME,
            "stats":   _NDVI_STATS,
            "series":  df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)
