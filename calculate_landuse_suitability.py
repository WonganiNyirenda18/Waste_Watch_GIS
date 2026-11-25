
import os
import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely import wkb

from database import get_db_connection


# --------------------------------------------------
# 1. FILE PATHS
# --------------------------------------------------

REFERENCE_RASTER = (
    "../data/population/"
    "Lilongwe_Population_Suitability.tif"
)

OUTPUT_FOLDER = "../data/landuse"

OUTPUT_RASTER = os.path.join(
    OUTPUT_FOLDER,
    "Lilongwe_Landuse_Suitability.tif"
)


# --------------------------------------------------
# 2. LAND-USE SCORING RULES
# --------------------------------------------------

LANDUSE_SCORES = {
    "residential": 0,
    "park": 0,
    "cemetery": 0,
    "military": 0,

    "forest": 20,

    "farmland": 30,
    "orchard": 30,

    "commercial": 40,
    "retail": 40,
    "farmyard": 40,

    "industrial": 80,
    "quarry": 80,

    "scrub": 90,
    "grass": 90,
    "meadow": 90
}


# --------------------------------------------------
# 3. LOAD REFERENCE RASTER
# --------------------------------------------------

print("Loading reference population raster...")

with rasterio.open(REFERENCE_RASTER) as src:

    reference_data = src.read(1)

    profile = src.profile.copy()

    transform = src.transform

    nodata = src.nodata

    crs = src.crs


height, width = reference_data.shape

valid_mask = (
    np.isfinite(reference_data)
    & (reference_data != nodata)
)

print("Raster dimensions:", width, "x", height)
print("CRS:", crs)
print("Valid analysis cells:", np.count_nonzero(valid_mask))


# --------------------------------------------------
# 4. RETRIEVE LAND-USE FEATURES FROM POSTGIS
# --------------------------------------------------

print("\nRetrieving land-use features from PostGIS...")

connection = get_db_connection()

try:

    with connection.cursor() as cursor:

        cursor.execute("""
            SELECT
                fclass,
                ST_AsBinary(geom)
            FROM public.landuse_source
            WHERE geom IS NOT NULL;
        """)

        landuse_rows = cursor.fetchall()

finally:

    connection.close()


print("Land-use features retrieved:", len(landuse_rows))


# --------------------------------------------------
# 5. CONVERT FEATURES INTO SCORED GEOMETRIES
# --------------------------------------------------

print("\nAssigning land-use suitability scores...")

scored_features = []

category_counts = {}

for fclass, geometry_data in landuse_rows:

    category = fclass.lower().strip()

    if category not in LANDUSE_SCORES:

        raise ValueError(
            f"No suitability score defined for: {category}"
        )

    score = LANDUSE_SCORES[category]

    geometry = wkb.loads(bytes(geometry_data))

    if geometry.is_empty:

        continue

    scored_features.append((geometry, score))

    category_counts[category] = (
        category_counts.get(category, 0) + 1
    )


print("\nLand-use categories and scores:")

for category, count in sorted(category_counts.items()):

    print(
        f"{category}: {count} features, "
        f"score {LANDUSE_SCORES[category]}"
    )


# --------------------------------------------------
# 6. PREPARE OVERLAPPING POLYGONS
# --------------------------------------------------

# When polygons overlap, apply the lower score last.
# This gives a conservative result where mapped
# land-use categories overlap.

scored_features.sort(
    key=lambda feature: feature[1],
    reverse=True
)


# --------------------------------------------------
# 7. RASTERIZE LAND-USE FEATURES
# --------------------------------------------------

print("\nRasterizing land-use polygons...")

landuse_raster = rasterize(
    scored_features,

    out_shape=(height, width),

    transform=transform,

    fill=nodata,

    dtype="float32",

    all_touched=False
)


# --------------------------------------------------
# 8. APPLY VALID ANALYSIS AREA
# --------------------------------------------------

landuse_raster[~valid_mask] = nodata

mapped_mask = (
    valid_mask
    & (landuse_raster != nodata)
)

unmapped_mask = (
    valid_mask
    & (landuse_raster == nodata)
)

mapped_cells = np.count_nonzero(mapped_mask)

unmapped_cells = np.count_nonzero(unmapped_mask)

total_valid_cells = np.count_nonzero(valid_mask)

coverage_percentage = (
    mapped_cells / total_valid_cells
) * 100


# --------------------------------------------------
# 9. SAVE LAND-USE SUITABILITY RASTER
# --------------------------------------------------

print("\nSaving land-use suitability raster...")

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

output_profile = profile.copy()

output_profile.update(
    dtype="float32",
    count=1,
    compress="lzw",
    nodata=nodata
)


with rasterio.open(
    OUTPUT_RASTER,
    "w",
    **output_profile
) as dst:

    dst.write(landuse_raster, 1)


# --------------------------------------------------
# 10. REPORT RESULTS
# --------------------------------------------------

print("\n====================================")

print("LAND-USE SUITABILITY ANALYSIS COMPLETE")

print("====================================")

print("Total land-use features:", len(landuse_rows))

print("Valid analysis cells:", total_valid_cells)

print("Mapped land-use cells:", mapped_cells)

print("Unmapped analysis cells:", unmapped_cells)

print(
    "Land-use coverage:",
    round(coverage_percentage, 2),
    "%"
)

print("\nSuitability score statistics:")

if mapped_cells > 0:

    valid_scores = landuse_raster[mapped_mask]

    print("Minimum score:", np.min(valid_scores))

    print("Maximum score:", np.max(valid_scores))

    print("Mean score:", np.mean(valid_scores))

    print(
        "Score categories:",
        np.unique(valid_scores, return_counts=True)
    )

else:

    print("No land-use polygons overlap the valid analysis area.")


print("\nOutput file:")

print(OUTPUT_RASTER)

print("\nAnalysis completed successfully!")
