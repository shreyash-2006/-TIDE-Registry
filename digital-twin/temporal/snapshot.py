"""
temporal/snapshot.py — Digital Twin data model and in-memory history store

TwinSnapshot is the core data object of this module.
Every change to the plot produces a NEW snapshot appended to the history —
the full list IS the twin's time-versioned state, enabling the healthy →
degraded → frozen → restored demo narrative.

Schema is intentionally Pydantic-model-compatible with a future Postgres
table (M5 can own persistence using this schema without changes).

Design:
  - All fields except plot_id + timestamp are Optional to allow partial updates
  - History store is in-memory for the hackathon (a dict of plot_id → list)
  - Thread-safe via a simple lock (FastAPI workers share the same process)
"""

import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────

class TwinSnapshot(BaseModel):
    """
    A single point-in-time state of a carbon plot's Digital Twin.

    Every incoming signal (IoT batch, satellite pass, community report,
    blockchain state change) appends one of these rather than overwriting
    the previous state.
    """
    # Identity
    plot_id:   str      = Field(..., description="Plot identifier, e.g. MNG-001")
    timestamp: datetime = Field(..., description="UTC timestamp of this snapshot")

    # Location + geometry
    location:  dict     = Field(default_factory=lambda: {"lat": 11.425, "lon": 79.785},
                                description="{lat, lon} of plot centroid")
    area_ha:   float    = Field(default=280.0, gt=0, description="Current plot area (ha)")

    # Vegetation + biomass
    ndvi:              Optional[float] = Field(None, ge=-1.0, le=1.0,
                                               description="Current mean NDVI")
    mangrove_density:  Optional[float] = Field(None, ge=0.0, le=1.0,
                                               description="Fractional canopy cover (0–1)")
    biomass:           Optional[float] = Field(None, description="Aboveground biomass (t/ha)")

    # Carbon
    carbon_stock:      Optional[float] = Field(None, description="Total CO2e stock (t) — from M1")
    carbon_confidence: Optional[float] = Field(None, ge=0.0, le=1.0,
                                               description="M1 confidence_level (0–1)")

    # Health scores (computed by scoring.py)
    health_score:       Optional[float] = Field(None, ge=0.0, le=100.0,
                                                description="Composite health score (0–100)")
    permanence_score:   Optional[float] = Field(None, ge=0.0, le=100.0,
                                                description="Carbon permanence score (0–100)")
    biodiversity_index: Optional[float] = Field(None, description="Simplified biodiversity proxy")

    # IoT sensor summaries (from M3)
    water_quality:   Optional[dict] = Field(None,
                        description="{salinity_ppt, ph, water_level_m, anomaly}")
    soil_conditions: Optional[dict] = Field(None,
                        description="{moisture_pct, temperature_c, anomaly}")

    # Plot lifecycle
    restoration_age_years: Optional[float] = Field(None, description="Years since restoration started")

    # Credit / chain state (from M4)
    credit_status: Optional[str] = Field(None,
                        description="ACTIVE | AT-RISK | FROZEN | UNDER_REVIEW | RESTORED")

    # Event metadata
    source_event: Optional[str] = Field(None,
                        description="routine_update | satellite_alert | community_report | reverification")
    notes: Optional[str] = Field(None, description="Free-text annotation for this snapshot")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY HISTORY STORE
# ─────────────────────────────────────────────────────────────────────────────

class TwinHistory:
    """
    Thread-safe in-memory store for TwinSnapshot time series.

    plot_id → [snapshot_0, snapshot_1, ..., snapshot_N]  (chronological order)

    For the hackathon this is intentionally kept in-memory. When M5 adds
    Postgres persistence, this class can be replaced with a DB-backed version
    without touching the API layer.
    """

    def __init__(self):
        self._store: Dict[str, List[TwinSnapshot]] = {}
        self._lock  = threading.Lock()

    def add(self, snapshot: TwinSnapshot) -> int:
        """Append snapshot and return the new total count for this plot."""
        with self._lock:
            if snapshot.plot_id not in self._store:
                self._store[snapshot.plot_id] = []
            self._store[snapshot.plot_id].append(snapshot)
            return len(self._store[snapshot.plot_id])

    def get_current(self, plot_id: str) -> Optional[TwinSnapshot]:
        """Return the most recent snapshot, or None if no history exists."""
        with self._lock:
            history = self._store.get(plot_id, [])
            return history[-1] if history else None

    def get_history(self, plot_id: str) -> List[TwinSnapshot]:
        """Return a copy of the full snapshot list (oldest first)."""
        with self._lock:
            return list(self._store.get(plot_id, []))

    def list_plots(self) -> List[str]:
        """Return all plot IDs that have at least one snapshot."""
        with self._lock:
            return list(self._store.keys())

    def snapshot_count(self, plot_id: str) -> int:
        with self._lock:
            return len(self._store.get(plot_id, []))

    def clear(self, plot_id: str) -> None:
        """Remove all snapshots for a plot (test helper — not exposed via API)."""
        with self._lock:
            self._store.pop(plot_id, None)


# ── Module-level singleton used by api.py and seed.py ────────────────────────
twin_history = TwinHistory()


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def now_utc() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(tz=timezone.utc)


def make_snapshot(**kwargs) -> TwinSnapshot:
    """
    Factory helper — sets timestamp to now (UTC) if not provided.

    Usage:
        snap = make_snapshot(plot_id="MNG-001", ndvi=0.42, health_score=85.0)
    """
    if "timestamp" not in kwargs:
        kwargs["timestamp"] = now_utc()
    return TwinSnapshot(**kwargs)
