"""
gui/web_app.py — Flask web UI for the Data Anonymizer.

Serves the single-page web interface and API endpoints that call
the existing Anonymizer/ImageAnonymizer engines.
"""

import logging
import os
import sys
import tempfile
import time
import uuid

from flask import Flask, jsonify, request

# Ensure project root is importable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from updater import __version__

logger = logging.getLogger(__name__)


def create_app(upload_dir: str = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # Upload directory for temp files
    if upload_dir is None:
        upload_dir = tempfile.mkdtemp(prefix="anonymizer_uploads_")
    app.config["UPLOAD_DIR"] = upload_dir

    # In-memory registry: file_id → {name, path, size}
    app.config["FILE_REGISTRY"] = {}

    # Track last request time for auto-shutdown
    app.config["LAST_REQUEST_TIME"] = time.time()

    @app.before_request
    def update_last_request_time():
        app.config["LAST_REQUEST_TIME"] = time.time()

    # --- Health endpoint ---
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": __version__})

    # --- Upload endpoint ---
    @app.route("/api/upload", methods=["POST"])
    def upload():
        files = request.files.getlist("files")
        if not files or all(f.filename == "" for f in files):
            return jsonify({"error": "未選擇任何檔案"}), 400

        results = []
        for f in files:
            if f.filename == "":
                continue
            file_id = str(uuid.uuid4())
            save_path = os.path.join(app.config["UPLOAD_DIR"], file_id + "_" + f.filename)
            f.save(save_path)
            size = os.path.getsize(save_path)
            app.config["FILE_REGISTRY"][file_id] = {
                "name": f.filename,
                "path": save_path,
                "size": size,
            }
            results.append({"id": file_id, "name": f.filename, "size": size})

        return jsonify({"files": results})

    return app
