import rasterio

file_path = "data/Mangrove_agb_India.tif"

with rasterio.open(file_path) as src:

    print("CRS:", src.crs)
    print("Width:", src.width)
    print("Height:", src.height)
    print("Bands:", src.count)

    print("Resolution:", src.res)

    print("Bounds:")
    print(src.bounds)

    print("NoData:", src.nodata)

    print("Data type:", src.dtypes[0])
    from config import PLOT_BOUNDS

    print("\nPichavaram plot:")
    print(PLOT_BOUNDS)