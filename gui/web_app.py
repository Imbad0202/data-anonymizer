"""
gui/web_app.py — Flask web UI for the Data Anonymizer.

Serves the single-page web interface and API endpoints that call
the existing Anonymizer/ImageAnonymizer engines.
"""

import io
import json
import logging
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
import zipfile

from flask import Flask, Response, jsonify, render_template, request, send_file, stream_with_context

# Ensure project root is importable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from updater import __version__

logger = logging.getLogger(__name__)

# Directories that should never be processed via batch (pre-normalized + resolved)
_SENSITIVE_DIRS = {
    os.path.normpath(os.path.realpath(p)) for p in [
        "/etc", "/var", "/usr", "/bin", "/sbin", "/boot", "/proc", "/sys", "/dev",
        os.path.expanduser("~/.ssh"),
        os.path.expanduser("~/.gnupg"),
        os.path.expanduser("~/.claude"),
    ]
}
# Windows-specific sensitive directories
if sys.platform == "win32":
    _SENSITIVE_DIRS.update(
        os.path.normpath(p) for p in [
            os.environ.get("SystemRoot", r"C:\Windows"),
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.path.expanduser("~\\AppData"),
        ] if p
    )


def _is_safe_batch_path(folder: str) -> bool:
    """Return True if the folder is safe to process in batch mode."""
    norm = os.path.normpath(os.path.realpath(folder))
    for s in _SENSITIVE_DIRS:
        if norm == s or norm.startswith(s + os.sep):
            return False
    return True


def create_app(upload_dir: str = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # Max upload size: 100MB
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

    # Upload directory for temp files
    if upload_dir is None:
        upload_dir = tempfile.mkdtemp(prefix="anonymizer_uploads_")
    app.config["UPLOAD_DIR"] = upload_dir

    # In-memory registry: file_id → {name, path, size, output_path, download_name}
    app.config["FILE_REGISTRY"] = {}

    # Track last request time for auto-shutdown
    app.config["LAST_REQUEST_TIME"] = time.time()

    from anonymizer import Anonymizer, get_parser
    from config_manager import (
        export_config,
        import_config,
        load_config,
        resolve_logo_template_paths,
        save_config,
    )
    from image_anonymizer import ImageAnonymizer, merge_regions
    from parsers.image_parser import ImageParser

    APP_DIR = _PROJECT_ROOT
    CONFIG_PATH = os.path.join(APP_DIR, "config.json")
    LOGO_DIR = os.path.join(APP_DIR, "logo_templates")
    IMAGE_EXTENSIONS = set(ImageParser.EXTENSIONS)

    def _load_runtime_config() -> dict:
        return resolve_logo_template_paths(load_config(CONFIG_PATH), LOGO_DIR)

    def build_download_name(filename: str, output_ext: str = None) -> str:
        base, original_ext = os.path.splitext(filename)
        ext = output_ext if output_ext is not None else original_ext
        return f"{base}_anonymized{ext}"

    def build_output_path(file_id: str, filename: str, output_ext: str = None) -> str:
        ext = output_ext if output_ext is not None else os.path.splitext(filename)[1]
        output_dir = os.path.join(app.config["UPLOAD_DIR"], "output")
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, f"{file_id}_{build_download_name(filename, ext)}")

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({"error": "檔案大小超過上限（100MB）"}), 413

    @app.before_request
    def update_last_request_time():
        app.config["LAST_REQUEST_TIME"] = time.time()

    # --- Index route ---
    @app.route("/")
    def index():
        return render_template("index.html")

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
                "output_path": None,
                "download_name": None,
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
        config = _load_runtime_config()
        reversible = mode == "reversible"

        ext = os.path.splitext(file_path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            parser = ImageParser()
            img = parser.parse(file_path)
            if img is None:
                return jsonify({"error": "無法讀取圖片"}), 400

            img_anon = ImageAnonymizer(config=config, use_ner=use_ner)
            regions = []
            regions.extend(img_anon._stage_ocr(img))
            regions.extend(img_anon._stage_face(img))
            regions.extend(img_anon._stage_logo(img))
            merged = merge_regions(regions, iou_threshold=0.3)

            summary = {}
            for region in merged:
                key = region.label or region.region_type
                summary[key] = summary.get(key, 0) + 1

            if merged:
                anonymized_text = f"偵測到 {len(merged)} 個敏感區域。處理後可下載脫敏圖片。"
            else:
                anonymized_text = "未發現敏感資訊。"

            return jsonify({
                "original": f"圖片檔：{file_info['name']}",
                "anonymized": anonymized_text,
                "spans": [],
                "summary": summary,
            })

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

    @app.route("/api/process", methods=["POST"])
    def process():
        data = request.get_json()
        file_ids = data.get("file_ids", [])
        mode = data.get("mode", "reversible")
        use_ner = data.get("use_ner", False)

        if not file_ids:
            return jsonify({"error": "未選擇任何檔案"}), 400

        reversible = mode == "reversible"
        config = _load_runtime_config()

        def generate():
            text_anon = Anonymizer(config=config, session_id="web_process",
                                   use_ner=use_ner, reversible=reversible)
            img_anon = ImageAnonymizer(config=config, use_ner=use_ner)
            total = len(file_ids)
            results = []
            output_dir = os.path.join(app.config["UPLOAD_DIR"], "output")
            os.makedirs(output_dir, exist_ok=True)

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
                        target_path = build_output_path(fid, fname)
                        anon_path, summary = img_anon.anonymize_image(
                            fpath,
                            output_dir=os.path.dirname(target_path),
                            reversible=reversible,
                        )
                        if anon_path is None:
                            shutil.copy2(fpath, target_path)
                        elif os.path.abspath(anon_path) != os.path.abspath(target_path):
                            shutil.move(anon_path, target_path)
                    else:
                        parser = get_parser(fpath)
                        if parser is None:
                            raise ValueError(f"不支援的檔案格式：{ext}")
                        preferred_ext = getattr(parser, "OUTPUT_EXTENSION", ext or ".txt")
                        target_path = build_output_path(fid, fname, preferred_ext)
                        final_output, summary = text_anon.anonymize_file_to_path(fpath, target_path)
                        if final_output is None:
                            target_path = build_output_path(fid, fname)
                            shutil.copy2(fpath, target_path)
                    file_info["output_path"] = target_path
                    file_info["download_name"] = os.path.basename(target_path).split("_", 1)[1]
                    results.append({"file_id": fid, "name": fname, "output": target_path, "summary": summary})
                except Exception as e:
                    file_info["output_path"] = None
                    file_info["download_name"] = None
                    results.append({"file_id": fid, "name": fname, "output": None, "summary": f"錯誤：{e}"})

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

        if not _is_safe_batch_path(folder):
            return jsonify({"error": "此路徑屬於系統敏感目錄，不允許批次處理"}), 403

        reversible = mode == "reversible"
        config = _load_runtime_config()
        from config_manager import DEFAULT_FILE_TYPES
        file_types = config.get("file_types") or DEFAULT_FILE_TYPES

        def generate():
            from batch import _collect_files
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
                rel = os.path.relpath(fpath, folder)
                out_path = os.path.join(output_dir, rel)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                yield f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'file': fname})}\n\n"

                try:
                    if ext in IMAGE_EXTENSIONS:
                        anon_path, summary = img_anon.anonymize_image(
                            fpath,
                            output_dir=os.path.dirname(out_path),
                            reversible=reversible,
                        )
                        if anon_path is None:
                            shutil.copy2(fpath, out_path)
                        elif os.path.abspath(anon_path) != os.path.abspath(out_path):
                            shutil.move(anon_path, out_path)
                        results.append({"name": fname, "summary": summary})
                    else:
                        parser = get_parser(fpath)
                        if parser is None:
                            raise ValueError(f"不支援的檔案格式：{ext}")
                        output_ext = getattr(parser, "OUTPUT_EXTENSION", ext or ".txt")
                        rel_output_path = os.path.splitext(rel)[0] + output_ext
                        out_path = os.path.join(output_dir, rel_output_path)
                        os.makedirs(os.path.dirname(out_path), exist_ok=True)
                        written_path, summary = text_anon.anonymize_file_to_path(fpath, out_path)
                        if written_path is None:
                            fallback_out = os.path.join(output_dir, rel)
                            os.makedirs(os.path.dirname(fallback_out), exist_ok=True)
                            shutil.copy2(fpath, fallback_out)
                        results.append({"name": fname, "summary": summary})
                except Exception as e:
                    results.append({"name": fname, "summary": f"錯誤：{e}"})

            yield f"data: {json.dumps({'type': 'done', 'results': results, 'output_dir': output_dir})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

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
        output_path = file_info.get("output_path")
        if output_path and os.path.isfile(output_path):
            return send_file(
                output_path,
                as_attachment=True,
                download_name=file_info.get("download_name") or build_download_name(file_info["name"]),
            )
        return jsonify({"error": "尚未處理此檔案"}), 404

    @app.route("/api/download-all", methods=["POST"])
    def download_all():
        data = request.get_json()
        file_ids = data.get("file_ids", [])

        downloadable = []
        for file_id in file_ids:
            file_info = app.config["FILE_REGISTRY"].get(file_id)
            if not file_info:
                continue
            output_path = file_info.get("output_path")
            if output_path and os.path.isfile(output_path):
                download_name = file_info.get("download_name") or build_download_name(file_info["name"])
                downloadable.append((output_path, download_name))

        if not downloadable:
            return "", 204

        buf = io.BytesIO()
        used_names = set()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for full, arcname in downloadable:
                final_name = arcname
                if final_name in used_names:
                    stem, ext = os.path.splitext(arcname)
                    suffix = 2
                    while f"{stem}_{suffix}{ext}" in used_names:
                        suffix += 1
                    final_name = f"{stem}_{suffix}{ext}"
                used_names.add(final_name)
                zf.write(full, final_name)

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


def monitor_and_shutdown(app: Flask, timeout_seconds: int = 600):
    """Monitor the last request time. Exit if idle for timeout_seconds."""
    while True:
        time.sleep(10)
        elapsed = time.time() - app.config["LAST_REQUEST_TIME"]
        if elapsed > timeout_seconds:
            logger.info("No activity for %ds, shutting down.", timeout_seconds)
            upload_dir = app.config.get("UPLOAD_DIR")
            if upload_dir and os.path.isdir(upload_dir):
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
