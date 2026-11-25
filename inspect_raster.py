
import rasterio

raster_path = "../data/population/Lilongwe_Population_Suitability.tif"

with rasterio.open(raster_path) as src:
    print("WASTEWATCH - REFERENCE RASTER INFORMATION")
    print("------------------------------------------")

    print("CRS:", src.crs)
    print("Resolution:", src.res)
    print("Width:", src.width)
    print("Height:", src.height)
    print("Bounds:", src.bounds)
    print("NoData:", src.nodata)
    print("Number of bands:", src.count)
    print("Data type:", src.dtypes)
