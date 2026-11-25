
import rasterio
import numpy as np
from pathlib import Path

from population_scoring import calculate_population_score

DATA_FOLDER = Path("../data/population")

source_file = DATA_FOLDER / "Lilongwe_Population_Density.tif"

output_file = DATA_FOLDER / "Lilongwe_Population_Suitability.tif"

with rasterio.open(source_file) as src:

    density = src.read(1)

    valid = (
        np.isfinite(density) &
        (density != src.nodata)
    )

    suitability = np.full(
        density.shape,
        -99999.0,
        dtype=np.float32
    )

    # Apply the scoring function to every valid cell
    suitability[valid] = np.interp(
        density[valid],
        [0, 500, 5000],
        [100, 100, 0]
    )

    profile = src.profile.copy()

    profile.update(
        dtype="float32",
        nodata=-99999.0,
        compress="lzw"
    )

    with rasterio.open(output_file, "w", **profile) as dst:
        dst.write(suitability, 1)

    scores = suitability[valid]

    print("POPULATION SUITABILITY RASTER CREATED")
    print("Output:", output_file)
    print("Valid cells:", len(scores))
    print("Minimum score:", float(scores.min()))
    print("Maximum score:", float(scores.max()))
    print("Mean score:", float(scores.mean()))

print("Done!")
