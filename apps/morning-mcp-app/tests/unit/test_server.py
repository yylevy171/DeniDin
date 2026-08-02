"""Unit tests for server.py's /health endpoint (Feature 034, REQ-VER-002).

Uses a real Starlette TestClient against the real build_asgi_app()/
_make_health_handler() - no mocking of internal code (CONSTITUTION SS I/V).
"""
import sys
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from starlette.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from denidin_mcp_morning.server import build_asgi_app  # noqa: E402


@pytest.fixture
def temp_version_file(tmp_path):
    return tmp_path / "VERSION"


def test_health_includes_version_field(temp_version_file):
    temp_version_file.write_text("0.3.0\n")
    mcp = FastMCP("test-health-server")
    app = build_asgi_app(mcp, environment="dev", version_file=temp_version_file)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "dev"
    assert body["version"] == "0.3.0"


def test_health_version_falls_back_to_unknown_when_version_file_missing(temp_version_file):
    mcp = FastMCP("test-health-server-missing")
    app = build_asgi_app(mcp, environment="dev", version_file=temp_version_file)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["version"] == "unknown"


def test_health_version_falls_back_to_unknown_when_version_file_malformed(temp_version_file):
    temp_version_file.write_text("not-a-version!!\n")
    mcp = FastMCP("test-health-server-malformed")
    app = build_asgi_app(mcp, environment="dev", version_file=temp_version_file)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["version"] == "unknown"


def test_health_status_and_environment_fields_unchanged(temp_version_file):
    """Regression guard: version is additive, existing consumers of status/environment
    must not break (spec.md REQ-VER-002 backward-compatibility requirement)."""
    temp_version_file.write_text("1.2.3\n")
    mcp = FastMCP("test-health-server-compat")
    app = build_asgi_app(mcp, environment="prod", version_file=temp_version_file)
    client = TestClient(app)

    response = client.get("/health")

    body = response.json()
    assert set(["status", "environment", "version"]).issubset(body.keys())
    assert body["status"] == "ok"
    assert body["environment"] == "prod"
