
import os
import numpy as np
import rasterio

# ==========================================
# WASTEWATCH GIS - WEIGHTED OVERLAY ANALYSIS
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

RASTERS = {
    "water": os.path.join(
        DATA_DIR, "water", "Lilongwe_Water_Suitability.tif"
    ),
    "residential": os.path.join(
        DATA_DIR, "residential",
        "Lilongwe_Residential_Suitability.tif"
    ),
    "roads": os.path.join(
        DATA_DIR, "roads", "Lilongwe_Road_Suitability.tif"
    ),
    "population": os.path.join(
        DATA_DIR, "population",
        "Lilongwe_Population_Suitability.tif"
    ),
    "landuse": os.path.join(
        DATA_DIR, "landuse", "Lilongwe_Landuse_Suitability.tif"
    )
}

# ==========================================
# WEIGHTING PROFILES
# ==========================================

PROFILES = {
    "balanced": {
        "water": 30,
        "residential": 25,
        "roads": 15,
        "population": 15,
        "landuse": 15
    },
    "environmental": {
        "water": 35,
        "residential": 30,
        "roads": 10,
        "population": 10,
        "landuse": 15
    },
    "accessibility": {
        "water": 20,
        "residential": 20,
        "roads": 30,
        "population": 15,
        "landuse": 15
    }
}

# Select the default profile
SELECTED_PROFILE = "balanced"

OUTPUT_DIR = os.path.join(DATA_DIR, "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    f"Lilongwe_{SELECTED_PROFILE.title()}_Suitability.tif"
)

NODATA = -9999.0


def load_rasters():
    arrays = {}
    reference_profile = None
    reference_shape = None

    print("Loading suitability rasters...")

    for name, path in RASTERS.items():

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Raster not found: {path}"
            )

        with rasterio.open(path) as src:

            array = src.read(1).astype(np.float32)

            if reference_profile is None:
                reference_profile = src.profile.copy()
                reference_shape = array.shape

            else:
                if array.shape != reference_shape:
                    raise ValueError(
                        f"{name} raster has a different shape."
                    )

                if src.transform != reference_profile["transform"]:
                    raise ValueError(
                        f"{name} raster has a different grid transform."
                    )

                if src.crs != reference_profile["crs"]:
                    raise ValueError(
                        f"{name} raster has a different CRS."
                    )

            nodata = src.nodata

            valid = np.isfinite(array)

            if nodata is not None:
                valid &= array != nodata

            arrays[name] = {
                "data": array,
                "valid": valid
            }

            print(
                f"{name}: {np.count_nonzero(valid)} valid cells"
            )

    return arrays, reference_profile


def calculate_weighted_overlay(arrays, weights):

    if sum(weights.values()) != 100:
        raise ValueError(
            "Weights must total exactly 100%."
        )

    if any(
        not isinstance(weight, (int, float))
        or not np.isfinite(weight)
        or weight < 0
        for weight in weights.values()
    ):
        raise ValueError(
            "Weights must be finite, non-negative numbers."
        )

    shape = arrays["water"]["data"].shape

    weighted_sum = np.zeros(shape, dtype=np.float64)
    available_weight = np.zeros(shape, dtype=np.float64)

    landuse_missing = np.zeros(shape, dtype=bool)

    print("\nCombining suitability criteria...")

    for name, weight in weights.items():

        data = arrays[name]["data"]
        valid = arrays[name]["valid"]

        weighted_sum[valid] += data[valid] * weight
        available_weight[valid] += weight

        print(
            f"{name}: weight {weight}% | "
            f"valid cells {np.count_nonzero(valid)}"
        )

        if name == "landuse":
            landuse_missing = ~valid

    result = np.full(shape, NODATA, dtype=np.float32)

    valid_result = available_weight > 0

    result[valid_result] = (
        weighted_sum[valid_result]
        / available_weight[valid_result]
    ).astype(np.float32)

    return result, valid_result, landuse_missing


def classify_suitability(result, valid):

    classified = np.full(
        result.shape,
        0,
        dtype=np.uint8
    )

    classified[valid & (result < 20)] = 1
    classified[valid & (result >= 20) & (result < 40)] = 2
    classified[valid & (result >= 40) & (result < 60)] = 3
    classified[valid & (result >= 60) & (result < 80)] = 4
    classified[valid & (result >= 80)] = 5

    return classified


def save_raster(data, reference_profile, output_path, nodata):

    profile = reference_profile.copy()

    profile.update(
        driver="GTiff",
        dtype=data.dtype,
        count=1,
        compress="lzw",
        nodata=nodata
    )

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data, 1)


def main():

    weights = PROFILES[SELECTED_PROFILE]

    print("===================================")
    print("WASTEWATCH GIS")
    print("WEIGHTED SUITABILITY ANALYSIS")
    print("===================================")

    print(f"\nSelected profile: {SELECTED_PROFILE}")
    print(f"Weights: {weights}")

    arrays, reference_profile = load_rasters()

    result, valid, landuse_missing = (
        calculate_weighted_overlay(arrays, weights)
    )

    classified = classify_suitability(result, valid)

    score_output = os.path.join(
        OUTPUT_DIR,
        f"Lilongwe_{SELECTED_PROFILE.title()}_Suitability.tif"
    )

    classification_output = os.path.join(
        OUTPUT_DIR,
        f"Lilongwe_{SELECTED_PROFILE.title()}_Classes.tif"
    )

    missing_output = os.path.join(
        OUTPUT_DIR,
        "Lilongwe_Landuse_Missing_Mask.tif"
    )

    save_raster(
        result,
        reference_profile,
        score_output,
        NODATA
    )

    save_raster(
        classified,
        reference_profile,
        classification_output,
        0
    )

    save_raster(
        landuse_missing.astype(np.uint8),
        reference_profile,
        missing_output,
        255
    )

    print("\n===================================")
    print("WEIGHTED ANALYSIS COMPLETED")
    print("===================================")

    print(f"Valid output cells: {np.count_nonzero(valid)}")
    print(f"Missing land-use cells: {np.count_nonzero(landuse_missing & valid)}")

    if np.any(valid):

        values = result[valid]

        print(f"Minimum score: {values.min():.2f}")
        print(f"Maximum score: {values.max():.2f}")
        print(f"Mean score: {values.mean():.2f}")

        print("\nSuitability classification:")

        labels = {
            1: "Very Low",
            2: "Low",
            3: "Moderate",
            4: "High",
            5: "Very High"
        }

        for code, label in labels.items():
            count = np.count_nonzero(classified == code)
            print(f"{label}: {count} cells")

    print("\nOutput files:")
    print(score_output)
    print(classification_output)
    print(missing_output)


if __name__ == "__main__":
    main()
