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
