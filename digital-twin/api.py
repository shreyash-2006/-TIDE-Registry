"""
api.py — Blue Carbon MRV Digital Twin + GIS Service

Exposes REST endpoints consumed by M5's backend and M6's frontend:

  GET  /api/twin/health                         → liveness + config echo
  GET  /api/twin/boundary                       → raw GeoJSON (for M6/Leaflet)
  GET  /api/twin/{plot_id}/current              → latest TwinSnapshot
  GET  /api/twin/{plot_id}/history              → full snapshot list
  POST /api/twin/{plot_id}/update               → append new snapshot
  GET  /api/twin/{plot_id}/satellite-change     → NDVI before/after + pct_change
  GET  /api/twin/{plot_id}/scores               → live health + permanence scores
  GET  /api/twin/{plot_id}/map                  → Folium HTML map page
  GET  /api/twin/{plot_id}/extent-history       → GMW mangrove area over time
  GET  /docs                                    → Swagger UI

Run:
  cd digital-twin/
  uvicorn api:app --reload --port 8002

Or from project root:
  uvicorn digital-twin.api:app --reload --port 8002
"""

import os
import sys
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# ── Path setup: work from digital-twin/ or from project root ─────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config          import PLOT_ID, SITE_NAME, PLOT_BOUNDS, CENTROID, GEE_PROJECT, NDVI_BASELINE
from temporal.snapshot   import TwinSnapshot, twin_history, make_snapshot, now_utc
from temporal.scoring    import score_snapshot, health_score, permanence_score, compute_volatility
from satellite.composites    import init_gee, get_both_composites
from satellite.change_detection  import get_satellite_change_report, compute_change
from gis.boundary    import load_boundary, boundary_area_ha, boundary_centroid
from gis.extent_history  import get_extent_history, extent_change_summary


# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "Blue Carbon MRV — Digital Twin + GIS Service",
    description = (
        "Digital Twin state management, satellite change detection, and GIS map "
        "endpoints for the TIDE Hackathon Blue Carbon Registry. "
        f"Demo plot: {SITE_NAME} ({PLOT_ID}). "
        "Twin history is append-only — every update produces a new timestamped "
        "snapshot, enabling the full healthy → degraded → frozen → restored narrative."
    ),
    version  = "1.0.0",
    docs_url = "/docs",
    redoc_url= "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup():
    """Seed demo history and attempt GEE init."""
    # Seed demo scenarios so the twin has meaningful history from request 1
    from seed import seed_demo_history
    seed_demo_history()
    print("[startup] Demo history seeded [OK]")

    # Attempt GEE (non-fatal if credentials not ready)
    init_gee(GEE_PROJECT)

    print("[startup] Digital Twin + GIS Service ready [OK]")


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class UpdateRequest(BaseModel):
    """
    Payload for pushing a new snapshot via POST /api/twin/{plot_id}/update.

    All fields are optional except the ones that drive scores (ndvi).
    M5 can send partial updates — only the fields that changed.
    """
    ndvi:               Optional[float] = Field(None, ge=-1.0, le=1.0)
    area_ha:            Optional[float] = Field(None, gt=0)
    carbon_stock:       Optional[float] = Field(None)
    carbon_confidence:  Optional[float] = Field(None, ge=0.0, le=1.0)
    biomass:            Optional[float] = Field(None)
    mangrove_density:   Optional[float] = Field(None, ge=0.0, le=1.0)
    water_quality:      Optional[dict]  = Field(None)
    soil_conditions:    Optional[dict]  = Field(None)
    credit_status:      Optional[str]   = Field(None)
    source_event:       Optional[str]   = Field(None)
    restoration_age_years: Optional[float] = Field(None)
    biodiversity_index: Optional[float] = Field(None)
    notes:              Optional[str]   = Field(None)
    # Scoring inputs from M1/M3 — used to compute health_score automatically
    iot_anomaly_penalty: Optional[float] = Field(0.0, ge=0.0)
    ai_anomaly_severity: Optional[float] = Field(0.0, ge=0.0, le=1.0)


class ScoreRequest(BaseModel):
    ndvi:               float = Field(..., ge=-1.0, le=1.0)
    iot_anomaly_penalty: float = Field(0.0, ge=0.0)
    ai_anomaly_severity: float = Field(0.0, ge=0.0, le=1.0)
    credit_status:       Optional[str] = Field(None)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/twin/health", tags=["Utility"])
def health():
    """Liveness check + module configuration echo."""
    return {
        "status":        "ok",
        "service":       "Blue Carbon MRV — Digital Twin + GIS Service",
        "plot_id":       PLOT_ID,
        "site":          SITE_NAME,
        "centroid":      CENTROID,
        "plot_bounds":   PLOT_BOUNDS,
        "ndvi_baseline": NDVI_BASELINE,
        "plots_tracked": twin_history.list_plots(),
        "snapshot_counts": {
            p: twin_history.snapshot_count(p)
            for p in twin_history.list_plots()
        },
    }


@app.get("/api/twin/boundary", tags=["GIS"], summary="Plot boundary as raw GeoJSON")
def get_boundary():
    """
    Returns the plot polygon as a GeoJSON FeatureCollection.

    Use this if M6 is rendering the map in React + Leaflet.js instead of
    the Folium iframe — they can consume this directly.
    """
    try:
        return load_boundary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Boundary load error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TWIN STATE ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/twin/{plot_id}/current",
    response_model=TwinSnapshot,
    tags=["Digital Twin"],
    summary="Latest TwinSnapshot for a plot",
)
def get_current_state(plot_id: str):
    """
    Returns the most recent snapshot for the given plot.
    This is the canonical "current state" consumed by M5's backend and M6's dashboard.
    """
    snap = twin_history.get_current(plot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"No twin data for plot '{plot_id}'")
    return snap


@app.get(
    "/api/twin/{plot_id}/history",
    response_model=List[TwinSnapshot],
    tags=["Digital Twin"],
    summary="Full snapshot history for a plot (oldest first)",
)
def get_history(plot_id: str, limit: Optional[int] = None):
    """
    Returns the complete list of snapshots in chronological order.

    Optionally limit to the N most recent with ?limit=N.
    This is what powers the timeline view — each snapshot is one point on
    the health/carbon chart.
    """
    history = twin_history.get_history(plot_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"No twin data for plot '{plot_id}'")
    if limit:
        history = history[-limit:]
    return history


@app.post(
    "/api/twin/{plot_id}/update",
    tags=["Digital Twin"],
    summary="Push a new snapshot (append-only)",
)
def push_update(plot_id: str, req: UpdateRequest):
    """
    Append a new TwinSnapshot to the plot's history.

    Called by M5's backend whenever fresh data arrives from any source
    (IoT batch, satellite, community report, blockchain state change).

    Health and permanence scores are computed automatically from the
    provided NDVI and anomaly inputs — no need for the caller to compute them.
    """
    # Inherit location + area from current state if not provided
    current = twin_history.get_current(plot_id)
    area_ha = req.area_ha or (current.area_ha if current else 280.0)

    # Auto-compute health + permanence scores
    ndvi = req.ndvi if req.ndvi is not None else (
        current.ndvi if current and current.ndvi is not None else NDVI_BASELINE
    )
    h = health_score(
        ndvi_current        = ndvi,
        ndvi_baseline       = NDVI_BASELINE,
        iot_anomaly_penalty = req.iot_anomaly_penalty or 0.0,
        ai_anomaly_severity = req.ai_anomaly_severity or 0.0,
    )
    history = twin_history.get_history(plot_id)
    volatility = compute_volatility(history, n=5)
    p = permanence_score(h, volatility, req.credit_status)

    snap = make_snapshot(
        plot_id            = plot_id,
        area_ha            = area_ha,
        ndvi               = req.ndvi,
        carbon_stock       = req.carbon_stock,
        carbon_confidence  = req.carbon_confidence,
        biomass            = req.biomass,
        mangrove_density   = req.mangrove_density,
        water_quality      = req.water_quality,
        soil_conditions    = req.soil_conditions,
        credit_status      = req.credit_status,
        source_event       = req.source_event,
        restoration_age_years = req.restoration_age_years,
        biodiversity_index = req.biodiversity_index,
        notes              = req.notes,
        health_score       = h,
        permanence_score   = p,
    )

    count = twin_history.add(snap)
    return {
        "status":         "recorded",
        "plot_id":        plot_id,
        "snapshot_count": count,
        "timestamp":      snap.timestamp.isoformat(),
        "health_score":   h,
        "permanence_score": p,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SATELLITE ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/twin/{plot_id}/satellite-change",
    tags=["Satellite"],
    summary="NDVI before/after change detection",
)
def satellite_change(plot_id: str):
    """
    Returns NDVI change statistics between the before and after periods.

    Includes:
    - ndvi_before, ndvi_after (mean values per period)
    - pct_change (signed %)
    - significant_degradation flag (|pct_change| > 15% and negative)
    - direction (improving / stable / degrading)

    The significance threshold (15%) is coordinated with M1's anomaly
    detector so both modules trigger together on stage.
    """
    try:
        return get_satellite_change_report(plot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# SCORING ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/twin/{plot_id}/scores",
    tags=["Digital Twin"],
    summary="Compute health + permanence scores for the latest snapshot",
)
def get_scores(
    plot_id: str,
    iot_anomaly_penalty: float = 0.0,
    ai_anomaly_severity: float = 0.0,
):
    """
    Computes live health and permanence scores for the current plot state.

    Pass IoT anomaly penalty and M1 anomaly severity as query params to
    get an updated score without pushing a full update snapshot.
    """
    snap = twin_history.get_current(plot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"No twin data for plot '{plot_id}'")

    history = twin_history.get_history(plot_id)
    result = score_snapshot(
        snapshot            = snap,
        ndvi_baseline       = NDVI_BASELINE,
        iot_anomaly_penalty = iot_anomaly_penalty,
        ai_anomaly_severity = ai_anomaly_severity,
        history             = history,
    )
    result["plot_id"] = plot_id
    result["snapshot_count"] = len(history)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# MAP ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/twin/{plot_id}/map",
    response_class=HTMLResponse,
    tags=["GIS"],
    summary="Interactive Folium map for the plot",
)
def get_map(plot_id: str):
    """
    Returns a self-contained Leaflet HTML page for the plot.

    Includes:
    - Plot boundary (color-coded green/yellow/red by health score)
    - Health indicator circle marker with full snapshot popup
    - NDVI before/after image overlay toggle (if thumbnails exist)
    - Satellite + OpenStreetMap basemap toggle
    - Measure tool + fullscreen button

    Note for M6: if embedding in React is needed, use the raw GeoJSON from
    GET /api/twin/boundary and the snapshot JSON from /current instead — this
    Folium HTML is best served in an <iframe> or standalone tab, not injected
    into a React component.
    """
    snap = twin_history.get_current(plot_id)
    try:
        from map.render import render_map_html
        html = render_map_html(snapshot=snap, include_ndvi_overlays=True)
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Map render error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# GIS / EXTENT HISTORY ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/twin/{plot_id}/extent-history",
    tags=["GIS"],
    summary="Mangrove extent area over time (GMW-based)",
)
def extent_history(plot_id: str):
    """
    Returns historical mangrove extent for the plot from GMW v3.

    Provides one data point per available GMW epoch (2000–2020) showing
    area in hectares. Use this on the Twin's history panel to tell the
    two-decade story independent of current NDVI values.

    Also returns a summary (total change, %, direction, years spanned).
    """
    return {
        "plot_id": plot_id,
        "site":    SITE_NAME,
        "history": get_extent_history(),
        "summary": extent_change_summary(),
        "note":    "Values derived from Global Mangrove Watch v3 (Bunting et al. 2018)",
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8002, reload=True)
