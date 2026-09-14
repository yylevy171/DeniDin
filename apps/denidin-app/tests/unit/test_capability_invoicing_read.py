"""Unit tests for the Invoicing/Morning — Read capability handler (T047)."""
from unittest.mock import MagicMock

from src.capabilities.invoicing.handler import build_read_tools, read_step


def test_build_read_tools_returns_none_when_locator_missing():
    assert build_read_tools(None, {}) is None


def test_build_read_tools_returns_none_when_server_unavailable():
    locator = MagicMock()
    locator.current_server_url.return_value = None
    assert build_read_tools(locator, {"morning_auth_token": "abc"}) is None


def test_build_read_tools_returns_none_when_token_missing():
    locator = MagicMock()
    locator.current_server_url.return_value = "https://example.ngrok.io/mcp"
    assert build_read_tools(locator, {}) is None


def test_build_read_tools_returns_mcp_tool_entry():
    locator = MagicMock()
    locator.current_server_url.return_value = "https://example.ngrok.io/mcp"
    tools = build_read_tools(locator, {"morning_auth_token": "abc123"})

    assert tools[0]["type"] == "mcp"
    assert tools[0]["server_url"] == "https://example.ngrok.io/mcp"
    assert tools[0]["headers"]["Authorization"] == "Bearer abc123"
    assert "list_invoices" in tools[0]["require_approval"]["never"]["tool_names"]


def test_read_step_attaches_tools_and_calls_capability_step():
    orchestrator = MagicMock()
    orchestrator.morning_mcp_locator.current_server_url.return_value = "https://example.ngrok.io/mcp"
    orchestrator.config.mcp = {"morning_auth_token": "abc123"}
    orchestrator.call_capability_step.return_value = "Invoice #123 is paid."
    request = MagicMock()

    result = read_step(orchestrator, request, "", "", {})

    assert result == "Invoice #123 is paid."
    _, kwargs = orchestrator.call_capability_step.call_args
    assert kwargs["tools"][0]["type"] == "mcp"
