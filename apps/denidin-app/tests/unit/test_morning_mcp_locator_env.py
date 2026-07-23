"""Env-isolation tests for MorningMcpLocator (019-env-separation, US2/FR-010).

Confirms MorningMcpLocator resolves purely from its injected config path
(mcp_config['morning_status_file']) with no hardcoded fallback to any other
path - the property that makes cross-environment MCP resolution structurally
impossible when dev/prod point at different status-file paths (per the
per-environment shared-volume mounts in docker/docker-compose.dev.yml/prod.yml).
"""
import json
from datetime import datetime, timezone

from src.handlers.morning_mcp_locator import MorningMcpLocator


def _write_status(path, status="running", server_url="https://example.ngrok-free.app/mcp"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "status": status,
        "server_url": server_url,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }))


def test_locator_resolves_only_its_configured_path(tmp_path):
    dev_status_path = tmp_path / "mcp-status-dev" / "morning_mcp_status.dev.json"
    prod_status_path = tmp_path / "mcp-status-prod" / "morning_mcp_status.prod.json"

    _write_status(dev_status_path, server_url="https://dev-tunnel.ngrok-free.app/mcp")
    _write_status(prod_status_path, server_url="https://prod-tunnel.ngrok-free.app/mcp")

    dev_locator = MorningMcpLocator({"morning_status_file": str(dev_status_path)})
    prod_locator = MorningMcpLocator({"morning_status_file": str(prod_status_path)})

    assert dev_locator.current_server_url() == "https://dev-tunnel.ngrok-free.app/mcp"
    assert prod_locator.current_server_url() == "https://prod-tunnel.ngrok-free.app/mcp"


def test_locator_never_falls_back_to_a_different_status_file(tmp_path):
    # Only the "prod" file exists. A locator configured for the (nonexistent)
    # dev path must report unavailable, never silently read prod's file.
    prod_status_path = tmp_path / "mcp-status-prod" / "morning_mcp_status.prod.json"
    _write_status(prod_status_path, server_url="https://prod-tunnel.ngrok-free.app/mcp")

    dev_status_path = tmp_path / "mcp-status-dev" / "morning_mcp_status.dev.json"
    dev_locator = MorningMcpLocator({"morning_status_file": str(dev_status_path)})

    assert dev_locator.current_server_url() is None
