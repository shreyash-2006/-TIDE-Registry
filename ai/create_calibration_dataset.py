import ee
import rasterio
import numpy as np
import pandas as pd

from config import PLOT_BOUNDS, PLOT_ID


# ============================================================
# 1. INITIALIZE EARTH ENGINE
# ============================================================

ee.Initialize(project="sihinternals")


# ============================================================
# 2. CONFIGURATION
# ============================================================

AGB_PATH = "data/mangrove_agb_india.tif"

OUTPUT_PATH = "data/ndvi_agb_samples.csv"

NUM_SAMPLES = 200

SENTINEL_IMAGE_ID = (
    "COPERNICUS/S2_SR_HARMONIZED/"
    "20240916T045659_20240916T051515_T44PLT"
)


# ============================================================
# 3. DEFINE PICHAVARAM PLOT
# ============================================================

plot = ee.Geometry.Rectangle([
    PLOT_BOUNDS["lon_min"],
    PLOT_BOUNDS["lat_min"],
    PLOT_BOUNDS["lon_max"],
    PLOT_BOUNDS["lat_max"]
])


# ============================================================
# 4. READ ONLY PICHAVARAM FROM NASA AGB RASTER
# ============================================================

print("\n========================================")
print("READING NASA AGB DATA")
print("========================================")

with rasterio.open(AGB_PATH) as src:

    window = rasterio.windows.from_bounds(
        PLOT_BOUNDS["lon_min"],
        PLOT_BOUNDS["lat_min"],
        PLOT_BOUNDS["lon_max"],
        PLOT_BOUNDS["lat_max"],
        src.transform
    )

    agb = src.read(
        1,
        window=window
    )

    window_transform = src.window_transform(
        window
    )

    print("CRS:", src.crs)
    print("Resolution:", src.res)
    print("Pichavaram raster shape:", agb.shape)


# ============================================================
# 5. FIND VALID AGB PIXELS
# ============================================================

valid_mask = (
    np.isfinite(agb) &
    (agb > 0)
)

rows, cols = np.where(
    valid_mask
)

print(
    "Valid AGB pixels:",
    len(rows)
)


if len(rows) == 0:
    raise RuntimeError(
        "No valid AGB pixels found."
    )


# ============================================================
# 6. RANDOMLY SELECT 200 AGB PIXELS
# ============================================================

rng = np.random.default_rng(42)

sample_count = min(
    NUM_SAMPLES,
    len(rows)
)

indices = rng.choice(
    len(rows),
    size=sample_count,
    replace=False
)


# ============================================================
# 7. CREATE EE FEATURES
#    IMPORTANT:
#    AGB IS STORED INSIDE EACH FEATURE
# ============================================================

features = []

for index in indices:

    row = rows[index]
    col = cols[index]

    lon, lat = rasterio.transform.xy(
        window_transform,
        row,
        col,
        offset="center"
    )

    agb_value = float(
        agb[row, col]
    )

    feature = ee.Feature(
        ee.Geometry.Point([
            lon,
            lat
        ]),
        {
            "plot_id": PLOT_ID,
            "latitude": lat,
            "longitude": lon,
            "agb_t_per_ha": agb_value
        }
    )

    features.append(feature)


points = ee.FeatureCollection(
    features
)


print(
    "Selected AGB samples:",
    sample_count
)


# ============================================================
# 8. LOAD SENTINEL-2 IMAGE
# ============================================================

print("\n========================================")
print("LOADING SENTINEL-2")
print("========================================")

image = ee.Image(
    SENTINEL_IMAGE_ID
)


# ============================================================
# 9. PIXEL-LEVEL QUALITY MASK
# ============================================================

scl = image.select("SCL")

# Keep:
# 4 = vegetation
# 5 = bare soil
# 6 = water
#
# Remove:
# 3 = cloud shadow
# 7 = unclassified
# 8 = cloud medium probability
# 9 = cloud high probability
# 10 = cirrus
# 11 = snow/ice

valid_scl = (
    scl.eq(4)
    .Or(scl.eq(5))
    .Or(scl.eq(6))
)

image = image.updateMask(
    valid_scl
)


# ============================================================
# 10. CALCULATE NDVI
# ============================================================

ndvi = image.normalizedDifference(
    ["B8", "B4"]
).rename("NDVI")


# ============================================================
# 11. SAMPLE NDVI AT THE SAME LOCATIONS
# ============================================================

print("\n========================================")
print("EXTRACTING NDVI")
print("========================================")

sampled = ndvi.addBands(
    image.select("SCL")
).sampleRegions(
    collection=points,
    properties=[
        "plot_id",
        "latitude",
        "longitude",
        "agb_t_per_ha"
    ],
    scale=30,
    geometries=False
)


results = sampled.getInfo()["features"]


print(
    "Samples returned:",
    len(results)
)


# ============================================================
# 12. BUILD DATAFRAME
# ============================================================

records = []

for feature in results:

    properties = feature["properties"]

    ndvi_value = properties.get(
        "NDVI"
    )

    agb_value = properties.get(
        "agb_t_per_ha"
    )

    if ndvi_value is None:
        continue

    if agb_value is None:
        continue

    records.append({

        "plot_id":
            properties["plot_id"],

        "latitude":
            properties["latitude"],

        "longitude":
            properties["longitude"],

        "ndvi":
            float(ndvi_value),

        "agb_t_per_ha":
            float(agb_value)
    })


df = pd.DataFrame(
    records
)


# ============================================================
# 13. VALIDATE NDVI
# ============================================================

df = df[
    (df["ndvi"] >= -1) &
    (df["ndvi"] <= 1)
]


df = df[
    df["agb_t_per_ha"] > 0
]


# ============================================================
# 14. SAVE
# ============================================================

df.to_csv(
    OUTPUT_PATH,
    index=False
)


# ============================================================
# 15. RESULTS
# ============================================================

print("\n========================================")
print("CALIBRATION DATASET COMPLETE")
print("========================================")

print(
    "Valid paired samples:",
    len(df)
)

print("\nFirst 10 samples:")
print(
    df.head(10)
)

print("\nNDVI statistics:")
print(
    df["ndvi"].describe()
)

print("\nAGB statistics:")
print(
    df["agb_t_per_ha"].describe()
)

print("\nCorrelation:")

print(
    df[
        ["ndvi", "agb_t_per_ha"]
    ].corr().iloc[0, 1]
)

print("\nSaved to:")
print(OUTPUT_PATH)