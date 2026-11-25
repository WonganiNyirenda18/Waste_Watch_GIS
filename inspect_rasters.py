import rasterio
import numpy as np
from pathlib import Path

DATA_FOLDER = Path("../data/population")

original_file = DATA_FOLDER / "Lilongwe_Population_Clipped.tif"
reprojected_file = DATA_FOLDER / "Lilongwe_Population_Sum_UTM.tif"

def inspect_population(file_path):
    with rasterio.open(file_path) as src:
        data = src.read(1, masked=True)

        total = float(data.sum(dtype=np.float64))
        valid_pixels = int(data.count())

        print(f"\nFILE: {file_path.name}")
        print("CRS:", src.crs)
        print("Dimensions:", src.width, "x", src.height)
        print("Resolution:", src.res)
        print("Valid pixels:", valid_pixels)
        print("Minimum:", float(data.min()))
        print("Maximum:", float(data.max()))
        print("Population total:", total)

        return total

original_total = inspect_population(original_file)
new_total = inspect_population(reprojected_file)

difference = new_total - original_total
percentage_difference = abs(difference) / original_total * 100

print("\n--- POPULATION PRESERVATION CHECK ---")
print("Original total:", original_total)
print("Reprojected total:", new_total)
print("Difference:", difference)
print("Percentage difference:", percentage_difference, "%")