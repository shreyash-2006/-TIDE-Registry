"""
seed.py — Seeds the database with demo data for MNG-001.

Run standalone:  python seed.py
Also auto-runs at backend startup.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config import PLOT_ID, SITE_NAME, CENTROID, DEFAULT_AREA_HA, BASELINE_NDVI
import database as db


def seed_demo_data():
    """Insert demo plots and rich sample data for all 4 roles if the database is empty."""
    existing = db.get_all_plots()
    if existing:
        print(f"[seed] Database already has {len(existing)} plot(s) -- skipping seed")
        return

    print("[seed] Seeding comprehensive multi-role demo data...")

    # 1. Create demo plots across key Indian blue-carbon hotspots
    plots_data = [
        (PLOT_ID, SITE_NAME, CENTROID["lat"], CENTROID["lon"], DEFAULT_AREA_HA, "mangrove", BASELINE_NDVI),
        ("MNG-002", "Sundarbans Delta Project Beta", 21.949, 88.900, 180.0, "mangrove", 0.48),
        ("SGR-001", "Gulf of Mannar Seagrass Sanctuary", 9.280, 79.120, 95.0, "seagrass", 0.35),
    ]
    for pid, name, lat, lng, area, eco, ndvi in plots_data:
        db.insert_plot(plot_id=pid, name=name, lat=lat, lng=lng, area_ha=area, ecosystem_type=eco, baseline_ndvi=ndvi)
    print(f"[seed]   Registered {len(plots_data)} blue-carbon plots")

    # 2. Sample healthy observations for MNG-001
    healthy_readings = [
        {"ndvi": 0.42, "salinity": 14.0, "temperature": 28.5, "ph": 7.8, "soil_moisture": 65.0, "water_level": 1.1},
        {"ndvi": 0.40, "salinity": 15.2, "temperature": 29.0, "ph": 7.6, "soil_moisture": 62.0, "water_level": 1.0},
        {"ndvi": 0.38, "salinity": 13.5, "temperature": 27.8, "ph": 7.9, "soil_moisture": 68.0, "water_level": 1.2},
    ]
    for r in healthy_readings:
        db.insert_observation(
            plot_id=PLOT_ID,
            ndvi=r["ndvi"], salinity=r["salinity"],
            temperature=r["temperature"], ph=r["ph"],
            soil_moisture=r["soil_moisture"], water_level=r["water_level"],
            source="seed",
        )
    print(f"[seed]   {len(healthy_readings)} sample sensor observations")

    # 3. Living Credits for marketplace and admin testing
    c1 = db.insert_credit(
        plot_id=PLOT_ID,
        quantity=42.0,
        lower_bound=32.1,
        mrv_score=88.5,
        evidence_hash="0xQmBaselineSentinelPichavaram789",
    )
    # Set c1 to ACTIVE
    db.update_credit_status(c1["id"], "ACTIVE")

    c2 = db.insert_credit(
        plot_id="MNG-002",
        quantity=58.0,
        lower_bound=46.5,
        mrv_score=91.0,
        evidence_hash="0xQmSundarbansBaselineEvidence104",
    )
    db.update_credit_status(c2["id"], "ACTIVE")

    c3 = db.insert_credit(
        plot_id="SGR-001",
        quantity=24.0,
        lower_bound=18.0,
        mrv_score=82.0,
        evidence_hash="0xQmGulfMannarSeagrassVerified",
    )
    db.update_credit_status(c3["id"], "PROPOSED")
    print("[seed]   3 Living Credit batches seeded (ACTIVE & PROPOSED)")

    # 4. Sample corporate carbon retirement
    db.insert_retirement(
        credit_id=c1["id"],
        plot_id=PLOT_ID,
        amount=5.0,
        beneficiary_name="Green Tech Corp India",
        offset_reason="Scope 1 & 2 Emissions Offset for Q1 2025",
        retiree_address="0xBuyerWallet94b2",
    )
    print("[seed]   1 sample offset retirement certificate logged")

    # 5. Community reports
    db.insert_community_report(
        plot_id=PLOT_ID,
        submitter="Ravi Fisher (Pichavaram Cooperative)",
        description="Mangroves healthy -- dense canopy observed during tidal field monitoring.",
        photo_uri="ipfs://QmPichavaramHealthyCanopy2026",
    )
    db.insert_community_report(
        plot_id=PLOT_ID,
        submitter="Meena Sundaram (Coastal Warden)",
        description="Minor debris accumulation near tidal canal creek #3; vegetation intact.",
        photo_uri="ipfs://QmCanalDebrisFieldObservation",
    )
    db.insert_community_report(
        plot_id="MNG-002",
        submitter="Sundarbans Ranger Station 4",
        description="New sapling growth verified in Zone B restoration corridor.",
        photo_uri="ipfs://QmSundarbansSaplingRegrowthProof",
    )
    print("[seed]   3 community ground-truth reports seeded")

    print("[seed] Done -- database seeded [OK]")


if __name__ == "__main__":
    seed_demo_data()
