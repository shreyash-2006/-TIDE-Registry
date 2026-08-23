import ee
import pandas as pd

from config import PLOT_BOUNDS, PLOT_ID


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
# 3. LOAD GEDI
# ============================================================

print("\n========================================")
print("LOADING GEDI")
print("========================================")

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

print(
    "GEDI monthly images:",
    gedi.size().getInfo()
)


# ============================================================
# 4. QUALITY FILTER
# ============================================================

def quality_mask(image):

    return image.updateMask(
        image.select("l4_quality_flag").eq(1)
        .And(
            image.select("degrade_flag").eq(0)
        )
    )


gedi_quality = gedi.map(
    quality_mask
)


# ============================================================
# 5. CREATE GEDI MEDIAN LAYERS
# ============================================================

agbd = gedi_quality.select(
    "agbd"
).median()

agbd_se = gedi_quality.select(
    "agbd_se"
).median()


# ============================================================
# 6. CHECK GEDI COVERAGE
# ============================================================

print("\n========================================")
print("CHECKING GEDI COVERAGE")
print("========================================")

coverage = agbd.reduceRegion(
    reducer=ee.Reducer.count(),
    geometry=plot,
    scale=25,
    maxPixels=1e9
)

print(
    "Valid GEDI pixels:",
    coverage.get("agbd").getInfo()
)


# ============================================================
# 7. SAMPLE GEDI
# ============================================================

print("\n========================================")
print("SAMPLING GEDI")
print("========================================")

gedi_stack = (
    agbd.rename("agbd")
    .addBands(
        agbd_se.rename("agbd_se")
    )
)


samples = gedi_stack.sample(
    region=plot,
    scale=25,
    numPixels=500,
    seed=42,
    geometries=True
)


features = samples.getInfo()["features"]

print(
    "GEDI samples returned:",
    len(features)
)


# ============================================================
# 8. CREATE POINT FEATURES
# ============================================================

points = []

for feature in features:

    props = feature["properties"]

    geometry = feature["geometry"]

    if geometry is None:
        continue

    agbd_value = props.get("agbd")
    se_value = props.get("agbd_se")

    if agbd_value is None:
        continue

    if se_value is None:
        continue

    if agbd_value <= 0:
        continue

    coordinates = geometry["coordinates"]

    lon = coordinates[0]
    lat = coordinates[1]

    points.append(
        ee.Feature(
            ee.Geometry.Point([
                lon,
                lat
            ]),
            {
                "plot_id": PLOT_ID,
                "latitude": lat,
                "longitude": lon,
                "agbd_mg_per_ha": agbd_value,
                "agbd_se": se_value
            }
        )
    )


gedi_points = ee.FeatureCollection(points)

print(
    "Valid GEDI points:",
    gedi_points.size().getInfo()
)


# ============================================================
# 9. LOAD SENTINEL-2
# ============================================================

print("\n========================================")
print("LOADING SENTINEL-2")
print("========================================")

sentinel = ee.Image(
    "COPERNICUS/S2_SR_HARMONIZED/"
    "20240916T045659_20240916T051515_T44PLT"
)


# ============================================================
# 10. CALCULATE NDVI
# ============================================================

ndvi = sentinel.normalizedDifference(
    ["B8", "B4"]
).rename("NDVI")


# ============================================================
# 11. GET SCL
# ============================================================

scl = sentinel.select(
    "SCL"
).rename(
    "SCL"
)


# ============================================================
# 12. SAMPLE SENTINEL-2 AT GEDI LOCATIONS
# ============================================================

print("\n========================================")
print("SAMPLING SENTINEL-2")
print("========================================")

s2_stack = (
    ndvi
    .addBands(scl)
)


paired = s2_stack.sampleRegions(
    collection=gedi_points,
    properties=[
        "plot_id",
        "latitude",
        "longitude",
        "agbd_mg_per_ha",
        "agbd_se"
    ],
    scale=25,
    geometries=False
)


paired_features = paired.getInfo()[
    "features"
]


print(
    "Sentinel-2 samples returned:",
    len(paired_features)
)


# ============================================================
# 13. BUILD DATAFRAME
# ============================================================

records = []

for feature in paired_features:

    p = feature["properties"]

    ndvi_value = p.get("NDVI")
    scl_value = p.get("SCL")

    if ndvi_value is None:
        continue

    if scl_value is None:
        continue

    # Remove cloud/shadow/water pixels
    #if scl_value not in [4, 5]:
     #   continue

    records.append({
        "plot_id": p["plot_id"],
        "latitude": p["latitude"],
        "longitude": p["longitude"],
        "ndvi": float(ndvi_value),
        "scl": int(scl_value),
        "agbd_mg_per_ha": float(p["agbd_mg_per_ha"]),
        "agbd_se": float(p["agbd_se"])
    })


df = pd.DataFrame(records)
print("\nSCL class distribution:")
print(df["scl"].value_counts().sort_index())


# ============================================================
# 14. SAFETY CHECK
# ============================================================

#if df.empty:

#    raise RuntimeError(
#        "GEDI points exist, but none overlap "
#        "valid vegetation/bare-soil Sentinel-2 pixels."
#    )


# ============================================================
# 15. VALIDATE NDVI
# ============================================================

df = df[
    (df["ndvi"] >= -1) &
    (df["ndvi"] <= 1)
].copy()


# ============================================================
# 16. SAVE
# ============================================================

output_path = "data/ndvi_gedi_samples.csv"

df.to_csv(
    output_path,
    index=False
)


# ============================================================
# 17. RESULTS
# ============================================================

print("\n========================================")
print("GEDI CALIBRATION DATASET COMPLETE")
print("========================================")

print(
    "Valid NDVI-GEDI pairs:",
    len(df)
)

print("\nFirst 10 samples:")
print(df.head(10))

print("\nNDVI statistics:")
print(df["ndvi"].describe())

print("\nGEDI AGB statistics:")
print(
    df["agbd_mg_per_ha"].describe()
)

print("\nGEDI uncertainty:")
print(
    df["agbd_se"].describe()
)

if len(df) > 1:

    correlation = df[
        [
            "ndvi",
            "agbd_mg_per_ha"
        ]
    ].corr().iloc[0, 1]

    print(
        "\nNDVI-GEDI correlation:",
        correlation
    )

print("\nSaved to:")
print(output_path)