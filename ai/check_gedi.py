import ee

from config import PLOT_BOUNDS


# ============================================================
# 1. INITIALIZE EARTH ENGINE
# ============================================================

ee.Initialize(project="sihinternals")


# ============================================================
# 2. PICHAVARAM PLOT
# ============================================================

plot = ee.Geometry.Rectangle([
    PLOT_BOUNDS["lon_min"],
    PLOT_BOUNDS["lat_min"],
    PLOT_BOUNDS["lon_max"],
    PLOT_BOUNDS["lat_max"]
])


# ============================================================
# 3. LOAD GEDI L4A
# ============================================================

gedi = (
    ee.ImageCollection(
        "LARSE/GEDI/GEDI04_A_002_MONTHLY"
    )
    .filterBounds(plot)
    .filterDate(
        "2019-04-01",
        "2024-12-31"
    )
)


# ============================================================
# 4. COUNT IMAGES
# ============================================================

print(
    "GEDI monthly images:",
    gedi.size().getInfo()
)


# ============================================================
# 5. CHECK AGB COVERAGE
# ============================================================

agbd = gedi.select("agbd").median()

stats = agbd.reduceRegion(
    reducer=ee.Reducer.count(),
    geometry=plot,
    scale=25,
    maxPixels=1e9
)


print(
    "GEDI valid AGB pixels:",
    stats.get("agbd").getInfo()
)


# ============================================================
# 6. AGB STATISTICS
# ============================================================

stats = agbd.reduceRegion(
    reducer=ee.Reducer.mean()
    .combine(
        ee.Reducer.min(),
        sharedInputs=True
    )
    .combine(
        ee.Reducer.max(),
        sharedInputs=True
    ),
    geometry=plot,
    scale=25,
    maxPixels=1e9
)


print("\nGEDI AGB statistics:")
print(stats.getInfo())