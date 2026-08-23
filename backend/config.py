"""
config.py — Shared constants for the M5 backend service.

Central configuration: service URLs, database path, plot defaults.
"""

import os

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH  = os.path.join(DATA_DIR, "tide.db")

# ── Upstream service URLs ──────────────────────────────────────────────
AI_SERVICE_URL   = os.getenv("AI_SERVICE_URL",   "http://localhost:8001")
TWIN_SERVICE_URL = os.getenv("TWIN_SERVICE_URL", "http://localhost:8002")

# ── Demo plot defaults ─────────────────────────────────────────────────
PLOT_ID   = "MNG-001"
SITE_NAME = "Pichavaram Mangrove Forest"
STATE     = "Tamil Nadu"
COUNTRY   = "India"

PLOT_BOUNDS = {
    "lon_min": 79.760,
    "lat_min": 11.400,
    "lon_max": 79.810,
    "lat_max": 11.450,
}

CENTROID = {
    "lat": (PLOT_BOUNDS["lat_min"] + PLOT_BOUNDS["lat_max"]) / 2,
    "lon": (PLOT_BOUNDS["lon_min"] + PLOT_BOUNDS["lon_max"]) / 2,
}

DEFAULT_AREA_HA   = 280.0
BASELINE_NDVI     = 0.42
CARBON_FRACTION   = 0.47

# ── Credit thresholds ──────────────────────────────────────────────────
MINT_THRESHOLD   = 85.0   # MRV score >= this → eligible to mint
FREEZE_THRESHOLD = 60.0   # MRV score <  this → trigger freeze
