"""
services.py — HTTP clients for calling the AI and Digital Twin services.

Each function wraps one upstream API call with error handling.
Uses httpx (sync) for simplicity. Each function is ~10 lines.
"""

import httpx

from config import AI_SERVICE_URL, TWIN_SERVICE_URL


# ── Timeout config ─────────────────────────────────────────────────────
TIMEOUT        = 10.0  # seconds for normal API calls
HEALTH_TIMEOUT = 2.0   # seconds for health checks (fail fast)


# ── AI SERVICE (port 8001) ─────────────────────────────────────────────

def ai_health() -> dict:
    """Check AI service liveness (fast timeout — fail quickly)."""
    try:
        r = httpx.get(f"{AI_SERVICE_URL}/api/ai/health", timeout=HEALTH_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"status": "unreachable"}


def ai_estimate(ndvi: float, area_ha: float, plot_id: str = "MNG-001") -> dict:
    """Call AI carbon estimation endpoint."""
    r = httpx.post(
        f"{AI_SERVICE_URL}/api/ai/estimate",
        json={"plot_id": plot_id, "ndvi": ndvi, "area_ha": area_ha},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def ai_detect_anomaly(current: dict, previous: dict, plot_id: str = "MNG-001") -> dict:
    """Call AI anomaly detection endpoint."""
    r = httpx.post(
        f"{AI_SERVICE_URL}/api/ai/detect-anomaly",
        json={"plot_id": plot_id, "current": current, "previous": previous},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def ai_mrv_full(current: dict, previous: dict, current_ndvi: float,
                area_ha: float, plot_id: str = "MNG-001") -> dict:
    """Call the all-in-one MRV pipeline endpoint."""
    r = httpx.post(
        f"{AI_SERVICE_URL}/api/ai/mrv-full",
        json={
            "plot_id": plot_id,
            "current": current,
            "previous": previous,
            "current_ndvi": current_ndvi,
            "area_ha": area_ha,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def ai_simulate(anomaly: bool = False) -> dict:
    """Get a simulated sensor reading from the AI service."""
    r = httpx.get(
        f"{AI_SERVICE_URL}/api/ai/simulate",
        params={"anomaly": str(anomaly).lower()},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def ai_ndvi_trend() -> dict:
    """Get NDVI trend analysis."""
    r = httpx.get(f"{AI_SERVICE_URL}/api/ai/ndvi-trend", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# ── DIGITAL TWIN SERVICE (port 8002) ──────────────────────────────────

def twin_health() -> dict:
    """Check Digital Twin service liveness (fast timeout — fail quickly)."""
    try:
        r = httpx.get(f"{TWIN_SERVICE_URL}/api/twin/health", timeout=HEALTH_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"status": "unreachable"}


def twin_current(plot_id: str) -> dict:
    """Get current twin snapshot."""
    r = httpx.get(
        f"{TWIN_SERVICE_URL}/api/twin/{plot_id}/current",
        timeout=HEALTH_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def twin_history(plot_id: str, limit: int = None) -> list:
    """Get twin snapshot history."""
    params = {}
    if limit:
        params["limit"] = limit
    r = httpx.get(
        f"{TWIN_SERVICE_URL}/api/twin/{plot_id}/history",
        params=params,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def twin_update(plot_id: str, data: dict) -> dict:
    """Push a new snapshot to the twin."""
    r = httpx.post(
        f"{TWIN_SERVICE_URL}/api/twin/{plot_id}/update",
        json=data,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def twin_satellite_change(plot_id: str) -> dict:
    """Get satellite NDVI change detection."""
    r = httpx.get(
        f"{TWIN_SERVICE_URL}/api/twin/{plot_id}/satellite-change",
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def twin_scores(plot_id: str) -> dict:
    """Get current health + permanence scores."""
    r = httpx.get(
        f"{TWIN_SERVICE_URL}/api/twin/{plot_id}/scores",
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()
