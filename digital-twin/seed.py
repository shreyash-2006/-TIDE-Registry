"""
seed.py — Demo scenario seeder for MNG-001 Digital Twin

Seeds the in-memory twin history with 4 pre-crafted snapshots that tell
the demo story:

  Snapshot 1 — Baseline healthy       (Day 0, pre-stress)
  Snapshot 2 — Pre-cyclone stress      (mild degradation signal)
  Snapshot 3 — Post-cyclone degraded   (severe — triggers freeze)
  Snapshot 4 — Post-restoration        (recovering, credit status restoring)

Called once at API startup. Designed so the demo has a meaningful history
from the very first request, and the health/carbon timeline chart shows
a clear, explainable shape on screen.

To re-seed (e.g. after a demo reset), call seed_demo_history() again —
it is idempotent if the plot history is empty, and skips if already seeded.
"""

import sys
import os
from datetime import datetime, timezone, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from temporal.snapshot import twin_history, TwinSnapshot
from config import PLOT_ID, NDVI_BASELINE


def _dt(days_ago: int, hour: int = 9) -> datetime:
    """Return a timezone-aware UTC datetime N days before now."""
    base = datetime.now(tz=timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0)
    return base - timedelta(days=days_ago)


def seed_demo_history(force: bool = False) -> int:
    """
    Seed MNG-001 with 4 demo snapshots.

    Parameters
    ----------
    force : bool
        If True, clears existing history before seeding.
        If False (default), skips seeding if history already exists.

    Returns
    -------
    int
        Number of snapshots added (0 if skipped).
    """
    if not force and twin_history.snapshot_count(PLOT_ID) > 0:
        print(f"[seed] {PLOT_ID} already has history — skipping seed (use force=True to reset)")
        return 0

    if force:
        twin_history.clear(PLOT_ID)

    snapshots = _build_demo_snapshots()
    for snap in snapshots:
        twin_history.add(snap)

    print(f"[seed] {PLOT_ID}: {len(snapshots)} demo snapshots loaded")
    return len(snapshots)


def _build_demo_snapshots():
    """Build the 4 demo scenario snapshots."""

    # ── Snapshot 1: Baseline Healthy ──────────────────────────────────────────
    # Day -90: everything is normal, pre-stress.
    # Health = (0.42 / 0.38) × 100 − 0 = 100 → capped 100
    s1 = TwinSnapshot(
        plot_id           = PLOT_ID,
        timestamp         = _dt(90),
        area_ha           = 281.4,
        ndvi              = 0.42,
        mangrove_density  = 0.78,
        biomass           = 105.2,
        carbon_stock      = 37_800.0,
        carbon_confidence = 0.91,
        health_score      = 100.0,
        permanence_score  = 95.0,
        biodiversity_index= 0.72,
        water_quality     = {"salinity_ppt": 14.2, "ph": 7.8, "water_level_m": 1.1, "anomaly": False},
        soil_conditions   = {"moisture_pct": 65.0, "temperature_c": 28.1, "anomaly": False},
        restoration_age_years = 12.0,
        credit_status     = "ACTIVE",
        source_event      = "routine_update",
        notes             = "Baseline healthy state — mint-eligible (Day 0 of demo scenario)",
    )

    # ── Snapshot 2: Pre-Cyclone Stress ────────────────────────────────────────
    # Day -30: NDVI starting to dip, one sensor flagging.
    # Health = (0.35 / 0.38) × 100 − 5 = 87.1
    s2 = TwinSnapshot(
        plot_id           = PLOT_ID,
        timestamp         = _dt(30),
        area_ha           = 281.4,
        ndvi              = 0.35,
        mangrove_density  = 0.71,
        biomass           = 94.6,
        carbon_stock      = 34_056.0,
        carbon_confidence = 0.87,
        health_score      = 87.1,
        permanence_score  = 80.0,
        biodiversity_index= 0.68,
        water_quality     = {"salinity_ppt": 18.5, "ph": 7.5, "water_level_m": 1.3, "anomaly": True},
        soil_conditions   = {"moisture_pct": 58.0, "temperature_c": 30.2, "anomaly": False},
        restoration_age_years = 12.2,
        credit_status     = "AT-RISK",
        source_event      = "satellite_alert",
        notes             = "Mild stress signal — salinity elevated, NDVI dipping. Credit flagged AT-RISK.",
    )

    # ── Snapshot 3: Post-Cyclone Degraded (freeze trigger) ───────────────────
    # Day -7: severe degradation, IoT anomaly, credit frozen.
    # Health = (0.19 / 0.38) × 100 − 5 − (1.0 × 30) = 50 − 35 = 15.0
    s3 = TwinSnapshot(
        plot_id           = PLOT_ID,
        timestamp         = _dt(7),
        area_ha           = 281.4,
        ndvi              = 0.19,
        mangrove_density  = 0.42,
        biomass           = 61.3,
        carbon_stock      = 22_068.0,
        carbon_confidence = 0.62,
        health_score      = 15.0,
        permanence_score  = 0.0,
        biodiversity_index= 0.41,
        water_quality     = {"salinity_ppt": 31.2, "ph": 6.9, "water_level_m": 0.4, "anomaly": True},
        soil_conditions   = {"moisture_pct": 22.0, "temperature_c": 36.8, "anomaly": True},
        restoration_age_years = 12.4,
        credit_status     = "FROZEN",
        source_event      = "satellite_alert",
        notes             = "Severe post-cyclone degradation — NDVI −55%, IoT anomaly. FREEZE triggered.",
    )

    # ── Snapshot 4: Post-Restoration (recovering) ─────────────────────────────
    # Today: NDVI recovering, sensors stabilising, credit under review.
    # Health = (0.31 / 0.38) × 100 − 2 − (0.2 × 30) = 81.6 − 8 = 73.6
    s4 = TwinSnapshot(
        plot_id           = PLOT_ID,
        timestamp         = _dt(0, hour=6),
        area_ha           = 281.4,
        ndvi              = 0.31,
        mangrove_density  = 0.59,
        biomass           = 78.4,
        carbon_stock      = 28_224.0,
        carbon_confidence = 0.79,
        health_score      = 73.6,
        permanence_score  = 58.6,
        biodiversity_index= 0.55,
        water_quality     = {"salinity_ppt": 16.1, "ph": 7.6, "water_level_m": 1.0, "anomaly": False},
        soil_conditions   = {"moisture_pct": 52.0, "temperature_c": 29.5, "anomaly": False},
        restoration_age_years = 12.5,
        credit_status     = "UNDER_REVIEW",
        source_event      = "reverification",
        notes             = "Post-restoration recovery — NDVI rising, sensors normalising. Reverification in progress.",
    )

    return [s1, s2, s3, s4]


if __name__ == "__main__":
    # Allow running directly to inspect seeded data
    n = seed_demo_history(force=True)
    print(f"Seeded {n} snapshots for {PLOT_ID}")
    for snap in twin_history.get_history(PLOT_ID):
        print(f"  {snap.timestamp.date()}  health={snap.health_score}  credit={snap.credit_status}  event={snap.source_event}")
