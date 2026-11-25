
from flask import Flask, jsonify
from flask_cors import CORS

from database import test_connection

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Welcome to WasteWatch GIS API",
        "status": "running"
    })


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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
