import ee
import pandas as pd
from config import PLOT_BOUNDS, PLOT_ID, SITE_NAME


# --------------------------------------------------
# 1. Initialize Earth Engine
# --------------------------------------------------

ee.Initialize(project="sihinternals")


# --------------------------------------------------
# 2. Define Pichavaram plot
# --------------------------------------------------

plot = ee.Geometry.Rectangle([
    PLOT_BOUNDS["lon_min"],
    PLOT_BOUNDS["lat_min"],
    PLOT_BOUNDS["lon_max"],
    PLOT_BOUNDS["lat_max"]
])


# --------------------------------------------------
# 3. Load Sentinel-2 Surface Reflectance
# --------------------------------------------------

collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(plot)
    .filterDate("2024-08-01", "2026-08-01")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
)


print("Number of Sentinel-2 images:", collection.size().getInfo())


# --------------------------------------------------
# 4. Calculate NDVI
# --------------------------------------------------

def add_ndvi(image):

    ndvi = image.normalizedDifference(
        ["B8", "B4"]
    ).rename("NDVI")

    return image.addBands(ndvi)


with_ndvi = collection.map(add_ndvi)


# --------------------------------------------------
# 5. Calculate mean NDVI over Pichavaram plot
# --------------------------------------------------

def get_mean_ndvi(image):

    mean_ndvi = image.select("NDVI").reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=plot,
        scale=10,
        maxPixels=1e9
    )

    return image.set(
        "mean_ndvi",
        mean_ndvi.get("NDVI")
    ).set(
        "date",
        image.date().format("YYYY-MM-dd")
    )


ts = with_ndvi.map(get_mean_ndvi)


# --------------------------------------------------
# 6. Extract results
# --------------------------------------------------

dates = ts.aggregate_array("date").getInfo()
ndvi_values = ts.aggregate_array("mean_ndvi").getInfo()


# --------------------------------------------------
# 7. Create dataframe
# --------------------------------------------------

df = pd.DataFrame({
    "plot_id": PLOT_ID,
    "site": SITE_NAME,
    "date": dates,
    "ndvi": ndvi_values
})


# Remove images where NDVI could not be calculated
df = df.dropna(subset=["ndvi"])


# Sort chronologically
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")


# --------------------------------------------------
# 8. Save
# --------------------------------------------------

output_path = "data/ndvi_timeseries.csv"

df.to_csv(output_path, index=False)


print("\nNDVI extraction complete!")
print("Rows:", len(df))
print("Saved to:", output_path)

print("\nFirst 10 observations:")
print(df.head(10))

print("\nNDVI statistics:")
print(df["ndvi"].describe())