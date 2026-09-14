"""
Invoicing/Morning capability (Feature 063) — Read step. Reaches the same remote
Morning MCP server `AIHandler._build_morning_mcp_tools` attaches today, over the same
real ngrok tunnel (REQ-063-03: no local import of denidin_mcp_morning code, same as
the legacy path) — new, standalone tool-attachment code, not shared with ai_handler.py.

Write (create_invoice/create_transaction_account/etc., with Group B reference-tool
approval-prompt building) is tracked in tasks.md's Deferred section.
"""
import logging
from typing import Any, Dict, List, Optional

from src.backbone.capability_tags import CapabilityTag
from src.models.message import AIRequest

logger = logging.getLogger(__name__)

# Read-only Morning MCP tools — no approval gate needed, mirrors the legacy read
# subset of _build_morning_mcp_tools' tool set (list_invoices/get_invoice_details/
# list_clients/resolve_client_name/get_client_details/get_financial_summary/
# download_invoice_pdf).
_READ_TOOL_NAMES = (
    "list_invoices", "get_invoice_details", "list_clients", "resolve_client_name",
    "get_client_details", "get_financial_summary", "download_invoice_pdf",
)


def build_read_tools(morning_mcp_locator, mcp_config: Dict) -> Optional[List[Dict]]:
    """Builds the Responses API `tools` entry for the Morning MCP server, read-only
    tool subset. Returns None if the server is unavailable or unconfigured — the
    step then proceeds without invoicing tools, same fallback shape as today."""
    if morning_mcp_locator is None:
        return None
    server_url = morning_mcp_locator.current_server_url()
    if not server_url:
        logger.warning("Morning MCP server unavailable - proceeding without invoicing_read tools")
        return None
    auth_token = (mcp_config or {}).get("morning_auth_token")
    if not auth_token:
        logger.warning("mcp.morning_auth_token not configured - proceeding without invoicing_read tools")
        return None

    return [{
        "type": "mcp",
        "server_label": (mcp_config or {}).get("morning_server_label", "morning-invoices"),
        "server_url": server_url,
        "require_approval": {"never": {"tool_names": list(_READ_TOOL_NAMES)}},
        "headers": {"Authorization": f"Bearer {auth_token}"},
    }]


def read_step(orchestrator, request: AIRequest, accumulated_context: str, note: str,
              turn_context: Dict[str, Any]) -> str:
    """Invoicing — Read step: attaches the read-only Morning MCP tools and lets the
    model answer directly (no local dispatch loop needed for read tools)."""
    del note, turn_context
    morning_mcp_locator = getattr(orchestrator, "morning_mcp_locator", None)
    mcp_config = getattr(orchestrator.config, "mcp", {}) or {}
    tools = build_read_tools(morning_mcp_locator, mcp_config)

    return str(orchestrator.call_capability_step(
        tag=CapabilityTag.INVOICING_READ,
        request=request,
        accumulated_context=accumulated_context,
        tools=tools,
    ))
