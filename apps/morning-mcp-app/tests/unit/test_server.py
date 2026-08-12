"""Unit tests for server.py's /health endpoint (Feature 034, REQ-VER-002).

Uses a real Starlette TestClient against the real build_asgi_app()/
_make_health_handler() - no mocking of internal code (CONSTITUTION SS I/V).
"""
import sys
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult
from starlette.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from denidin_mcp_morning.server import _call_with_error_boundary, build_asgi_app  # noqa: E402
from denidin_mcp_morning.tools import ClientNameNotResolvedError, ClientNotFoundError  # noqa: E402


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


def _fake_tool_name(func):
    """`_call_with_error_boundary` reads `func.__name__` for logging; a
    plain lambda has none of the confusion a real bound method would add."""
    func.__name__ = "fake_tool"
    return func


def test_call_with_error_boundary_returns_the_plain_result_on_success():
    """Two-outcomes-only contract (2026-08-12 follow-up): success is still
    a plain string, completely unchanged - only the failure path changed
    shape."""
    func = _fake_tool_name(lambda client: "success text")

    result = _call_with_error_boundary(func, "fake-client")

    assert result == "success text"
    assert not isinstance(result, CallToolResult)


def test_call_with_error_boundary_returns_isError_true_on_client_not_found():
    """The exact fix this test guards: a raised ClientNotFoundError must
    come back as a real CallToolResult(isError=True), not plain text
    indistinguishable from success (bugfix-028 B4(c), tightened 2026-08-12)."""

    def func(client):
        raise ClientNotFoundError("לא נמצא לקוח בשם הזה. (בדיקה)")

    result = _call_with_error_boundary(_fake_tool_name(func), "fake-client")

    assert isinstance(result, CallToolResult)
    assert result.isError is True
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    assert text == "לא נמצא לקוח בשם הזה. (בדיקה)"


def test_call_with_error_boundary_returns_isError_true_on_name_not_resolved():
    """Same fix, the other new failure class (2026-08-12 follow-up): a
    caller that skipped resolve_client_name must also come back as a real
    failure, not the old ordinary-text procedural refusal."""

    def func(client):
        raise ClientNameNotResolvedError("יש לפנות תחילה לכלי resolve_client_name...")

    result = _call_with_error_boundary(_fake_tool_name(func), "fake-client")

    assert isinstance(result, CallToolResult)
    assert result.isError is True


def test_call_with_error_boundary_never_leaks_raw_exception_text_on_error():
    """CONSTITUTION §X: friendly wording only, even in the new
    CallToolResult shape - the raw exception text must never surface."""

    def func(client):
        raise RuntimeError("raw internal detail, never shown to caller")

    result = _call_with_error_boundary(_fake_tool_name(func), "fake-client")

    assert isinstance(result, CallToolResult)
    assert result.isError is True
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    assert "raw internal detail" not in text
    assert "❌" in text


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
