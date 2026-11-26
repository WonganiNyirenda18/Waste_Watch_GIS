
from flask import Flask, jsonify, request, send_from_directory, url_for
from flask_cors import CORS
import os

from database import test_connection

from calculate_weighted_suitability import (
    run_analysis,
    PROFILES,
    OUTPUT_DIR
)


# ==========================================
# WASTEWATCH GIS API
# ==========================================

app = Flask(__name__)
CORS(app)


# ==========================================
# HOME ROUTE
# ==========================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "message": "Welcome to WasteWatch GIS API",
        "application": "WasteWatch GIS",
        "status": "running"
    })


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/api/health", methods=["GET"])
def health():

    try:

        database_result = test_connection()

        return jsonify({
            "application": "WasteWatch GIS",
            "backend": "online",
            "database": "connected",
            "database_name": database_result[0],
            "postgis": database_result[1]
        })

    except Exception as error:

        return jsonify({
            "application": "WasteWatch GIS",
            "backend": "online",
            "database": "connection_failed",
            "error": str(error)
        }), 500


# ==========================================
# GET AVAILABLE ANALYSIS PROFILES
# ==========================================

@app.route("/api/analysis/profiles", methods=["GET"])
def get_analysis_profiles():

    return jsonify({
        "status": "success",
        "profiles": PROFILES,
        "custom_weights_supported": True,
        "criteria": [
            "water",
            "residential",
            "roads",
            "population",
            "landuse"
        ]
    })


# ==========================================
# RUN SUITABILITY ANALYSIS
# ==========================================

@app.route("/api/analysis/run", methods=["POST"])
def run_suitability_analysis():

    try:

        # Receive JSON data from the frontend
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "status": "error",
                "message": "A valid JSON request body is required."
            }), 400

        # Read selected profile
        profile = data.get("profile", "balanced")

        if not isinstance(profile, str):
            return jsonify({
                "status": "error",
                "message": "Profile must be a string."
            }), 400

        profile = profile.lower().strip()

        # Custom weighting analysis
        if profile == "custom":

            custom_weights = data.get("weights")

            if custom_weights is None:
                return jsonify({
                    "status": "error",
                    "message": (
                        "Custom weights are required "
                        "when using the custom profile."
                    )
                }), 400

            result = run_analysis(
                custom_weights=custom_weights
            )

        # Predefined weighting analysis
        else:

            if profile not in PROFILES:
                return jsonify({
                    "status": "error",
                    "message": "Invalid analysis profile.",
                    "available_profiles": list(PROFILES.keys())
                }), 400

            result = run_analysis(
                profile=profile
            )

        # Convert local raster paths into API download links
        output_links = {}

        for output_name, output_path in result["outputs"].items():

            filename = os.path.basename(output_path)

            output_links[output_name] = url_for(
                "download_analysis",
                filename=filename,
                _external=True
            )

        # Return analysis results to frontend
        response = {
            "status": "success",
            "message": "Suitability analysis completed successfully.",
            "results": {
                "profile": result["profile"],
                "weights": result["weights"],
                "valid_cells": result["valid_cells"],
                "missing_landuse_cells": (
                    result["missing_landuse_cells"]
                ),
                "statistics": result["statistics"],
                "classification_counts": (
                    result["classification_counts"]
                ),
                "outputs": output_links
            }
        }

        return jsonify(response), 200

    except ValueError as error:

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except FileNotFoundError as error:

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500

    except Exception as error:

        app.logger.exception(
            "Suitability analysis failed."
        )

        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred during analysis."
        }), 500


# ==========================================
# DOWNLOAD ANALYSIS OUTPUTS
# ==========================================

@app.route(
    "/api/analysis/download/<path:filename>",
    methods=["GET"]
)
def download_analysis(filename):

    allowed_files = {
        "Lilongwe_Balanced_Suitability.tif",
        "Lilongwe_Balanced_Classes.tif",

        "Lilongwe_Environmental_Suitability.tif",
        "Lilongwe_Environmental_Classes.tif",

        "Lilongwe_Accessibility_Suitability.tif",
        "Lilongwe_Accessibility_Classes.tif",

        "Lilongwe_Custom_Suitability.tif",
        "Lilongwe_Custom_Classes.tif",

        "Lilongwe_Landuse_Missing_Mask.tif"
    }

    if filename not in allowed_files:
        return jsonify({
            "status": "error",
            "message": "Requested output file is not allowed."
        }), 403

    if not os.path.isfile(
        os.path.join(OUTPUT_DIR, filename)
    ):
        return jsonify({
            "status": "error",
            "message": "Requested analysis output was not found."
        }), 404

    return send_from_directory(
        OUTPUT_DIR,
        filename,
        as_attachment=True
    )


# ==========================================
# START APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )
