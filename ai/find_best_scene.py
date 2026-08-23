import ee

from config import PLOT_BOUNDS


# ============================================================
# 1. INITIALIZE EARTH ENGINE
# ============================================================

ee.Initialize(project="sihinternals")


# ============================================================
# 2. DEFINE PICHAVARAM PLOT
# ============================================================

plot = ee.Geometry.Rectangle([
    PLOT_BOUNDS["lon_min"],
    PLOT_BOUNDS["lat_min"],
    PLOT_BOUNDS["lon_max"],
    PLOT_BOUNDS["lat_max"]
])


# ============================================================
# 3. GET SENTINEL-2 IMAGES
# ============================================================

collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(plot)
    .filterDate("2024-08-01", "2026-08-01")
    .filter(
        ee.Filter.lt(
            "CLOUDY_PIXEL_PERCENTAGE",
            20
        )
    )
    .sort("CLOUDY_PIXEL_PERCENTAGE")
)


# ============================================================
# 4. GET BEST IMAGE
# ============================================================

best = ee.Image(
    collection.first()
)


# ============================================================
# 5. PRINT INFORMATION
# ============================================================

image_id = best.get(
    "system:index"
).getInfo()

date = ee.Date(
    best.get("system:time_start")
).format(
    "YYYY-MM-dd"
).getInfo()

cloud_percentage = best.get(
    "CLOUDY_PIXEL_PERCENTAGE"
).getInfo()


print("\n========================================")
print("BEST SENTINEL-2 SCENE")
print("========================================")

print("Image ID:", image_id)
print("Date:", date)
print("Cloud percentage:", cloud_percentage)