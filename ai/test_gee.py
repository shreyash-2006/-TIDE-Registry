import ee
from config import PLOT_BOUNDS

# Authenticate only the first time
ee.Authenticate()

# Replace with your Google Cloud / Earth Engine project ID
ee.Initialize(project="sihinternals")

plot = ee.Geometry.Rectangle([
    79.760,
    11.400,
    79.810,
    11.450
])

print("Earth Engine initialized successfully!")
print("Plot:", plot.getInfo())