
import rasterio
import numpy as np
from pathlib import Path

raster_file = Path("../data/population/Lilongwe_Population_Density.tif")

with rasterio.open(raster_file) as src:
    density = src.read(1)

    valid = (
        np.isfinite(density) &
        (density != src.nodata)
    )

    values = density[valid]

    print("POPULATION DENSITY RASTER")
    print("-------------------------")
    print("CRS:", src.crs)
    print("Dimensions:", src.width, "x", src.height)
    print("Resolution:", src.res)
    print("Valid cells:", len(values))
    print("Minimum:", float(values.min()))
    print("Maximum:", float(values.max()))
    print("Mean:", float(values.mean()))

    print("\nQUANTILE CLASS CHECK")
    print("-------------------------")
    print("25th percentile:", float(np.percentile(values, 25)))
    print("50th percentile:", float(np.percentile(values, 50)))
    print("75th percentile:", float(np.percentile(values, 75)))
