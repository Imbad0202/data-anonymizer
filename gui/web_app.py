"""
gui/web_app.py — Flask web UI for the Data Anonymizer.

Serves the single-page web interface and API endpoints that call
the existing Anonymizer/ImageAnonymizer engines.
"""

import io
import json
import logging
import os
import socket
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
import zipfile

from flask import Flask, Response, jsonify, request, send_file, stream_with_context

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
    from config_manager import export_config, import_config, load_config, save_config

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

    from image_anonymizer import ImageAnonymizer
    from parsers.image_parser import ImageParser

    IMAGE_EXTENSIONS = set(ImageParser.EXTENSIONS)

    @app.route("/api/process", methods=["POST"])
    def process():
        data = request.get_json()
        file_ids = data.get("file_ids", [])
        mode = data.get("mode", "reversible")
        use_ner = data.get("use_ner", False)

        if not file_ids:
            return jsonify({"error": "未選擇任何檔案"}), 400

        reversible = mode == "reversible"
        config = load_config(CONFIG_PATH)

        def generate():
            text_anon = Anonymizer(config=config, session_id="web_process",
                                   use_ner=use_ner, reversible=reversible)
            img_anon = ImageAnonymizer(config=config, use_ner=use_ner)
            total = len(file_ids)
            results = []

            for idx, fid in enumerate(file_ids):
                file_info = app.config["FILE_REGISTRY"].get(fid)
                if not file_info:
                    continue

                fpath = file_info["path"]
                fname = file_info["name"]
                ext = os.path.splitext(fpath)[1].lower()

                yield f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'file': fname})}\n\n"

                try:
                    if ext in IMAGE_EXTENSIONS:
                        out_dir = os.path.join(app.config["UPLOAD_DIR"], "output")
                        os.makedirs(out_dir, exist_ok=True)
                        anon_path, summary = img_anon.anonymize_image(
                            fpath, output_dir=out_dir, reversible=reversible)
                        results.append({"file_id": fid, "name": fname, "output": anon_path, "summary": summary})
                    else:
                        anon_path, summary = text_anon.anonymize_file(fpath)
                        results.append({"file_id": fid, "name": fname, "output": anon_path, "summary": summary})
                except Exception as e:
                    results.append({"file_id": fid, "name": fname, "output": None, "summary": f"錯誤：{e}"})

            output_dir = os.path.join(app.config["UPLOAD_DIR"], "output")
            yield f"data: {json.dumps({'type': 'done', 'results': results, 'output_dir': output_dir})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.route("/api/batch", methods=["POST"])
    def batch():
        data = request.get_json()
        folder = data.get("folder")
        mode = data.get("mode", "reversible")
        use_ner = data.get("use_ner", False)

        if not folder or not os.path.isdir(folder):
            return jsonify({"error": "無效的資料夾路徑"}), 400

        reversible = mode == "reversible"
        config = load_config(CONFIG_PATH)
        file_types = config.get("file_types") or [".txt", ".md", ".docx", ".xlsx", ".pptx", ".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"]

        def generate():
            from batch import _collect_files
            import shutil
            files = _collect_files(folder, file_types)
            text_anon = Anonymizer(config=config, session_id="web_batch",
                                   use_ner=use_ner, reversible=reversible)
            img_anon = ImageAnonymizer(config=config, use_ner=use_ner)
            total = len(files)
            output_dir = folder.rstrip(os.sep) + "_anonymized"
            os.makedirs(output_dir, exist_ok=True)
            results = []

            for idx, fpath in enumerate(files):
                fname = os.path.basename(fpath)
                ext = os.path.splitext(fpath)[1].lower()
                yield f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'file': fname})}\n\n"

                try:
                    if ext in IMAGE_EXTENSIONS:
                        anon_path, summary = img_anon.anonymize_image(
                            fpath, output_dir=output_dir, reversible=reversible)
                        results.append({"name": fname, "summary": summary})
                    else:
                        anon_path, summary = text_anon.anonymize_file(fpath)
                        if anon_path:
                            rel = os.path.relpath(fpath, folder)
                            dest = os.path.join(output_dir, rel)
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            shutil.copy2(anon_path, dest)
                        results.append({"name": fname, "summary": summary})
                except Exception as e:
                    results.append({"name": fname, "summary": f"錯誤：{e}"})

            yield f"data: {json.dumps({'type': 'done', 'results': results, 'output_dir': output_dir})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    from config_manager import export_config, import_config, save_config

    LOGO_DIR = os.path.join(APP_DIR, "logo_templates")

    @app.route("/api/config")
    def get_config():
        config = load_config(CONFIG_PATH)
        return jsonify(config)

    @app.route("/api/config/import", methods=["POST"])
    def import_config_route():
        if "file" not in request.files:
            return jsonify({"error": "未選擇設定檔"}), 400
        f = request.files["file"]
        tmp_zip = os.path.join(app.config["UPLOAD_DIR"], "config_import.zip")
        f.save(tmp_zip)
        try:
            config, summary = import_config(tmp_zip, APP_DIR)
            config["logo_templates"] = [
                os.path.join(LOGO_DIR, lt) for lt in config["logo_templates"]
            ]
            save_config(config, CONFIG_PATH)
            return jsonify({"summary": summary})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/config/export")
    def export_config_route():
        config = load_config(CONFIG_PATH)
        tmp_zip = os.path.join(app.config["UPLOAD_DIR"], "config_export.zip")
        export_config(config, LOGO_DIR, tmp_zip)
        return send_file(tmp_zip, as_attachment=True,
                         download_name=".anonymizer-config.zip")

    @app.route("/api/download/<file_id>")
    def download_file(file_id):
        file_info = app.config["FILE_REGISTRY"].get(file_id)
        if not file_info:
            return jsonify({"error": "找不到檔案"}), 404
        output_dir = os.path.join(app.config["UPLOAD_DIR"], "output")
        anon_name = os.path.splitext(file_info["name"])[0] + "_anonymized" + os.path.splitext(file_info["name"])[1]
        for root, dirs, files in os.walk(output_dir):
            for fname in files:
                if file_id in fname or file_info["name"] in fname:
                    return send_file(os.path.join(root, fname), as_attachment=True,
                                     download_name=anon_name)
        return jsonify({"error": "尚未處理此檔案"}), 404

    @app.route("/api/download-all", methods=["POST"])
    def download_all():
        data = request.get_json()
        file_ids = data.get("file_ids", [])
        output_dir = os.path.join(app.config["UPLOAD_DIR"], "output")

        if not os.path.isdir(output_dir):
            return "", 204

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(output_dir):
                for fname in files:
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, output_dir)
                    zf.write(full, arcname)

        buf.seek(0)
        if buf.getbuffer().nbytes <= 22:  # Empty zip
            return "", 204

        return send_file(buf, as_attachment=True, download_name="anonymized_output.zip",
                         mimetype="application/zip")

    return app


def find_free_port() -> int:
    """Find a random available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def wait_for_server(port: int, timeout: float = 10.0):
    """Block until the Flask server is responding."""
    import urllib.request
    import urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/api/health", timeout=1)
            return
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.2)
    raise RuntimeError(f"Server did not start within {timeout}s")


def monitor_and_shutdown(app: Flask, timeout_seconds: int = 120):
    """Monitor the last request time. Exit if idle for timeout_seconds."""
    while True:
        time.sleep(10)
        elapsed = time.time() - app.config["LAST_REQUEST_TIME"]
        if elapsed > timeout_seconds:
            logger.info("No activity for %ds, shutting down.", timeout_seconds)
            upload_dir = app.config.get("UPLOAD_DIR")
            if upload_dir and os.path.isdir(upload_dir):
                import shutil
                shutil.rmtree(upload_dir, ignore_errors=True)
            os._exit(0)


def main():
    """Entry point: start Flask server, open browser, monitor for shutdown."""
    logging.basicConfig(level=logging.INFO)

    port = find_free_port()
    app = create_app()

    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    wait_for_server(port)
    logger.info("Server started on http://localhost:%d", port)

    webbrowser.open(f"http://localhost:{port}")

    monitor_and_shutdown(app)


if __name__ == "__main__":
    main()
