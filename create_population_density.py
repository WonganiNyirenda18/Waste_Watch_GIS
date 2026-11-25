
import rasterio
import numpy as np
from pathlib import Path

DATA_FOLDER = Path("../data/population")

source_file = DATA_FOLDER / "Lilongwe_Population_Sum_UTM.tif"
output_file = DATA_FOLDER / "Lilongwe_Population_Density.tif"

with rasterio.open(source_file) as src:

    population = src.read(1)

    # Calculate the actual area of one raster cell in square metres
    transform = src.transform

    pixel_area_m2 = abs(
        transform.a * transform.e -
        transform.b * transform.d
    )

    # Convert square metres into square kilometres
    pixel_area_km2 = pixel_area_m2 / 1_000_000

    # Identify valid population cells
    valid = (
        np.isfinite(population) &
        (population != src.nodata)
    )

    # Calculate people per square kilometre
    density = np.full(
        population.shape,
        -99999.0,
        dtype=np.float32
    )

    density[valid] = (
        population[valid] / pixel_area_km2
    )

    # Save the density raster
    profile = src.profile.copy()

    profile.update(
        dtype="float32",
        nodata=-99999.0,
        compress="lzw"
    )

    with rasterio.open(output_file, "w", **profile) as dst:
        dst.write(density, 1)

    print("POPULATION DENSITY CREATED")
    print("Output:", output_file)
    print("Cell area (km²):", pixel_area_km2)
    print("Valid pixels:", np.count_nonzero(valid))
    print("Minimum density:", float(np.min(density[valid])))
    print("Maximum density:", float(np.max(density[valid])))

print("Done!")
