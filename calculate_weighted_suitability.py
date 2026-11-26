
import os
import numpy as np
import rasterio

# ==========================================
# WASTEWATCH GIS
# FINAL WEIGHTED SUITABILITY ANALYSIS
# WITH MANDATORY EXCLUSIONS
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))

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

EXCLUSION_MASK = os.path.join(
    DATA_DIR, "results", "Lilongwe_Exclusion_Mask.tif"
)

OUTPUT_DIR = os.path.join(DATA_DIR, "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

NODATA = -9999.0

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

# Default profile when running this script directly
SELECTED_PROFILE = "balanced"


# ==========================================
# VALIDATE WEIGHTS
# ==========================================

def validate_weights(weights):

    required_criteria = {
        "water",
        "residential",
        "roads",
        "population",
        "landuse"
    }

    if not isinstance(weights, dict):
        raise ValueError("Weights must be provided as an object.")

    if set(weights.keys()) != required_criteria:
        raise ValueError(
            "Weights must contain exactly: "
            "water, residential, roads, population, landuse."
        )

    validated_weights = {}

    for criterion, weight in weights.items():

        if isinstance(weight, (bool, np.bool_)):
            raise ValueError(
                f"Weight for {criterion} must be numeric."
            )

        if not isinstance(weight, (int, float, np.number)):
            raise ValueError(
                f"Weight for {criterion} must be numeric."
            )

        weight = float(weight)

        if not np.isfinite(weight) or weight < 0:
            raise ValueError(
                f"Weight for {criterion} must be finite "
                "and non-negative."
            )

        validated_weights[criterion] = weight

    if not np.isclose(
        sum(validated_weights.values()),
        100,
        atol=1e-6
    ):
        raise ValueError("Weights must total exactly 100%.")

    return validated_weights


# ==========================================
# LOAD SUITABILITY RASTERS
# ==========================================

def load_rasters():

    arrays = {}
    reference_profile = None
    reference_shape = None

    print("\nLoading suitability rasters...")

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
                        f"{name} has a different raster shape."
                    )

                if src.transform != reference_profile["transform"]:
                    raise ValueError(
                        f"{name} has a different grid transform."
                    )

                if src.crs != reference_profile["crs"]:
                    raise ValueError(
                        f"{name} has a different CRS."
                    )

            valid = np.isfinite(array)

            if src.nodata is not None:
                valid &= array != src.nodata

            arrays[name] = {
                "data": array,
                "valid": valid
            }

            print(
                f"{name}: {np.count_nonzero(valid)} valid cells"
            )

    return arrays, reference_profile


# ==========================================
# LOAD MANDATORY EXCLUSION MASK
# ==========================================

def load_exclusion_mask(reference_profile):

    print("\nLoading mandatory exclusion mask...")

    if not os.path.exists(EXCLUSION_MASK):
        raise FileNotFoundError(
            f"Exclusion mask not found: {EXCLUSION_MASK}"
        )

    with rasterio.open(EXCLUSION_MASK) as src:

        if src.shape != (
            reference_profile["height"],
            reference_profile["width"]
        ):
            raise ValueError(
                "Exclusion mask dimensions do not match."
            )

        if src.transform != reference_profile["transform"]:
            raise ValueError(
                "Exclusion mask grid does not match."
            )

        if src.crs != reference_profile["crs"]:
            raise ValueError(
                "Exclusion mask CRS does not match."
            )

        mask = src.read(1)

        # 1 = excluded
        # 0 = eligible
        # 255 = outside analysis area
        excluded = mask == 1

        print(
            f"Excluded cells: {np.count_nonzero(excluded)}"
        )

    return excluded


# ==========================================
# CALCULATE WEIGHTED OVERLAY
# ==========================================

def calculate_weighted_overlay(arrays, weights):

    weights = validate_weights(weights)

    shape = arrays["water"]["data"].shape

    weighted_sum = np.zeros(
        shape,
        dtype=np.float64
    )

    available_weight = np.zeros(
        shape,
        dtype=np.float64
    )

    landuse_missing = np.zeros(
        shape,
        dtype=bool
    )

    print("\nCombining suitability criteria...")

    for name, weight in weights.items():

        data = arrays[name]["data"]
        valid = arrays[name]["valid"]

        weighted_sum[valid] += data[valid] * weight
        available_weight[valid] += weight

        if name == "landuse":
            landuse_missing = ~valid

        print(
            f"{name}: {weight}% | "
            f"{np.count_nonzero(valid)} valid cells"
        )

    result = np.full(
        shape,
        NODATA,
        dtype=np.float32
    )

    valid_result = available_weight > 0

    result[valid_result] = (
        weighted_sum[valid_result] /
        available_weight[valid_result]
    ).astype(np.float32)

    return result, valid_result, landuse_missing


# ==========================================
# APPLY MANDATORY EXCLUSIONS
# ==========================================

def apply_exclusions(result, valid, excluded):

    print("\nApplying mandatory exclusions...")

    valid_before = np.count_nonzero(valid)

    # Excluded locations must never receive
    # a suitability score.
    result[excluded] = NODATA
    valid[excluded] = False

    print(f"Valid cells before exclusion: {valid_before}")

    print(
        f"Excluded cells in mask: "
        f"{np.count_nonzero(excluded)}"
    )

    print(
        f"Valid cells after exclusion: "
        f"{np.count_nonzero(valid)}"
    )

    return result, valid


# ==========================================
# CLASSIFY SUITABILITY
# ==========================================

def classify_suitability(result, valid):

    classified = np.zeros(
        result.shape,
        dtype=np.uint8
    )

    classified[valid & (result < 20)] = 1
    classified[valid & (result >= 20) & (result < 40)] = 2
    classified[valid & (result >= 40) & (result < 60)] = 3
    classified[valid & (result >= 60) & (result < 80)] = 4
    classified[valid & (result >= 80)] = 5

    # 0 = NoData / outside analysis area

    return classified


# ==========================================
# SAVE RASTER
# ==========================================

def save_raster(data, reference_profile, output_path, nodata):

    profile = reference_profile.copy()

    profile.update(
        driver="GTiff",
        dtype=data.dtype,
        count=1,
        compress="lzw",
        nodata=nodata
    )

    with rasterio.open(
        output_path,
        "w",
        **profile
    ) as dst:

        dst.write(data, 1)


# ==========================================
# RUN SUITABILITY ANALYSIS
# ==========================================

def run_analysis(profile="balanced", custom_weights=None):

    # Select weighting profile or custom weights
    if custom_weights is not None:

        selected_profile = "custom"
        weights = validate_weights(custom_weights)

    else:

        if profile not in PROFILES:
            raise ValueError(
                f"Unknown profile: {profile}. "
                f"Available profiles: {list(PROFILES.keys())}"
            )

        selected_profile = profile
        weights = validate_weights(PROFILES[profile])

    print("\n======================================")
    print("WASTEWATCH GIS")
    print("FINAL SUITABILITY ANALYSIS")
    print("======================================")

    print(f"Selected profile: {selected_profile}")
    print(f"Weights: {weights}")

    # Load input rasters
    arrays, reference_profile = load_rasters()

    # Load exclusion mask
    excluded = load_exclusion_mask(reference_profile)

    # Calculate weighted overlay
    result, valid, landuse_missing = (
        calculate_weighted_overlay(arrays, weights)
    )

    # Apply mandatory exclusions
    result, valid = apply_exclusions(
        result,
        valid,
        excluded
    )

    # Classify results
    classified = classify_suitability(
        result,
        valid
    )

    # ======================================
    # OUTPUT FILES
    # ======================================

    prefix = f"Lilongwe_{selected_profile.title()}"

    score_output = os.path.join(
        OUTPUT_DIR,
        f"{prefix}_Suitability.tif"
    )

    classification_output = os.path.join(
        OUTPUT_DIR,
        f"{prefix}_Classes.tif"
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

    # Create missing land-use mask.
    # 1 = missing land-use data in eligible cell
    # 0 = land-use data available in eligible cell
    # 255 = excluded or outside analysis area

    missing_mask = np.full(
        landuse_missing.shape,
        255,
        dtype=np.uint8
    )

    missing_mask[valid] = (
        landuse_missing[valid].astype(np.uint8)
    )

    save_raster(
        missing_mask,
        reference_profile,
        missing_output,
        255
    )

    # ======================================
    # STATISTICS
    # ======================================

    classification_labels = {
        1: "Very Low",
        2: "Low",
        3: "Moderate",
        4: "High",
        5: "Very High"
    }

    classification_counts = {}

    for code, label in classification_labels.items():

        classification_counts[label] = int(
            np.count_nonzero(classified == code)
        )

    valid_cells = int(
        np.count_nonzero(valid)
    )

    missing_landuse_cells = int(
        np.count_nonzero(landuse_missing & valid)
    )

    if valid_cells > 0:

        values = result[valid]

        statistics = {
            "minimum_score": float(values.min()),
            "maximum_score": float(values.max()),
            "mean_score": float(values.mean())
        }

    else:

        statistics = {
            "minimum_score": None,
            "maximum_score": None,
            "mean_score": None
        }

    # ======================================
    # DISPLAY RESULTS
    # ======================================

    print("\n======================================")
    print("FINAL SUITABILITY ANALYSIS COMPLETE")
    print("======================================")

    print(f"Valid output cells: {valid_cells}")

    print(
        "Missing land-use cells among eligible locations: "
        f"{missing_landuse_cells}"
    )

    print("\nSuitability statistics:")

    for name, value in statistics.items():
        print(f"{name}: {value}")

    print("\nSuitability classification:")

    for label, count in classification_counts.items():
        print(f"{label}: {count} cells")

    print("\nOutput files:")
    print(score_output)
    print(classification_output)
    print(missing_output)

    # Return results for Flask or another application
    return {
        "status": "success",
        "profile": selected_profile,
        "weights": weights,
        "valid_cells": valid_cells,
        "missing_landuse_cells": missing_landuse_cells,
        "statistics": statistics,
        "classification_counts": classification_counts,
        "outputs": {
            "suitability_raster": os.path.abspath(
                score_output
            ),
            "classification_raster": os.path.abspath(
                classification_output
            ),
            "missing_landuse_mask": os.path.abspath(
                missing_output
            )
        }
    }


# ==========================================
# RUN DIRECTLY
# ==========================================

if __name__ == "__main__":

    run_analysis(
        profile=SELECTED_PROFILE
    )
