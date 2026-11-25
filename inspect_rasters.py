
import rasterio
from pathlib import Path

DATA_FOLDER = Path("../data/population")

filename = "Lilongwe_Population_Clipped.tif"
filepath = DATA_FOLDER / filename

with rasterio.open(filepath) as raster:
    population = raster.read(1, masked=True)

    print("WORLDPOP - LILONGWE VALIDATION")
    print("--------------------------------")
    print("CRS:", raster.crs)
    print("Width:", raster.width)
    print("Height:", raster.height)
    print("Resolution:", raster.res)
    print("NoData:", raster.nodata)
    print("Valid pixels:", population.count())
    print("Minimum population:", population.min())
    print("Maximum population:", population.max())

    total_population = float(population.sum())

    print("--------------------------------")
    print("Estimated population total:", total_population)
