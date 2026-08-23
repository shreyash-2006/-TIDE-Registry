import ee

from config import PLOT_BOUNDS


# ============================================================
# 1. INITIALIZE
# ============================================================

ee.Initialize(
    project="sihinternals"
)


# ============================================================
# 2. PICHAVARAM
# ============================================================

plot = ee.Geometry.Rectangle([
    PLOT_BOUNDS["lon_min"],
    PLOT_BOUNDS["lat_min"],
    PLOT_BOUNDS["lon_max"],
    PLOT_BOUNDS["lat_max"]
])


# ============================================================
# 3. GEDI
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


def quality_mask(image):

    return image.updateMask(
        image.select(
            "l4_quality_flag"
        ).eq(1)
        .And(
            image.select(
                "degrade_flag"
            ).eq(0)
        )
    )


gedi = gedi.map(
    quality_mask
)


agbd = gedi.select(
    "agbd"
).median()

agbd_se = gedi.select(
    "agbd_se"
).median()


# ============================================================
# 4. GET GEDI POINTS
# ============================================================

gedi_stack = (
    agbd.rename("agbd")
    .addBands(
        agbd_se.rename("agbd_se")
    )
)


gedi_samples = gedi_stack.sample(
    region=plot,
    scale=25,
    numPixels=50,
    seed=42,
    geometries=True
)


gedi_features = gedi_samples.getInfo()[
    "features"
]


print("\n========================================")
print("GEDI DEBUG")
print("========================================")

print(
    "GEDI samples:",
    len(gedi_features)
)


if len(gedi_features) == 0:

    raise RuntimeError(
        "GEDI returned zero samples."
    )


# ============================================================
# 5. PRINT FIRST GEDI POINT
# ============================================================

first = gedi_features[0]

print("\nFirst GEDI feature:")

print(first)


# ============================================================
# 6. CREATE GEDI FEATURE COLLECTION
# ============================================================

points = []

for feature in gedi_features:

    props = feature["properties"]

    geometry = feature["geometry"]

    if geometry is None:
        continue

    coordinates = geometry[
        "coordinates"
    ]

    points.append(
        ee.Feature(
            ee.Geometry.Point(
                coordinates
            ),
            {
                "agbd": props.get(
                    "agbd"
                ),
                "agbd_se": props.get(
                    "agbd_se"
                )
            }
        )
    )


gedi_points = ee.FeatureCollection(
    points
)


print(
    "\nGEDI point count:",
    gedi_points.size().getInfo()
)


# ============================================================
# 7. LOAD SENTINEL-2
# ============================================================

sentinel = ee.Image(
    "COPERNICUS/S2_SR_HARMONIZED/"
    "20240916T045659_20240916T051515_T44PLT"
)


print("\n========================================")
print("SENTINEL-2 DEBUG")
print("========================================")


# ============================================================
# 8. CALCULATE NDVI
# ============================================================

ndvi = sentinel.normalizedDifference(
    ["B8", "B4"]
).rename(
    "NDVI"
)


# ============================================================
# 9. GET SCL
# ============================================================

scl = sentinel.select(
    "SCL"
).rename(
    "SCL"
)


# ============================================================
# 10. SAMPLE WITHOUT ANY MASKING
# ============================================================

stack = (
    ndvi
    .addBands(scl)
)


result = stack.sampleRegions(
    collection=gedi_points,
    properties=[
        "agbd",
        "agbd_se"
    ],
    scale=10,
    geometries=True
)


result_features = result.getInfo()[
    "features"
]


print(
    "Sentinel samples returned:",
    len(result_features)
)


# ============================================================
# 11. PRINT RAW RESULTS
# ============================================================

print("\nFirst 10 Sentinel results:")

for feature in result_features[:10]:

    print(
        feature
    )


# ============================================================
# 12. COUNT VALUES
# ============================================================

ndvi_count = 0
scl_count = 0

scl_values = {}


for feature in result_features:

    props = feature["properties"]

    ndvi_value = props.get(
        "NDVI"
    )

    scl_value = props.get(
        "SCL"
    )

    if ndvi_value is not None:

        ndvi_count += 1

    if scl_value is not None:

        scl_count += 1

        scl_values[
            str(scl_value)
        ] = (
            scl_values.get(
                str(scl_value),
                0
            ) + 1
        )


print("\n========================================")
print("SUMMARY")
print("========================================")

print(
    "Total returned:",
    len(result_features)
)

print(
    "NDVI values:",
    ndvi_count
)

print(
    "SCL values:",
    scl_count
)

print(
    "SCL distribution:",
    scl_values
)