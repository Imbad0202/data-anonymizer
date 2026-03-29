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

    from anonymizer import Anonymizer, get_parser
    from config_manager import load_config

    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_PATH = os.path.join(APP_DIR, "config.json")

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

    # --- Preview endpoint ---
    @app.route("/api/preview", methods=["POST"])
    def preview():
        data = request.get_json()
        file_id = data.get("file_id")
        mode = data.get("mode", "reversible")
        use_ner = data.get("use_ner", False)

        file_info = app.config["FILE_REGISTRY"].get(file_id)
        if not file_info:
            return jsonify({"error": "找不到檔案"}), 404

        file_path = file_info["path"]
        config = load_config(CONFIG_PATH)
        reversible = mode == "reversible"

        anon = Anonymizer(config=config, session_id=f"preview_{file_id}",
                          use_ner=use_ner, reversible=reversible)

        parser = get_parser(file_path)
        if parser is None:
            return jsonify({"error": f"不支援的檔案格式：{os.path.splitext(file_path)[1]}"}), 400

        text = parser.parse(file_path)
        spans = anon._collect_spans(text)
        anonymized = anon._apply_spans(text, spans) if spans else text

        spans_json = [
            {"start": s.start, "end": s.end, "text": s.text, "category": s.category}
            for s in spans
        ]

        summary = {}
        for s in spans:
            summary[s.category] = summary.get(s.category, 0) + 1

        return jsonify({
            "original": text,
            "anonymized": anonymized,
            "spans": spans_json,
            "summary": summary,
        })

    return app
