"""
config.py — Digital Twin + GIS module constants

Mirrors ai/config.py so both services agree on plot identity.
Lock these values with M1 before the demo.
"""

PLOT_ID   = "MNG-001"
SITE_NAME = "Pichavaram Mangrove Forest"
STATE     = "Tamil Nadu"
COUNTRY   = "India"

# Bounding box: [lon_min, lat_min, lon_max, lat_max]
BBOX_LIST = [79.760, 11.400, 79.810, 11.450]

PLOT_BOUNDS = {
    "lon_min": 79.760,
    "lat_min": 11.400,
    "lon_max": 79.810,
    "lat_max": 11.450,
}

# Approximate centroid for map centering
CENTROID = {"lat": 11.425, "lon": 79.785}

# NDVI baseline from the AI module's real GEE time series (MNG-001, 2024-2026)
NDVI_BASELINE = 0.38

# Satellite change-detection threshold — coordinate with M1's anomaly detector
# so both modules agree on what "significant" means
SIGNIFICANCE_THRESHOLD_PCT = 15.0   # |pct_change| > 15% → significant degradation

# Health / permanence scoring
HEALTH_HEALTHY_THRESHOLD  = 70.0
HEALTH_STRESSED_THRESHOLD = 40.0

# GEE project — only used when GEE mode is enabled
GEE_PROJECT = "your-gee-project"   # replace with actual project ID before demo
