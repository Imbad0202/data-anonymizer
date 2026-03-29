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
