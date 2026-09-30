"""
Per-capability toolsets — the ONE place that says, for every domain
CapabilityTag, which real tools `load_capabilities` attaches (Feature 063,
2026-09-24 "resolution" redesign; see
specs/repo/features/063-refactor-oversized-handlers/contracts/capability-resolution-loop.md).

Every capability works the same way, no exceptions: loading it attaches its
prompt text (build_instructions) AND the tools listed here, every round, for
as long as it stays in the chat's persisted `Session.active_capabilities`.
Two tool shapes exist, both attached identically:

- **Local function tools** (reminders, ledger query, media analysis, docx):
  the model emits a `function_call`, the orchestrator dispatches it to that
  capability's own `dispatch_direct_tool_call` and feeds back the result.
- **Morning MCP tools** (invoicing read/write, client read/write): all four
  capabilities share ONE remote Morning MCP server entry, restricted via
  `allowed_tools` to the union of every loaded capability's tool names, with
  `require_approval: "never"` uniformly - OpenAI executes those calls
  server-side (they come back as `mcp_call` items, never as calls this app
  dispatches). Approval before a write is NEVER an MCP-protocol handshake:
  it is the plain, domain-agnostic `approval_with_yes_no_buttons` tool of the
  on-demand cap_approval_with_buttons capability, loaded by whichever flow
  needs a sign-off - each write capability's own prompt lists the details the
  approval must state. Reading and writing are strictly separate: cap_invoicing_read
  never resolves names (that is cap_client_read's `resolve_client_name`).

Everything here is imported lazily by name from each capability's own
package, so src/backbone never hard-depends on every capability at import time.
"""
import logging
from typing import Any, Dict, List, Optional

from src.backbone.capability_tags import CapabilityTag
from src.tool_actions.morning_mcp import resolve_morning_mcp_connection

logger = logging.getLogger(__name__)

_MORNING_READ_TOOLS = (
    "list_invoices", "get_invoice_details", "get_financial_summary",
    "download_invoice_pdf",
)
_MORNING_INVOICE_WRITE_TOOLS = (
    "create_invoice", "create_transaction_account", "create_combo_document",
    "create_credit_note", "create_receipt", "create_combo_document_as_reference",
    "cancel_transaction_account",
)
_MORNING_CLIENT_READ_TOOLS = ("list_clients", "resolve_client_name", "get_client_details")
_MORNING_CLIENT_WRITE_TOOLS = ("add_client", "update_client")

# tag -> Morning MCP tool names this capability makes available. Write
# capabilities carry ONLY their write tools; reading is a separate capability
# the model itself decides to load.
MORNING_MCP_TOOL_NAMES: Dict[CapabilityTag, tuple] = {
    CapabilityTag.INVOICING_READ: _MORNING_READ_TOOLS,
    CapabilityTag.INVOICING_WRITE: _MORNING_INVOICE_WRITE_TOOLS,
    CapabilityTag.CLIENT_READ: _MORNING_CLIENT_READ_TOOLS,
    CapabilityTag.CLIENT_WRITE: _MORNING_CLIENT_WRITE_TOOLS,
}


def build_morning_mcp_tool(orchestrator, tags: List[CapabilityTag],
                            turn_context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """The single Morning MCP `tools` entry for every loaded Morning-backed
    capability in `tags`, or None when none is loaded / the server is
    unavailable / unconfigured (logged - the capability then simply has no
    tools this round, same fallback the old per-capability builders had)."""
    names: List[str] = []
    for tag in tags:
        for name in MORNING_MCP_TOOL_NAMES.get(tag, ()):
            if name not in names:
                names.append(name)
    if not names:
        return None
    locator = getattr(orchestrator, "morning_mcp_locator", None)
    if locator is None:
        return None
    turn_context = turn_context or {}
    connection = resolve_morning_mcp_connection(
        locator, orchestrator.config, turn_context.get("request_id"), turn_context.get("role"),
    )
    if connection is None:
        return None
    server_url, auth_token, mcp_config = connection
    return {
        "type": "mcp",
        "server_label": mcp_config.get("morning_server_label", "morning-invoices"),
        "server_url": server_url,
        "allowed_tools": names,
        "require_approval": "never",
        "headers": {"Authorization": f"Bearer {auth_token}"},
    }


def _local_tools_by_tag() -> Dict[CapabilityTag, Any]:
    """tag -> that capability's local tools (imported lazily by name from each
    capability's own package, so src/backbone never hard-depends on them)."""
    # pylint: disable=import-outside-toplevel
    from src.backbone.orchestration_tools import APPROVAL_WITH_YES_NO_BUTTONS_TOOL
    from src.capabilities.ledger_events.tools import QUERY_LEDGER_EVENTS_TOOL
    from src.capabilities.media_analysis.tools import ANALYZE_MEDIA_TOOL
    from src.capabilities.reminders.tools import (
        CREATE_REMINDER_TOOL, LIST_REMINDERS_TOOL, MODIFY_DELETE_REMINDER_TOOLS,
    )
    return {
        CapabilityTag.REMINDERS_READ: [LIST_REMINDERS_TOOL],
        CapabilityTag.REMINDERS_WRITE: [CREATE_REMINDER_TOOL] + list(MODIFY_DELETE_REMINDER_TOOLS),
        CapabilityTag.LEDGER_QUERY: [QUERY_LEDGER_EVENTS_TOOL],
        CapabilityTag.MEDIA_ANALYSIS: [ANALYZE_MEDIA_TOOL],
        CapabilityTag.APPROVAL_WITH_BUTTONS: [APPROVAL_WITH_YES_NO_BUTTONS_TOOL],
    }


def local_tools_for(orchestrator, tag: CapabilityTag, turn_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The local function tools capability `tag` attaches (possibly none)."""
    if tag == CapabilityTag.DOCX_WRITE:
        from src.capabilities.docx.handler import build_tools  # pylint: disable=import-outside-toplevel
        return build_tools(orchestrator, turn_context)
    return list(_local_tools_by_tag().get(tag, []))


def build_capability_tools(orchestrator, tags: List[CapabilityTag],
                            turn_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every domain tool for every loaded capability in `tags`, de-duplicated
    by tool name, rebuilt fresh every round from the persisted set."""
    tools: List[Dict[str, Any]] = []
    seen = set()
    for tag in tags:
        for tool in local_tools_for(orchestrator, tag, turn_context):
            if tool["name"] not in seen:
                seen.add(tool["name"])
                tools.append(tool)
    mcp_tool = build_morning_mcp_tool(orchestrator, tags, turn_context)
    if mcp_tool is not None:
        tools.append(mcp_tool)
    return tools


def local_tool_owners(orchestrator, tags: List[CapabilityTag],
                       turn_context: Dict[str, Any]) -> Dict[str, CapabilityTag]:
    """tool name -> owning tag, for every LOCAL function tool currently
    attached that this module dispatches (MCP tools are executed by OpenAI;
    the approval tool is executed by the orchestrator itself, since it ends
    the turn)."""
    owners: Dict[str, CapabilityTag] = {}
    for tag in tags:
        if tag == CapabilityTag.APPROVAL_WITH_BUTTONS:
            continue
        for tool in local_tools_for(orchestrator, tag, turn_context):
            owners.setdefault(tool["name"], tag)
    return owners


def dispatch_local_tool(orchestrator, tag: CapabilityTag, tool_name: str,
                         args: Dict[str, Any], turn_context: Dict[str, Any]) -> str:
    """Executes one local domain tool call on behalf of capability `tag`."""
    # pylint: disable=import-outside-toplevel
    if tag in (CapabilityTag.REMINDERS_READ, CapabilityTag.REMINDERS_WRITE):
        from src.capabilities.reminders.handler import dispatch_direct_tool_call
    elif tag == CapabilityTag.LEDGER_QUERY:
        from src.capabilities.ledger_events.handler import dispatch_direct_tool_call
    elif tag == CapabilityTag.MEDIA_ANALYSIS:
        from src.capabilities.media_analysis.handler import dispatch_direct_tool_call
    elif tag == CapabilityTag.DOCX_WRITE:
        from src.capabilities.docx.handler import dispatch_direct_tool_call
    else:
        return f"error: capability {tag.value} has no local tool {tool_name!r}"
    return dispatch_direct_tool_call(orchestrator, tool_name, args, turn_context)


def extract_local_calls(response, owners: Dict[str, CapabilityTag]) -> List[tuple]:
    """(call_id, tool_name, args, tag) for every function_call in `response`
    naming a currently-attached local domain tool. Malformed arguments are
    skipped (logged), never fatal."""
    import json  # pylint: disable=import-outside-toplevel
    calls = []
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call":
            continue
        name = getattr(item, "name", None)
        if name not in owners:
            continue
        try:
            args = json.loads(item.arguments)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Malformed %r function_call arguments discarded: %s", name, exc)
            continue
        calls.append((getattr(item, "call_id", ""), name, args, owners[name]))
    return calls
