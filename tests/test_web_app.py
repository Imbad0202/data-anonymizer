"""Tests for the Flask web UI API endpoints."""

import json
import os
import sys

import pytest

# Ensure project root is on path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from gui.web_app import create_app


@pytest.fixture
def client(tmp_path):
    """Create a Flask test client with a temporary upload directory."""
    app = create_app(upload_dir=str(tmp_path))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"

    def test_health_returns_version(self, client):
        resp = client.get("/api/health")
        data = json.loads(resp.data)
        assert "version" in data


class TestUpload:
    def test_upload_single_file(self, client, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("張三的電話 0912345678", encoding="utf-8")
        with open(test_file, "rb") as f:
            resp = client.post("/api/upload", data={"files": (f, "test.txt")},
                               content_type="multipart/form-data")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "test.txt"
        assert "id" in data["files"][0]
        assert data["files"][0]["size"] > 0

    def test_upload_multiple_files(self, client, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("內容一", encoding="utf-8")
        f2.write_text("內容二", encoding="utf-8")
        with open(f1, "rb") as fa, open(f2, "rb") as fb:
            resp = client.post("/api/upload",
                               data={"files": [(fa, "a.txt"), (fb, "b.txt")]},
                               content_type="multipart/form-data")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["files"]) == 2

    def test_upload_no_files_returns_400(self, client):
        resp = client.post("/api/upload", data={},
                           content_type="multipart/form-data")
        assert resp.status_code == 400


class TestPreview:
    def _upload_file(self, client, tmp_path, filename, content):
        """Helper: upload a file and return its file_id."""
        fpath = tmp_path / filename
        fpath.write_text(content, encoding="utf-8")
        with open(fpath, "rb") as f:
            resp = client.post("/api/upload", data={"files": (f, filename)},
                               content_type="multipart/form-data")
        return json.loads(resp.data)["files"][0]["id"]

    def test_preview_returns_original_and_anonymized(self, client, tmp_path):
        file_id = self._upload_file(client, tmp_path, "test.txt",
                                     "張三的電話 0912345678")
        resp = client.post("/api/preview",
                           data=json.dumps({"file_id": file_id, "mode": "reversible", "use_ner": False}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "original" in data
        assert "anonymized" in data
        assert "spans" in data
        assert "summary" in data
        assert "0912345678" in data["original"]
        # Phone should be detected
        assert data["summary"].get("PHONE", 0) > 0

    def test_preview_invalid_file_id_returns_404(self, client):
        resp = client.post("/api/preview",
                           data=json.dumps({"file_id": "nonexistent", "mode": "reversible", "use_ner": False}),
                           content_type="application/json")
        assert resp.status_code == 404

    def test_preview_no_pii_found(self, client, tmp_path):
        file_id = self._upload_file(client, tmp_path, "clean.txt",
                                     "今天天氣很好")
        resp = client.post("/api/preview",
                           data=json.dumps({"file_id": file_id, "mode": "reversible", "use_ner": False}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["original"] == data["anonymized"]
        assert len(data["spans"]) == 0


class TestProcess:
    def _upload_file(self, client, tmp_path, filename, content):
        fpath = tmp_path / filename
        fpath.write_text(content, encoding="utf-8")
        with open(fpath, "rb") as f:
            resp = client.post("/api/upload", data={"files": (f, filename)},
                               content_type="multipart/form-data")
        return json.loads(resp.data)["files"][0]["id"]

    def test_process_returns_sse_stream(self, client, tmp_path):
        fid = self._upload_file(client, tmp_path, "test.txt", "張三 0912345678")
        resp = client.post("/api/process",
                           data=json.dumps({"file_ids": [fid], "mode": "reversible", "use_ner": False}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/event-stream")
        # Collect SSE events
        text = resp.get_data(as_text=True)
        assert "progress" in text
        assert "done" in text

    def test_process_empty_file_ids_returns_400(self, client):
        resp = client.post("/api/process",
                           data=json.dumps({"file_ids": [], "mode": "reversible", "use_ner": False}),
                           content_type="application/json")
        assert resp.status_code == 400
