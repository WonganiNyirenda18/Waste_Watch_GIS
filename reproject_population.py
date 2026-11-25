
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pathlib import Path
import numpy as np

DATA_FOLDER = Path("../data/population")

source_file = DATA_FOLDER / "Lilongwe_Population_Clipped.tif"
output_file = DATA_FOLDER / "Lilongwe_Population_Sum_UTM.tif"

with rasterio.open(source_file) as src:

    # Calculate the projected raster dimensions
    transform, width, height = calculate_default_transform(
        src.crs,
        "EPSG:32736",
        src.width,
        src.height,
        *src.bounds
    )

    profile = src.profile.copy()
    profile.update(
        crs="EPSG:32736",
        transform=transform,
        width=width,
        height=height,
        dtype="float32",
        nodata=-99999.0,
        compress="lzw"
    )

    with rasterio.open(output_file, "w", **profile) as dst:

        reproject(
            source=rasterio.band(src, 1),
            destination=rasterio.band(dst, 1),
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=transform,
            dst_crs="EPSG:32736",
            dst_nodata=-99999.0,
            resampling=Resampling.sum
        )

print("Population reprojection completed!")
print("Output:", output_file)
print("Dimensions:", width, "x", height)
