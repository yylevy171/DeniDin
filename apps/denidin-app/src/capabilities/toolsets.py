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
  the model emits a `function_call`, the backbone dispatches it to that
  capability's own `dispatch_direct_tool_call` and feeds back the result.
- **Morning MCP tools** (invoicing read/write, client read/write): each loaded
  capability gets its OWN remote Morning MCP server entry - same server URL and
  token, its own `server_label` and its own fixed `allowed_tools` (see
  build_morning_mcp_tools for why), with
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
_REMINDER_WRITE_TOOLS = ("create_reminder", "modify_reminder", "delete_reminder")
_AGREEMENTS_WRITE_TOOLS = ("update_agreement", "update_component", "add_component",
                           "set_component_status", "set_agreement_status")

# Every tool that changes something (a Morning document/client, a reminder) - the
# writes an approval answers. The backbone's approved-turn guard (Item4) counts
# their executions.
WRITE_TOOL_NAMES = frozenset(_MORNING_INVOICE_WRITE_TOOLS + _MORNING_CLIENT_WRITE_TOOLS
                             + _REMINDER_WRITE_TOOLS + _AGREEMENTS_WRITE_TOOLS)

# tag -> the write tools that capability carries (what an approval answered while it
# was loaded could have been about).
WRITE_TOOLS_BY_TAG: Dict[CapabilityTag, tuple] = {
    CapabilityTag.INVOICING_WRITE: _MORNING_INVOICE_WRITE_TOOLS,
    CapabilityTag.CLIENT_WRITE: _MORNING_CLIENT_WRITE_TOOLS,
    CapabilityTag.REMINDERS_WRITE: _REMINDER_WRITE_TOOLS,
    CapabilityTag.AGREEMENTS_WRITE: _AGREEMENTS_WRITE_TOOLS,
}

# tag -> Morning MCP tool names this capability makes available. Write
# capabilities carry ONLY their write tools; reading is a separate capability
# the model itself decides to load.
MORNING_MCP_TOOL_NAMES: Dict[CapabilityTag, tuple] = {
    CapabilityTag.INVOICING_READ: _MORNING_READ_TOOLS,
    CapabilityTag.INVOICING_WRITE: _MORNING_INVOICE_WRITE_TOOLS,
    CapabilityTag.CLIENT_READ: _MORNING_CLIENT_READ_TOOLS,
    CapabilityTag.CLIENT_WRITE: _MORNING_CLIENT_WRITE_TOOLS,
}


def morning_server_label_for(base_label: str, tag: CapabilityTag) -> str:
    """The Morning MCP `server_label` for one capability's entry, e.g.
    'morning-invoices' + cap_invoicing_read -> 'morning-invoices-invoicing-read'."""
    return f"{base_label}-{tag.value.removeprefix('cap_').replace('_', '-')}"


def build_morning_mcp_tools(backbone, tags: List[CapabilityTag],
                            turn_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """One Morning MCP `tools` entry per loaded Morning-backed capability in
    `tags` - all on the same server URL/token, each with its own server_label
    and its own fixed `allowed_tools`. Empty when none is loaded / the server
    is unavailable / unconfigured (logged - the capabilities then simply have
    no tools this round).

    Why one entry per capability (2026-10-01, T1): OpenAI fetches an MCP
    server's tool list ONCE per previous_response_id chain, keyed by
    server_label, the first time that label appears - widening the same
    label's `allowed_tools` later in the chain is silently ignored. With one
    shared entry, a capability loaded mid-turn never reached the model
    (T1: cap_invoicing_read loaded, list_invoices never callable). Verified
    against the real API: a label added mid-chain gets its own listing and
    its tools are callable; an existing label's widened allowed_tools are not.
    Each label's tool set here is fixed, so it never needs re-listing."""
    loaded = [tag for tag in dict.fromkeys(tags) if MORNING_MCP_TOOL_NAMES.get(tag)]
    if not loaded:
        return []
    turn_context = turn_context or {}
    connection = backbone.morning_mcp_connection(turn_context.get("request_id"), turn_context.get("role"))
    if connection is None:
        return []
    base_label = connection[2].get("morning_server_label", "morning-invoices")
    return [
        backbone.morning_mcp_entry(
            connection,
            server_label=morning_server_label_for(base_label, tag),
            allowed_tools=list(MORNING_MCP_TOOL_NAMES[tag]),
            require_approval="never",
        )
        for tag in loaded
    ]


def _local_tools_by_tag() -> Dict[CapabilityTag, Any]:
    """tag -> that capability's local tools (imported lazily by name from each
    capability's own package, so src/backbone never hard-depends on them)."""
    # pylint: disable=import-outside-toplevel
    from src.backbone.resolution_tools import APPROVAL_WITH_YES_NO_BUTTONS_TOOL
    from src.capabilities.agreements.tools import AGREEMENTS_READ_TOOLS, AGREEMENTS_WRITE_TOOLS
    from src.capabilities.media_analysis.tools import ANALYZE_MEDIA_TOOL
    from src.tool_actions.tool_schemas import (
        CREATE_REMINDER_TOOL, DELETE_REMINDER_TOOL, LIST_REMINDERS_TOOL, MODIFY_REMINDER_TOOL,
        QUERY_LEDGER_EVENTS_TOOL,
    )
    return {
        CapabilityTag.REMINDERS_READ: [LIST_REMINDERS_TOOL],
        CapabilityTag.REMINDERS_WRITE: [CREATE_REMINDER_TOOL, MODIFY_REMINDER_TOOL, DELETE_REMINDER_TOOL],
        CapabilityTag.AGREEMENTS_READ: list(AGREEMENTS_READ_TOOLS),
        CapabilityTag.AGREEMENTS_WRITE: list(AGREEMENTS_WRITE_TOOLS),
        CapabilityTag.LEDGER_QUERY: [QUERY_LEDGER_EVENTS_TOOL],
        CapabilityTag.MEDIA_ANALYSIS: [ANALYZE_MEDIA_TOOL],
        CapabilityTag.APPROVAL_WITH_BUTTONS: [APPROVAL_WITH_YES_NO_BUTTONS_TOOL],
    }


def local_tools_for(backbone, tag: CapabilityTag, turn_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The local function tools capability `tag` attaches (possibly none)."""
    if tag == CapabilityTag.DOCX_WRITE:
        from src.capabilities.docx.handler import build_tools  # pylint: disable=import-outside-toplevel
        return build_tools(backbone, turn_context)
    return list(_local_tools_by_tag().get(tag, []))


def build_capability_tools(backbone, tags: List[CapabilityTag],
                            turn_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every domain tool for every loaded capability in `tags`, de-duplicated
    by tool name, rebuilt fresh every round from the persisted set."""
    tools: List[Dict[str, Any]] = []
    seen = set()
    for tag in tags:
        for tool in local_tools_for(backbone, tag, turn_context):
            if tool["name"] not in seen:
                seen.add(tool["name"])
                tools.append(tool)
    tools.extend(build_morning_mcp_tools(backbone, tags, turn_context))
    return tools


def local_tool_owners(backbone, tags: List[CapabilityTag],
                       turn_context: Dict[str, Any]) -> Dict[str, CapabilityTag]:
    """tool name -> owning tag, for every LOCAL function tool currently
    attached that this module dispatches (MCP tools are executed by OpenAI;
    the approval tool is executed by the backbone itself, since it ends
    the turn)."""
    owners: Dict[str, CapabilityTag] = {}
    for tag in tags:
        if tag == CapabilityTag.APPROVAL_WITH_BUTTONS:
            continue
        for tool in local_tools_for(backbone, tag, turn_context):
            owners.setdefault(tool["name"], tag)
    return owners


def dispatch_local_tool(backbone, tag: CapabilityTag, tool_name: str,
                         args: Dict[str, Any], turn_context: Dict[str, Any]) -> str:
    """Executes one local domain tool call on behalf of capability `tag`."""
    # pylint: disable=import-outside-toplevel
    if tag in (CapabilityTag.REMINDERS_READ, CapabilityTag.REMINDERS_WRITE):
        from src.capabilities.reminders.handler import dispatch_direct_tool_call
    elif tag in (CapabilityTag.AGREEMENTS_READ, CapabilityTag.AGREEMENTS_WRITE):
        from src.capabilities.agreements.handler import dispatch_direct_tool_call
    elif tag == CapabilityTag.LEDGER_QUERY:
        from src.capabilities.ledger_events.handler import dispatch_direct_tool_call
    elif tag == CapabilityTag.MEDIA_ANALYSIS:
        from src.capabilities.media_analysis.handler import dispatch_direct_tool_call
    elif tag == CapabilityTag.DOCX_WRITE:
        from src.capabilities.docx.handler import dispatch_direct_tool_call
    else:
        return f"error: capability {tag.value} has no local tool {tool_name!r}"
    return dispatch_direct_tool_call(backbone, tool_name, args, turn_context)


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
