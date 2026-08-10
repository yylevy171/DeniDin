"""Tests for the status-file writer used by the container entrypoint (019-env-separation).

Extracted from run_morning_mcp.sh's write_status_running/write_status_not_running
bash functions so the same logic is testable and reusable from the in-container
Python entrypoint. Real filesystem writes (tmp_path) - no mocking of internal code.
"""
import json
from datetime import datetime

from denidin_mcp_morning.status_writer import write_status_not_running, write_status_running
from denidin_mcp_morning.utils.time_utils import LOCAL_TZ


def test_write_status_running_writes_expected_shape(tmp_path):
    status_path = tmp_path / "morning_mcp_status.dev.json"

    write_status_running(status_path, "https://abc123.ngrok-free.app")

    data = json.loads(status_path.read_text())
    assert data["status"] == "running"
    assert data["server_url"] == "https://abc123.ngrok-free.app/mcp"
    # Israel-local ISO8601, parseable, carrying the real offset (bugfix-037,
    # CONSTITUTION SS II as amended 2026-08-10 - was UTC until then).
    parsed = datetime.fromisoformat(data["updated_at"])
    assert parsed.utcoffset() == parsed.astimezone(LOCAL_TZ).utcoffset()
    assert parsed.utcoffset() == LOCAL_TZ.utcoffset(parsed.replace(tzinfo=None))


def test_write_status_not_running_writes_expected_shape(tmp_path):
    status_path = tmp_path / "morning_mcp_status.dev.json"

    write_status_not_running(status_path)

    data = json.loads(status_path.read_text())
    assert data["status"] == "not running"
    assert data["server_url"] is None
    datetime.fromisoformat(data["updated_at"])  # does not raise


def test_write_status_creates_parent_directories(tmp_path):
    status_path = tmp_path / "nested" / "dir" / "morning_mcp_status.dev.json"

    write_status_not_running(status_path)

    assert status_path.exists()


def test_write_status_running_overwrites_previous_not_running(tmp_path):
    status_path = tmp_path / "morning_mcp_status.dev.json"

    write_status_not_running(status_path)
    write_status_running(status_path, "https://xyz789.ngrok-free.app")

    data = json.loads(status_path.read_text())
    assert data["status"] == "running"
    assert data["server_url"] == "https://xyz789.ngrok-free.app/mcp"
