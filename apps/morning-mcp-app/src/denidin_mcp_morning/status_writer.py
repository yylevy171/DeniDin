"""Writes the MCP tunnel status file consumed by the paired denidin-app environment.

Extracted from run_morning_mcp.sh's write_status_running/write_status_not_running
bash functions (019-env-separation) so the container entrypoint can call the same
logic directly, without a host-level ngrok-launching shell process.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def write_status_not_running(status_path: Path) -> None:
    """Write the safe default state, before any tunnel attempt."""
    _write(status_path, status="not running", server_url=None)


def write_status_running(status_path: Path, public_url: str) -> None:
    """Write the live state once ngrok has confirmed a public HTTPS tunnel."""
    _write(status_path, status="running", server_url=f"{public_url}/mcp")


def _write(status_path: Path, status: str, server_url: Optional[str]) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "server_url": server_url,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    status_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
