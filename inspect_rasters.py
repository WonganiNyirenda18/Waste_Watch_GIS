
import rasterio
from pathlib import Path

DATA_FOLDER = Path("../data/population")

files = [
    "mwi_pop_2025_CN_100m_R2024B_v1.tif",
    "Lilongwe_Density.tif"
]

for filename in files:
    filepath = DATA_FOLDER / filename

    print("\n" + "=" * 50)
    print(f"FILE: {filename}")
    print("=" * 50)

    with rasterio.open(filepath) as raster:
        print("CRS:", raster.crs)
        print("Width:", raster.width)
        print("Height:", raster.height)
        print("Bands:", raster.count)
        print("Resolution:", raster.res)
        print("NoData:", raster.nodata)
        print("Bounds:", raster.bounds)

        values = raster.read(1, masked=True)

        print("Minimum:", values.min())
        print("Maximum:", values.max())
