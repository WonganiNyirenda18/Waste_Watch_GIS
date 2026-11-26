
import os
import numpy as np
import rasterio
import psycopg
from rasterio.features import rasterize
from shapely import wkb
from shapely import make_valid

from database import get_db_connection

# ==========================================
# WASTEWATCH GIS
# EXISTING DISPOSAL SITE EXCLUSION MASK
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

REFERENCE_RASTER = os.path.join(
    DATA_DIR,
    "population",
    "Lilongwe_Population_Suitability.tif"
)

OUTPUT_DIR = os.path.join(DATA_DIR, "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "Lilongwe_Exclusion_Mask.tif"
)

BUFFER_DISTANCE = 500  # metres - project assumption

NODATA = 255


def get_existing_sites():

    print("\nRetrieving existing disposal sites from PostGIS...")

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT
                    site_name,
                    site_status,
                    ST_AsBinary(geom)
                FROM public.existing_disposal_sites
                WHERE geom IS NOT NULL
            """)

            rows = cursor.fetchall()

    finally:
        connection.close()

    print(f"Existing disposal-site geometries: {len(rows)}")

    return rows


def main():

    print("======================================")
    print("WASTEWATCH GIS")
    print("EXCLUSION MASK GENERATION")
    print("======================================")

    # Load reference raster
    print("\nLoading reference raster...")

    with rasterio.open(REFERENCE_RASTER) as src:

        reference = src.read(1)

        profile = src.profile.copy()

        transform = src.transform

        height = src.height
        width = src.width

        nodata = src.nodata

        valid_area = np.isfinite(reference)

        if nodata is not None:
            valid_area &= reference != nodata

        print(f"Raster dimensions: {width} x {height}")
        print(f"CRS: {src.crs}")
        print(f"Valid analysis cells: {np.count_nonzero(valid_area)}")

    # Retrieve existing disposal sites
    rows = get_existing_sites()

    exclusion_geometries = []

    print("\nPreparing exclusion geometries...")

    for site_name, site_status, geometry_bytes in rows:

        if geometry_bytes is None:
            continue

        # Only confirmed sites are used for exclusion.
        # Review status vocabulary before inserting records.
        if str(site_status).strip().lower() not in (
            "operational",
            "active",
            "confirmed"
        ):
            print(
                f"Skipping unconfirmed site: {site_name} "
                f"(status: {site_status})"
            )
            continue

        geometry = wkb.loads(bytes(geometry_bytes))

        if geometry.is_empty:
            continue

        if not geometry.is_valid:
            geometry = make_valid(geometry)

        if geometry.is_empty:
            continue

        # Buffer in projected CRS, so units are metres.
        buffered_geometry = geometry.buffer(BUFFER_DISTANCE)

        exclusion_geometries.append(buffered_geometry)

        print(f"Prepared exclusion for: {site_name}")

    print(f"\nConfirmed exclusion geometries: {len(exclusion_geometries)}")

    # Rasterize exclusion zones
    print("\nRasterizing exclusion zones...")

    exclusion_mask = np.zeros(
        (height, width),
        dtype=np.uint8
    )

    if exclusion_geometries:

        exclusion_mask = rasterize(
            [(geom, 1) for geom in exclusion_geometries],
            out_shape=(height, width),
            transform=transform,
            fill=0,
            dtype=np.uint8,
            all_touched=True
        )

    # Excluded cells = 1
    # Eligible cells = 0
    # Outside analysis area = NoData
    exclusion_mask[~valid_area] = NODATA

    eligible = valid_area & (exclusion_mask == 0)
    excluded = valid_area & (exclusion_mask == 1)

    print("\nSaving exclusion mask...")

    profile.update(
        driver="GTiff",
        count=1,
        dtype="uint8",
        nodata=NODATA,
        compress="lzw"
    )

    with rasterio.open(OUTPUT_FILE, "w", **profile) as dst:
        dst.write(exclusion_mask, 1)

    print("\n======================================")
    print("EXCLUSION MASK COMPLETED")
    print("======================================")

    print(f"Buffer distance: {BUFFER_DISTANCE} metres")
    print(f"Excluded cells: {np.count_nonzero(excluded)}")
    print(f"Eligible cells: {np.count_nonzero(eligible)}")
    print(f"Total valid cells: {np.count_nonzero(valid_area)}")

    print("\nOutput file:")
    print(OUTPUT_FILE)

    if not rows:
        print(
            "\nNOTE: No disposal-site records exist yet. "
            "All valid cells remain eligible. "
            "This does not establish that Lilongwe has no "
            "existing disposal sites."
        )


if __name__ == "__main__":
    main()
