"""
Invoicing/Morning capability (Feature 063) — Read + Write steps. Reaches the same
remote Morning MCP server `AIHandler._build_morning_mcp_tools` attaches today, over
the same real ngrok tunnel (REQ-063-03: no local import of denidin_mcp_morning code,
same as the legacy path) — new, standalone tool-attachment code, not shared with
ai_handler.py.

Write (create_invoice/create_transaction_account/etc.) uses OpenAI's own native MCP
approval mechanism (`require_approval`) plus the existing, unmodified
`PendingApprovalManager` (REQ-063-03) - same real approval round-trip Feature 022
already implements, reimplemented as new, standalone code (REQ-063-07). Simplified
relative to the legacy path: no bugfix-038 Group B reference-document-lookup
enrichment of the approval prompt (tracked as a follow-up refinement) - the fallback
text still names the action/client/amount whenever the model's own call arguments
carry them.
"""
import logging
from typing import Any, Dict, List, Optional

from src.backbone.capability_tags import CapabilityTag
from src.capabilities.invoicing.tools import (
    APPROVAL_REQUIRED_MCP_TOOLS,
    build_fallback_text,
    count_executed_calls,
    find_approval_request,
)
from src.capabilities.reminders.tools import is_affirmative_reply
from src.constants.error_messages import BACKBONE_CAPABILITY_NOT_CONFIGURED
from src.managers.pending_approval_manager import PendingApproval
from src.models.message import AIRequest, AIResponse, NO_REPLY_SENTINEL
from src.models.user import Role
from src.utils.time_utils import now_local

logger = logging.getLogger(__name__)

APPROVAL_QUESTION = "לאשר? (כן/לא)"

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


def build_write_tools(morning_mcp_locator, mcp_config: Dict) -> Optional[List[Dict]]:
    """Same Morning MCP server as build_read_tools, but with the write-tool subset
    gated behind OpenAI's own native `require_approval` mechanism - a call to any
    of APPROVAL_REQUIRED_MCP_TOOLS comes back as a pending `mcp_approval_request`
    instead of executing, exactly like the legacy path's `_assemble_tools`."""
    if morning_mcp_locator is None:
        return None
    server_url = morning_mcp_locator.current_server_url()
    if not server_url:
        logger.warning("Morning MCP server unavailable - proceeding without invoicing_write tools")
        return None
    auth_token = (mcp_config or {}).get("morning_auth_token")
    if not auth_token:
        logger.warning("mcp.morning_auth_token not configured - proceeding without invoicing_write tools")
        return None

    return [{
        "type": "mcp",
        "server_label": (mcp_config or {}).get("morning_server_label", "morning-invoices"),
        "server_url": server_url,
        "require_approval": {
            "always": {"tool_names": list(APPROVAL_REQUIRED_MCP_TOOLS)},
            "never": {"tool_names": list(_READ_TOOL_NAMES)},
        },
        "headers": {"Authorization": f"Bearer {auth_token}"},
    }]


def propose_write(orchestrator, request: AIRequest, accumulated_context: str, note: str,
                   turn_context: Dict[str, Any]) -> str:
    """Invoicing — Write step: attaches the Morning MCP tools (write subset gated
    behind approval) and lets the model act; a document-creating call comes back
    as a pending `mcp_approval_request`, tracked via the existing, unmodified
    `PendingApprovalManager` (REQ-063-03) - same real approval round-trip
    Feature 022 already implements, reimplemented here as new code (REQ-063-07).

    2026-09-16 (closing a real, structural gap found via T7/T10 investigation,
    fixed properly per explicit user direction: adapt the shared tool, not the
    capability): this used to be the ONLY domain capability handler that
    bypassed `orchestrator.call_capability_step` entirely, reimplementing the
    whole call inline - because it needs the raw `response` object (to detect
    an mcp_approval_request via find_approval_request), and call_capability_step
    used to only ever return plain output_text. That reimplementation silently
    dropped `_turn_conversation_history` and BACKBONE_TOOLS, which is why a
    default the constitution states plainly (payment_method defaulting to
    bank_transfer) got asked-about anyway mid-flow - the model genuinely
    couldn't see prior turns. Fixed at the root: call_capability_step now takes
    `return_response=True` to hand back the raw response instead of forcing a
    second call path - every capability step, write flows included, goes
    through the one shared method."""
    del note
    if orchestrator.pending_approval_manager is None:
        return BACKBONE_CAPABILITY_NOT_CONFIGURED

    morning_mcp_locator = getattr(orchestrator, "morning_mcp_locator", None)
    mcp_config = getattr(orchestrator.config, "mcp", {}) or {}
    tools = build_write_tools(morning_mcp_locator, mcp_config)

    response = orchestrator.call_capability_step(
        tag=CapabilityTag.INVOICING_WRITE,
        request=request,
        accumulated_context=accumulated_context,
        tools=tools,
        return_response=True,
    )
    response_text = (getattr(response, "output_text", "") or "").strip()

    approval_request = find_approval_request(response)
    if approval_request is None:
        return response_text or "לא זוהתה בקשה ליצירת/עדכון מסמך."

    chat_id = turn_context.get("chat_id") or request.chat_id
    orchestrator.pending_approval_manager.set(
        chat_id,
        PendingApproval(
            response_id=getattr(response, "id", ""),
            approval_request_id=approval_request.id,
            tool_name=approval_request.name,
            arguments=approval_request.arguments,
            server_label=approval_request.server_label,
            created_at=now_local().isoformat(),
        ),
    )
    details = build_fallback_text(approval_request.name, approval_request.arguments)
    return f"{response_text}\n\n{details}" if response_text else details


def _resolve_approval(orchestrator, pending: PendingApproval, request: AIRequest) -> tuple:
    """Resolves a pending MCP approval via a follow-up call chained by
    `previous_response_id` (mirrors ai_handler.py's `_call_openai_approval_api` +
    duplicate-execution guard - a real, billed 2026-08-03 production incident:
    the approved action must never execute more than once). `max_retries=0`
    for the same reason the legacy path disables retry here: a failed attempt
    must surface as a clean error, never silently re-execute an already-approved
    document-creating call.

    Returns (reply_text, mcp_calls) - 2026-09-15 (closing a real gap found via
    T7): the actual create_invoice/etc. call that executes here is this
    response's own mcp_call item, but this response never passed through
    call_capability_step/_resolve_backbone_tool_calls (the only two places that
    used to populate BackboneOrchestrator._turn_mcp_calls), so the resulting
    AIResponse.mcp_calls was always empty even on a fully successful create -
    tests/other code reading ai_response.mcp_calls (e.g. the billed E2E suite's
    _calls_for helper) saw nothing despite a real, successful execution."""
    approval_item = {
        "type": "mcp_approval_response",
        "approval_request_id": pending.approval_request_id,
        "approve": True,
    }
    morning_mcp_locator = getattr(orchestrator, "morning_mcp_locator", None)
    mcp_config = getattr(orchestrator.config, "mcp", {}) or {}
    tools = build_write_tools(morning_mcp_locator, mcp_config)

    try:
        response = orchestrator.client.with_options(max_retries=0).responses.create(
            model=request.model,
            instructions=orchestrator.build_instructions(CapabilityTag.INVOICING_WRITE, "", request.timestamp),
            input=[approval_item],
            previous_response_id=pending.response_id,
            max_output_tokens=request.max_tokens,
            **({"tools": tools} if tools else {}),
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Approval-resolution call failed for tool=%r: %s", pending.tool_name, exc)
        return "⚠️ הפעולה נכשלה. נסו שוב.", []

    mcp_calls = orchestrator._extract_mcp_call_items(response)  # pylint: disable=protected-access

    executions = count_executed_calls(response, pending.tool_name)
    if executions > 1:
        logger.error(
            "DUPLICATE EXECUTION DETECTED: tool=%r executed %d times in one approval "
            "resolution (expected exactly 1) - check Morning manually.",
            pending.tool_name, executions,
        )
        return "⚠️ ייתכן שהפעולה בוצעה יותר מפעם אחת — יש לבדוק ידנית במורנינג.", mcp_calls
    if executions == 0:
        logger.warning("Approval resolution produced zero executions of tool=%r", pending.tool_name)
        return getattr(response, "output_text", "") or "⚠️ הפעולה לא בוצעה.", mcp_calls
    return getattr(response, "output_text", "") or "✅ הפעולה בוצעה.", mcp_calls


def resolve_button_tap(orchestrator, chat_id: str, selected_id: str, stanza_id: str,
                        request: Optional[AIRequest]) -> Optional[AIResponse]:
    """Resolves a "כן"/"לא" interactive-button tap against a pending
    invoicing_write MCP approval. Returns None for a stale tap (no pending
    approval, or stanza_id mismatch) - same staleness guard as reminders'
    resolve_button_tap / AIHandler.resolve_button_tap."""
    pending = orchestrator.pending_approval_manager.get(chat_id)
    if pending is None or pending.sent_message_id != stanza_id:
        return None

    orchestrator.pending_approval_manager.clear(chat_id)

    if selected_id != "denidin_approve":
        return AIResponse(
            request_id=(request.request_id if request else ""),
            response_text="בוטל.",
            tokens_used=0, prompt_tokens=0, completion_tokens=0,
            model=(request.model if request else ""),
            finish_reason="stop",
            timestamp=int(now_local().timestamp()),
        )

    if request:
        reply_text, mcp_calls = _resolve_approval(orchestrator, pending, request)
    else:
        reply_text, mcp_calls = "⚠️ הפעולה נכשלה.", []
    should_reply = reply_text.strip() != NO_REPLY_SENTINEL
    # 2026-09-15: approval-resolution turns bypass get_response's normal
    # _finalize_response entirely, so they need their own session-persistence
    # call - same real gap fix as _finalize_response's own (see
    # BackboneOrchestrator._persist_turn's docstring). This tool family is
    # RBAC-gated GODFATHER/ADMIN-only.
    if request is not None:
        orchestrator._persist_turn(  # pylint: disable=protected-access
            request, reply_text, should_reply, chat_id, Role.GODFATHER,
            None, None, None, None, False, None,
        )
    return AIResponse(
        request_id=(request.request_id if request else ""),
        response_text=reply_text,
        tokens_used=0, prompt_tokens=0, completion_tokens=0,
        model=(request.model if request else ""),
        finish_reason="stop",
        timestamp=int(now_local().timestamp()),
        should_reply=should_reply,
        mcp_calls=mcp_calls,
    )


def resolve_typed_reply(orchestrator, request: AIRequest, chat_id: str) -> Optional[AIResponse]:
    """Resolves a typed "כן"/"לא" reply against a pending invoicing_write MCP
    approval - the local equivalent of AIHandler._resolve_pending_approval,
    reimplemented as new code (REQ-063-07). Checked by
    BackboneOrchestrator.get_response BEFORE Intent Identification/Planning run.

    Returns the final AIResponse if approved. None if declined/unrecognized -
    same contract as reminders' resolve_typed_reply: the caller then processes
    this same message as a normal fresh turn."""
    pending = orchestrator.pending_approval_manager.get(chat_id)
    if pending is None:
        return None

    if not is_affirmative_reply(request.user_prompt):
        orchestrator.pending_approval_manager.clear(chat_id)
        return None

    orchestrator.pending_approval_manager.clear(chat_id)
    reply_text, mcp_calls = _resolve_approval(orchestrator, pending, request)
    should_reply = reply_text.strip() != NO_REPLY_SENTINEL
    # 2026-09-15: see resolve_button_tap's own comment above - same real gap fix.
    orchestrator._persist_turn(  # pylint: disable=protected-access
        request, reply_text, should_reply, chat_id, Role.GODFATHER,
        None, None, None, None, False, None,
    )
    return AIResponse(
        request_id=request.request_id,
        response_text=reply_text,
        tokens_used=0, prompt_tokens=0, completion_tokens=0,
        model=request.model,
        finish_reason="stop",
        timestamp=request.timestamp or int(now_local().timestamp()),
        should_reply=should_reply,
        mcp_calls=mcp_calls,
    )
