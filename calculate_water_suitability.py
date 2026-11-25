
import os
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from shapely import wkb

from database import get_db_connection


# ---------------------------------------
# 1. FILE PATHS AND SETTINGS
# ---------------------------------------

REFERENCE_RASTER = (
    "../data/population/Lilongwe_Population_Suitability.tif"
)

OUTPUT_FOLDER = "../data/water"

DISTANCE_OUTPUT = os.path.join(
    OUTPUT_FOLDER,
    "Lilongwe_Water_Distance.tif"
)

SUITABILITY_OUTPUT = os.path.join(
    OUTPUT_FOLDER,
    "Lilongwe_Water_Suitability.tif"
)

# Illustrative project threshold, in metres
PREFERRED_DISTANCE = 500.0

NODATA = -99999.0


# ---------------------------------------
# 2. RETRIEVE WATER GEOMETRIES
# ---------------------------------------

def get_water_geometries():

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT ST_AsBinary(geom)
                FROM public.water_features
                WHERE geom IS NOT NULL;
            """)

            rows = cursor.fetchall()

        geometries = [
            wkb.loads(bytes(row[0]))
            for row in rows
        ]

        print("Water features retrieved:", len(geometries))

        return geometries

    finally:
        connection.close()


# ---------------------------------------
# 3. RASTERIZE WATER FEATURES
# ---------------------------------------

def calculate_water_suitability():

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    geometries = get_water_geometries()

    if not geometries:
        raise ValueError("No water geometries were retrieved.")

    with rasterio.open(REFERENCE_RASTER) as reference:

        transform = reference.transform
        width = reference.width
        height = reference.height

        reference_data = reference.read(1)

        valid_mask = reference_data != reference.nodata

        print("\nReference grid:", width, "x", height)
        print("Valid population cells:", np.count_nonzero(valid_mask))

        # Burn water features into the reference grid
        water_mask = rasterize(
            [(geometry, 1) for geometry in geometries],
            out_shape=(height, width),
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=True
        )

        water_cells = np.count_nonzero(water_mask)

        if water_cells == 0:
            raise ValueError(
                "No water features overlap the reference raster."
            )

        print("Raster cells containing water:", water_cells)

        # ---------------------------------------
        # 4. CALCULATE DISTANCE TO NEAREST WATER
        # ---------------------------------------

        pixel_width = abs(transform.a)
        pixel_height = abs(transform.e)

        distance = distance_transform_edt(
            water_mask == 0,
            sampling=(pixel_height, pixel_width)
        )

        # ---------------------------------------
        # 5. CONVERT DISTANCE TO SUITABILITY SCORE
        # ---------------------------------------

        suitability = np.clip(
            (distance / PREFERRED_DISTANCE) * 100,
            0,
            100
        )

        # Preserve areas without population data
        distance = distance.astype("float32")
        suitability = suitability.astype("float32")

        distance[~valid_mask] = NODATA
        suitability[~valid_mask] = NODATA

        # ---------------------------------------
        # 6. SAVE OUTPUT RASTERS
        # ---------------------------------------

        output_profile = reference.profile.copy()

        output_profile.update(
            dtype="float32",
            count=1,
            nodata=NODATA,
            compress="lzw"
        )

        with rasterio.open(
            DISTANCE_OUTPUT,
            "w",
            **output_profile
        ) as destination:

            destination.write(distance, 1)

        with rasterio.open(
            SUITABILITY_OUTPUT,
            "w",
            **output_profile
        ) as destination:

            destination.write(suitability, 1)

        # ---------------------------------------
        # 7. DISPLAY RESULTS
        # ---------------------------------------

        valid_scores = suitability[valid_mask]

        print("\nWATER SUITABILITY CALCULATION COMPLETE")
        print("---------------------------------------")
        print("Valid cells:", len(valid_scores))
        print("Minimum score:", float(valid_scores.min()))
        print("Maximum score:", float(valid_scores.max()))
        print("Mean score:", float(valid_scores.mean()))

        print("\nDistance raster:", DISTANCE_OUTPUT)
        print("Suitability raster:", SUITABILITY_OUTPUT)


if __name__ == "__main__":
    calculate_water_suitability()
