
import os
import numpy as np
import rasterio

from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from shapely import wkb

from database import get_db_connection


# ---------------------------------------
# 1. SETTINGS
# ---------------------------------------

REFERENCE_RASTER = (
    "../data/population/Lilongwe_Population_Suitability.tif"
)

OUTPUT_FOLDER = "../data/residential"

DISTANCE_OUTPUT = os.path.join(
    OUTPUT_FOLDER,
    "Lilongwe_Residential_Distance.tif"
)

SUITABILITY_OUTPUT = os.path.join(
    OUTPUT_FOLDER,
    "Lilongwe_Residential_Suitability.tif"
)

# Illustrative project assumption, in metres
PREFERRED_DISTANCE = 1000.0

NODATA = -99999.0
BATCH_SIZE = 5000


# ---------------------------------------
# 2. RASTERIZE BUILDINGS IN BATCHES
# ---------------------------------------

def rasterize_buildings(
    width,
    height,
    transform
):

    building_mask = np.zeros(
        (height, width),
        dtype="uint8"
    )

    connection = get_db_connection()

    total_processed = 0

    try:
        # Named cursor retrieves records in batches
        with connection.cursor(
            name="building_cursor"
        ) as cursor:

            cursor.execute("""
                SELECT ST_AsBinary(geom)
                FROM public.residential_buildings
                WHERE geom IS NOT NULL;
            """)

            while True:

                rows = cursor.fetchmany(BATCH_SIZE)

                if not rows:
                    break

                shapes = []

                for row in rows:

                    geometry = wkb.loads(
                        bytes(row[0])
                    )

                    if not geometry.is_empty:
                        shapes.append((geometry, 1))

                if shapes:

                    batch_mask = rasterize(
                        shapes,
                        out_shape=(height, width),
                        transform=transform,
                        fill=0,
                        dtype="uint8",
                        all_touched=True
                    )

                    building_mask = np.maximum(
                        building_mask,
                        batch_mask
                    )

                total_processed += len(rows)

                print(
                    "Buildings processed:",
                    total_processed
                )

    finally:
        connection.close()

    return building_mask


# ---------------------------------------
# 3. CALCULATE RESIDENTIAL SUITABILITY
# ---------------------------------------

def calculate_residential_suitability():

    os.makedirs(
        OUTPUT_FOLDER,
        exist_ok=True
    )

    with rasterio.open(
        REFERENCE_RASTER
    ) as reference:

        transform = reference.transform

        width = reference.width
        height = reference.height

        reference_data = reference.read(1)

        valid_mask = (
            reference_data != reference.nodata
        )

        print("Reference grid:", width, "x", height)

        print(
            "Valid population cells:",
            np.count_nonzero(valid_mask)
        )

        # Rasterize all building footprints
        building_mask = rasterize_buildings(
            width,
            height,
            transform
        )

        building_cells = np.count_nonzero(
            building_mask
        )

        if building_cells == 0:
            raise ValueError(
                "No buildings overlap the reference raster."
            )

        print(
            "Raster cells containing buildings:",
            building_cells
        )

        # ---------------------------------------
        # 4. CALCULATE DISTANCE
        # ---------------------------------------

        pixel_width = abs(transform.a)
        pixel_height = abs(transform.e)

        distance = distance_transform_edt(
            building_mask == 0,
            sampling=(
                pixel_height,
                pixel_width
            )
        )

        # ---------------------------------------
        # 5. CALCULATE SUITABILITY SCORE
        # ---------------------------------------

        suitability = np.clip(
            (
                distance /
                PREFERRED_DISTANCE
            ) * 100,
            0,
            100
        )

        distance = distance.astype("float32")
        suitability = suitability.astype("float32")

        # Preserve NoData areas
        distance[~valid_mask] = NODATA
        suitability[~valid_mask] = NODATA

        # ---------------------------------------
        # 6. SAVE OUTPUTS
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

        print("\nRESIDENTIAL SUITABILITY COMPLETE")
        print("--------------------------------")

        print(
            "Valid cells:",
            len(valid_scores)
        )

        print(
            "Minimum score:",
            float(valid_scores.min())
        )

        print(
            "Maximum score:",
            float(valid_scores.max())
        )

        print(
            "Mean score:",
            float(valid_scores.mean())
        )

        print("\nDistance raster:", DISTANCE_OUTPUT)

        print(
            "Suitability raster:",
            SUITABILITY_OUTPUT
        )


if __name__ == "__main__":
    calculate_residential_suitability()
