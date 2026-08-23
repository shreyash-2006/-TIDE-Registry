"""
api.py — Blue Carbon MRV Unified Backend (M5)

The integration backbone. Orchestrates AI (port 8001) and Digital Twin
(port 8002) services, owns the database, and serves the diagnostic UI.

Run:
  cd backend/
  uvicorn api:app --reload --port 8000

Endpoints:
  GET  /                            → Diagnostic UI
  GET  /api/health                  → Liveness + service status
  POST /api/plots                   → Register a new plot
  GET  /api/plots                   → List all plots
  GET  /api/plots/{id}              → Get plot details
  POST /api/observations            → Record sensor observation
  GET  /api/plots/{id}/observations → List observations for a plot
  POST /api/plots/{id}/analyze      → Full MRV pipeline (calls AI + Twin)
  GET  /api/plots/{id}/anomalies    → List anomalies
  POST /api/credits/mint            → Mint credits from MRV result
  GET  /api/credits                 → List credits
  POST /api/credits/{id}/freeze     → Freeze a credit
  POST /api/credits/{id}/reverify   → Reverify a credit
  POST /api/community-reports       → Submit community report
  GET  /api/dashboard-data          → Aggregated data for diagnostic UI
"""

import os
import sys
import json
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# ── Path setup ────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config import (
    PLOT_ID, SITE_NAME, CENTROID, PLOT_BOUNDS,
    DEFAULT_AREA_HA, BASELINE_NDVI,
    MINT_THRESHOLD, FREEZE_THRESHOLD,
    AI_SERVICE_URL, TWIN_SERVICE_URL,
)
import database as db
import services as svc


# ─────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "TIDE — Unified Backend (M5)",
    description = (
        "Integration backbone for the Blue Carbon MRV system. "
        "Orchestrates AI, Digital Twin, and database operations. "
        f"Demo plot: {SITE_NAME} ({PLOT_ID})."
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


# ─────────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup():
    """Seed the demo plot if the database is empty."""
    from seed import seed_demo_data
    seed_demo_data()
    print("[startup] M5 Backend ready [OK]")


# ─────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────

class PlotCreate(BaseModel):
    id:             str   = Field(..., example="MNG-001")
    name:           str   = Field(..., example="Pichavaram Mangrove Forest")
    lat:            float = Field(..., example=11.425)
    lng:            float = Field(..., example=79.785)
    area_ha:        float = Field(..., gt=0, example=280.0)
    ecosystem_type: str   = Field(default="mangrove")
    baseline_ndvi:  float = Field(default=0.42, ge=-1.0, le=1.0)


class ObservationCreate(BaseModel):
    plot_id:       str   = Field(..., example="MNG-001")
    ndvi:          Optional[float] = None
    salinity:      Optional[float] = None
    soil_moisture: Optional[float] = None
    temperature:   Optional[float] = None
    ph:            Optional[float] = None
    water_level:   Optional[float] = None
    source:        str   = Field(default="simulator")


class MintRequest(BaseModel):
    plot_id:       str   = Field(..., example="MNG-001")
    quantity:      float = Field(..., gt=0, example=42.0)
    lower_bound:   float = Field(..., gt=0, example=32.1)
    mrv_score:     Optional[float] = None
    evidence_hash: Optional[str]   = None


class CommunityReportCreate(BaseModel):
    plot_id:     str = Field(..., example="MNG-001")
    submitter:   str = Field(..., example="local_user_1")
    description: str = Field(..., example="Mangrove clearing detected near boundary")
    photo_uri:   Optional[str] = None


class CreditStatusRequest(BaseModel):
    status: str = Field(..., example="ACTIVE")


class TransferRequest(BaseModel):
    recipient_address: str   = Field(..., example="0x71C...B42")
    amount:            float = Field(..., gt=0, example=5.0)


class RetireRequest(BaseModel):
    amount:           float = Field(..., gt=0, example=5.0)
    beneficiary_name: str   = Field(..., example="Green Tech Corp India")
    offset_reason:    str   = Field(..., example="Scope 1 & 2 Emissions Offset for Q1 2025")
    retiree_address:  Optional[str] = Field(default="0xBuyerWallet78a9")


class ReportStatusRequest(BaseModel):
    status: str = Field(..., example="verified")


class ThresholdsRequest(BaseModel):
    mint_threshold:   float = Field(..., ge=0, le=100)
    freeze_threshold: float = Field(..., ge=0, le=100)


# ─────────────────────────────────────────────────────────────────────
# DIAGNOSTIC UI
# ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, tags=["UI"])
def diagnostic_ui():
    """Serve the diagnostic HTML page."""
    html_path = os.path.join(_HERE, "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ─────────────────────────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Utility"])
def health():
    """Liveness check + status of upstream services."""
    ai_status   = svc.ai_health()
    twin_status = svc.twin_health()
    return {
        "status":       "ok",
        "service":      "TIDE — Unified Backend (M5)",
        "plot_id":      PLOT_ID,
        "site":         SITE_NAME,
        "db_stats":     db.get_stats(),
        "upstream": {
            "ai_service":   {"url": AI_SERVICE_URL,   "status": ai_status.get("status", "unknown")},
            "twin_service": {"url": TWIN_SERVICE_URL, "status": twin_status.get("status", "unknown")},
        },
        "thresholds": {
            "mint":   MINT_THRESHOLD,
            "freeze": FREEZE_THRESHOLD,
        },
    }


# ─────────────────────────────────────────────────────────────────────
# PLOTS
# ─────────────────────────────────────────────────────────────────────

@app.post("/api/plots", tags=["Plots"])
def create_plot(req: PlotCreate):
    """Register a new mangrove plot."""
    plot = db.insert_plot(
        plot_id=req.id, name=req.name, lat=req.lat, lng=req.lng,
        area_ha=req.area_ha, ecosystem_type=req.ecosystem_type,
        baseline_ndvi=req.baseline_ndvi,
    )
    return {"status": "created", "plot": plot}


@app.get("/api/plots", tags=["Plots"])
def list_plots():
    """List all registered plots."""
    return db.get_all_plots()


@app.get("/api/plots/{plot_id}", tags=["Plots"])
def get_plot(plot_id: str):
    """Get details for a specific plot."""
    plot = db.get_plot(plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail=f"Plot '{plot_id}' not found")
    return plot


# ─────────────────────────────────────────────────────────────────────
# OBSERVATIONS
# ─────────────────────────────────────────────────────────────────────

@app.post("/api/observations", tags=["Observations"])
def record_observation(req: ObservationCreate):
    """Record a sensor observation for a plot."""
    plot = db.get_plot(req.plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail=f"Plot '{req.plot_id}' not found")

    obs = db.insert_observation(
        plot_id=req.plot_id, ndvi=req.ndvi, salinity=req.salinity,
        soil_moisture=req.soil_moisture, temperature=req.temperature,
        ph=req.ph, water_level=req.water_level, source=req.source,
    )
    return {"status": "recorded", "observation": obs}


@app.get("/api/plots/{plot_id}/observations", tags=["Observations"])
def list_observations(plot_id: str, limit: int = 20):
    """List recent observations for a plot."""
    return db.get_observations(plot_id, limit=limit)


# ─────────────────────────────────────────────────────────────────────
# MRV PIPELINE (the core integration endpoint)
# ─────────────────────────────────────────────────────────────────────

@app.post("/api/plots/{plot_id}/analyze", tags=["MRV Pipeline"])
def analyze_plot(plot_id: str, ndvi: float = 0.38, anomaly_mode: bool = False):
    """
    Full MRV analysis pipeline:
    1. Gets a simulated sensor reading from AI service
    2. Runs carbon estimation + anomaly detection + MRV confidence
    3. Updates the digital twin
    4. Stores results in the local database
    5. Returns everything in one response

    Use ?anomaly_mode=true to simulate a degradation event.
    """
    plot = db.get_plot(plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail=f"Plot '{plot_id}' not found")

    area_ha = plot["area_ha"]

    # Step 1: Get simulated sensor readings
    try:
        current_reading  = svc.ai_simulate(anomaly=anomaly_mode)
        previous_reading = svc.ai_simulate(anomaly=False)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI simulate failed: {e}")

    # Override NDVI with the provided value
    current_reading["ndvi"] = ndvi

    # Step 2: Run full MRV pipeline via AI service
    try:
        mrv_result = svc.ai_mrv_full(
            current=current_reading,
            previous=previous_reading,
            current_ndvi=ndvi,
            area_ha=area_ha,
            plot_id=plot_id,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI MRV pipeline failed: {e}")

    # Step 3: Store observation in local DB
    obs = db.insert_observation(
        plot_id=plot_id,
        ndvi=ndvi,
        salinity=current_reading.get("salinity"),
        soil_moisture=current_reading.get("soil_moisture"),
        temperature=current_reading.get("temperature"),
        ph=current_reading.get("ph"),
        water_level=current_reading.get("water_level"),
        source="mrv_pipeline",
    )

    # Step 4: If anomaly detected, store it
    anomaly_data = mrv_result.get("anomaly", {})
    if anomaly_data.get("anomaly", False):
        db.insert_anomaly(
            plot_id=plot_id,
            severity=anomaly_data.get("severity", 0),
            description="Auto-detected by MRV pipeline",
            reasons=json.dumps(anomaly_data.get("reasons", [])),
            source="ai_pipeline",
        )

    # Step 5: Update twin (best-effort — twin might not be running)
    twin_updated = False
    try:
        carbon_data = mrv_result.get("carbon", {})
        svc.twin_update(plot_id, {
            "ndvi": ndvi,
            "carbon_stock": carbon_data.get("carbon_estimate"),
            "carbon_confidence": 0.90,
            "ai_anomaly_severity": anomaly_data.get("severity", 0),
            "source_event": "mrv_pipeline",
        })
        twin_updated = True
    except Exception:
        pass  # Twin not running — that's OK

    # Step 6: Update plot health status
    mrv_info = mrv_result.get("mrv", {})
    mrv_score = mrv_info.get("mrv_confidence", 0)
    if mrv_score >= MINT_THRESHOLD:
        db.update_plot_health(plot_id, "healthy")
    elif mrv_score < FREEZE_THRESHOLD:
        db.update_plot_health(plot_id, "degraded")
    else:
        db.update_plot_health(plot_id, "at_risk")

    return {
        "plot_id":        plot_id,
        "carbon":         mrv_result.get("carbon"),
        "anomaly":        mrv_result.get("anomaly"),
        "mrv":            mrv_result.get("mrv"),
        "observation":    obs,
        "twin_updated":   twin_updated,
        "sensor_reading": current_reading,
    }


# ─────────────────────────────────────────────────────────────────────
# CREDITS
# ─────────────────────────────────────────────────────────────────────

@app.post("/api/credits/mint", tags=["Credits"])
def mint_credit(req: MintRequest):
    """Mint a new carbon credit (status = PROPOSED)."""
    plot = db.get_plot(req.plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail=f"Plot '{req.plot_id}' not found")

    credit = db.insert_credit(
        plot_id=req.plot_id, quantity=req.quantity, lower_bound=req.lower_bound,
        mrv_score=req.mrv_score, evidence_hash=req.evidence_hash,
    )
    return {"status": "minted", "credit": credit}


@app.get("/api/credits", tags=["Credits"])
def list_credits(plot_id: Optional[str] = None):
    """List all credits, optionally filtered by plot."""
    return db.get_credits(plot_id=plot_id)


@app.post("/api/credits/{credit_id}/freeze", tags=["Credits"])
def freeze_credit(credit_id: str):
    """Freeze a credit (degradation detected)."""
    credit = db.update_credit_status(credit_id, "FROZEN")
    if not credit:
        raise HTTPException(status_code=404, detail=f"Credit '{credit_id}' not found")
    return {"status": "frozen", "credit": credit}


@app.post("/api/credits/{credit_id}/reverify", tags=["Credits"])
def reverify_credit(credit_id: str):
    """Reverify a frozen credit (evidence shows recovery)."""
    credit = db.update_credit_status(credit_id, "REVERIFIED")
    if not credit:
        raise HTTPException(status_code=404, detail=f"Credit '{credit_id}' not found")
    return {"status": "reverified", "credit": credit}


@app.post("/api/credits/{credit_id}/status", tags=["Credits"])
def update_credit_status(credit_id: str, req: CreditStatusRequest):
    """Set status of a living credit (ACTIVE, PROPOSED, UNDER_REVIEW, FROZEN, REVERIFIED, REVOKED)."""
    credit = db.update_credit_status(credit_id, req.status.upper())
    if not credit:
        raise HTTPException(status_code=404, detail=f"Credit '{credit_id}' not found")
    return {"status": "updated", "credit": credit}


@app.post("/api/credits/{credit_id}/transfer", tags=["Credits"])
def transfer_credit(credit_id: str, req: TransferRequest):
    """Simulate smart contract safeTransferFrom — blocks if status is FROZEN."""
    credits = db.get_credits()
    target = next((c for c in credits if c["id"] == credit_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Credit '{credit_id}' not found")
    
    # Enforce Living Credit rule: FROZEN credits CANNOT be transferred!
    if target["status"] in ("FROZEN", "REVOKED", "EXPIRED"):
        raise HTTPException(
            status_code=400,
            detail=f"Smart Contract Restriction: Cannot transfer Living Credit while status is '{target['status']}'."
        )
    
    if req.amount > target["lower_bound"]:
        raise HTTPException(
            status_code=400,
            detail=f"Requested amount ({req.amount} t) exceeds available creditable balance ({target['lower_bound']} t)."
        )
    
    # Record transfer simulation (log tx hash)
    tx_hash = f"0x{uuid.uuid4().hex[:16]}...{uuid.uuid4().hex[:8]}"
    return {
        "status": "transferred",
        "credit_id": credit_id,
        "amount": req.amount,
        "recipient": req.recipient_address,
        "tx_hash": tx_hash,
        "message": f"Successfully transferred {req.amount} tCO2e Living Credits on-chain."
    }


@app.post("/api/credits/{credit_id}/retire", tags=["Credits"])
def retire_credit(credit_id: str, req: RetireRequest):
    """Retire (burn) Living Carbon Credits to offset corporate footprint and generate official certificate."""
    credits = db.get_credits()
    target = next((c for c in credits if c["id"] == credit_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Credit '{credit_id}' not found")
    
    if target["status"] in ("FROZEN", "REVOKED"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retire credit while status is '{target['status']}'."
        )
    
    if req.amount > target["lower_bound"]:
        raise HTTPException(
            status_code=400,
            detail=f"Requested retirement amount ({req.amount} t) exceeds available balance ({target['lower_bound']} t)."
        )
    
    retirement = db.insert_retirement(
        credit_id=credit_id,
        plot_id=target["plot_id"],
        amount=req.amount,
        beneficiary_name=req.beneficiary_name,
        offset_reason=req.offset_reason,
        retiree_address=req.retiree_address or "0xBuyerWallet78a9",
    )
    return {
        "status": "retired",
        "retirement": retirement,
        "certificate_id": retirement["certificate_id"],
        "message": f"Permanently retired {req.amount} tCO2e for {req.beneficiary_name}."
    }


@app.get("/api/retirements", tags=["Credits"])
def list_retirements(credit_id: Optional[str] = None):
    """List all corporate carbon offset retirements and certificate records."""
    return db.get_retirements(credit_id=credit_id)


# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────

@app.post("/api/config/thresholds", tags=["Utility"])
def update_thresholds(req: ThresholdsRequest):
    """Update dynamic MRV mint and freeze confidence score thresholds."""
    db.set_config("mint_threshold", str(req.mint_threshold))
    db.set_config("freeze_threshold", str(req.freeze_threshold))
    return {
        "status": "updated",
        "mint_threshold": req.mint_threshold,
        "freeze_threshold": req.freeze_threshold,
    }


# ─────────────────────────────────────────────────────────────────────
# ANOMALIES
# ─────────────────────────────────────────────────────────────────────

@app.get("/api/plots/{plot_id}/anomalies", tags=["Anomalies"])
def list_anomalies(plot_id: str, limit: int = 20):
    """List recent anomalies for a plot."""
    return db.get_anomalies(plot_id, limit=limit)


# ─────────────────────────────────────────────────────────────────────
# COMMUNITY REPORTS
# ─────────────────────────────────────────────────────────────────────

@app.post("/api/community-reports", tags=["Community"])
def submit_report(req: CommunityReportCreate):
    """Submit a community verification report."""
    plot = db.get_plot(req.plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail=f"Plot '{req.plot_id}' not found")

    report = db.insert_community_report(
        plot_id=req.plot_id, submitter=req.submitter,
        description=req.description, photo_uri=req.photo_uri,
    )
    return {"status": "submitted", "report": report}


@app.get("/api/plots/{plot_id}/community-reports", tags=["Community"])
def list_community_reports(plot_id: str, limit: int = 20):
    """List recent community reports for a plot."""
    return db.get_community_reports(plot_id, limit=limit)


@app.get("/api/community-reports", tags=["Community"])
def list_all_community_reports(limit: int = 50):
    """List all community reports across all plots."""
    return db.get_community_reports(limit=limit)


@app.post("/api/community-reports/{report_id}/status", tags=["Community"])
def update_report_status(report_id: str, req: ReportStatusRequest):
    """Update verification status of a community field report."""
    report = db.update_community_report_status(report_id, req.status)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return {"status": "updated", "report": report}


# ─────────────────────────────────────────────────────────────────────
# DASHBOARD DATA (aggregated for the diagnostic UI)
# ─────────────────────────────────────────────────────────────────────

@app.get("/api/dashboard-data", tags=["UI"])
def dashboard_data():
    """
    Aggregated snapshot of everything all four portal views need.
    One call instead of many.
    """
    plots   = db.get_all_plots()
    credits = db.get_credits()
    stats   = db.get_stats()
    retirements = db.get_retirements()

    # Get demo plot details
    demo_plot = db.get_plot(PLOT_ID)
    observations = db.get_observations(PLOT_ID, limit=15) if demo_plot else []
    anomalies    = db.get_anomalies(PLOT_ID, limit=15) if demo_plot else []
    reports      = db.get_community_reports(limit=25)

    # Dynamic thresholds from DB config (falls back to defaults)
    mint_thr = float(db.get_config("mint_threshold", str(MINT_THRESHOLD)))
    freeze_thr = float(db.get_config("freeze_threshold", str(FREEZE_THRESHOLD)))

    # Check upstream services
    ai_status   = svc.ai_health()
    twin_status = svc.twin_health()

    # Try to get twin state
    twin_state = None
    try:
        twin_state = svc.twin_current(PLOT_ID)
    except Exception:
        pass

    return {
        "stats":        stats,
        "plots":        plots,
        "demo_plot":    demo_plot,
        "credits":      credits,
        "retirements":  retirements,
        "observations": observations,
        "anomalies":    anomalies,
        "community_reports": reports,
        "twin_state":   twin_state,
        "services": {
            "backend":  {"status": "ok"},
            "ai":       {"status": ai_status.get("status", "unreachable")},
            "twin":     {"status": twin_status.get("status", "unreachable")},
        },
        "config": {
            "plot_id":    PLOT_ID,
            "site_name":  SITE_NAME,
            "centroid":   CENTROID,
            "bounds":     PLOT_BOUNDS,
            "thresholds": {"mint": mint_thr, "freeze": freeze_thr},
        },
    }


# ─────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
