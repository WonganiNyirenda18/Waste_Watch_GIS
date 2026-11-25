
import os
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from shapely import wkb

from database import get_db_connection


# --------------------------------------------------
# 1. FILE PATHS
# --------------------------------------------------

REFERENCE_RASTER = "../data/population/Lilongwe_Population_Suitability.tif"

OUTPUT_FOLDER = "../data/roads"
DISTANCE_OUTPUT = os.path.join(
    OUTPUT_FOLDER, "Lilongwe_Road_Distance.tif"
)
SUITABILITY_OUTPUT = os.path.join(
    OUTPUT_FOLDER, "Lilongwe_Road_Suitability.tif"
)


# --------------------------------------------------
# 2. SCORING FUNCTION
# --------------------------------------------------

def calculate_road_score(distance):
    """
    Score road accessibility from 0 to 100.

    0 m       = 70
    100-500 m = 100
    1000 m    = approximately 66.67
    1500 m    = approximately 33.33
    2000+ m   = 0
    """

    if distance < 100:
        return 70 + (distance / 100) * 30

    elif distance <= 500:
        return 100

    elif distance < 2000:
        return 100 * (2000 - distance) / 1500

    else:
        return 0


# --------------------------------------------------
# 3. LOAD REFERENCE RASTER
# --------------------------------------------------

print("Loading reference population raster...")

with rasterio.open(REFERENCE_RASTER) as src:
    reference_data = src.read(1)
    profile = src.profile.copy()
    transform = src.transform
    crs = src.crs
    nodata = src.nodata

height, width = reference_data.shape

valid_mask = (
    np.isfinite(reference_data)
    & (reference_data != nodata)
)

pixel_width = abs(transform.a)
pixel_height = abs(transform.e)

print("Raster dimensions:", width, "x", height)
print("CRS:", crs)
print("Pixel width:", pixel_width)
print("Pixel height:", pixel_height)
print("Valid cells:", np.count_nonzero(valid_mask))


# --------------------------------------------------
# 4. RETRIEVE ROADS FROM POSTGIS
# --------------------------------------------------

print("\nRetrieving accessible roads from PostGIS...")

connection = get_db_connection()

try:
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT ST_AsBinary(geom)
            FROM public.accessible_roads
            WHERE geom IS NOT NULL;
        """)

        road_rows = cursor.fetchall()

finally:
    connection.close()

road_geometries = [
    wkb.loads(bytes(row[0]))
    for row in road_rows
]

print("Road features retrieved:", len(road_geometries))

if not road_geometries:
    raise ValueError("No road geometries were retrieved.")


# --------------------------------------------------
# 5. RASTERIZE ROAD FEATURES
# --------------------------------------------------

print("\nRasterizing road network...")

road_mask = rasterize(
    [(geometry, 1) for geometry in road_geometries],
    out_shape=(height, width),
    transform=transform,
    fill=0,
    all_touched=True,
    dtype="uint8"
)

road_cells = np.count_nonzero(road_mask)

print("Raster cells touched by roads:", road_cells)

if road_cells == 0:
    raise ValueError(
        "No roads intersect the reference raster. "
        "Check the coordinate systems and study area."
    )


# --------------------------------------------------
# 6. CALCULATE DISTANCE TO NEAREST ROAD
# --------------------------------------------------

print("\nCalculating distance to nearest accessible road...")

distance_array = distance_transform_edt(
    road_mask == 0,
    sampling=(pixel_height, pixel_width)
)

distance_array = distance_array.astype("float32")

print("Minimum distance:", np.min(distance_array))
print("Maximum distance:", np.max(distance_array))


//add after this line
valid_distances = distance_array[valid_mask]

print("Maximum distance inside study area:",
      np.max(valid_distances))

print("Cells at least 2000m from roads:",
      np.count_nonzero(valid_distances >= 2000))

//valid scores
print("Score percentiles:",
      np.percentile(valid_scores, [0, 25, 50, 75, 100]))


# --------------------------------------------------
# 7. CALCULATE ROAD SUITABILITY
# --------------------------------------------------

print("\nCalculating road suitability scores...")

suitability = np.full(
    (height, width),
    nodata,
    dtype="float32"
)

for row in range(height):
    for col in range(width):

        if valid_mask[row, col]:

            distance = distance_array[row, col]

            suitability[row, col] = calculate_road_score(
                distance
            )


# --------------------------------------------------
# 8. SAVE OUTPUT RASTERS
# --------------------------------------------------

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

output_profile = profile.copy()
output_profile.update(
    dtype="float32",
    count=1,
    compress="lzw",
    nodata=nodata
)

print("\nSaving road distance raster...")

with rasterio.open(
    DISTANCE_OUTPUT, "w", **output_profile
) as dst:
    dst.write(distance_array, 1)

print("Saving road suitability raster...")

with rasterio.open(
    SUITABILITY_OUTPUT, "w", **output_profile
) as dst:
    dst.write(suitability, 1)


# --------------------------------------------------
# 9. REPORT RESULTS
# --------------------------------------------------

valid_scores = suitability[valid_mask]

print("\n====================================")
print("ROAD SUITABILITY ANALYSIS COMPLETE")
print("====================================")

print("Road features:", len(road_geometries))
print("Road raster cells:", road_cells)
print("Valid analysis cells:", len(valid_scores))

print("Minimum suitability:", np.min(valid_scores))
print("Maximum suitability:", np.max(valid_scores))
print("Mean suitability:", np.mean(valid_scores))

print("\nOutputs:")
print(DISTANCE_OUTPUT)
print(SUITABILITY_OUTPUT)

