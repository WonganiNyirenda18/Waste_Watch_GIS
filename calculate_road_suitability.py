
import os
import numpy as np
import rasterio
from shapely import wkb, STRtree
from shapely.geometry import Point

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
# 2. SUITABILITY SCORING FUNCTION
# --------------------------------------------------

def calculate_road_score(distance):

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
    nodata = src.nodata

height, width = reference_data.shape

valid_mask = (
    np.isfinite(reference_data)
    & (reference_data != nodata)
)

print("Raster dimensions:", width, "x", height)
print("CRS:", profile["crs"])
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

road_geometries = [
    geom for geom in road_geometries
    if not geom.is_empty
]

print("Road features retrieved:", len(road_geometries))

if not road_geometries:
    raise ValueError("No valid road geometries retrieved.")


# --------------------------------------------------
# 5. BUILD SPATIAL INDEX
# --------------------------------------------------

print("\nBuilding road spatial index...")

road_tree = STRtree(road_geometries)

print("Spatial index created successfully.")


# --------------------------------------------------
# 6. CALCULATE DISTANCE FROM CELL CENTRES
# --------------------------------------------------

print("\nCalculating distance to nearest actual road...")

distance_array = np.full(
    (height, width),
    nodata,
    dtype="float32"
)

valid_positions = np.argwhere(valid_mask)

total_cells = len(valid_positions)

for index, (row, col) in enumerate(valid_positions):

    # Find the centre of the raster cell
    x, y = transform * (col + 0.5, row + 0.5)

    point = Point(x, y)

    # Find nearest actual road geometry
    nearest_index = road_tree.nearest(point)

    nearest_road = road_geometries[int(nearest_index)]

    # Calculate actual distance in metres
    distance = point.distance(nearest_road)

    distance_array[row, col] = distance

    if (index + 1) % 5000 == 0:
        print(
            f"Processed {index + 1:,} "
            f"of {total_cells:,} cells..."
        )


# --------------------------------------------------
# 7. REPORT DISTANCE STATISTICS
# --------------------------------------------------

valid_distances = distance_array[valid_mask]

print("\nDistance statistics:")

print("Minimum distance:", np.min(valid_distances))

print("Maximum distance:", np.max(valid_distances))

print("Mean distance:", np.mean(valid_distances))

print(
    "Cells at least 2000m from roads:",
    np.count_nonzero(valid_distances >= 2000)
)


# --------------------------------------------------
# 8. CALCULATE ROAD SUITABILITY
# --------------------------------------------------

print("\nCalculating road suitability scores...")

suitability = np.full(
    (height, width),
    nodata,
    dtype="float32"
)

for row, col in valid_positions:

    distance = distance_array[row, col]

    suitability[row, col] = calculate_road_score(
        distance
    )


valid_scores = suitability[valid_mask]


# --------------------------------------------------
# 9. SAVE OUTPUT RASTERS
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
# 10. REPORT FINAL RESULTS
# --------------------------------------------------

print("\nScore percentiles:")

print(
    np.percentile(
        valid_scores,
        [0, 25, 50, 75, 100]
    )
)

print("\n====================================")
print("ROAD SUITABILITY ANALYSIS COMPLETE")
print("====================================")

print("Road features:", len(road_geometries))

print("Valid analysis cells:", len(valid_scores))

print("Minimum suitability:", np.min(valid_scores))

print("Maximum suitability:", np.max(valid_scores))

print("Mean suitability:", np.mean(valid_scores))

print("\nOutputs:")
print(DISTANCE_OUTPUT)
print(SUITABILITY_OUTPUT)

print("\nAnalysis completed successfully!")
