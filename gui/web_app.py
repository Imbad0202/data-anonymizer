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

from flask import Flask, jsonify

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

    # Track last request time for auto-shutdown
    app.config["LAST_REQUEST_TIME"] = time.time()

    @app.before_request
    def update_last_request_time():
        app.config["LAST_REQUEST_TIME"] = time.time()

    # --- Health endpoint ---
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": __version__})

    return app
