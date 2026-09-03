"""
AIHandler - Handles OpenAI API interactions with retry logic and error handling
Phase 5: US3 - Error Handling & Resilience
Phase 5 (002+007): Memory system integration
Phase 6: RBAC (Role-Based Access Control)
"""
import copy
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast, Optional, List, Dict

from openai import OpenAI, APITimeoutError, RateLimitError, APIError
from src.models.config import AppConfiguration
from src.models.message import (
    WhatsAppMessage, AIRequest, AIResponse,
    NO_REPLY_SENTINEL as _NO_REPLY_SENTINEL,
)
from src.utils.logger import get_logger, read_version, DEFAULT_VERSION_FILE
from src.utils.time_utils import now_local, local_from_timestamp, to_local
from src.managers.session_manager import SessionManager, Session
from src.managers.memory_manager import MemoryManager
from src.managers.ledger_event_manager import LedgerEventManager, is_incomplete_capture
from src.managers.user_manager import UserManager
from src.managers.pending_approval_manager import (
    PendingApprovalManager, PendingApproval, BUTTON_ID_APPROVE
)
from src.managers.reminder_manager import (
    ReminderManager, ReminderPastDateError, ReminderCapExceededError, ReminderNotFoundError,
    InvalidRecurrenceError, OccurrenceNotFoundError,
)
from src.managers.pending_local_tool_approval_manager import (
    PendingLocalToolApprovalManager, PendingLocalToolApproval,
)
from src.models.user import Role
from src.handlers.morning_mcp_locator import MorningMcpLocator
from src.constants.error_messages import (
    APPROVAL_FAILED_TRY_AGAIN, APPROVAL_POSSIBLY_DUPLICATED, LEDGER_FOLLOWUP_FAILED_TRY_AGAIN,
    REMINDER_ACTION_FAILED_TRY_AGAIN, REMINDER_PAST_DATE_REJECTED, REMINDER_CAP_EXCEEDED,
)

logger = get_logger(__name__)

# 2026-08-25, explicit user directive after test_monthly_income_aggregation's
# zero-match failure was undiagnosable from logs: the OpenAI SDK's own DEBUG
# HTTP logging (openai._base_client / httpcore) logs REQUEST OPTIONS and
# RESPONSE HEADERS only - never a response BODY, so there was previously no
# way to see what a model's function_call actually asked for, or what a
# response actually contained, short of ad hoc re-instrumentation after the
# fact. These two helpers are called at every responses.create() call site in
# this app (and, via import, in accounting_reconciliation_service.py and
# image_extractor.py) - deliberately verbose, deliberately everywhere: "I want
# logs of EVERYTHING so we can get to the bottom of what is going on" (disk
# space is explicitly not a constraint here). Never raises - a logging
# failure must never break the actual call it's describing.

def _log_outgoing_request(context: str, kwargs: Dict[str, Any]) -> None:
    """Logs exactly what's about to be sent to responses.create(), mirroring
    _log_raw_response for the outgoing side. `context` is a short label
    identifying the call site (e.g. "get_response (initial call)",
    "_call_openai_query_ledger_events_followup_api")."""
    try:
        tools = kwargs.get("tools") or []
        tool_names = [
            t.get("name") or t.get("server_label") or t.get("type") for t in tools
        ]
        logger.debug(
            f"[RAWLOG] {context} >>> SENDING: model={kwargs.get('model')!r}, "
            f"tools={tool_names!r}, input={kwargs.get('input')!r}, "
            f"previous_response_id={kwargs.get('previous_response_id')!r}, "
            f"instructions_len={len(kwargs.get('instructions') or '')}, "
            f"max_output_tokens={kwargs.get('max_output_tokens')!r}"
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[RAWLOG] {context} >>> SENDING: failed to log outgoing request: {e}", exc_info=True)


def _log_raw_response(context: str, response) -> None:
    """Logs the FULL raw content of a responses.create() result: every
    output item verbatim (a function_call's raw, unparsed `arguments`
    string and `call_id`; a message's full content; an mcp_call/
    mcp_approval_request's name/arguments/output/error), plus output_text,
    status, and usage. `context` matches the paired _log_outgoing_request
    call for the same request."""
    try:
        items_repr = []
        for item in (getattr(response, "output", None) or []):
            item_type = getattr(item, "type", None)
            detail: Dict[str, Any] = {"type": item_type}
            if item_type == "function_call":
                detail["name"] = getattr(item, "name", None)
                detail["call_id"] = getattr(item, "call_id", None)
                detail["arguments_raw"] = getattr(item, "arguments", None)
            elif item_type == "message":
                detail["content"] = getattr(item, "content", None)
            elif item_type in ("mcp_call", "mcp_approval_request"):
                detail["id"] = getattr(item, "id", None)
                detail["name"] = getattr(item, "name", None)
                detail["arguments"] = getattr(item, "arguments", None)
                detail["output"] = getattr(item, "output", None)
                detail["error"] = getattr(item, "error", None)
            elif item_type == "mcp_list_tools":
                tools_list = getattr(item, "tools", None) or []
                detail["tool_count"] = len(tools_list)
                detail["tool_names"] = [getattr(t, "name", None) for t in tools_list]
            items_repr.append(detail)
        logger.debug(
            f"[RAWLOG] {context} <<< RECEIVED: response.id={getattr(response, 'id', None)!r}, "
            f"status={getattr(response, 'status', None)!r}, "
            f"incomplete_details={getattr(response, 'incomplete_details', None)!r}, "
            f"output_text={getattr(response, 'output_text', None)!r}, "
            f"usage={getattr(response, 'usage', None)!r}, "
            f"output_items={items_repr!r}"
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[RAWLOG] {context} <<< RECEIVED: failed to log raw response: {e}", exc_info=True)

# Roles authorized to have the Morning MCP invoicing tools attached (Feature 018)
MORNING_MCP_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

# Roles authorized to have the reminder tools attached (Feature 054) - there is
# exactly one reminder list, owned by "the godfather"; ADMIN manages it too via
# this app's existing blanket-access pattern, not a reminder-specific rule.
REMINDER_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

# Roles authorized to have the query_ledger_events tool attached (Feature 044)
# - its own distinct constant (not a reuse of MORNING_MCP_AUTHORIZED_ROLES/
# REMINDER_AUTHORIZED_ROLES, even though the values coincide today), matching
# this codebase's existing per-feature-constant convention (research.md
# Decision 9).
LEDGER_QUERY_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

# Feature 039 (US4a): the model outputs this exact string as its entire response_text
# to mean "send nothing back" (e.g. a group message clearly directed at someone else,
# per runtime_constitution.md's group-etiquette guidance) - double-bracketed to make
# accidental collision with genuine Hebrew conversational output as close to
# impossible as a plain-text sentinel can get.
#
# bugfix-028 B5: the definition now lives in src.models.message, because AIResponse
# itself enforces the response-owed contract and a model may not import a handler.
# Re-exported here so every existing `from src.handlers.ai_handler import
# NO_REPLY_SENTINEL` keeps working.
NO_REPLY_SENTINEL = _NO_REPLY_SENTINEL

# Architectural fix (2026-08-25): _finalize_response used to run the local-tool
# handlers (_handle_query_ledger_events / _handle_list_reminders) exactly
# ONCE each, against the turn's original
# response only - a fixed one-hop chain, not a real loop. A model that
# legitimately wants to call a second local tool (or the same one again) from
# inside what the code assumed was the FINAL follow-up had nowhere to go: the
# follow-up's own output_text was empty (a function_call, not text), nothing
# re-inspected it for further actionable items, and the turn crashed into
# AIResponse's "owes a reply but carries no text" guard (confirmed live,
# 2026-08-25, tests/billed/test_ledger_query_billed.py::test_monthly_income_aggregation
# - the model correctly answered from query_ledger_events, then legitimately
# issued a second query_ledger_events call to widen its search, and the app
# had no way to execute that second call).
#
# The model is free to call any of these tools, any number of times, in
# whatever order it needs - the fix is a real loop, not narrowing what's
# available to it (see the same-day discussion this bound came out of). Each
# iteration re-runs all three detectors against whatever response is current;
# the loop only stops when a full pass makes no further progress (real text,
# or a terminal pending-approval item - see PendingApproval/
# PendingLocalToolApproval, which are NEVER auto-continued past). This cap is
# a safety bound against a model stuck cycling tool calls, not an expected
# depth - every scenario seen so far resolves in 1-2 rounds.
#
# Raised 5 -> 10 (2026-08-26, explicit user directive): a real billed run
# (test_client_explicit_everything_request_gets_the_complete_picture) hit the
# old cap of 5 after a legitimate list_invoices(client_name=...) call
# succeeded, but a SECOND list_invoices(status="שולם") call came back with a
# seemingly-contradictory empty result (see the separate tasks.md follow-up
# to file a bug on Morning status-filtering) - the model then spent its
# remaining iterations re-verifying via query_ledger_events instead of
# trusting the data it already had, and ran out of budget before it could
# settle on a final reply. This is a widening of the safety margin for that
# kind of multi-tool back-and-forth, not a claim that looping this deep is
# expected or desired behavior.
MAX_LOCAL_TOOL_LOOP_ITERATIONS = 10

def _normalize_self_mentions(text: str, own_whatsapp_number: str) -> str:
    """bugfix-024: rewrite an @-mention of DeniDin's own WhatsApp number (WhatsApp's
    native @-mention picker inserts the mentioned contact's raw phone number into
    message text, never a display name - confirmed via a real Green API getWaSettings
    call, see bugfix-024's spec; this was previously, and wrongly, assumed to always
    render as "@DisplayName") into the name-shaped "@DeniDin" form the model's
    existing, already-verified "@Name" addressee judgment knows how to recognize (see
    runtime_constitution.md's Group Conversation Etiquette section and US7's case6
    billed test) - a deterministic, code-level check performed BEFORE the text ever
    reaches the model, not something left to model judgment (CONSTITUTION.md "NO
    UNVERIFIED THIRD-PARTY ASSUMPTIONS").

    A plain substring replace, not a regex: the real, verified mention format is an
    exact match on `own_whatsapp_number`'s own bare-digit string (both the real
    getWaSettings response and a real captured mention text use the identical bare
    format, 2026-08-05) - no confirmed case involves a different digit format (e.g. a
    "+" prefix) needing normalization, so handling one isn't justified. `str.replace`
    already rewrites every occurrence, and can't touch anyone else's mentioned number
    since it only ever searches for this exact self-mention substring.

    No-op (returns text unchanged) if own_whatsapp_number is empty - e.g. the
    startup fetch (denidin.py's initialize_app) failed or hasn't run, matching this
    codebase's fail-open convention for non-critical startup data (CONSTITUTION §VI).
    """
    if not own_whatsapp_number:
        return text
    return text.replace(f"@{own_whatsapp_number}", "@DeniDin")

# MCP tool names that require explicit human approval before they actually
# execute (Feature 022; renamed from DOCUMENT_CREATING_MCP_TOOLS by Feature
# 026, which extended coverage to client-mutating tools, not just
# document-creating ones).
# Feature 021's create_transaction_account/create_combo_document/
# create_credit_note/create_receipt all create a real Morning document too,
# same as create_invoice - gated for the same reason. `update_invoice_status`
# (removed, feature 023) used to be gated here too; its status-word phrasing
# now dispatches directly to create_receipt/create_combo_document_as_reference/
# create_credit_note instead, which are already covered here.
# create_combo_document_as_reference (feature 023) creates a real Morning document
# the same way - gated for the same reason. add_client/update_client
# (feature 026) are real, persisted client-record writes - same category.
APPROVAL_REQUIRED_MCP_TOOLS = (
    "create_invoice",
    "create_transaction_account",
    "create_combo_document",
    "create_credit_note",
    "create_receipt",
    "create_combo_document_as_reference",
    "cancel_transaction_account",
    "add_client",
    "update_client",
)

# The remaining Morning MCP tools (read-only client/invoice lookups) -
# explicitly listed as "never" require approval. Confirmed empirically
# (2026-07-23, real E2E run) that a `require_approval` filter with ONLY an
# "always" key does NOT leave unlisted tools defaulting to no-approval as
# assumed from docs/smoke-testing - `download_invoice_pdf` (not in
# APPROVAL_REQUIRED_MCP_TOOLS) still came back as a pending
# mcp_approval_request. Being fully explicit about both sides of the filter
# avoids relying on that unconfirmed default.
NO_APPROVAL_MCP_TOOLS = (
    "list_invoices", "get_invoice_details", "get_financial_summary",
    "download_invoice_pdf", "list_clients", "get_client_details",
    "resolve_client_name",
)


def _build_pending_approval_fallback_text(tool_name: str, arguments_json: str) -> str:
    """Build a specific fallback message for a pending MCP approval, used
    only when the model itself produced no narrating text alongside the
    tool call (see the call site below - the constitution instructs the
    model to always narrate, but that's prompt guidance, not a guarantee).

    The pending approval's own `arguments` already carry everything needed
    to name the specific pending action (confirmed live, 2026-07-30: a
    resolved client name, an amount, etc.) - this builds a per-tool message
    from them instead of a fully generic "there's a pending action" string,
    so the user can still tell what they're approving even when the model
    stayed silent.

    Never includes `original_internal_morning_id` (a raw internal UUID) - the
    constitution's "never ask for or mention internal_morning_id" rule applies here
    too, so create_credit_note/create_receipt/create_combo_document_as_reference
    fall back to naming the ACTION only, plus any safe (non-id) fields
    present (amount/description), never the id itself.

    Falls back to the fully generic text on any parsing issue - this must
    never raise, since it runs on the response-handling hot path.
    """
    generic = (
        "יש פעולה הממתינה לאישורך לפני שהיא מתבצעת. "
        "אישור — כן/לא?"
    )
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except (json.JSONDecodeError, TypeError):
        return generic
    if not isinstance(args, dict):
        return generic

    def _amount_suffix() -> str:
        amount = args.get("amount")
        return f" על סך {amount} ₪" if amount is not None else ""

    try:
        if tool_name == "create_invoice":
            return f"ליצור חשבונית ל{args['client_name']}{_amount_suffix()} עבור {args['description']} — לאשר?"
        if tool_name == "create_transaction_account":
            return f"להפיק חשבון עסקה ל{args['client_name']}{_amount_suffix()} — לאשר?"
        if tool_name == "create_combo_document":
            return f"להפיק חשבונית מס/קבלה ל{args['client_name']}{_amount_suffix()} — לאשר?"
        if tool_name == "create_credit_note":
            return f"להפיק חשבונית זיכוי לחשבונית שזוהתה בשיחה{_amount_suffix()} — לאשר?"
        if tool_name == "create_receipt":
            return f"להפיק קבלה עבור החשבונית שזוהתה בשיחה{_amount_suffix()} — לאשר?"
        if tool_name == "create_combo_document_as_reference":
            return f"לסגור את חשבון העסקה שזוהה בשיחה{_amount_suffix()} — לאשר?"
        if tool_name == "cancel_transaction_account":
            return "לבטל את חשבון העסקה שזוהה בשיחה — לא ייווצר שום מסמך — לאשר?"
        if tool_name == "add_client":
            return f"ליצור לקוח חדש: {args['name']}, {args['email']}, {args['phone']} — לאשר?"
        if tool_name == "update_client":
            display_name = args.get("new_name") or args["name"]
            return f"לעדכן את פרטי הלקוח {display_name} — לאשר?"
    except KeyError:
        return generic
    return generic


_DOCUMENT_TYPE_LABELS = {
    "create_invoice": "חשבונית מס",
    "create_transaction_account": "חשבון עסקה",
    "create_combo_document": "חשבונית מס/קבלה",
    "create_credit_note": "חשבונית זיכוי",
    "create_receipt": "קבלה",
    "create_combo_document_as_reference": "חשבונית מס/קבלה (סגירת חשבון עסקה)",
}

# bugfix-038: the three "Group B" tools that create a document AGAINST an
# existing one (identified only by original_internal_morning_id, an internal Morning
# id the constitution forbids ever showing the user). Design confirmed live
# with the user 2026-08-13: these tools' MCP signatures stay thin (no new
# display-only params) - instead, the model is required
# (runtime_constitution.md) to call get_invoice_details on the original,
# FRESH, in the SAME turn, before proposing any of these. See
# _find_referenced_document_details below for the correlation this enables.
_GROUP_B_REFERENCE_TOOLS = {
    "create_receipt", "create_credit_note", "create_combo_document_as_reference",
    # Feature 056: cancel_transaction_account is the same shape (only takes
    # original_internal_morning_id) - found missing during manual QA
    # (2026-08-20), left the approval prompt with zero account details.
    "cancel_transaction_account",
}

# The exact line format_invoice_confirmation (morning-mcp-app) always appends
# to get_invoice_details' output - the one line that must never reach the
# user (an internal Morning document id), even though the rest of that same
# real output is otherwise shown verbatim as bugfix-038's Part 1.
_INTERNAL_MORNING_ID_LINE_PREFIX = "מזהה פנימי"


def _find_referenced_document_details(original_internal_morning_id: Optional[str], mcp_calls: List[Dict[str, Any]]) -> Optional[str]:
    """bugfix-038: find a get_invoice_details call, already executed earlier
    in this SAME turn, whose internal_morning_id argument matches original_internal_morning_id -
    and return its real output verbatim (the referenced document's own real
    data, as Morning returned it - client name, amount, dates, status, etc.).

    Returns None if no matching lookup exists in mcp_calls - the accepted
    risk of this design (user, 2026-08-13): correctness here depends on the
    model actually complying with the constitution's "look it up first, same
    turn" instruction, not a structural guarantee. When None, the pending-
    approval block simply has no reference section, same failure shape as
    before this bugfix - never raises, never fabricates data.

    Never a network call itself - `mcp_calls` is the turn's own already-
    materialized tool-call history (see ai_handler.py's _finalize_response),
    so this is a pure, free correlation, not a new fetch."""
    if not original_internal_morning_id or not mcp_calls:
        return None
    for call in mcp_calls:
        if call.get("name") != "get_invoice_details":
            continue
        try:
            call_args = json.loads(call.get("arguments") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(call_args, dict):
            continue
        output = call.get("output")
        if call_args.get("internal_morning_id") == original_internal_morning_id and output:
            return str(output)
    return None


def _strip_internal_morning_id_line(details_text: str) -> str:
    """Never show the internal Morning document id to the user (constitution -
    see bugfix-038's Origin). get_invoice_details' raw output always includes
    it (morning-mcp-app's format_invoice_confirmation); this strips exactly
    that one line, leaving everything else - client name, amount, dates,
    status, linked documents - intact and unmodified."""
    return "\n".join(
        line for line in details_text.split("\n")
        if not line.startswith(_INTERNAL_MORNING_ID_LINE_PREFIX)
    )

_PAYMENT_METHOD_LABELS = {
    "bank_transfer": "העברה בנקאית",
    "cash": "מזומן",
    "cheque": "צ׳ק",
    "credit_card": "כרטיס אשראי",
    "paypal": "פייפאל",
    "bit": "ביט",
}

APPROVAL_QUESTION = "אישור — כן/לא?"


def _format_date_for_display(raw: str) -> str:
    """bugfix-028: render any date in the approval block as DD/MM/YYYY,
    matching the document-date line built a few lines above this call site.

    `payment_date` arrives here as whatever the model passed to the Morning
    tool - ISO (the tool's own required format, per `_validate_payment_date`
    in morning-mcp-app) - and was previously echoed verbatim. That produced a
    single approval message showing "תאריך המסמך: 09/08/2026" next to "תאריך
    העסקה: 2026-07-12" - two different date formats side by side, confusing
    for exactly the non-technical user this block exists to inform. Falls
    back to the raw string on anything unparseable rather than hiding it.
    """
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return raw


def _build_pending_approval_details(
    tool_name: str, arguments_json: str, mcp_calls: Optional[List[Dict[str, Any]]] = None
) -> str:
    """bugfix-028 B3/A4: state EXACTLY what will be created, every time.

    This is not a fallback. Before this, the message a user was asked to approve
    was either the model's own free narration or - when it narrated nothing, as
    it did on 22 turns in the 7-9 Aug window - a one-line string built from tool
    arguments. Neither was guaranteed to state what the document would be, so a
    user approved figures that did not match what got created (₪2,360 approved,
    ₪2,784.80 stored) and consecutive attempts were byte-identical.

    Mandatory in every document-creation approval (user, 2026-08-09): document
    type, document date, client, amount, VAT treatment, purpose. Optional when
    known: bank details, transaction date, reference invoice number. An element
    that is missing is shown as such rather than omitted - "not stated" is
    information too, and silently dropping it is how the ₪40,000 request lost
    both its purpose and its "לפני מע״מ".

    bugfix-038: for the three "Group B" reference tools (`_GROUP_B_REFERENCE_
    TOOLS`), the approval gains a PART 1 preceding the block above - the
    referenced document's own real data (client name, document date, amount at
    minimum; everything else get_invoice_details returns, except its internal
    id line), found via `_find_referenced_document_details` correlating
    `original_internal_morning_id` against a get_invoice_details call already executed
    earlier in this SAME turn (`mcp_calls`). Absent for every other tool, and
    absent for Group B tools too when no matching lookup is found (accepted
    risk - see that function's docstring).

    Never raises: it runs on the response-handling hot path.
    """
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except (json.JSONDecodeError, TypeError):
        args = {}
    if not isinstance(args, dict):
        args = {}

    reference_block = ""
    if tool_name in _GROUP_B_REFERENCE_TOOLS:
        reference_details = _find_referenced_document_details(
            args.get("original_internal_morning_id"), mcp_calls or []
        )
        if reference_details:
            reference_block = (
                f"📄 המסמך המקושר:\n"
                f"{_strip_internal_morning_id_line(reference_details)}\n\n"
            )

    if tool_name == "cancel_transaction_account":
        # Feature 056: unlike the other Group B tools, this one creates NO
        # document at all (REQ-INV-020) - the generic per-document-creation
        # Part 2 body below (date/VAT/amount/purpose) doesn't fit a
        # cancellation ("VAT: not specified" makes no sense here), so this
        # gets its own dedicated body instead of a _DOCUMENT_TYPE_LABELS
        # entry. reference_block (Part 1, above) already carries the real
        # client/amount/date when the model looked the account up first
        # (mandatory per runtime_constitution.md, same as the other three
        # Group B tools) - this Part 2 only needs to state the action.
        return (
            reference_block
            + "📋 לאישור:\n"
            + "פעולה: ביטול חשבון עסקה — לא ייווצר שום מסמך, "
            + "החשבון יסומן כמבוטל/מטופל במורנינג בלבד\n\n"
            + APPROVAL_QUESTION
        )
    if tool_name == "add_client":
        return (
            f"📋 לאישור — לקוח חדש:\n"
            f"שם: {args.get('name', '(חסר)')}\n"
            f"מייל: {args.get('email', '(חסר)')}\n"
            f"טלפון: {args.get('phone', '(חסר)')}\n\n{APPROVAL_QUESTION}"
        )
    if tool_name == "update_client":
        changed = [f"{k}: {v}" for k, v in args.items() if k != "name" and v]
        return (
            f"📋 לאישור — עדכון לקוח:\n"
            f"לקוח: {args.get('name', '(חסר)')}\n"
            f"שינויים: {', '.join(changed) if changed else '(לא צוינו)'}\n\n{APPROVAL_QUESTION}"
        )

    doc_label = _DOCUMENT_TYPE_LABELS.get(tool_name)
    if doc_label is None:
        return f"יש פעולה הממתינה לאישורך לפני שהיא מתבצעת.\n\n{APPROVAL_QUESTION}"

    today = now_local().date().strftime("%d/%m/%Y")
    amount = args.get("amount")
    vat_included = args.get("vat_included")
    if vat_included is True:
        vat_label = "כולל מע״מ"
    elif vat_included is False:
        vat_label = "לא כולל מע״מ"
    else:
        vat_label = "(לא צוין — יש להבהיר לפני ההפקה)"

    lines = [
        "📋 לאישור:",
        f"סוג מסמך: {doc_label}",
        f"תאריך המסמך: {today}",
        f"לקוח: {args.get('client_name') or '(מהמסמך המקושר)'}",
        f"סכום: {amount if amount is not None else '(חסר)'} ₪",
        f"מע״מ: {vat_label}",
        f"עבור: {args.get('description') or '(לא צוין)'}",
    ]

    # Optionals - shown only when they actually exist (user, 2026-08-09).
    if args.get("payment_date"):
        lines.append(f"תאריך העסקה: {_format_date_for_display(args['payment_date'])}")
    method = args.get("payment_method")
    if method:
        lines.append(f"אמצעי תשלום: {_PAYMENT_METHOD_LABELS.get(method, method)}")
    bank_bits = [
        f"בנק {args['bank_number']}" if args.get("bank_number") else "",
        f"סניף {args['bank_branch']}" if args.get("bank_branch") else "",
        f"חשבון {args['bank_account']}" if args.get("bank_account") else "",
    ]
    bank_bits = [b for b in bank_bits if b]
    if bank_bits:
        lines.append(f"פרטי בנק: {', '.join(bank_bits)}")
    if args.get("transaction_reference"):
        lines.append(f"אסמכתה: {args['transaction_reference']}")
    if args.get("invoice_number") or args.get("original_invoice_number"):
        ref = args.get("invoice_number") or args.get("original_invoice_number")
        lines.append(f"חשבונית מקושרת: {ref}")

    return reference_block + "\n".join(lines) + f"\n\n{APPROVAL_QUESTION}"


# Free-form affirmative replies recognized as approval of a pending MCP
# document-creation request (Feature 022) - matched against the trimmed,
# casefolded message (or its leading token), not as a substring-anywhere
# check, to avoid false positives on unrelated longer sentences.
_AFFIRMATIVE_REPLIES = {
    "yes", "yep", "yeah", "sure", "ok", "okay", "go ahead",
    "כן", "אישור", "בסדר", "אוקיי", "אוקי",
    # Feature 046: additional common Hebrew affirmatives - "מאשר"/"מאשרת" ("I
    # confirm", masc./fem.) plus "בטח"/"סבבה", not previously recognized.
    "מאשר", "מאשרת", "בטח", "סבבה",
    # bugfix-028 B1: the prompt itself ended "— לאשר?" while this set had only
    # "אישור", so the prompt invited a word the parser rejected. Live: the user
    # answered "לאשר" twice, got the identical prompt back twice, and gave up.
    # The prompt is now a closed question (see _build_pending_approval_details),
    # but the word it used to invite must still be understood.
    "לאשר",
}


def _is_affirmative_reply(text: str) -> bool:
    """Whether `text` reads as a free-form yes/no approval of a pending
    document-creation request (Feature 022) - matched as the whole trimmed
    message or its leading token, not a substring-anywhere check, to avoid
    false positives on longer unrelated sentences (e.g. one that happens to
    contain "כן" as a substring of another word).
    """
    normalized = text.strip().casefold()
    if not normalized:
        return False
    if normalized in _AFFIRMATIVE_REPLIES:
        return True
    # bugfix-028 B2: the leading token is found by searching for the first RUN OF
    # WORD CHARACTERS rather than by splitting on whitespace, because WhatsApp
    # prefixes RTL text with Unicode bidi controls (U+200F RIGHT-TO-LEFT MARK and
    # friends) that are NOT whitespace - `'‏'.isspace()` is False - so
    # `.strip().split()[0]` yielded `'‏כן'` and missed this set entirely.
    # Verified live: 2026-08-09 04:00:45 UTC the user sent `‏כן` and the log
    # recorded approve=False; 8 messages in that window carried bidi controls.
    #
    # Deliberately NOT a list of characters to strip (rejected by the user) and
    # deliberately NOT a substring-anywhere check: `\w` excludes every bidi
    # control, punctuation and quote mark by definition, so no enumeration is
    # needed, while anchoring on the FIRST word still refuses "לא נכון, אל תפיק"
    # - a containment test would read that as approval and create a real
    # financial document against an explicit refusal.
    leading_match = re.search(r"\w+", normalized, flags=re.UNICODE)
    if leading_match is None:
        return False
    return leading_match.group(0) in _AFFIRMATIVE_REPLIES

# Ledger Event Recognition (runtime_constitution.md) - a local OpenAI function tool,
# NOT a remote MCP server: nothing is executed anywhere when the model "calls" it. The
# API just returns structured, schema-validated arguments as a `function_call` output
# item alongside (never instead of) the normal reply - see `extract_function_call`.
# Used by both the text path (AIHandler) and the image path (ImageExtractor).
#
# `components` array (2026-07-30, REQ-DATA-004 redesign): replaces relying on the
# model choosing to invoke this tool N times for a multi-stage/conditional agreement -
# proven unreliable even with a materially stronger model (real evidence: two separate
# real documents, both correctly comprehended in full by the extraction step, both still
# only produced ONE tool call each, with every component after the first dumped into
# free-text `notes` instead of split out - see spec.md's Clarifications for the full
# investigation). A single call with a `components` array is a fundamentally more
# reliable capability (structured output) than depending on autonomous repeated tool
# invocation, and was validated externally (real API calls, real images, this exact
# schema) before being wired into the app - both real test documents correctly produced
# 3 and 6 components respectively in ONE call each.
LEDGER_EVENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "capture_ledger_event",
    "description": (
        "Capture a fee-agreement or bank-deposit event mentioned in the user's message "
        "or image, for later review and merging into the bookkeeping ledger. Call this "
        "in addition to your normal reply - never instead of it. Only call it when the "
        "content genuinely states, changes, or cancels a fee arrangement, or shows a "
        "bank-transfer/deposit confirmation. Do not call it for ordinary conversation, "
        "questions, or content unrelated to money/engagement terms. If the agreement "
        "states multiple distinct fee components (different tracks/stages/conditions), "
        "list ALL of them in the components array in this ONE call - never omit any, "
        "never merge them into one component, and never make a second separate call for "
        "the same agreement. "
        "Feature 025: this tool also serves a second, different job - source_type=חשבונית "
        "transcribes a Morning accounting document's already-structured fields verbatim "
        "(from the document data given directly in your instructions), never inferred "
        "from conversation text - a distinct task from recognizing a fee-agreement/bank-"
        "deposit signal in free text or an image."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "source_type": {
                "type": "string",
                "enum": ["הסכם", "בנק", "חשבונית"],
                "description": (
                    "הסכם for a fee-agreement event, בנק for a bank deposit/transfer, "
                    "חשבונית for a Morning-sourced accounting document (any document "
                    "type - invoice, receipt, credit note, etc.) transcribed from "
                    "structured document data given to you directly, never inferred "
                    "from conversation."
                ),
            },
            "event_subtype": {
                "type": "string",
                # עדכון/ביטול/אישור-מימוש disabled until further notice (2026-08-03) -
                # the downstream tooling to reconcile a correction/cancellation/payment-
                # confirmation against a specific prior record doesn't exist yet. A
                # correction, cancellation, or payment confirmation for an existing
                # agreement is captured as a fresh יצירה describing the current state
                # instead - see runtime_constitution.md's Ledger Event Recognition
                # section. Restore these enum values here when that capability is built.
                "enum": ["יצירה", "הפקדה", "הפקה"],
                "description": (
                    "For source_type=הסכם: always יצירה (a correction/cancellation/"
                    "payment-confirmation for an existing arrangement is still captured "
                    "as יצירה, describing the current state - see the constitution). "
                    "For source_type=בנק: always הפקדה. For source_type=חשבונית: pass "
                    "הפקה as a placeholder - it is IGNORED and overwritten by code with "
                    "the document's real Morning type (e.g. חשבונית מס, חשבונית זיכוי, "
                    "קבלה), read from the accounting_document_json payload. Applies to "
                    "the whole call - every component shares the same subtype."
                ),
            },
            "client_name": {
                "type": ["string", "null"],
                "description": (
                    "The client's name, verbatim. For source_type=בנק, this is the "
                    "depositor/account-holder name shown on the bank-transfer confirmation "
                    "or banking-app screenshot ('שם חשבון מחויב' or the 'העברה מ-X' line) - "
                    "always put it here, never in payer_name, which does not apply to בנק "
                    "events at all (see payer_name's own description)."
                ),
            },
            "payer_name": {
                "type": ["string", "null"],
                "description": (
                    "For source_type=הסכם ONLY: the paying entity, ONLY if different from "
                    "client_name (e.g. an insurer/union routing payment). Watch specifically "
                    "for 'דרך X' / 'באמצעות X' / 'via X' / 'through X' near a client's name "
                    "(often its own line right after the client name) - a strong, common "
                    "signal that X is the payer, not part of the agreement_id's label "
                    "component or description. "
                    "ALWAYS null for source_type=בנק - a bank deposit's account-holder name "
                    "goes in client_name, never here; there is no payer/client distinction "
                    "for a בנק event."
                ),
            },
            "agreement_id": {
                "type": ["string", "null"],
                "description": (
                    "The unique id for the matter/agreement as a whole - YOU build this "
                    "string yourself, once, in the exact format "
                    "'{MM}{YY}-{client_slug}-{label_slug}' (e.g. '0726-אתי_אסולין-ערעור_לארצי'): "
                    "MM/YY are the current month/year (from today's date given to you in your "
                    "instructions); client_slug is client_name with every run of whitespace/"
                    "punctuation replaced by a single underscore (no leading/trailing "
                    "underscore); label_slug is the same transform applied to a short "
                    "human-readable Hebrew label for the matter as a whole (e.g. 'ערעור "
                    "לארצי', 'תביעת נזיקין נגד מדינה' - a few words, not a full sentence) - "
                    "that label exists only inside this string, never as a separate field "
                    "anywhere. Required (non-null) for source_type=הסכם; always null for בנק. "
                    "Build it ONCE, when this matter's first component(s) are created, then "
                    "reuse this EXACT string verbatim for every later component/message "
                    "referencing this SAME matter - never rebuild, reword, or vary it."
                ),
            },
            "reference_hint": {
                "type": ["string", "null"],
                "description": (
                    "Free-text explanation of how this event relates to a PRIOR one already "
                    "captured earlier in this SAME conversation - covers replacing/correcting/"
                    "cancelling a prior arrangement, an explicit ADDITION/supplement to one "
                    "('תוספת', 'עוד X על מה ששולם', 'בנוסף ל-'), AND a looser, non-superseding "
                    "relation to a related matter - all of these are a 'reference', uniformly "
                    "(there is no separate 'replace' mechanism). Set this whenever the message "
                    "itself uses this kind of language, even if you can't identify exactly "
                    "which prior event it targets - describe what you DO know (amount "
                    "mentioned, approximate timing, client) so a human/script can resolve it "
                    "later; never skip it just because the exact match is unclear. "
                    "Conversely: leave this null for a plain NEW mention with no correction/"
                    "addition/cancellation language at all (e.g. a fresh hourly work-log entry, "
                    "a brand-new fee agreement) - superficial similarity to another entry "
                    "(same client, similar amount) is NOT by itself a reason to set this."
                ),
            },
            "bank_number": {
                "type": ["string", "null"],
                "description": (
                    "The bank's NUMBER (e.g. '31'), never its name - only for source_type=בנק, "
                    "always null for הסכם. A deposit screenshot's extracted text gives you the "
                    "number, not a name - never guess or invent a bank name to fill this in. "
                    "Null if the screenshot doesn't state it clearly."
                ),
            },
            "bank_branch": {
                "type": ["string", "null"],
                "description": "The bank branch number, only for source_type=בנק, always null for הסכם.",
            },
            "bank_account": {
                "type": ["string", "null"],
                "description": "The bank account number, only for source_type=בנק, always null for הסכם.",
            },
            "accounting_document_json": {
                "type": ["string", "null"],
                "description": (
                    "Only for source_type=חשבונית: the document's ENTIRE JSON object, "
                    "copied verbatim and unmodified from the tool output you were given "
                    "(the whole {...} object for that one document, as a single string). "
                    "Do not summarise it, reorder it, translate it, drop fields, or fill "
                    "anything in yourself - every value is read out of this JSON by code. "
                    "ALWAYS null for הסכם/בנק."
                ),
            },
            "component_count": {
                "type": "integer",
                "description": (
                    "State this FIRST, before the components array below: the exact number "
                    "of entries you are about to list in components. Every genuinely-"
                    "qualifying event has at least one component - this must never be 0. "
                    "components MUST end up containing EXACTLY this many entries - if you "
                    "find yourself wanting to list a different number of components than "
                    "you stated here, go back and make them match before responding."
                ),
            },
            "components": {
                "type": "array",
                "description": (
                    "One entry per genuinely distinct fee component/track/stage/condition "
                    "stated in the document or message - even if there's only one. A base "
                    "amount and its own VAT-inclusive total for the SAME component (e.g. "
                    "'20,000 + VAT = 23,600') is ONE entry, not two - only split when the "
                    "source genuinely describes separate stages/tracks/conditions, each with "
                    "its own amount. MUST contain exactly component_count entries."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "component_label": {
                            "type": ["string", "null"],
                            "description": (
                                "Short human-readable Hebrew label for just THIS component "
                                "(e.g. 'בסיס', 'שעות עבודה', 'בונוס אם מגיעים לפיצויים') - a "
                                "few words, not a full sentence, distinct from other "
                                "components of the same agreement. Required (non-null) for "
                                "source_type=הסכם; always null for בנק."
                            ),
                        },
                        "description": {
                            "type": ["string", "null"],
                            "description": (
                                "The matter/engagement for this component, verbatim or closely "
                                "paraphrased - PLUS any ambiguity/uncertainty about THIS "
                                "component worth flagging for the human reviewer (e.g. additive "
                                "vs. alternative to another component), appended to the same "
                                "field rather than a separate one. Reserve reference_hint "
                                "specifically for reasoning about how this event relates to a "
                                "PRIOR event - everything else about this component's own "
                                "content goes here."
                            ),
                        },
                        "amount": {
                            "type": ["string", "null"],
                            "description": (
                                "The stated amount for THIS component, verbatim (no currency "
                                "conversion, no math). MUST resolve to exactly one number - "
                                "when both a pre-VAT base and a computed VAT-inclusive total "
                                "are stated for this same component, use the total."
                            ),
                        },
                        "percent": {"type": ["string", "null"], "description": "A stated percentage figure for this component, if any (e.g. success-fee percentage)."},
                        "percent_base": {"type": ["string", "null"], "description": "What this component's percent applies to, if stated."},
                        "hours": {"type": ["string", "null"], "description": "Stated hours, for an hourly work-log component."},
                        "hourly_rate": {"type": ["string", "null"], "description": "Stated hourly rate for this component, if any."},
                        "txn_date": {
                            "type": ["string", "null"],
                            "description": (
                                "The actual calendar date this component's own content "
                                "refers to, as ISO-8601 (YYYY-MM-DD), when that's distinct "
                                "from the message's own timestamp. Two cases: (1) for an "
                                "hourly work-log component (this component's 'hours' is "
                                "non-null) - REQUIRED (non-null) - the actual date the hours "
                                "were worked; resolve relative phrases like 'אתמול'/'היום' "
                                "yourself using the current date given to you in your "
                                "instructions. (2) for a source_type=בנק component - OPTIONAL "
                                "- the transaction/value date the screenshot itself states, "
                                "ONLY when the screenshot shows an explicit date distinct from "
                                "other dates that might also appear on screen (e.g. when it "
                                "was forwarded). Null in every other case. Never a substitute "
                                "for the real message timestamp - that stays whatever it "
                                "actually is, independent of this field."
                            ),
                        },
                        "vat_status": {
                            "type": "string",
                            "enum": ["כולל", "לא כולל", "לא צוין"],
                            "description": "VAT-inclusive, VAT-exclusive, or not stated for THIS component - never assumed.",
                        },
                        "trigger_condition": {
                            "type": ["string", "null"],
                            "description": (
                                "The condition THIS component's amount/existence depends on, "
                                "verbatim or closely paraphrased, when the source states one "
                                "(e.g. 'אם הבקשה נקבעת לדיון', 'במידה ועושים גם ברע', 'בתנאי "
                                "ש...') - only for source_type=הסכם, always null for בנק and "
                                "for an unconditional component. Put the condition itself here, "
                                "not in description - description is for the component's own "
                                "matter/content, this is specifically for what has to happen "
                                "for it to apply."
                            ),
                        },
                    },
                    "required": [
                        "component_label", "description", "amount", "percent", "percent_base",
                        "hours", "hourly_rate", "txn_date", "vat_status", "trigger_condition",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "source_type", "event_subtype", "client_name", "payer_name", "agreement_id",
            "reference_hint", "bank_number", "bank_branch", "bank_account",
            "accounting_document_json",
            "component_count", "components",
        ],
        "additionalProperties": False,
    },
}


# Feature 069 (mechanism move): the post-turn recognition call reports its verdict
# by calling this dedicated function tool. Its `event` sub-object reuses
# LEDGER_EVENT_TOOL's parameter schema verbatim (the same prose->schema mapping the
# old inline capture_ledger_event tool performed), wrapped with the tri-state
# verdict envelope (data-model.md 2 / contracts/recognition-and-logging.md C2).
# NOT `strict` - the envelope is genuinely a union (event is populated only for
# `complete`, the declined-only fields only for `declined`).
RECOGNITION_TOOL_NAME = "report_ledger_recognition"

RECOGNITION_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": RECOGNITION_TOOL_NAME,
    "description": (
        "Report whether THIS conversational round finished a complete, ledger-worthy "
        "event (a fee agreement, a bank deposit, or a Morning accounting document "
        "created this turn). Call this exactly once. "
        "verdict='complete' ONLY when every mandatory field for the event's "
        "source_type is already present in the conversation (client resolved to an "
        "exact Morning client name included) - then fill `event` with the full "
        "schema mapping and set `trigger_message_id` to the id of the message that "
        "first stated the event. "
        "verdict='declined' ONLY when the operator was offered the closed "
        "store-anyway question and explicitly answered not to store - set "
        "source_type + client_name_stated + reason. "
        "verdict='none' for everything else: ordinary conversation, a still-missing "
        "mandatory field, an unresolved/ambiguous client, a read-only Morning "
        "question, or a mid-flow turn that has not yet completed the event. "
        "A bare contact detail sent on its own - an email address, a phone number, "
        "an ID/tax number, a mailing address - or a bare client name, a greeting, "
        "or a status question, with NO fee arrangement, NO deposit/transfer and NO "
        "Morning document created this turn, is NOT a ledger event: verdict='none'. "
        "Providing a missing field for a client record (e.g. answering \"what's "
        "their email?\") is client-record maintenance, never a ledger event."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["complete", "none", "declined"],
                "description": "The tri-state recognition verdict for this round.",
            },
            "event": {
                "type": ["object", "null"],
                "description": (
                    "Populated ONLY for verdict='complete': the finished event mapped "
                    "onto the ledger schema (same fields capture_ledger_event used). "
                    "One event per call - a staggered sibling that completes on a "
                    "later turn is reported by that later turn's call."
                ),
                "properties": copy.deepcopy(LEDGER_EVENT_TOOL["parameters"]["properties"]),
            },
            "trigger_message_id": {
                "type": ["string", "null"],
                "description": (
                    "verdict='complete' only: the id of the conversation message that "
                    "first stated this event - the ledgerer reads its timestamp for "
                    "event_datetime. Null otherwise."
                ),
            },
            "source_type": {
                "type": ["string", "null"],
                "description": "verdict='declined' only: הסכם or בנק. Null otherwise.",
            },
            "client_name_stated": {
                "type": ["string", "null"],
                "description": (
                    "verdict='declined' only: the client name the operator used, "
                    "verbatim free text (need not resolve to a Morning client). "
                    "Null otherwise."
                ),
            },
            "reason": {
                "type": ["string", "null"],
                "description": "verdict='declined' only: always 'declined_by_operator'. Null otherwise.",
            },
        },
        "required": ["verdict"],
        "additionalProperties": False,
    },
}


_STASH_MISSING = "לא זוהה"


def _stash_val(value: Any) -> str:
    """One stash field value, or the fixed 'not recognised' token."""
    if value is None:
        return _STASH_MISSING
    text = str(value).strip()
    return text or _STASH_MISSING


def build_ledger_stash_text(
    extracted_text: Optional[str],
    analysis: Optional[Dict],
    source_type: str,
    source_medium: str = "image",
) -> str:
    """Feature 069 C3: render a media extractor's ledger-event analysis + the
    VERBATIM text read off the file into one structured Hebrew "stash" block.

    A synthetic conversational turn carries this stash as its `text_content`, so
    the model does ordinary client resolution (`resolve_client_name` / `add_client`
    / the approval gate) and the post-turn recognition call then sees the full
    payload. `analysis` is one event's fields (the shape
    `capture_ledger_events_from_text` returns per event) or None for a `.docx`
    where only the parsed body text is available.

    `source_type` ∈ {"בנק", "הסכם"}; `source_medium` ∈ {"image", "document"}.
    """
    a = analysis or {}
    is_doc = source_medium == "document"
    lines: List[str] = []

    if source_type == "בנק":
        lines.append("📸 התקבלה תמונה של אסמכתת העברה/הפקדה בנקאית.")
        lines.append(f"תת-סוג: {_stash_val(a.get('event_subtype') or 'הפקדה')}")
        lines.append(f"סכום: {_stash_val(a.get('amount'))}")
        lines.append(f"מטבע: {_stash_val(a.get('currency') or 'שקל')}")
        lines.append(f"תאריך הפקדה: {_stash_val(a.get('txn_date'))}")
        lines.append(f"מספר בנק: {_stash_val(a.get('bank_number'))}")
        lines.append(f"מספר סניף: {_stash_val(a.get('bank_branch'))}")
        lines.append(f"מספר חשבון: {_stash_val(a.get('bank_account'))}")
        lines.append(f"שם על האסמכתא: {_stash_val(a.get('client_name'))}")
        lines.append(f"מספר אסמכתא: {_stash_val(a.get('reference_number') or a.get('reference'))}")
    else:  # הסכם
        lines.append(
            "📄 התקבל קובץ מסמך (DOCX) של הסכם שכר טרחה."
            if is_doc else
            "📸 התקבלה תמונה של הסכם שכר טרחה."
        )
        lines.append(f"תת-סוג: {_stash_val(a.get('event_subtype') or 'יצירה')}")
        lines.append(f"שם הלקוח בהסכם: {_stash_val(a.get('client_name'))}")
        lines.append(f"תאריך ההסכם: {_stash_val(a.get('agreement_date') or a.get('txn_date'))}")
        components = a.get("components") or []
        for comp in components:
            if comp.get("percent") is not None:
                basis = comp.get("percent_base") or comp.get("description") or ""
                lines.append(f"אחוז: {_stash_val(comp.get('percent'))} — {_stash_val(basis)}")
            else:
                cur = comp.get("currency") or "שקל"
                desc = comp.get("description") or comp.get("component_label") or ""
                lines.append(f"סכום קבוע: {_stash_val(comp.get('amount'))} {cur} — {_stash_val(desc)}")
        lines.append(f'מע"מ: {_stash_val(a.get("vat_status"))}')
        lines.append(f"שם המשלם: {_stash_val(a.get('payer_name'))}")

    frame = (
        "--- טקסט שחולץ מהמסמך (מילה במילה) ---"
        if is_doc else
        "--- טקסט שחולץ מהתמונה (מילה במילה) ---"
    )
    lines.append("")
    lines.append(frame)
    lines.append((extracted_text or "").strip() or _STASH_MISSING)
    return "\n".join(lines)


# Reminders (Feature 054) - a local `type: "function"` tool, same shape/parsing
# machinery as LEDGER_EVENT_TOOL, but - unlike capture_ledger_event, which
# dispatches immediately - this one creates a PendingLocalToolApproval instead
# of executing (see _handle_reminder_creation_proposal /
# contracts/local-tool-approval-gate.md). No owner/chat_id field in the
# schema itself: the model never supplies a delivery target. It's resolved by
# the application at approval time instead (2026-08-19, user decision,
# supersedes the original "always config.godfather_phone" FR-008 design) -
# delivery_chat_id is set to the chat/group the request was actually made in
# (_resolve_pending_local_tool_approval passes effective_chat_id), with a
# fallback to the requester's own 1:1 chat only if delivery there ever fails
# (see reminder_delivery_service.py's _deliver_one_occurrence).
CREATE_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "create_reminder",
    "description": (
        "ONLY call this when the user's own message explicitly asks to be "
        "reminded of something at a future time (e.g. \"תזכיר לי...\", a "
        "recurring cadence like \"כל יום/שבוע\"). NEVER call this to interpret "
        "a confirmation reply (\"כן\"/\"לא\"), an ambiguous message, or any "
        "message about clients, invoices, or documents - those are handled by "
        "entirely separate tools and this one is never a fallback for them. "
        "Propose creating a new reminder, after gathering the message text and "
        "either a one-time date/time or a full recurrence rule through conversation. "
        "This call itself does NOT persist anything - it is presented to the user as "
        "an approval summary (with the actual time shown AFTER rounding to the "
        "nearest 5 minutes); the reminder is only created if the user then "
        "explicitly approves."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "message_text": {
                "type": "string",
                "description": (
                    "The actual thing to be reminded about, in the user's own words - "
                    "taken directly from what they said. Never a placeholder "
                    "(\"תזכורת\", \"בדיקה\", \"test\", or similar) - if the user's message "
                    "doesn't actually contain something to be reminded about, do not "
                    "call this tool at all."
                ),
            },
            "schedule_type": {"type": "string", "enum": ["one_time", "recurring"]},
            "one_time_due_at": {
                "type": ["string", "null"],
                "description": (
                    "ISO-8601 local datetime (Asia/Jerusalem), required iff "
                    "schedule_type=one_time, must be strictly in the future after "
                    "rounding to the nearest 5 minutes."
                ),
            },
            "recurrence": {
                "type": ["object", "null"],
                "description": "Required iff schedule_type=recurring, else null.",
                "properties": {
                    "interval": {"type": "integer", "description": "Every N units, minimum 1."},
                    "freq": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                    "weekdays": {
                        "type": ["array", "null"],
                        "items": {"type": "string", "enum": ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]},
                        "description": "Required (non-empty) iff freq=weekly, else null.",
                    },
                    "month_day": {
                        "type": ["integer", "null"],
                        "description": "1-31, one of two monthly variants; null unless freq=monthly.",
                    },
                    "month_nth_weekday": {
                        "type": ["object", "null"],
                        "description": (
                            "The other monthly variant, e.g. {n:1, weekday:'MO'} = first "
                            "Monday; null unless freq=monthly."
                        ),
                        "properties": {
                            "n": {"type": "integer", "enum": [1, 2, 3, 4, -1], "description": "-1 means 'last'."},
                            "weekday": {"type": "string", "enum": ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]},
                        },
                        "required": ["n", "weekday"],
                        "additionalProperties": False,
                    },
                    "first_occurrence_at": {
                        "type": "string",
                        "description": "ISO-8601 local datetime of the FIRST occurrence, must be strictly in the future after rounding.",
                    },
                    "end_condition": {"type": "string", "enum": ["never", "after_n", "until_date"]},
                    "end_count": {"type": ["integer", "null"], "description": "Required iff end_condition=after_n."},
                    "end_until": {
                        "type": ["string", "null"],
                        "description": "ISO-8601 local date, required iff end_condition=until_date, must not be in the past.",
                    },
                },
                "required": [
                    "interval", "freq", "weekdays", "month_day", "month_nth_weekday",
                    "first_occurrence_at", "end_condition", "end_count", "end_until",
                ],
                "additionalProperties": False,
            },
        },
        "required": ["message_text", "schedule_type", "one_time_due_at", "recurrence"],
        "additionalProperties": False,
    },
}

# Read-only - no approval gate applies (FR-013), dispatched immediately like
# capture_ledger_event, never creates a PendingLocalToolApproval. Lets the
# model resolve a user's natural-language description of a reminder to a
# concrete reminder_id before calling modify_reminder/delete_reminder - never
# a code-level fuzzy string match, never a guessed identifier.
LIST_REMINDERS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "list_reminders",
    "description": (
        "ONLY call this when the user's own message explicitly asks about their "
        "reminders (e.g. \"מה יש לי מחר\", or as a precursor to an explicit modify/"
        "delete request). NEVER call this to interpret a confirmation reply "
        "(\"כן\"/\"לא\"), an ambiguous message, or any message about clients, "
        "invoices, or documents - those are handled by entirely separate tools. "
        "Returns the current active reminder list (message text + human-readable schedule) "
        "so you can resolve a user's natural-language description of a reminder to a concrete "
        "reminder_id before calling modify_reminder or delete_reminder. Never guess a "
        "reminder_id - always call this first if you don't already know it from earlier in "
        "the conversation. Read-only: calling this never changes anything and needs no "
        "user approval."
    ),
    "strict": True,
    "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
}

# modify_reminder/delete_reminder share the reminder_id+scope shape - both
# create a PendingLocalToolApproval, never dispatch immediately, same as
# create_reminder.
MODIFY_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "modify_reminder",
    "description": (
        "ONLY call this when the user's own message explicitly asks to change an "
        "existing reminder (e.g. \"תעדכן/תדחה את התזכורת...\"). NEVER call this to "
        "interpret a confirmation reply (\"כן\"/\"לא\"), an ambiguous message, or any "
        "message about clients, invoices, or documents - those are handled by "
        "entirely separate tools and this one is never a fallback for them. "
        "Propose a modification to an existing reminder already identified via "
        "list_reminders or earlier conversation - never a guessed reminder_id. Does not "
        "persist anything - presented as an approval summary first, with any new time "
        "shown AFTER rounding to the nearest 5 minutes."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reminder_id": {"type": "string"},
            "scope": {"type": "string", "enum": ["single_occurrence", "whole_series"]},
            "occurrence_date_hint": {
                "type": ["string", "null"],
                "description": (
                    "ISO-8601 local date/datetime identifying WHICH occurrence (matched "
                    "against the plain rule's own generated dates), required iff "
                    "scope=single_occurrence."
                ),
            },
            "new_message_text": {
                "type": ["string", "null"],
                "description": (
                    "The new text, in the user's own words, if they're changing what the "
                    "reminder is about; null if only the schedule is changing. Never a "
                    "placeholder (\"תזכורת\", \"בדיקה\", \"test\", or similar)."
                ),
            },
            "new_due_at": {
                "type": ["string", "null"],
                "description": (
                    "The new due date/time - meaningful for scope=single_occurrence, or for "
                    "scope=whole_series when the target reminder is one-time (no recurrence "
                    "to replace); must be in the future after rounding."
                ),
            },
            "new_recurrence": {
                "type": ["object", "null"],
                "description": "Only meaningful for scope=whole_series on a recurring reminder; same shape as create_reminder's recurrence.",
                "properties": CREATE_REMINDER_TOOL["parameters"]["properties"]["recurrence"]["properties"],
                "required": CREATE_REMINDER_TOOL["parameters"]["properties"]["recurrence"]["required"],
                "additionalProperties": False,
            },
        },
        "required": [
            "reminder_id", "scope", "occurrence_date_hint",
            "new_message_text", "new_due_at", "new_recurrence",
        ],
        "additionalProperties": False,
    },
}

DELETE_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "delete_reminder",
    "description": (
        "ONLY call this when the user's own message explicitly asks to cancel an "
        "existing reminder (e.g. \"תבטל את התזכורת...\"). NEVER call this to "
        "interpret a confirmation reply (\"כן\"/\"לא\"), an ambiguous message, or any "
        "message about clients, invoices, or documents - those are handled by "
        "entirely separate tools and this one is never a fallback for them. "
        "Propose deleting a reminder (single occurrence or whole series), already identified "
        "via list_reminders or earlier conversation - never a guessed reminder_id. Does not "
        "persist anything - presented as an approval summary first."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reminder_id": {"type": "string"},
            "scope": {"type": "string", "enum": ["single_occurrence", "whole_series"]},
            "occurrence_date_hint": {"type": ["string", "null"], "description": "Required iff scope=single_occurrence."},
        },
        "required": ["reminder_id", "scope", "occurrence_date_hint"],
        "additionalProperties": False,
    },
}


# Ledger Event Querying (Feature 044) - a local `type: "function"` tool,
# RBAC-gated like the reminder tools (LEDGER_QUERY_AUTHORIZED_ROLES), but
# read-only and dispatched immediately - no PendingLocalToolApproval, ever.
# Unlike list_reminders, a single turn may legitimately contain SEVERAL calls
# to this tool (research.md Decision 10) - see _handle_query_ledger_events.
QUERY_LEDGER_EVENTS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "query_ledger_events",
    "description": (
        "Search previously captured ledger events (fee agreements, bank-deposit records, "
        "and accounting documents pulled from Morning) to answer a question about past "
        "agreements, amounts, hours, percentages, or payments - without needing the user "
        "to paste the original message again. This is a synced CACHE of Morning's own "
        "data (documents) alongside ledger-only records (fee agreements, bank deposits) "
        "that never exist in Morning at all - for ANY query-shaped question (how much, "
        "who, when, which document, what status, how many), prefer this over a live "
        "Morning tool (list_invoices/get_invoice_details/get_financial_summary/etc.). "
        "Once this has answered the question in this turn, that answer is final - do "
        "NOT also call a Morning tool afterward to double-check; only fall back to a "
        "live Morning tool if the ledger genuinely can't answer or the user explicitly "
        "insists on a live check. ONLY call this when the user's question gives "
        "you at least ONE identifying detail to search on - if the question is too vague to "
        "form a real search (e.g. 'what did we agree on' with nothing else), ASK the user "
        "for the missing detail FIRST; never call this with an empty criteria list just to "
        "see what comes back. "
        "criteria is a list of {text, hint} pairs, one per distinct fact you're searching "
        "for. EVERY criterion searches EVERY field on every event (name, date, amount, "
        "percent, description, document number, bank details, everything) - there is no "
        "way to restrict a criterion to only one field. A NUMBER given as text (e.g. "
        "'100', '40000') is compared numerically against the event's numeric fields only "
        "(amount, hourly_rate, percent, percent_base, split_percent, bank_number, "
        "bank_branch, bank_account) - exact value, not fuzzy string similarity, so pass the "
        "literal number, not a description of it. Any other text is fuzzy/typo-tolerant "
        "matched (NOT meaning-based - it finds similar WORDING, not a differently-phrased "
        "version of the same idea) against every text field. Resolve relative/approximate "
        "phrasing yourself before calling (e.g. 'August' -> pass a date like '2026-08', "
        "'around 40,000, might include VAT' -> consider searching both the round number and "
        "a VAT-adjusted figure as separate criteria if genuinely ambiguous). "
        "hint is optional and is a SOFT signal only, never a hard filter - see the hint "
        "parameter's own description below for the full list of groups and what each means. "
        "If the question is scoped to a time period (this month, this week, since Monday, "
        "etc.) always add a separate criterion with hint='date' carrying that period - this "
        "tool applies no date filtering on its own, so without a date-hinted criterion a "
        "time-scoped question can match events from ANY month, not just the intended one. "
        "Multiple criteria in ONE call are ANDed - only events matching ALL of them "
        "(individually, above a real-match confidence floor) come back. Each returned event "
        "also carries a 'confidence' score - higher means a stronger match across the given "
        "criteria; use your judgment about how much confidence to trust for borderline "
        "matches. "
        "If an 'identity'-hinted criterion matches more than one distinct real client/payer "
        "with no single clear winner, this returns candidates instead of events - relay them "
        "to the user and ask which one they meant. If they confirm more than one (or 'both'/"
        "'all'), call this again ONCE PER confirmed exact name and combine the results "
        "yourself. An empty result means no matching record was found - say so plainly, "
        "never fabricate an answer. "
        "For OR-type questions (spanning more than one name, date range, or other criterion "
        "where ANY may match - e.g. 'client A or client B', 'hours in August or September'), "
        "issue ONE SEPARATE CALL PER alternative and combine all the results yourself when "
        "you reply - this tool is read-only, so calling it several times in the same turn is "
        "always safe. For NOT/exclusion or numeric-threshold questions (e.g. 'everyone except "
        "X', 'who owes more than 100'), call this with a broad criteria set that retrieves "
        "every plausibly-relevant event (do NOT try to encode the exclusion/threshold into "
        "criteria - there is no such filter), then apply the exclusion or threshold yourself "
        "by reasoning over the returned events' own fields before replying. For a question "
        "needing arithmetic (a sum, a balance owed, a total across clients/periods), use the "
        "returned events' own clean numeric fields yourself - this tool never computes totals "
        "for you. If a single call's matches are very numerous, don't just dump every event "
        "verbatim - use your own judgment about summarizing or asking the user to narrow "
        "further, the same way you would for any other long answer."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "criteria": {
                "type": "array",
                "description": (
                    "One entry per distinct fact being searched for within this call "
                    "(ANDed together). Use multiple calls, not multiple array entries, for "
                    "OR-type questions - see the tool description."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": (
                                "The literal value to search for - a name, a date, a plain "
                                "number, or free text. Searched against every field on every "
                                "event; see the tool description for how numbers vs. text are "
                                "compared."
                            ),
                        },
                        "hint": {
                            "type": ["string", "null"],
                            "enum": [
                                "identity", "date", "event_type", "vat", "amount",
                                "percentage", "free_text", "document", "banking", None,
                            ],
                            "description": (
                                "Optional soft weighting signal - which closed field group "
                                "this text is most likely describing. Never a hard filter: "
                                "every field is always checked regardless, this only nudges "
                                "scoring if the text's best match lands in the hinted group. "
                                "Leave null if unsure. Groups: "
                                "'identity' = client name, payer name, or split-partner name. "
                                "'date' = the event's own date/time or a transaction date - "
                                "use this whenever the question is scoped to a period (this "
                                "month, this week, since Monday, etc.); pass the "
                                "period/date as the criterion's text. "
                                "'event_type' = source type (הסכם/בנק/חשבונית) or event "
                                "subtype (e.g. חשבונית מס, קבלה). "
                                "'vat' = VAT status/treatment. "
                                "'amount' = amount or hourly rate. "
                                "'percentage' = percent, percent base, or split percent. "
                                "'free_text' = the free-text description, a trigger "
                                "condition, or a reference hint - prose, not a specific field. "
                                "'document' = the accounting document's display number, "
                                "payment method, or its status/status label (open/paid/"
                                "cancelled etc. - a document lifecycle fact, not the event's "
                                "own date). "
                                "'banking' = bank number, branch, or account."
                            ),
                        },
                    },
                    "required": ["text", "hint"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["criteria"],
        "additionalProperties": False,
    },
}


def _format_reminder_schedule(rrule_str: Optional[str], dtstart_iso: str) -> str:
    """Human-readable Hebrew summary of a reminder's schedule, for the approval
    block (_build_reminder_approval_details). The persisted RRULE string is the
    source of truth for actual firing (ReminderManager/recurring_ical_events) -
    this is display-only and deliberately simple, not a full RFC5545 renderer.
    """
    try:
        when = datetime.fromisoformat(dtstart_iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        when = dtstart_iso

    if not rrule_str:
        return f"חד-פעמי, {when}"

    parts = dict(p.split("=", 1) for p in rrule_str.split(";") if "=" in p)
    freq_labels = {"DAILY": "יומי", "WEEKLY": "שבועי", "MONTHLY": "חודשי"}
    freq_label = freq_labels.get(parts.get("FREQ", ""), parts.get("FREQ", ""))
    interval = parts.get("INTERVAL")
    cadence = f"כל {interval} × {freq_label}" if interval else freq_label

    extra = ""
    if "BYDAY" in parts:
        byday_labels = {
            "SU": "א", "MO": "ב", "TU": "ג", "WE": "ד",
            "TH": "ה", "FR": "ו", "SA": "ש",
        }
        days_he = ",".join(
            byday_labels.get(code, code) for code in parts["BYDAY"].split(",")
        )
        extra = f", בימים {days_he}"
    elif "BYMONTHDAY" in parts:
        extra = f", ביום {parts['BYMONTHDAY']} לחודש"

    end = ""
    if "COUNT" in parts:
        end = f", {parts['COUNT']} פעמים"
    elif "UNTIL" in parts:
        end = f", עד {parts['UNTIL'][:8]}"

    return f"{cadence}{extra}, החל מ-{when}{end}"


def _build_reminder_approval_details(
    tool_name: str, args: Dict[str, Any], due_at_iso: Optional[str] = None,
    rrule_str: Optional[str] = None, current_message_text: Optional[str] = None,
) -> str:
    """Structured approval summary for a reminder create/modify/delete proposal -
    same "state exactly what will happen, every time" discipline as
    _build_pending_approval_details (bugfix-028 B3/A4), not left to the model's
    own narration. For create_reminder, due_at_iso/rrule_str are the ALREADY-
    ROUNDED/VALIDATED values from ReminderManager.resolve_schedule - what's
    shown here is exactly what will be persisted on approval. For modify/delete,
    current_message_text (fetched by the caller) identifies WHICH reminder,
    since a reminder_id is not human-readable.
    """
    if tool_name == "create_reminder":
        schedule = _format_reminder_schedule(rrule_str, due_at_iso or "")
        return (
            f"📋 לאישור — תזכורת חדשה:\n"
            f"טקסט: {args.get('message_text', '(חסר)')}\n"
            f"מועד: {schedule}\n\n{APPROVAL_QUESTION}"
        )

    scope_label = "כל הסדרה" if args.get("scope") == "whole_series" else "מופע בודד"
    reminder_label = current_message_text or "(תזכורת)"

    if tool_name == "modify_reminder":
        changes = []
        if args.get("new_message_text"):
            changes.append(f"טקסט חדש: {args['new_message_text']}")
        if args.get("new_due_at"):
            changes.append(f"מועד חדש: {_format_reminder_schedule(None, args['new_due_at'])}")
        if args.get("new_recurrence"):
            changes.append("תבנית חזרה חדשה")
        changes_text = "; ".join(changes) if changes else "(לא צוינו שינויים)"
        return (
            f"📋 לאישור — עדכון תזכורת \"{reminder_label}\" ({scope_label}):\n"
            f"{changes_text}\n\n{APPROVAL_QUESTION}"
        )

    if tool_name == "delete_reminder":
        return (
            f"📋 לאישור — מחיקת תזכורת \"{reminder_label}\" ({scope_label})\n\n{APPROVAL_QUESTION}"
        )

    return f"יש פעולת תזכורת הממתינה לאישורך.\n\n{APPROVAL_QUESTION}"


def extract_function_call(response, tool_name: str) -> Optional[Dict]:
    """Find a `function_call` item named `tool_name` in a Responses API `response.output`
    and return its parsed arguments, or None if absent.

    Never raises - malformed `arguments` JSON is logged and treated as "not called",
    the same as if the model hadn't called the tool at all. Shared by the text path
    (AIHandler._finalize_response) and the image path (ImageExtractor._vision_extract) -
    the extraction logic itself doesn't care which one is calling it.
    """
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call" or getattr(item, "name", None) != tool_name:
            continue
        try:
            return cast(Dict, json.loads(item.arguments))
        except json.JSONDecodeError as e:
            logger.warning(f"Malformed {tool_name!r} function_call arguments discarded: {e}")
            return None
    return None


def extract_function_call_id(response, tool_name: str) -> Optional[str]:
    """Find a `function_call` item named `tool_name` in a Responses API `response.output`
    and return its `call_id`, or None if absent.

    Companion to `extract_function_call` - needed only when a real second round-trip
    must report a result back for this specific call (see AIHandler._finalize_response's
    ledger-event follow-up: reasoning models emit a `function_call` OR a final `message`
    in one turn, never both, so `output_text` is empty until the call's result is
    reported back via `previous_response_id` + `function_call_output`).
    """
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call" or getattr(item, "name", None) != tool_name:
            continue
        return getattr(item, "call_id", None)
    return None


def extract_all_function_calls(response, tool_name: str) -> List[Dict]:
    """Find EVERY `function_call` item named `tool_name` in a Responses API
    `response.output`, returning each as {"arguments": dict, "call_id": str}.

    A single turn can legitimately contain more than one call to the same tool -
    e.g. runtime_constitution.md's Ledger Event Recognition explicitly wants one
    capture per hourly work-log entry, never aggregated, so a message describing
    several entries produces several `capture_ledger_event` calls in one turn.
    OpenAI requires a `function_call_output` for EVERY pending function call
    before it will continue a conversation (confirmed empirically, 2026-07-28: a
    follow-up round-trip that only resolved the first of two calls was rejected
    with "No tool output found for function call ..."), so any follow-up must
    account for all of them, not just the first (unlike `extract_function_call`/
    `extract_function_call_id`, which only ever return the first match).

    Never raises - malformed `arguments` JSON on any individual item (most often a
    truncated response - see `arguments=None` below) is logged and kept in the
    results with `arguments=None`, NOT dropped: OpenAI still considers that
    call_id pending regardless of whether we could parse it, so any follow-up
    must still resolve it (bugfix-018 - a dropped call_id here left OpenAI
    rejecting the whole follow-up with "No tool output found for function call
    ...", which in turn left the user with a silently empty reply).
    """
    results = []
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call" or getattr(item, "name", None) != tool_name:
            continue
        call_id = getattr(item, "call_id", None)
        try:
            arguments = json.loads(item.arguments)
        except json.JSONDecodeError as e:
            logger.warning(f"Malformed {tool_name!r} function_call arguments discarded: {e}")
            results.append({"arguments": None, "call_id": call_id})
            continue
        results.append({"arguments": arguments, "call_id": call_id})
    return results


# Maximum message length to prevent excessive API costs
MAX_MESSAGE_LENGTH = 10000


class AIHandler:
    """
    Handles AI operations including request creation and OpenAI API calls.
    Implements retry logic with exponential backoff for transient failures.
    """

    def __init__(self, ai_client: OpenAI, config: AppConfiguration, cleanup_interval_seconds: Optional[int] = None):
        """
        Initialize AI handler with OpenAI client and configuration.

        Args:
            ai_client: Configured AI client instance (OpenAI)
            config: Application configuration with AI settings
            cleanup_interval_seconds: Optional override for session cleanup interval (for testing)
        """
        self.client = ai_client
        self.config = config

        # Feature 034 (REQ-VER-005): read once at construction, not per-call - a version
        # can't change mid-process (research.md Decision 4), unlike today's date below.
        self._app_version = read_version(DEFAULT_VERSION_FILE)

        # Constitution loading state (mtime-based caching)
        self._constitution_content: Optional[str] = None
        self._constitution_mtime: Optional[float] = None

        # Feature 069: the dedicated post-turn ledger-recognition prompt, loaded
        # from config/ledger_recognition_prompt.md (same base_dir as the
        # constitution), mtime-cached exactly like it - NOT part of the
        # constitution the conversational turn sees.
        self._recognition_prompt_content: Optional[str] = None
        self._recognition_prompt_mtime: Optional[float] = None

        # Memory system and RBAC are always on (2026-07-14 decision: both
        # graduated from feature flags to permanent behavior).
        self.memory_enabled = True
        self.memory_manager = None

        self.rbac_enabled = True
        self.user_manager = None

        logger.info("RBAC enabled - initializing UserManager")
        godfather_phone = getattr(config, 'godfather_phone', None)
        user_roles = getattr(config, 'user_roles', {})
        admin_phones = user_roles.get('admin_phones', [])
        blocked_phones = user_roles.get('blocked_phones', [])
        logger.debug(
            "UserManager config: godfather_phone_set=%s, admin_phones=%d, blocked_phones=%d",
            bool(godfather_phone),
            len(admin_phones),
            len(blocked_phones)
        )

        self.user_manager = UserManager(
            godfather_phone=godfather_phone,
            admin_phones=admin_phones,
            blocked_phones=blocked_phones
        )
        logger.info(f"UserManager initialized with godfather: {godfather_phone}, admins: {len(admin_phones)}, blocked: {len(blocked_phones)}")

        logger.info("Initializing SessionManager and MemoryManager")

        # Initialize SessionManager
        session_config = config.memory.get('session', {})

        # Note: cleanup_interval_seconds moved to app-level background thread
        # SessionManager no longer runs its own cleanup thread

        self.session_manager = SessionManager(
            storage_dir=session_config.get('storage_dir', 'data/sessions'),
            session_timeout_hours=session_config.get('session_timeout_hours', 24)
        )

        # LedgerEventManager (Feature 033): sibling to MemoryManager, own permanent
        # storage under {data_root}/events/ - composed from config.data_root at
        # construction time (REQ-STORE-001), matching MediaFileManager's pattern,
        # never the config.memory pre-baked-dict pattern SessionManager/MemoryManager
        # use (events aren't session-scoped data).
        self.ledger_event_manager = LedgerEventManager(
            storage_dir=str(Path(config.data_root) / "events"),
            session_manager=self.session_manager,  # Feature 069: the ledgerer reads
        )                                          # trigger timestamps / writes back-links

        # Store token limits for later use in conversation retrieval
        self.max_tokens_by_role = session_config.get('max_tokens_by_role', {
            'client': 4000,
            'godfather': 100000
        })

        # Initialize MemoryManager
        longterm_config = config.memory.get('longterm', {})
        if longterm_config.get('enabled', True):
            self.memory_manager = MemoryManager(
                storage_dir=longterm_config.get('storage_dir', 'data/memory'),
                embedding_model=config.ai_embedding_model,
                ai_client=self.client
            )

            # Store collection name and query params for later use
            self.memory_collection_name = longterm_config.get('collection_name', 'godfather_memory')
            self.memory_top_k = longterm_config.get('top_k_results', 5)
            self.memory_min_similarity = longterm_config.get('min_similarity', 0.7)

            logger.info(f"MemoryManager initialized with collection: {self.memory_collection_name}")
        else:
            logger.info("Long-term memory disabled in config")

        # Morning MCP integration (Feature 018): locate the current tunnel URL via
        # the shared status file the morning-mcp-app publishes. No cross-app import.
        self.morning_mcp_locator = MorningMcpLocator(getattr(config, 'mcp', {}) or {})

        # bugfix-024: DeniDin's own WhatsApp phone number (bare digits, e.g.
        # "972559723730"), fetched ONCE at startup via a real Green API call and set
        # externally by denidin.py's initialize_app (never re-fetched per message -
        # this constructor only establishes the "not yet known" default). Used by
        # create_request to normalize a native @-mention of DeniDin's own number into
        # the name-shaped form the model's existing addressee judgment recognizes.
        self.own_whatsapp_number: str = ""

        # Feature 022: tracks, per chat_id, an MCP document-creation call
        # currently held pending the user's explicit approval. In-memory only
        # (see PendingApprovalManager docstring for why).
        self.pending_approval_manager = PendingApprovalManager()

        # Reminders (Feature 054): ReminderManager owns {data_root}/reminders/
        # (REQ-STORE-001-style discipline, matching LedgerEventManager/
        # MediaFileManager - composed here at construction time, never read from
        # config internally). max_active_reminders is likewise caller-composed
        # from config.reminders, not read by ReminderManager itself. No feature
        # flag - RBAC (REMINDER_AUTHORIZED_ROLES) is the only gate.
        reminders_config = getattr(config, 'reminders', {}) or {}
        self.reminder_manager = ReminderManager(
            storage_dir=str(Path(config.data_root) / "reminders"),
            max_active_reminders=reminders_config.get('max_active_reminders', 20),
        )
        # Local-tool approval gate (create_reminder/modify_reminder/delete_reminder)
        # - a separate, parallel manager to pending_approval_manager, never merged
        # into it (CONSTITUTION test-immutability protects Feature 047's existing
        # approval-gate tests; PendingApproval is structurally MCP-specific - see
        # contracts/local-tool-approval-gate.md).
        self.pending_local_tool_approval_manager = PendingLocalToolApprovalManager()

        # Most recent successful AIResponse, for observability/E2E test verification.
        self.last_response: Optional[AIResponse] = None

        logger.debug(
            f"AIHandler initialized with models: text={config.ai_model}, "
            f"vision={config.ai_vision_model}, embedding={config.ai_embedding_model}"
        )

    def _load_constitution(self) -> str:
        """
        Load constitution file with mtime-based caching.
        Reads constitution file only when modified (checks mtime).
        
        Returns:
            Constitution content if file exists and is configured,
            otherwise fallback to config.system_message
        """
        # Get constitution file from config (support both 'file' and legacy 'files' keys)
        constitution_config = self.config.constitution_config
        filename = constitution_config.get('file')
        
        # Backward compatibility: if 'file' not found, try 'files' array and use first
        if not filename:
            files_array = constitution_config.get('files', [])
            if files_array:
                filename = files_array[0]
        
        # If no constitution file configured, fallback to system_message
        if not filename:
            return ""
        
        # Build constitution file path. Defaults to config/ (same base as
        # CONFIG_PATH='config/config.json' in denidin.py), not data_root -
        # the constitution isn't per-environment data, it's shared config
        # content, identical for dev/prod/test alike. Overridable via
        # constitution_config.base_dir (e.g. tests pointing at a tmp_path).
        base_dir = constitution_config.get('base_dir', 'config')
        filepath = Path(base_dir) / filename
        
        # Check if file exists
        if not filepath.exists():
            logger.warning(f"Constitution file not found: {filepath}, using system_message fallback")
            return ""
        
        # Check file modification time
        try:
            current_mtime = filepath.stat().st_mtime
            
            # Reload if file changed or not yet cached
            if self._constitution_mtime != current_mtime:
                self._constitution_content = filepath.read_text(encoding='utf-8').strip()
                self._constitution_mtime = current_mtime
                logger.debug(f"Constitution loaded: {filename} ({len(self._constitution_content)} chars, mtime: {current_mtime})")
            
            # If constitution is empty after loading, fallback to system_message
            if not self._constitution_content:
                logger.warning(f"Constitution file is empty: {filepath}, using system_message fallback")
                return ""
            
            return self._constitution_content
            
        except Exception as e:
            logger.error(f"Failed to load constitution file {filepath}: {e}", exc_info=True)
            return ""

    def _load_recognition_prompt(self) -> str:
        """Feature 069: load config/ledger_recognition_prompt.md with mtime-based
        caching, exactly like `_load_constitution`. This is the dedicated prompt
        the post-turn recognition call uses INSTEAD of the full constitution -
        the constitution keeps only the conversational side of ledger events.

        Resolved under the same `constitution_config.base_dir` (default 'config')
        so a test pointing the constitution at a tmp dir picks this up from the
        same place. Returns '' if the file is missing/empty (the caller then
        falls back to a minimal inline directive rather than crashing).
        """
        constitution_config = self.config.constitution_config
        base_dir = constitution_config.get('base_dir', 'config')
        filepath = Path(base_dir) / 'ledger_recognition_prompt.md'

        if not filepath.exists():
            logger.warning(f"Recognition prompt file not found: {filepath}")
            return ""

        try:
            current_mtime = filepath.stat().st_mtime
            if self._recognition_prompt_mtime != current_mtime:
                self._recognition_prompt_content = filepath.read_text(encoding='utf-8').strip()
                self._recognition_prompt_mtime = current_mtime
                logger.debug(
                    f"Recognition prompt loaded: {filepath} "
                    f"({len(self._recognition_prompt_content or '')} chars, mtime: {current_mtime})"
                )
            return self._recognition_prompt_content or ""
        except Exception as e:
            logger.error(f"Failed to load recognition prompt file {filepath}: {e}", exc_info=True)
            return ""

    def create_request(self, message: WhatsAppMessage, chat_id: Optional[str] = None,
                       user_role: str = 'client', user_phone: Optional[str] = None) -> AIRequest:
        """
        Create an AIRequest from a WhatsApp message.
        Validates and truncates message length if needed.

        Args:
            message: WhatsApp message to convert
            chat_id: Optional chat ID for memory recall (uses message.chat_id if not provided)
            user_role: User role for token limits ('client' or 'godfather') - DEPRECATED when RBAC enabled
            user_phone: User's phone number for RBAC (uses message.sender_id if not provided)

        Returns:
            AIRequest ready for OpenAI API with optional memory context

        Raises:
            PermissionError: If user is blocked (when RBAC enabled)
        """
        # Use provided chat_id or fall back to message.chat_id
        effective_chat_id = chat_id or message.chat_id

        # RBAC: Check if user is blocked
        if self.rbac_enabled and self.user_manager:
            effective_user_phone = user_phone or message.sender_id
            user = self.user_manager.get_user(effective_user_phone)

            if user.is_blocked:
                logger.warning(f"Blocked user attempted to create request: {effective_user_phone}")
                raise PermissionError(f"User is blocked: {effective_user_phone}")

        # bugfix-024: normalize a native @-mention of DeniDin's own number (e.g.
        # "@972559723730") into the name-shaped "@DeniDin" form BEFORE the model ever
        # sees it - a deterministic check, done here so both the OpenAI call and the
        # persisted session history (which stores this same user_prompt) consistently
        # reflect who was actually addressed. No-op for a message with no self-mention,
        # or if own_whatsapp_number hasn't been resolved.
        user_prompt = _normalize_self_mentions(message.text_content, self.own_whatsapp_number)

        # Validate and truncate message length
        if len(user_prompt) > MAX_MESSAGE_LENGTH:
            logger.warning(
                f"Message length {len(user_prompt)} exceeds maximum {MAX_MESSAGE_LENGTH} chars. "
                f"Truncating from sender {message.sender_name}"
            )
            user_prompt = user_prompt[:MAX_MESSAGE_LENGTH]

        # Build system message with constitution (if configured) + optional memory context
        constitution = self._load_constitution()

        # Add recalled memories if memory system enabled
        if self.memory_enabled and self.memory_manager:
            try:
                # Recall relevant long-term memories
                collection_name = f"memory_{effective_chat_id.replace('@c.us', '')}"

                # RBAC: Use RBAC-filtered recall if enabled
                if self.rbac_enabled and self.user_manager:
                    effective_user_phone = user_phone or message.sender_id
                    user = self.user_manager.get_user(effective_user_phone)

                    recalled_memories = self.memory_manager.recall_with_rbac_filter(
                        query=user_prompt,
                        collection_names=[collection_name],
                        user_phone=effective_user_phone,
                        allowed_scopes=user.allowed_memory_scopes,
                        can_see_all_memories=user.can_see_all_memories,
                        top_k=self.memory_top_k,
                        min_similarity=self.memory_min_similarity
                    )
                else:
                    # Existing behavior: regular recall without RBAC
                    recalled_memories = self.memory_manager.recall(
                        query=user_prompt,
                        collection_names=[collection_name],
                        top_k=self.memory_top_k,
                        min_similarity=self.memory_min_similarity
                    )

                if recalled_memories:
                    memory_context = "\n\nRECALLED MEMORIES (from past conversations):\n"
                    for mem in recalled_memories:
                        memory_context += f"- {mem['content']} (relevance: {mem['similarity']:.2f})\n"

                    constitution += memory_context
                    logger.info(f"Added {len(recalled_memories)} recalled memories to system prompt")
            except Exception as e:
                logger.error(f"Failed to recall memories: {e}", exc_info=True)

        # Create AI request
        request = AIRequest(
            user_prompt=user_prompt,
            constitution=constitution,
            max_tokens=self.config.ai_reply_max_tokens,
            model=self.config.ai_model,
            chat_id=message.chat_id,
            message_id=message.message_id,
            # Feature 024: the real Green API notification timestamp - without this,
            # AIRequest.__post_init__ silently falls back to datetime.now(), so a
            # captured ledger event's message_timestamp (the constitution's "hard
            # pointer") reflected processing time, not when the user actually sent
            # the message. Same class of bug as the image path's (found and fixed
            # 2026-07-28), just one level upstream - exposed by strengthening this
            # feature's E2E persistence assertions to check the exact value, not
            # just truthiness.
            timestamp=message.timestamp,
            # 2026-08-19: the whole original message, not just the fields this
            # function happened to need at the time - see AIRequest.original_message's
            # own docstring for why (ends a real created_by_phone bug for group turns).
            original_message=message,
        )

        logger.debug(f"Created AIRequest {request.request_id} for message {message.message_id}")
        return request

    def _build_morning_mcp_tools(self, user_obj, correlation_id: str) -> Optional[List[Dict]]:
        """
        Build the Responses API `tools` entry for the Morning MCP server, if this
        user's role is authorized and the server is currently reachable.

        Args:
            user_obj: Resolved User (RBAC), or None if RBAC is disabled
            correlation_id: The AIRequest's request_id, for REQ-SEC-002 audit
                logging (ties this attachment to the request's other log lines).

        Returns:
            A one-item `tools` list registering the Morning MCP server as a remote
            tool, or None if the tools should not be attached (unauthorized role,
            RBAC disabled, or the server is currently unavailable).
        """
        if user_obj is None or user_obj.role not in MORNING_MCP_AUTHORIZED_ROLES:
            return None

        server_url = self.morning_mcp_locator.current_server_url()
        if not server_url:
            logger.warning("Morning MCP server unavailable - proceeding without invoicing tools")
            return None

        mcp_config = getattr(self.config, 'mcp', {}) or {}
        auth_token = mcp_config.get('morning_auth_token')
        if not auth_token:
            logger.warning("mcp.morning_auth_token not configured - proceeding without invoicing tools")
            return None

        masked_token = f"{auth_token[:4]}...{auth_token[-4:]}" if len(auth_token) > 8 else "***"
        logger.info(
            f"Attaching Morning MCP tools for request={correlation_id}, role={user_obj.role}, "
            f"url_host={server_url.split('/')[2] if '//' in server_url else server_url}, "
            f"token={masked_token}"
        )

        return [{
            "type": "mcp",
            "server_label": mcp_config.get('morning_server_label', 'morning-invoices'),
            "server_url": server_url,
            # Feature 022 (extended by Feature 026): any tool in
            # APPROVAL_REQUIRED_MCP_TOOLS requires explicit human approval
            # before it executes; everything in NO_APPROVAL_MCP_TOOLS proceeds
            # immediately. Both sides of the filter are listed explicitly -
            # see NO_APPROVAL_MCP_TOOLS's comment for why.
            "require_approval": {
                "always": {"tool_names": list(APPROVAL_REQUIRED_MCP_TOOLS)},
                "never": {"tool_names": list(NO_APPROVAL_MCP_TOOLS)},
            },
            "headers": {"Authorization": f"Bearer {auth_token}"}
        }]

    def _build_reminder_tools(self, user_obj) -> List[Dict]:
        """Reminder tools (Feature 054), RBAC-gated the same way Morning MCP tools
        are - only GODFATHER/ADMIN get them attached. list_reminders is read-only
        (no approval gate); create/modify/delete all go through the
        PendingLocalToolApproval gate.
        """
        if user_obj is None or user_obj.role not in REMINDER_AUTHORIZED_ROLES:
            return []
        return [CREATE_REMINDER_TOOL, LIST_REMINDERS_TOOL, MODIFY_REMINDER_TOOL, DELETE_REMINDER_TOOL]

    def _build_ledger_query_tools(self, user_obj) -> List[Dict]:
        """Ledger Event Querying (Feature 044), RBAC-gated the same way the
        reminder/Morning MCP tools are - only GODFATHER/ADMIN get
        query_ledger_events attached. Read-only, no approval gate, ever."""
        if user_obj is None or user_obj.role not in LEDGER_QUERY_AUTHORIZED_ROLES:
            return []
        return [QUERY_LEDGER_EVENTS_TOOL]

    def _assemble_tools(self, user_obj, correlation_id: str) -> Optional[List[Dict]]:
        """Merge the (RBAC-gated) Morning MCP tools, the (RBAC-gated) reminder
        tools, and the (RBAC-gated) ledger-query tool into one `tools` list -
        all can be attached in the same turn. Returns None (not an empty list)
        when nothing applies, matching the Responses API's own convention for
        "no tools this call".

        Feature 069 (mechanism move): the inline `capture_ledger_event` tool is
        no longer attached here - ledger capture is now a dedicated post-turn
        recognition call (`recognize_ledger_event`) feeding a zero-AI ledgerer,
        external to the conversational turn. `query_ledger_events` (read/search)
        stays."""
        morning_tools = self._build_morning_mcp_tools(user_obj, correlation_id) if self.rbac_enabled else None
        reminder_tools = self._build_reminder_tools(user_obj) if self.rbac_enabled else []
        ledger_query_tools = self._build_ledger_query_tools(user_obj) if self.rbac_enabled else []
        # Reminder tools deliberately go LAST (2026-08-19, user decision after a
        # real cross-feature confusion incident): Morning's tools are one opaque
        # `mcp` entry needing runtime discovery, so reminder tools - individually
        # inlined `function` entries - were the most directly-visible tools in the
        # list whenever they came right after it. Position isn't the only fix
        # (see the tool descriptions' own explicit negative scoping above), but
        # reduces whatever residual bias position/primacy contributes.
        # query_ledger_events goes alongside reminder tools (also inlined
        # `function` entries, same visibility reasoning), before reminders.
        combined = (
            (morning_tools or []) + ledger_query_tools + reminder_tools
        )
        return combined or None

    def _build_instructions(self, constitution: str, today_timestamp: Optional[int] = None) -> str:
        """
        Build the `instructions` string (constitution + current-date suffix)
        for a Responses API call. Used by a normal turn's call, the Feature 022
        approval-resolution follow-up call, the Feature 024 ledger follow-up
        call, and the Feature 024 image-path ledger classification call
        (ImageExtractor._classify_ledger_event) — `previous_response_id` chains
        the prior conversation's input/output, but NOT the `instructions`
        parameter itself (confirmed empirically, same as `tools` needing to be
        re-passed - see `_call_openai_approval_api`), so every call needs its
        own full instructions to keep following the constitution's guidance.

        Takes the constitution text directly (not a full AIRequest) so any
        caller with just a constitution string - not necessarily a full
        request object - can build the same instructions.

        Args:
            today_timestamp: (Feature 043, research.md R4) Unix epoch int
                overriding "today" for relative-date resolution. `None` (the
                default - every pre-043 call site) preserves current
                behavior exactly: real wall-clock UTC "today". A caller
                replaying a historical message (the WhatsApp export player)
                passes that message's own timestamp instead, so the model
                resolves "היום"/"אתמול" etc. against the message's actual
                historical date rather than whenever the replay happens to
                run - this was the one real correctness gap a full replay
                audit found (see research.md R4); every OTHER date-derived
                ledger field already correctly derives from the message's
                own timestamp, never wall-clock.
        """
        # Give the model the actual current date AND time. It has no clock of
        # its own — its training cutoff makes it default to a stale "current
        # year", which produced real wrong-year invoice lookups (e.g.
        # resolving "7 בפברואר" to 2023). Time-of-day was added for Feature
        # 054 (reminders) — without it the model cannot resolve a relative
        # clock offset ("תזכיר לי בעוד שעה") and has to ask the user for the
        # current time instead of just computing it, confirmed via a real
        # billed-test failure. This is appended at reply time, computed per
        # call in Israel local time (bugfix-037 — NOT UTC) — NOT templated
        # into the constitution file. today_timestamp (Feature 043) overrides
        # "now" for the WhatsApp export player's historical replay - see this
        # method's own docstring above.
        if today_timestamp is not None:
            now = local_from_timestamp(today_timestamp)
        else:
            now = now_local()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")
        return (
            f"{constitution}\n\n---\n"
            f"THE CURRENT DATE AND TIME IS {today} {current_time} (Asia/Jerusalem, "
            f"Israel local time). Treat this as the authoritative \"now\" when "
            f"resolving any relative or partial date/time the user gives (a "
            f"day/month with no year, \"היום\", \"אתמול\", \"בעוד שעה\", \"בעוד "
            f"חצי שעה\", etc.) — never fall back on a year from your training "
            f"data, and never ask the user what time it is now.\n"
            f"YOUR CURRENT VERSION IS {self._app_version}. If asked what version you are "
            f"running (in any language), state this exact value."
        )

    def _call_openai_api(self, request: AIRequest, conversation_history: Optional[List[Dict]] = None,
                         tools: Optional[List[Dict]] = None):
        """
        Make the actual OpenAI Responses API call.

        Retries on transient failures (RateLimitError/APITimeoutError/APIError)
        are handled entirely by the OpenAI SDK's own client-level max_retries
        (2026-08-19 - see AppConfiguration.max_retries' own docstring for why
        this method no longer carries its own tenacity @retry decorator: it
        used to double up with the SDK's own previously-unconfigured default
        retry behavior, up to 6 real HTTP attempts for one logical call). The
        SDK honors real server Retry-After guidance, which a fixed local wait
        never did.

        Args:
            request: AI request to send
            conversation_history: Optional conversation history to include
            tools: Optional Responses API `tools` list (e.g. Morning MCP server)

        Returns:
            OpenAI Responses API response

        Raises:
            RateLimitError: After the client's own max_retries attempts are exhausted
            APITimeoutError: Same
            APIError: Same
        """
        logger.debug(f"Calling OpenAI Responses API for request {request.request_id}")

        # Build input array with optional conversation history (same shape as
        # conversation_history: list of {"role": ..., "content": ...})
        input_items = []
        if conversation_history:
            input_items.extend(conversation_history)
            logger.debug(f"Including {len(conversation_history)} messages from conversation history")
        input_items.append({"role": "user", "content": request.user_prompt})

        kwargs = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution, today_timestamp=request.timestamp),
            "input": input_items,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        # kwargs is built dynamically (tools conditionally added) so its inferred
        # type (dict[str, object]) never lines up with any single overload of the
        # SDK's heavily-overloaded create() - safe to ignore, the actual value
        # types are correct for the Responses API.
        _log_outgoing_request("_call_openai_api (initial call)", kwargs)
        response = self.client.responses.create(**kwargs)  # type: ignore[call-overload]
        _log_raw_response("_call_openai_api (initial call)", response)

        return response

    def get_response(self, request: AIRequest, chat_id: Optional[str] = None,
                     user_role: str = 'client', sender: Optional[str] = None,
                     recipient: Optional[str] = None, user_phone: Optional[str] = None,
                     is_group: bool = False, chat_name: Optional[str] = None,
                     sender_phone: Optional[str] = None) -> AIResponse:
        """
        Get AI response for a request with error handling and fallbacks.
        Includes memory system integration for session storage.

        Args:
            request: AI request to process
            chat_id: Optional chat ID for session management (uses request.chat_id if not provided)
            user_role: User role for token limits ('client' or 'godfather') - DEPRECATED when RBAC enabled
            sender: Sender's resolved display name (2026-08-19: NOT a WhatsApp
                ID despite this parameter's name - historical naming, kept for
                caller compatibility. `user_phone` below carries the real
                WhatsApp JID.
            recipient: Historical/display-only, same caveat as `sender` -
                superseded by the is_group/chat_name-driven recipient
                resolution in _finalize_response for what actually gets
                persisted on Message.recipient now.
            user_phone: User's real WhatsApp JID (RBAC lookup AND, 2026-08-19,
                now also the real Message.sender for a user turn) - uses
                `sender` if not provided.
            is_group: Whether effective_chat_id is a WhatsApp group
                (2026-08-19) - drives Message.recipient/.recipient_name
                resolution: a group message is addressed to the group's own
                JID/name, never to one individual member or to DeniDin alone.
            chat_name: Green API's resolved chat display name
                (senderData.chatName, WhatsAppMessage.chat_name) - a group's
                real subject/name when is_group, used for
                Message.recipient_name.
            sender_phone: The ACTUAL individual sender's real WhatsApp JID
                (2026-08-19, message.sender_id) - deliberately separate from
                `user_phone`, which for a group turn is the most-permissive
                MEMBER's phone (Feature 039's group RBAC resolution, possibly
                a different person entirely, chosen only for its role/token
                limit). Message.sender must always be who actually sent this
                specific message, never whoever's role happened to govern the
                turn. Falls back to `user_phone` when not given (the 1:1 case,
                where they're always the same person anyway).

        Returns:
            AIResponse with generated text or fallback message

        Raises:
            PermissionError: If user is blocked (when RBAC enabled)
        """
        # Use provided chat_id or fall back to request.chat_id
        effective_chat_id = chat_id or request.chat_id

        # RBAC: Check if user is blocked
        user_obj = None
        if self.rbac_enabled and self.user_manager:
            effective_user_phone = user_phone or sender
            if effective_user_phone:
                user_obj = self.user_manager.get_user(effective_user_phone)

                if user_obj.is_blocked:
                    logger.warning(f"Blocked user attempted to get response: {effective_user_phone}")
                    raise PermissionError(f"User is blocked: {effective_user_phone}")

        # Feature 022: if a document-creation MCP call is pending approval for
        # this chat, this turn resolves it (approve/decline) instead of being
        # processed as a normal new request. Returns None only for the decline
        # case, meaning: fall through and process this message as a fresh turn.
        logger.info(
            f"[022] get_response: effective_chat_id={effective_chat_id!r}, "
            f"user_obj={'present' if user_obj else None}, "
            f"user_prompt={request.user_prompt!r}"
        )
        pending = self.pending_approval_manager.get(effective_chat_id) if user_obj else None
        logger.info(f"[022] pending_approval_manager.get({effective_chat_id!r}) -> {pending!r}")
        if pending is not None:
            logger.info(
                f"[022] Pending approval FOUND for chat={effective_chat_id!r} - "
                f"routing to _resolve_pending_approval instead of a normal turn"
            )
            resolved = self._resolve_pending_approval(
                pending, request, effective_chat_id, user_obj, user_role, sender, recipient,
                user_phone=user_phone, is_group=is_group, chat_name=chat_name,
                sender_phone=sender_phone
            )
            logger.info(
                f"[022] _resolve_pending_approval returned "
                f"{'an AIResponse (approved)' if resolved is not None else 'None (declined - falling through to a normal turn)'}"
            )
            if resolved is not None:
                return resolved
        else:
            logger.info(f"[022] No pending approval for chat={effective_chat_id!r} - normal turn processing")
            # Reminders (Feature 054): checked only when there's no MCP pending
            # approval - at most one of the two managers is ever populated for a
            # given chat_id in practice (a user doesn't have two simultaneous
            # approval flows), and this order is deterministic (matches
            # contracts/local-tool-approval-gate.md).
            local_pending = self.pending_local_tool_approval_manager.get(effective_chat_id) if user_obj else None
            if local_pending is not None:
                logger.info(
                    f"[054] Pending local-tool approval FOUND for chat={effective_chat_id!r} - "
                    "routing to _resolve_pending_local_tool_approval instead of a normal turn"
                )
                local_resolved = self._resolve_pending_local_tool_approval(
                    local_pending, request, effective_chat_id, user_obj, user_role, sender, recipient
                )
                if local_resolved is not None:
                    return local_resolved

        # Retrieve conversation history if memory enabled
        conversation_history = None
        if self.memory_enabled and self.session_manager and effective_chat_id:
            try:
                # RBAC: Use user's token limit if enabled
                if self.rbac_enabled and user_obj:
                    max_tokens = user_obj.token_limit
                else:
                    # Existing behavior: use role-based token limits
                    max_tokens = self.max_tokens_by_role.get(user_role, 4000)

                conversation_history = self.session_manager.get_conversation_history(
                    whatsapp_chat=effective_chat_id,
                    max_tokens=max_tokens
                )
                if conversation_history:
                    logger.info(f"Retrieved {len(conversation_history)} messages from session history")
            except Exception as e:
                logger.error(f"Failed to retrieve conversation history: {e}", exc_info=True)

        try:
            # Morning MCP tools (Feature 018, RBAC-gated) + the ledger-event tool
            # (Feature 024, always attached) merged into one tools list.
            tools = self._assemble_tools(user_obj, request.request_id)

            # Call OpenAI Responses API with retry logic, conversation history, and
            # whichever tools apply this turn
            response = self._call_openai_api(request, conversation_history=conversation_history, tools=tools)

            return self._finalize_response(
                request, response, effective_chat_id, user_obj, user_role, sender, recipient, tools,
                user_phone=user_phone, is_group=is_group, chat_name=chat_name,
                sender_phone=sender_phone
            )

        except APITimeoutError as e:
            logger.error(
                f"OpenAI API timeout for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "Sorry, I'm having trouble connecting to my AI service. Please try again later."
            )

        except RateLimitError as e:
            logger.error(
                f"OpenAI rate limit exceeded for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "I'm currently at capacity. Please try again in a minute."
            )

        except APIError as e:
            logger.error(
                f"OpenAI API error for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "Sorry, I encountered an error processing your request. Please try again."
            )

        except Exception as e:
            logger.error(
                f"Unexpected error in get_response for request {request.request_id}: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "Sorry, I encountered an unexpected error. Please try again."
            )

    def _handle_accounting_reconciliation_capture(self, response) -> List[str]:
        """Feature 025 (Morning-Sourced Ledger Events): thin adapter for the
        accounting-document reconciliation sweep's headless OpenAI+MCP call
        (services/accounting_reconciliation_service.py) - parses every
        capture_ledger_event call in `response` and passes each straight
        through to LedgerEventManager.add_ledger_events_from_call,
        unconditionally.

        Structurally separate from the conversational post-turn recognition
        call (`recognize_ledger_event`, Feature 069):
        - NO same-turn-mcp_call suppression - list_invoices/
          get_invoice_details mcp_calls co-occurring with capture_ledger_event
          in the same turn is the normal, expected shape here.
        - NO one-call-per-turn limit - calling once per new document, several
          times in the same sweep tick, is the normal case.
        - NO dedup/anomaly decision of its own (round 3 of spec.md's
          Clarifications: "it's clearly a ledger requirement regardless of
          ai") - LedgerEventManager.add_ledger_event owns that entirely via
          its own in-memory cache; this handler trusts it completely, same
          as every other capture path.
        - NO follow-up OpenAI round-trip, no confirmation reply - this is not
          a conversational turn, nothing user-facing is ever produced here.

        Returns the list of newly-persisted event_ids (empty if nothing was
        captured, or everything was a true duplicate/malformed).
        """
        calls = extract_all_function_calls(response, LEDGER_EVENT_TOOL["name"])
        event_ids: List[str] = []
        for call in calls:
            if call["arguments"] is None:
                logger.error(
                    "[025] Reconciliation sweep: capture_ledger_event call had "
                    f"unparseable arguments (call_id={call['call_id']!r}) - rejected, "
                    "not silently dropped"
                )
                continue
            # message_timestamp=None: this sweep has no real source message, and
            # LedgerEventManager.add_ledger_event already derives the correct
            # event_datetime itself for source_type=חשבונית directly from the
            # Morning document's own creation timestamp (carried inside
            # accounting_document_json, expanded internally) - it only falls
            # back to message_timestamp/now_local() when that's unavailable.
            # A prior separate ai_handler-side timestamp derivation here
            # (removed 2026-08-25) was redundant with that and, since it read
            # the raw un-expanded call arguments, never actually fired.
            try:
                new_event_ids = self.ledger_event_manager.add_ledger_events_from_call(
                    session_id="accounting-reconciliation",
                    call_arguments=call["arguments"],
                    message_id=None,
                    message_timestamp=None,
                )
                event_ids.extend(new_event_ids)
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    f"[025] Failed to persist accounting-document ledger event(s): {e}",
                    exc_info=True
                )
        return event_ids

    def _handle_reminder_creation_proposal(
        self, request: AIRequest, response, effective_chat_id: Optional[str],
    ) -> "tuple[Optional[str], bool]":
        """Reminders (Feature 054): detect a `create_reminder` function_call and
        turn it into a pending local-tool approval - never dispatched immediately.
        Unlike the MCP approval-request path, no
        second OpenAI round-trip happens here either: the approval summary is
        built deterministically from the (validated, rounded) arguments, same
        "state exactly what will happen" discipline as
        _build_pending_approval_details (bugfix-028 B3/A4).

        Returns (response_text_override, new_local_tool_pending_created).
        response_text_override is None when no create_reminder call was made
        this turn - the caller leaves response_text untouched in that case.
        """
        if effective_chat_id is None:
            return None, False

        args = extract_function_call(response, CREATE_REMINDER_TOOL["name"])
        if args is None:
            return None, False

        try:
            # cast: args is a Dict[Any, Any] (from json.loads), so .get() is
            # typed Any to mypy - ReminderManager.resolve_schedule validates
            # the actual value at runtime regardless (InvalidRecurrenceError on
            # anything not a real "one_time"/"recurring" string), this is a
            # type-checker signal only.
            rrule_str, dtstart = self.reminder_manager.resolve_schedule(
                schedule_type=cast(str, args.get("schedule_type")),
                one_time_due_at=args.get("one_time_due_at"),
                recurrence=args.get("recurrence"),
            )
        except ReminderPastDateError as e:
            logger.info(f"[054] create_reminder proposal rejected (past date): {e}")
            return REMINDER_PAST_DATE_REJECTED, False
        except InvalidRecurrenceError as e:
            logger.warning(f"[054] create_reminder proposal rejected (invalid recurrence): {e}")
            return REMINDER_ACTION_FAILED_TRY_AGAIN, False

        # Proposal-time cap check (UX: reject immediately rather than proposing
        # something that will fail at approval time) - re-checked again at
        # actual approval/persist time regardless (TOCTOU-closing, see
        # contracts/local-tool-approval-gate.md), never trusted from this check
        # alone.
        if len(self.reminder_manager.list_active()) >= self.reminder_manager.max_active_reminders:
            logger.info(f"[054] create_reminder proposal rejected (cap reached): chat={effective_chat_id!r}")
            return REMINDER_CAP_EXCEEDED, False

        pending = PendingLocalToolApproval(
            tool_name=CREATE_REMINDER_TOOL["name"],
            response_id=response.id,
            call_id=extract_function_call_id(response, CREATE_REMINDER_TOOL["name"]) or "",
            arguments=args,
            created_at=now_local().isoformat(),
        )
        self.pending_local_tool_approval_manager.set(effective_chat_id, pending)
        logger.info(
            f"[054] Pending local-tool approval created for chat={effective_chat_id!r}, "
            f"tool={CREATE_REMINDER_TOOL['name']!r}, due_at={dtstart.isoformat()}"
        )
        details = _build_reminder_approval_details(
            CREATE_REMINDER_TOOL["name"], args, dtstart.isoformat(), rrule_str
        )
        return details, True

    def _call_openai_list_reminders_followup_api(
        self, request: AIRequest, previous_response_id: str, call_id: str,
        reminders_summary: List[Dict[str, Any]], tools: Optional[List[Dict]] = None,
    ):
        """Reports list_reminders' result back as that call's function_call_output,
        via a follow-up chained to the SAME turn's response.id - same pattern as
        _call_openai_query_ledger_events_followup_api (list_reminders dispatches
        immediately, unlike create/modify/delete_reminder, so no PendingLocalToolApproval
        is involved and no later turn is needed).
        """
        output_items = [{
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps({"reminders": reminders_summary}, ensure_ascii=False),
        }]
        kwargs = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution),
            "input": output_items,
            "previous_response_id": previous_response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        logger.info(f"[054] _call_openai_list_reminders_followup_api: call_id={call_id!r}")
        _log_outgoing_request("_call_openai_list_reminders_followup_api", kwargs)
        response = self.client.responses.create(**kwargs)  # type: ignore[call-overload]
        _log_raw_response("_call_openai_list_reminders_followup_api", response)
        return response

    def _handle_list_reminders(self, request: AIRequest, response, tools: Optional[List[Dict]]):
        """Reminders (Feature 054): list_reminders (FR-013) is read-only, dispatched
        immediately (unlike create/modify/delete_reminder), same as
        capture_ledger_event - needs a follow-up round-trip for the same reason
        (reasoning models emit function_call OR message, never both in one turn).

        Returns the follow-up response (whose output_text/usage should replace the
        original response's), or None if no list_reminders call was made this turn,
        or if the follow-up call itself failed.
        """
        call_id = extract_function_call_id(response, LIST_REMINDERS_TOOL["name"])
        if call_id is None:
            return None

        reminders = self.reminder_manager.list_active()
        summary = [
            {
                "reminder_id": r["reminder_id"],
                "message_text": r["message_text"],
                "schedule": _format_reminder_schedule(r["rrule"], r["dtstart"]),
            }
            for r in reminders
        ]
        try:
            return self._call_openai_list_reminders_followup_api(
                request, response.id, call_id, summary, tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[054] list_reminders follow-up call failed: {e}", exc_info=True)
            return None

    def _call_openai_query_ledger_events_followup_api(
        self, request: AIRequest, previous_response_id: str,
        outputs: List[Dict[str, Any]], tools: Optional[List[Dict]] = None,
    ):
        """Feature 044 (research.md Decision 10): report EVERY
        query_ledger_events call's own result back as its own
        function_call_output, via a follow-up chained to the SAME turn's
        response.id - multi-item batched (a list comprehension, one output item per call_id),
        NOT _call_openai_list_reminders_followup_api's single-item shape,
        since a turn may contain several query_ledger_events calls at once.

        outputs: list of {"call_id": str, "payload": dict} - one entry per
        query_ledger_events call from the previous turn, in the order
        extract_all_function_calls found them. OpenAI rejects the follow-up
        outright if any pending call from that turn is left unresolved, so
        EVERY call_id - a real result or a parse-failure error (data-model.md
        shape D) - must appear here, none silently omitted.
        """
        output_items = [
            {
                "type": "function_call_output",
                "call_id": item["call_id"],
                "output": json.dumps(item["payload"], ensure_ascii=False),
            }
            for item in outputs
        ]
        kwargs = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution, today_timestamp=request.timestamp),
            "input": output_items,
            "previous_response_id": previous_response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        call_ids = [item["call_id"] for item in outputs]
        logger.info(f"[044] _call_openai_query_ledger_events_followup_api: call_ids={call_ids!r}")
        logger.debug(f"[044][RAWLOG] query_events payload(s) sent back to model: {outputs!r}")
        _log_outgoing_request("_call_openai_query_ledger_events_followup_api", kwargs)
        response = self.client.responses.create(**kwargs)  # type: ignore[call-overload]
        _log_raw_response("_call_openai_query_ledger_events_followup_api", response)
        return response

    def _handle_query_ledger_events(self, request: AIRequest, response, tools: Optional[List[Dict]]):
        """Feature 044 (research.md Decision 10): query_ledger_events is
        read-only, dispatched immediately (like list_reminders) - needs a
        follow-up round-trip for the same reasoning-model
        function_call-OR-message limitation.

        UNLIKE list_reminders (single-call), this uses
        extract_all_function_calls: a turn may legitimately contain SEVERAL
        query_ledger_events calls (e.g. "client A or client B" - the model
        calls once per criterion and combines results itself). query_ledger_events
        writes nothing, so every call is independent and safe to execute
        regardless of how many others are present this turn.

        A call whose arguments fail to parse (truncated mid-generation, same
        failure mode bugfix-018 guards against) gets its own isolated error
        output (data-model.md shape D) WITHOUT affecting any other call from
        the same turn - never a whole-turn rejection.

        Returns the follow-up response (whose output_text/usage should
        replace the original response's), or None if no query_ledger_events
        call was made this turn, or if the follow-up call itself failed.
        """
        calls = extract_all_function_calls(response, QUERY_LEDGER_EVENTS_TOOL["name"])
        if not calls:
            return None
        logger.debug(
            f"[044][RAWLOG] query_ledger_events calls extracted from response.id="
            f"{getattr(response, 'id', None)!r}: {calls!r}"
        )

        outputs = []
        for call in calls:
            if call["arguments"] is None:
                logger.warning(
                    f"[044] query_ledger_events call {call['call_id']!r} had unparseable "
                    "arguments (likely truncated) - reporting an isolated error for this "
                    "call only, other calls this turn are unaffected"
                )
                outputs.append({
                    "call_id": call["call_id"],
                    "payload": {
                        "status": "error",
                        "reason": "Arguments could not be parsed - do not resubmit this exact call.",
                    },
                })
                continue
            logger.debug(
                f"[044][RAWLOG] query_ledger_events call {call['call_id']!r} - "
                f"calling LedgerEventManager.query_events with arguments={call['arguments']!r}"
            )
            result = self.ledger_event_manager.query_events(**call["arguments"])
            logger.debug(
                f"[044][RAWLOG] query_ledger_events call {call['call_id']!r} - "
                f"query_events returned: {result!r}"
            )
            outputs.append({"call_id": call["call_id"], "payload": result})

        try:
            return self._call_openai_query_ledger_events_followup_api(
                request, response.id, outputs, tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[044] query_ledger_events follow-up call failed: {e}", exc_info=True)
            return None

    def _handle_reminder_modify_or_delete_proposal(
        self, request: AIRequest, response, effective_chat_id: Optional[str],
    ) -> "tuple[Optional[str], bool]":
        """Reminders (Feature 054): detect a modify_reminder/delete_reminder
        function_call and turn it into a pending local-tool approval - same
        pattern as _handle_reminder_creation_proposal, covering both tools since
        their proposal-time handling (lookup, scope validation, approval-summary
        build) is nearly identical.

        Returns (response_text_override, new_local_tool_pending_created) - same
        contract as _handle_reminder_creation_proposal.
        """
        if effective_chat_id is None:
            return None, False

        for tool_name in (MODIFY_REMINDER_TOOL["name"], DELETE_REMINDER_TOOL["name"]):
            args = extract_function_call(response, tool_name)
            if args is not None:
                return self._propose_reminder_modify_or_delete(
                    tool_name, args, request, response, effective_chat_id
                )
        return None, False

    def _propose_reminder_modify_or_delete(
        self, tool_name: str, args: Dict[str, Any], request: AIRequest, response,
        effective_chat_id: str,
    ) -> "tuple[Optional[str], bool]":
        # DEBUG (2026-08-18, root-causing a real billed-test failure): the raw
        # function_call arguments exactly as the model supplied them, before any
        # parsing/validation - occurrence_date_hint in particular, since it must
        # exactly match a real generated occurrence datetime downstream
        # (ReminderManager._upsert_exception logs the actual candidate set).
        logger.debug(f"[054] {tool_name} raw args from model: {args!r}")
        reminder_id = args.get("reminder_id")
        scope = args.get("scope")
        if scope not in ("single_occurrence", "whole_series"):
            logger.warning(f"[054] {tool_name} proposal rejected (invalid scope): {scope!r}")
            return REMINDER_ACTION_FAILED_TRY_AGAIN, False

        current = self.reminder_manager.get_reminder(cast(str, reminder_id))
        if current is None:
            logger.warning(f"[054] {tool_name} proposal rejected (reminder not found): {reminder_id!r}")
            return REMINDER_ACTION_FAILED_TRY_AGAIN, False

        if scope == "single_occurrence" and not args.get("occurrence_date_hint"):
            logger.warning(f"[054] {tool_name} proposal rejected (missing occurrence_date_hint)")
            return REMINDER_ACTION_FAILED_TRY_AGAIN, False
        if scope == "single_occurrence" and current["rrule"] is None:
            logger.warning(f"[054] {tool_name} proposal rejected (single_occurrence on a one-time reminder)")
            return REMINDER_ACTION_FAILED_TRY_AGAIN, False

        # Proposal-time validation only (UX: reject immediately rather than
        # proposing something that will fail at approval time) - discarded, not
        # persisted; re-validated for real at approval time (TOCTOU-closing, see
        # contracts/local-tool-approval-gate.md).
        try:
            if scope == "single_occurrence":
                # Bug fix (2026-08-18): validate occurrence_date_hint resolves to
                # exactly one real occurrence NOW, at proposal time, rather than
                # only discovering a bad/mismatched hint at approval time (or
                # worse, silently succeeding at approval time with an orphaned
                # exception that never actually overrides anything - the original
                # bug, root-caused via a real billed-test failure).
                self.reminder_manager.resolve_occurrence_datetime(
                    cast(str, reminder_id), current, cast(str, args.get("occurrence_date_hint"))
                )
            if tool_name == MODIFY_REMINDER_TOOL["name"]:
                if scope == "single_occurrence" and args.get("new_due_at"):
                    self.reminder_manager.resolve_schedule("one_time", args["new_due_at"], None)
                elif scope == "whole_series":
                    if current["rrule"] is not None and args.get("new_recurrence"):
                        self.reminder_manager.resolve_schedule("recurring", None, args["new_recurrence"])
                    elif current["rrule"] is None and args.get("new_due_at"):
                        self.reminder_manager.resolve_schedule("one_time", args["new_due_at"], None)
        except ReminderPastDateError as e:
            logger.info(f"[054] {tool_name} proposal rejected (past date): {e}")
            return REMINDER_PAST_DATE_REJECTED, False
        except InvalidRecurrenceError as e:
            logger.warning(f"[054] {tool_name} proposal rejected (invalid recurrence): {e}")
            return REMINDER_ACTION_FAILED_TRY_AGAIN, False
        except OccurrenceNotFoundError as e:
            logger.warning(f"[054] {tool_name} proposal rejected (occurrence_date_hint mismatch): {e}")
            return REMINDER_ACTION_FAILED_TRY_AGAIN, False

        pending = PendingLocalToolApproval(
            tool_name=tool_name,
            response_id=response.id,
            call_id=extract_function_call_id(response, tool_name) or "",
            arguments=args,
            created_at=now_local().isoformat(),
        )
        self.pending_local_tool_approval_manager.set(effective_chat_id, pending)
        logger.info(
            f"[054] Pending local-tool approval created for chat={effective_chat_id!r}, "
            f"tool={tool_name!r}, reminder_id={reminder_id!r}, scope={scope!r}"
        )
        details = _build_reminder_approval_details(
            tool_name, args, current_message_text=current["message_text"]
        )
        return details, True

    @staticmethod
    def _extract_mcp_error_text(call) -> str:
        """Pull human-readable failure text off a Responses API `mcp_call`
        item's `.error` field (client-name-resolution root-cause fix
        follow-up, 2026-08-12).

        Before this fix, a failed MCP tool call still reported `error=None`
        and carried its failure text in `.output`, indistinguishable from
        success - `.error` was never populated by anything upstream. Now
        that morning-mcp-app's tools raise real, typed failures instead of
        returning ordinary refusal text, a failed call has `output=None` and
        a real `.error` object instead - confirmed live (real OpenAI call,
        real MCP server, no mocking): `error` is a dict shaped
        `{"type": "mcp_tool_execution_error", "content": [{"type": "text",
        "text": "<our friendly message>"}]}`. Without this, the B4(b)
        zero-execution failure-detail extraction below would silently lose
        the actual reason (falling through to a fully generic message)
        every time, since it only ever looked at `.output`.
        """
        error = getattr(call, "error", None)
        if not error:
            return ""
        content = error.get("content") if isinstance(error, dict) else getattr(error, "content", None)
        if not content:
            return ""
        for block in content:
            text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
            if text:
                return str(text)
        return ""

    def _run_local_tool_dispatch_loop(
        self, request: AIRequest, response, effective_chat_id: Optional[str],
        sender: Optional[str], tools: Optional[List[Dict]],
    ):
        """The multi-round local-tool dispatch loop extracted out of
        `_finalize_response` (2026-08-25 - see MAX_LOCAL_TOOL_LOOP_ITERATIONS's
        own comment for the incident/design rationale). Repeatedly re-runs
        `_handle_query_ledger_events` / `_handle_list_reminders` against
        whichever response is current, following up whenever one of them fires,
        until a full pass makes no further progress (real text, or a terminal
        pending-approval item - those are never auto-continued past) or the
        iteration cap is hit.

        Feature 069 (mechanism move): ledger *capture* is no longer one of the
        loop's handlers - it is a dedicated post-turn recognition step outside
        this turn entirely. `ledger_event_ids` stays in the return tuple (always
        empty now) so callers' unpacking is unchanged.

        Returns (final_response, extra_tokens, extra_prompt_tokens,
        extra_completion_tokens, usage_response, ledger_event_ids) - the
        three "extra_*" fields are deltas to ADD to the caller's own running
        totals (which already include the turn's original response.usage),
        never absolute totals themselves. `usage_response` is whichever
        response's usage/finish_reason is authoritative (the last one that
        actually produced a follow-up, or the original if none did).
        """
        current_response = response
        usage_response = response
        extra_tokens = extra_prompt_tokens = extra_completion_tokens = 0
        ledger_event_ids: List[str] = []
        for _loop_round in range(MAX_LOCAL_TOOL_LOOP_ITERATIONS):
            made_progress = False

            # Ledger Event Querying (Feature 044): query_ledger_events is
            # read-only, dispatched immediately (may involve SEVERAL calls in
            # one turn - see research.md Decision 10), and needs a follow-up
            # round-trip for its reply for the same function_call-OR-message
            # reason as everything else in this loop.
            ledger_query_followup = self._handle_query_ledger_events(
                request, current_response, tools
            )
            if ledger_query_followup is not None:
                current_response = ledger_query_followup
                usage_response = ledger_query_followup
                extra_tokens += ledger_query_followup.usage.total_tokens
                extra_prompt_tokens += ledger_query_followup.usage.input_tokens
                extra_completion_tokens += ledger_query_followup.usage.output_tokens
                made_progress = True
                continue

            # Reminders (Feature 054): list_reminders is read-only, dispatched
            # immediately (unlike create/modify/delete_reminder), and needs a
            # follow-up round-trip for its reply for the same function_call-
            # OR-message reason as ledger events.
            list_reminders_followup = self._handle_list_reminders(
                request, current_response, tools
            )
            if list_reminders_followup is not None:
                current_response = list_reminders_followup
                usage_response = list_reminders_followup
                extra_tokens += list_reminders_followup.usage.total_tokens
                extra_prompt_tokens += list_reminders_followup.usage.input_tokens
                extra_completion_tokens += list_reminders_followup.usage.output_tokens
                made_progress = True
                continue

            break  # a full pass made no progress - current_response is final
        else:
            logger.error(
                f"[LOOP] Local-tool dispatch loop hit MAX_LOCAL_TOOL_LOOP_ITERATIONS "
                f"({MAX_LOCAL_TOOL_LOOP_ITERATIONS}) without settling for request "
                f"{request.request_id} - forcing stop; the model may be stuck "
                "repeatedly calling tools. Whatever current_response holds now is "
                "used as final."
            )

        return (
            current_response, extra_tokens, extra_prompt_tokens,
            extra_completion_tokens, usage_response, ledger_event_ids,
        )

    def _finalize_response(self, request: AIRequest, response, effective_chat_id: Optional[str],
                           user_obj, user_role: str, sender: Optional[str],
                           recipient: Optional[str], tools: Optional[List[Dict]], *,
                           user_phone: Optional[str] = None, is_group: bool = False,
                           chat_name: Optional[str] = None,
                           sender_phone: Optional[str] = None) -> AIResponse:
        """
        Shared post-API-call logic: extract mcp_calls, detect a new pending
        approval (Feature 022), store messages in session, build the final
        AIResponse. Used by both the normal turn path and the pending-approval
        resolution path in `get_response`/`_resolve_pending_approval`.
        """
        # Extract response
        response_text = response.output_text
        tokens_used = response.usage.total_tokens
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        usage_response = response  # tracks whichever call's usage/finish_reason is authoritative

        # Local-tool dispatch LOOP (2026-08-25 architectural fix - see
        # MAX_LOCAL_TOOL_LOOP_ITERATIONS's own comment for the incident this
        # replaced, and _run_local_tool_dispatch_loop's own docstring for the
        # mechanics). This used to be a fixed one-hop chain: each of the three
        # local-tool handlers ran exactly once, against the turn's ORIGINAL
        # response only. Now they're re-run in a real loop against whichever
        # response is current, so a model that calls a local tool, gets its
        # result, and then legitimately calls another one (the same tool
        # again, or a different one) keeps getting executed and followed up,
        # instead of being silently stranded.
        (
            current_response, extra_tokens, extra_prompt_tokens,
            extra_completion_tokens, usage_response, ledger_event_ids,
        ) = self._run_local_tool_dispatch_loop(
            request, response, effective_chat_id, sender, tools
        )
        tokens_used += extra_tokens
        prompt_tokens += extra_prompt_tokens
        completion_tokens += extra_completion_tokens

        # `response` is reassigned (not just a new local name) so every use
        # below this point - mcp_calls extraction, approval_requests
        # extraction, PendingApproval.response_id, the [022] log line, the
        # final observability retention - automatically reflects whichever
        # response the loop above actually settled on, not the turn's
        # original response. This also fixes a real, related gap: previously
        # those checks only ever looked at the ORIGINAL response, so an
        # mcp_approval_request or mcp_call that only appeared after a local-
        # tool round (e.g. right after a query_ledger_events lookup) was
        # invisible to them entirely.
        response = current_response
        response_text = response.output_text

        # Bug fix (2026-08-18, caught by a real billed test): when list_reminders
        # was called this turn, the model - now knowing the reminder_id - very
        # often calls create/modify/delete_reminder in the SAME follow-up
        # response, not the original one. create/modify/delete detection below
        # already sees this naturally now: `response` above IS whichever
        # response the loop last produced, so no separate reminder_tool_response
        # variable is needed any more (2026-08-25 - the loop generalizes what
        # this used to special-case for exactly one pairing).
        reminder_tool_response = response

        # Reminders (Feature 054): a create_reminder call produces empty
        # output_text too (same reasoning-model function_call-OR-message
        # limitation as ledger events), but unlike ledger capture, this NEVER
        # dispatches immediately - it becomes a pending local-tool approval, and
        # response_text is replaced with a deterministic summary (no second
        # OpenAI round-trip needed at proposal time, unlike the ledger path).
        reminder_details, new_local_tool_pending_created = self._handle_reminder_creation_proposal(
            request, reminder_tool_response, effective_chat_id
        )
        if reminder_details is not None:
            response_text = reminder_details

        # Reminders (Feature 054): modify_reminder/delete_reminder proposals -
        # same pending-approval pattern as create_reminder. Only checked if
        # create_reminder didn't already claim this turn (a turn calls at most
        # one reminder tool in practice).
        if not new_local_tool_pending_created:
            modify_delete_details, modify_delete_pending_created = (
                self._handle_reminder_modify_or_delete_proposal(
                    request, reminder_tool_response, effective_chat_id
                )
            )
            if modify_delete_details is not None:
                response_text = modify_delete_details
                new_local_tool_pending_created = modify_delete_pending_created

        # bugfix-045-followup (2026-08-27): this used to need its own
        # all_output_items union of response.output + a same-turn ledger-
        # capture followup's output, to fix the exact scenario the bugfix-045
        # near-duplicate-name regression test exposed (a capture_ledger_event
        # follow-up round ALSO proposing an approval-gated Morning tool, e.g.
        # add_client, whose mcp_approval_request then went undetected).
        # Superseded by the merge from master (2026-08-27): the
        # `_run_local_tool_dispatch_loop` architectural fix above (2026-08-25,
        # landed independently on master while this branch was still on the
        # pre-loop code) already reassigns `response = current_response` to
        # whichever response the loop actually settled on - `response.output`
        # below is now already correct on its own, loop-followup items
        # included, so the extra union is redundant (and would in fact be
        # broken here, since the loop no longer exposes a same-named
        # `followup` local variable to reference). Re-verified: the
        # regression test still passes against this simpler, already-fixed
        # upstream code.
        logger.info(
            f"[022] _finalize_response: response.id={getattr(response, 'id', None)!r}, "
            f"effective_chat_id={effective_chat_id!r}, "
            f"output item types={[getattr(i, 'type', None) for i in (response.output or [])]!r}, "
            f"output_text={response_text!r}"
        )

        # Extract Morning MCP tool calls, if any (REQ-SEC-002 audit logging;
        # also lets E2E tests verify tool usage without a second AI call).
        # Includes arguments/output for diagnosability (e.g. confirming
        # which internal_morning_id the model actually passed to a follow-up tool
        # call) - never logged/returned with secrets, just tool I/O.
        mcp_calls = [
            {
                "name": item.name,
                "error": item.error,
                "arguments": item.arguments,
                "output": item.output
            }
            for item in (response.output or [])
            if getattr(item, "type", None) == "mcp_call"
        ]
        if mcp_calls:
            logger.info(f"MCP calls for request {request.request_id}: {mcp_calls}")
        elif tools and any(
            phrase in response_text
            for phrase in ("הוצאה בהצלחה", "סומנה כשולמה", "בוטלה בהצלחה", "נוסף בהצלחה")
        ):
            # Invoicing tools were offered this turn and the reply reads like
            # a state-changing confirmation, but no mcp_call was made - the
            # model may have pattern-completed a fabricated success from
            # earlier turns instead of actually calling the tool. Log only;
            # this is a detection safety net, not a behavior change.
            logger.warning(
                f"Possible hallucinated invoicing confirmation for request "
                f"{request.request_id}: reply text suggests a state-changing "
                f"action succeeded, but no MCP tool was called. "
                f"Reply: {response_text!r}"
            )

        # Feature 022: a document-creation tool call may come back as an
        # mcp_approval_request instead of an mcp_call - nothing executed on
        # the Morning side yet. Track it so the next turn can resolve it.
        approval_requests = [
            item for item in (response.output or [])
            if getattr(item, "type", None) == "mcp_approval_request"
        ]
        logger.info(
            f"[022] approval_requests found in this turn's output: {len(approval_requests)} "
            f"(effective_chat_id={effective_chat_id!r})"
        )
        # Feature 047: this turn creates a pending approval iff the block above will
        # actually store one - same condition, computed once here so both the
        # PendingApproval creation below and AIResponse.offer_approval_buttons stay
        # in lockstep by construction (never two separately-maintained conditions
        # that could drift apart).
        new_pending_approval_created = bool(approval_requests and effective_chat_id)
        if approval_requests and effective_chat_id:
            ar = approval_requests[0]
            new_pending = PendingApproval(
                response_id=response.id,
                approval_request_id=ar.id,
                tool_name=ar.name,
                arguments=ar.arguments,
                server_label=ar.server_label,
                created_at=now_local().isoformat(),
            )
            self.pending_approval_manager.set(effective_chat_id, new_pending)
            logger.info(
                f"[022] pending_approval_manager.set({effective_chat_id!r}, {new_pending!r}) - "
                f"store id now: {id(self.pending_approval_manager)}"
            )
            logger.info(
                f"Pending MCP approval created for chat={effective_chat_id}, "
                f"tool={ar.name}, request={request.request_id}"
            )
            # bugfix-028 B3: the authoritative statement of what will be created
            # is appended EVERY time, not only when the model stayed silent. The
            # model's narration is conversation; this is the record of the action
            # being authorised, and the user must see the same fields in the same
            # place on every approval - including the ones the model's own
            # phrasing dropped (in production: "לפני מע״מ" and the purpose).
            # bugfix-038: mcp_calls (this SAME turn's already-executed real tool
            # calls, extracted above) is passed through so a Group B reference
            # tool's approval can be enriched with the referenced document's own
            # real data - see _find_referenced_document_details.
            details = _build_pending_approval_details(ar.name, ar.arguments, mcp_calls)
            if response_text.strip():
                response_text = f"{response_text.strip()}\n\n{details}"
            else:
                response_text = details
                logger.warning(
                    f"Model produced no narrating text alongside a pending "
                    f"approval for request {request.request_id} - the approval "
                    f"details block is the entire reply."
                )

            # (The former "model narrated nothing" fallback that lived here is
            # gone: _build_pending_approval_details above now runs on every
            # approval turn, so response_text can no longer be empty at this
            # point. `_build_pending_approval_fallback_text` is kept as the
            # one-line summary form used elsewhere.)
        elif approval_requests and not effective_chat_id:
            logger.warning(
                f"[022] mcp_approval_request found but effective_chat_id is falsy "
                f"({effective_chat_id!r}) - pending approval NOT stored, this request will be lost!"
            )

        # Generic final safety net (2026-08-25, replaces the old ledger-only
        # one that used to live where the local-tool loop above now is).
        # By this point every legitimate reason response_text could still be
        # empty has already filled it in: a pending MCP approval (block
        # above), a pending local-tool approval (reminder_details/
        # modify_delete_details), or the model actually producing text. The
        # NO_REPLY sentinel is never empty-string, so it can never trip this.
        # Anything else reaching here empty means some round-trip genuinely
        # failed (a follow-up call raised, the loop above hit its iteration
        # cap, or a case nobody's hit yet) - never let that surface as a
        # silent, crash-inducing empty WhatsApp reply (see
        # AIResponse.__post_init__'s own guard, and MAX_LOCAL_TOOL_LOOP_
        # ITERATIONS's comment for the incident this generalizes).
        if not response_text.strip():
            logger.error(
                f"[LOOP] response_text still empty for request {request.request_id} "
                f"after all local-tool/approval handling - using generic fallback "
                "text so the user never receives a silently empty reply or a crash."
            )
            response_text = LEDGER_FOLLOWUP_FAILED_TRY_AGAIN

        logger.info(
            f"AI response generated for request {request.request_id}: "
            f"{tokens_used} tokens, {len(response_text)} chars"
        )
        logger.debug(f"Full response: {response_text[:200]}...")

        # Feature 039 (US4a): the model signals "send nothing" by returning exactly
        # the sentinel as its entire response - the user's message is still
        # persisted below (conversation context isn't lost), but no assistant
        # reply is stored, and the caller (denidin.py) must not send anything.
        should_reply = response_text.strip() != NO_REPLY_SENTINEL

        # Store messages in session if memory enabled
        if self.memory_enabled and self.session_manager and effective_chat_id:
            try:
                # 2026-08-19: real WhatsApp identifiers for Message.sender/
                # .recipient, replacing the old Feature 039 sentinel-retirement
                # scheme (recipient=None for role="user", sender=None for
                # role="assistant"). `sender` (this method's own parameter) stays
                # the resolved display name - now Message.sender_name.
                # own_whatsapp_number is bare digits (bugfix-024's getWaSettings
                # call) - "" when unresolved (e.g. no live Green API client, the
                # player), same fail-open convention as everywhere else it's used.
                own_number_jid = f"{self.own_whatsapp_number}@c.us" if self.own_whatsapp_number else None
                # sender_phone (this method's own param) is the ACTUAL sender's
                # JID - deliberately NOT user_phone, which for a group turn is
                # the most-permissive MEMBER's phone (possibly someone else
                # entirely - see get_response's docstring). Falls back to
                # user_phone (1:1 case, always the same person), then to
                # effective_chat_id as a last resort (Green API's own 1:1
                # chatId IS the contact's JID - never true for a group).
                resolved_sender_phone = sender_phone or user_phone or (
                    effective_chat_id if not is_group else None
                )
                sender_name_val = sender
                # A group message is addressed to the whole group (its own
                # JID/name), regardless of which individual sent it or that
                # DeniDin is replying - never to one member, never to DeniDin
                # alone.
                user_msg_recipient = effective_chat_id if is_group else own_number_jid
                user_msg_recipient_name = (chat_name or effective_chat_id) if is_group else "DeniDin"
                assistant_msg_recipient = effective_chat_id if is_group else resolved_sender_phone
                assistant_msg_recipient_name = (chat_name or effective_chat_id) if is_group else sender_name_val

                if self.rbac_enabled and user_obj:
                    # Store user message with token limit
                    self.session_manager.add_message_with_token_limit(
                        chat_id=effective_chat_id,
                        role="user",
                        content=request.user_prompt,
                        user_role=user_obj.role,
                        token_limit=user_obj.token_limit,
                        sender=resolved_sender_phone,
                        sender_name=sender_name_val,
                        recipient=user_msg_recipient,
                        recipient_name=user_msg_recipient_name,
                        ledger_event_ids=ledger_event_ids,
                        message_id=request.message_id
                    )

                    if should_reply:
                        # Store AI response with token limit
                        self.session_manager.add_message_with_token_limit(
                            chat_id=effective_chat_id,
                            role="assistant",
                            content=response_text,
                            user_role=user_obj.role,
                            token_limit=user_obj.token_limit,
                            sender=own_number_jid,
                            sender_name="DeniDin",
                            recipient=assistant_msg_recipient,
                            recipient_name=assistant_msg_recipient_name,
                            mcp_calls=mcp_calls,
                        )
                else:
                    # Existing behavior: regular add_message without token limits
                    self.session_manager.add_message(
                        chat_id=effective_chat_id,
                        role="user",
                        content=request.user_prompt,
                        user_role=user_role or "client",
                        sender=resolved_sender_phone,
                        sender_name=sender_name_val,
                        recipient=user_msg_recipient,
                        recipient_name=user_msg_recipient_name,
                        ledger_event_ids=ledger_event_ids,
                        message_id=request.message_id
                    )

                    if should_reply:
                        # Store AI response
                        self.session_manager.add_message(
                            chat_id=effective_chat_id,
                            role="assistant",
                            content=response_text,
                            user_role=user_role or "client",
                            sender=own_number_jid,
                            sender_name="DeniDin",
                            recipient=assistant_msg_recipient,
                            recipient_name=assistant_msg_recipient_name,
                            mcp_calls=mcp_calls,
                        )

                storage_note = (
                    " + assistant reply" if should_reply
                    else " (no-reply sentinel, no assistant message stored)"
                )
                logger.debug(f"Stored user message{storage_note} in session {effective_chat_id}")
            except Exception as e:
                logger.error(f"Failed to store messages in session: {e}", exc_info=True)

        # Create response object.
        # Responses API has no per-choice finish_reason; derive from
        # incomplete_details when present, else "stop". Uses usage_response
        # (the ledger follow-up call when one happened, else the original
        # call) so finish_reason/model reflect whichever turn actually
        # produced response_text.
        finish_reason = "stop"
        if getattr(usage_response, "incomplete_details", None) is not None:
            finish_reason = usage_response.incomplete_details.reason or "incomplete"

        ai_response = AIResponse(
            request_id=request.request_id,
            response_text=response_text,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=usage_response.model,
            finish_reason=finish_reason,
            timestamp=int(time.time()),
            is_truncated=False,
            should_reply=should_reply,
            mcp_calls=mcp_calls,
            offer_approval_buttons=new_pending_approval_created or new_local_tool_pending_created
        )

        # Check if response needs truncation for WhatsApp
        if len(response_text) > 4000:
            ai_response = ai_response.truncate_for_whatsapp()
            logger.warning("Response truncated to 4000 chars for WhatsApp")

        # Retain the most recent response for observability (audit logging,
        # E2E test verification of mcp_calls) - purely additive, read-only
        # for callers; does not change get_response's behavior or return value.
        self.last_response = ai_response

        return ai_response

    def _call_openai_reminder_followup_api(
        self, request: AIRequest, pending: PendingLocalToolApproval, result: Dict[str, Any],
    ):
        """Reminders (Feature 054): report the concrete result of an approved
        create_reminder/modify_reminder/delete_reminder action back as that
        call's `function_call_output`, via a follow-up Responses API call
        chained to the ORIGINAL proposal turn via `previous_response_id` -
        spread across two separate WhatsApp turns (the proposal, and the later
        "כן" reply), since pending.response_id/call_id are what make that
        possible once the original `response` object is long out of scope.

        Lets the model phrase a natural Hebrew confirmation from the real
        result, instead of a hardcoded template - confirmed as the preferred
        approach over a template (one extra billed call per approved
        action, judged worth it for voice consistency).
        """
        output_items = [{
            "type": "function_call_output",
            "call_id": pending.call_id,
            "output": json.dumps({"status": "success", **result}, ensure_ascii=False),
        }]
        kwargs = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution),
            "input": output_items,
            "previous_response_id": pending.response_id,
            "max_output_tokens": request.max_tokens,
        }
        logger.info(f"[054] _call_openai_reminder_followup_api: call_id={pending.call_id!r}, result={result!r}")
        _log_outgoing_request("_call_openai_reminder_followup_api", kwargs)
        response = self.client.responses.create(**kwargs)  # type: ignore[call-overload]
        _log_raw_response("_call_openai_reminder_followup_api", response)
        logger.info(
            f"[054] _call_openai_reminder_followup_api response: id={getattr(response, 'id', None)!r}, "
            f"output_text={response.output_text!r}"
        )
        return response

    def capture_ledger_events_from_text(self, text: str, today_timestamp: Optional[int] = None) -> List[Dict]:
        """
        Ledger Event Recognition (Feature 024) for the image path: a separate, internal
        text-only classification call over already-extracted document text, using the
        same tool/constitution as the text path.

        Needed because attaching the ledger tool directly to the vision call makes it
        one-action-per-turn - confirmed empirically (real E2E run, 2026-07-28): both
        gpt-4o and gpt-4o-mini, when they called the tool, produced ZERO extraction
        text in that same turn, which broke the user-facing document summary entirely
        (MediaHandler treats an empty summary as an extraction failure). This call's
        own `output_text` is never shown to the user - ImageExtractor's vision call
        already produced the real reply - only whether it called the tool matters, so
        no further round-trip is needed.

        Returns a list of parsed `capture_ledger_event` arguments dicts - one per call
        the model made this turn (REQ-CAPTURE-003: uses the plural `extract_all_
        function_calls`, not the singular `extract_function_call`, as a defensive
        measure for the now-rare case of genuinely multiple SEPARATE calls in one
        turn - e.g. two unrelated clients/agreements mentioned in the same document -
        so nothing after the first is silently dropped. A single agreement's own
        multiple fee components are NOT split across separate calls like this - see
        the `components` array on `LEDGER_EVENT_TOOL` itself; each call here is
        expected to normally be either zero or one). Empty list if none were called
        (including when `text` is empty - nothing to classify).

        (Added 2026-08-02, REQ-DATA-008): if any returned call `is_incomplete_capture`
        (empty `components` despite calling the tool, or a `component_count` mismatch -
        a real, observed billed failure: 2026-07-31, the Mor ben-Shaya 6-component
        agreement image produced exactly this, silently persisting nothing with no
        error logged anywhere), retry ONCE with an explicit corrective message naming
        the defect. If it's still incomplete after that, this method still returns
        whatever it got - add_ledger_events_from_call owns the final never-silently-drop
        fallback, since it's the one path both the text and image routes persist
        through.

        Args:
            today_timestamp: (Feature 043) passed straight through to
                _build_instructions - see that method's own docstring.
                `None` (the default) preserves current wall-clock behavior;
                callers replaying a historical image message pass that
                message's own timestamp instead.
        """
        if not text:
            return []

        constitution = self._load_constitution()
        kwargs = {
            "model": self.config.ai_model,
            "instructions": self._build_instructions(constitution, today_timestamp=today_timestamp),
            "input": [{"role": "user", "content": text}],
            "tools": [LEDGER_EVENT_TOOL],
            "max_output_tokens": self.config.ai_reply_max_tokens,
        }

        logger.info("[024] capture_ledger_events_from_text: classifying extracted image text")
        # See _call_openai_api's comment: dynamically-built kwargs never match a
        # single create() overload.
        _log_outgoing_request("capture_ledger_events_from_text", kwargs)
        response = self.client.responses.create(**kwargs)  # type: ignore[call-overload]
        _log_raw_response("capture_ledger_events_from_text", response)
        ledger_calls = extract_all_function_calls(response, LEDGER_EVENT_TOOL["name"])
        ledger_events = [c["arguments"] for c in ledger_calls]
        logger.info(
            f"[024] capture_ledger_events_from_text response: id={getattr(response, 'id', None)!r}, "
            f"output item types={[getattr(i, 'type', None) for i in (response.output or [])]!r}, "
            f"ledger_events_captured={len(ledger_events)}, ledger_events={ledger_events!r}"
        )

        if any(is_incomplete_capture(e) for e in ledger_events):
            logger.warning(
                f"[024] capture_ledger_events_from_text: detected an incomplete capture "
                f"(empty components, or component_count/components length mismatch) - "
                f"retrying once with corrective feedback: {ledger_events!r}"
            )
            retry_kwargs = dict(kwargs)
            retry_kwargs["input"] = cast(List[Dict], kwargs["input"]) + [{
                "role": "user",
                "content": (
                    "Your previous capture_ledger_event call indicated a real "
                    "fee-agreement/bank-deposit event but either listed zero "
                    "components, or its component_count did not match the number of "
                    "components actually listed. That is invalid - every genuinely-"
                    "qualifying event needs at least one component, and "
                    "component_count must equal the number of items in components. "
                    "Re-examine the source text above and call capture_ledger_event "
                    "again with every component actually included."
                ),
            }]
            # See _call_openai_api's comment: dynamically-built kwargs never match a
            # single create() overload.
            _log_outgoing_request("capture_ledger_events_from_text (retry)", retry_kwargs)
            response = self.client.responses.create(**retry_kwargs)  # type: ignore[call-overload]
            _log_raw_response("capture_ledger_events_from_text (retry)", response)
            ledger_calls = extract_all_function_calls(response, LEDGER_EVENT_TOOL["name"])
            ledger_events = [c["arguments"] for c in ledger_calls]
            logger.info(
                f"[024] capture_ledger_events_from_text retry response: "
                f"id={getattr(response, 'id', None)!r}, "
                f"ledger_events_captured={len(ledger_events)}, ledger_events={ledger_events!r}"
            )

        return ledger_events

    @staticmethod
    def _parse_message_timestamp(raw: Optional[str]) -> Optional[datetime]:
        """Best-effort parse of a persisted Message.timestamp ISO string into an
        aware local datetime. None when it can't be parsed (that message is then
        kept in the window rather than dropped)."""
        if not raw:
            return None
        try:
            return to_local(datetime.fromisoformat(raw))
        except (ValueError, TypeError):
            return None

    def _assemble_recognition_input(
        self, session: Session, reply_text: str, turn_mcp_calls: List[Dict]
    ) -> List[Dict]:
        """Feature 069: build the `input` list for the post-turn recognition call.

        Only the last `ledger_recognition_context_window_hours` of the chat is
        included (older messages excluded). Each windowed line is
        `<message_id> [<role>] <content>`, with a `[✓ captured as <ids>]` marker
        for a message that already produced a ledger event, its attachment's
        extracted text, and the Morning MCP calls persisted on that message's
        turn (arguments + real result). The reply just sent and this turn's own
        MCP calls follow.
        """
        window_hours = float(
            getattr(self.config, "ledger_recognition_context_window_hours", 1.0) or 1.0
        )
        cutoff = now_local() - timedelta(hours=window_hours)

        lines = [
            f"THE CONVERSATION WINDOW (the last {window_hours:g}h, oldest first) - "
            "'<message_id> [<role>] <content>':"
        ]
        excluded = 0
        for mid in session.message_ids:
            msg = self.session_manager.load_message(session, mid)
            if msg is None:
                continue
            ts = self._parse_message_timestamp(getattr(msg, "timestamp", None))
            if ts is not None and ts < cutoff:
                excluded += 1
                continue
            marker = (
                f"  [✓ captured as {', '.join(msg.ledger_event_ids)}]"
                if getattr(msg, "ledger_event_ids", None) else ""
            )
            lines.append(f"{mid} [{msg.role}] {msg.content}{marker}")
            if msg.extracted_text:
                lines.append(f"    (extracted from attachment) {msg.extracted_text}")
            for call in (getattr(msg, "mcp_calls", None) or []):
                lines.append(
                    "    (morning MCP call on this message's turn) "
                    + json.dumps(call, ensure_ascii=False, default=str)
                )
        if excluded:
            lines.insert(1, f"({excluded} older message(s) are outside the window and omitted.)")

        lines.append("")
        lines.append("THE REPLY JUST SENT TO THE OPERATOR THIS ROUND:")
        lines.append(reply_text or "")

        lines.append("")
        if turn_mcp_calls:
            lines.append(
                "MORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its "
                "arguments and its real result):"
            )
            lines.append(json.dumps(turn_mcp_calls, ensure_ascii=False, indent=2, default=str))
        else:
            lines.append("NO Morning MCP tools were called this turn.")

        lines.append("")
        lines.append(
            "Follow the recognition prompt above: query the client's ledger history "
            f"first when the round concerns a client, then call {RECOGNITION_TOOL_NAME} "
            "exactly once with the verdict for THIS round."
        )
        return [{"role": "user", "content": "\n".join(lines)}]

    # Feature 069: how many chained query_ledger_events round-trips the recognition
    # call may take before it must report. The prompt tells it to query once up
    # front (client history) and, at most, a couple more times to pin a link.
    MAX_RECOGNITION_QUERY_ROUNDS = 3

    def recognize_ledger_event(
        self,
        *,
        session: Session,
        reply_text: str,
        turn_mcp_calls: List[Dict],
        constitution_text: Optional[str] = None,  # noqa: ARG002 - kept for call-site compat
    ) -> Dict:
        """
        Feature 069 (mechanism move): the ONE dedicated, text-only OpenAI call fired
        AFTER a godfather/admin turn's reply has already been sent - "like a finally
        block". Single question: did THIS round finish a complete, ledger-worthy
        event, and if so, here is its data mapped to the ledger schema.

        Uses the dedicated `config/ledger_recognition_prompt.md` (via
        `_load_recognition_prompt`) - NOT the full constitution - plus today's date
        and a small directive header. Context is the last
        `ledger_recognition_context_window_hours` of the chat + the reply just sent
        + this turn's Morning MCP calls with their results
        (`_assemble_recognition_input`).

        `query_ledger_events` (read-only, in-memory, no tunnel) is attached: the
        model queries the client's ledger history first, then reports. Up to
        `MAX_RECOGNITION_QUERY_ROUNDS` chained round-trips before it must call
        `report_ledger_recognition`. This method normalizes that tool call into the
        tri-state verdict (`data-model.md` 2 / `contracts/recognition-and-logging.md`
        C2):

          - {"verdict": "complete", "event": {...schema-mapped...}, "trigger_message_id": "..."}
          - {"verdict": "none"}
          - {"verdict": "declined", "source_type": ..., "client_name_stated": ...,
             "reason": "declined_by_operator"}

        One-shot retry on a parse failure of our tool's arguments, or on an
        `is_incomplete_capture` `הסכם` verdict. Its output is NEVER appended to the
        session and NEVER surfaced to the operator - the zero-AI ledgerer
        (`LedgerEventManager.persist_recognized_event`) is its only consumer.
        """
        prompt = self._load_recognition_prompt()
        today = now_local().strftime("%d/%m/%Y")
        directive = (
            "POST-TURN LEDGER RECOGNITION: the operator's reply for this round has "
            "already been sent. Do not produce a reply. Your only task is to call "
            f"{RECOGNITION_TOOL_NAME} exactly once with the verdict for this round, "
            "after any ledger-history lookups the prompt calls for. When in doubt, "
            "verdict='none'."
        )
        instructions = (
            (prompt + "\n\n---\n" if prompt else "")
            + f"Today's date (Israel local): {today}\n\n"
            + directive
        )
        tools = [RECOGNITION_TOOL, QUERY_LEDGER_EVENTS_TOOL]
        base_kwargs: Dict[str, Any] = {
            "model": self.config.ai_model,
            "instructions": instructions,
            "tools": tools,
            "max_output_tokens": self.config.ai_reply_max_tokens,
        }

        kwargs = dict(base_kwargs)
        kwargs["input"] = self._assemble_recognition_input(session, reply_text, turn_mcp_calls)
        _log_outgoing_request("recognize_ledger_event", kwargs)
        response = self.client.responses.create(**kwargs)
        _log_raw_response("recognize_ledger_event", response)

        # Bounded query_ledger_events loop: keep feeding the model its own lookup
        # results until it reports, or the round budget is spent.
        for _round in range(self.MAX_RECOGNITION_QUERY_ROUNDS):
            if extract_all_function_calls(response, RECOGNITION_TOOL_NAME):
                break
            query_calls = extract_all_function_calls(response, QUERY_LEDGER_EVENTS_TOOL["name"])
            if not query_calls:
                break
            output_items = []
            for call in query_calls:
                if call["arguments"] is None:
                    payload: Dict[str, Any] = {
                        "status": "error",
                        "reason": "Arguments could not be parsed - do not resubmit this exact call.",
                    }
                else:
                    try:
                        payload = self.ledger_event_manager.query_events(**call["arguments"])
                    except Exception as exc:  # noqa: BLE001 - isolate one bad call
                        logger.warning(f"[069] recognition query_events failed: {exc}")
                        payload = {"status": "error", "reason": str(exc)}
                output_items.append({
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": json.dumps(payload, ensure_ascii=False, default=str),
                })
            follow_kwargs = dict(base_kwargs)
            follow_kwargs["input"] = output_items
            follow_kwargs["previous_response_id"] = response.id
            _log_outgoing_request("recognize_ledger_event (query round)", follow_kwargs)
            response = self.client.responses.create(**follow_kwargs)
            _log_raw_response("recognize_ledger_event (query round)", response)

        # If the model produced no report call at all (only text, or it spent its
        # query budget without reporting), that is a plain `none` - not a retry case.
        if not extract_all_function_calls(response, RECOGNITION_TOOL_NAME):
            return {"verdict": "none"}

        args = self._extract_recognition_args(response)

        if self._recognition_needs_retry(args):
            retry_kwargs = dict(base_kwargs)
            retry_kwargs["input"] = [{
                "role": "user",
                "content": (
                    f"Your previous {RECOGNITION_TOOL_NAME} call could not be used - "
                    "either its arguments were not valid JSON, or it reported "
                    "verdict='complete' for a הסכם while listing zero components or a "
                    "component_count that did not match the components array. Re-examine "
                    "the round above and call the tool again, once, correctly."
                ),
            }]
            retry_kwargs["previous_response_id"] = response.id
            _log_outgoing_request("recognize_ledger_event (retry)", retry_kwargs)
            response = self.client.responses.create(**retry_kwargs)
            _log_raw_response("recognize_ledger_event (retry)", response)
            args = self._extract_recognition_args(response)

        return self._normalize_recognition_verdict(args)

    @staticmethod
    def _extract_recognition_args(response) -> Optional[Dict]:
        """First `report_ledger_recognition` call's parsed args, or None when the
        model called nothing / the args were unparseable (the two are told apart by
        `_recognition_needs_retry`, which only retries the unparseable case)."""
        calls = extract_all_function_calls(response, RECOGNITION_TOOL_NAME)
        if not calls:
            return None
        return cast(Optional[Dict], calls[0]["arguments"])

    @staticmethod
    def _recognition_needs_retry(args: Optional[Dict]) -> bool:
        if args is None:
            # None here means "a call was present but its args did not parse" only
            # when a call item existed at all; a genuinely-absent call is handled as
            # a plain `none` verdict without a retry (see _extract_recognition_args's
            # callers - this predicate is only consulted right after extraction).
            return True
        if args.get("verdict") != "complete":
            return False
        event = args.get("event") or {}
        return event.get("source_type") == "הסכם" and is_incomplete_capture(event)

    @staticmethod
    def _normalize_recognition_verdict(args: Optional[Dict]) -> Dict:
        if not args:
            return {"verdict": "none"}
        verdict = args.get("verdict")
        if verdict == "complete":
            return {
                "verdict": "complete",
                "event": args.get("event"),
                "trigger_message_id": args.get("trigger_message_id"),
            }
        if verdict == "declined":
            return {
                "verdict": "declined",
                "source_type": args.get("source_type"),
                "client_name_stated": args.get("client_name_stated"),
                "reason": args.get("reason") or "declined_by_operator",
            }
        return {"verdict": "none"}

    def _call_openai_approval_api(self, request: AIRequest, pending: PendingApproval,
                                  approve: bool, tools: Optional[List[Dict]] = None):
        """
        Resolve a pending MCP approval request (Feature 022) via a follow-up
        Responses API call chained to the original call via `previous_response_id`,
        so OpenAI resolves the approval against its own server-side state
        rather than requiring the full prior input/output to be replayed.
        """
        approval_item = {
            "type": "mcp_approval_response",
            "approval_request_id": pending.approval_request_id,
            "approve": approve,
        }
        kwargs = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution, today_timestamp=request.timestamp),
            "input": [approval_item],
            "previous_response_id": pending.response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        logger.info(f"[022] _call_openai_approval_api: approve={approve}, kwargs={kwargs!r}")
        # See _call_openai_api's comment: dynamically-built kwargs never match a
        # single create() overload.
        # max_retries=0: this call resolves an approval that, if approve=True,
        # executes a real document-creating MCP tool server-side (Feature
        # 022) - a real, billed incident (2026-08-03) showed the SDK's
        # default auto-retry-on-429 re-executing that already-approved tool
        # call a second time (two invoices created from one approval). A
        # failed attempt here must surface as a clean error to the caller,
        # never retry itself - explicitly overriding the client's own
        # max_retries=config.max_retries (2026-08-19, see
        # AppConfiguration.max_retries' own docstring) via .with_options(...)
        # right here, rather than relying on any outer/shared retry layer to
        # respect this. No retry of this call is ever safe, at any layer.
        response = self.client.with_options(max_retries=0).responses.create(**kwargs)  # type: ignore[call-overload]
        _log_raw_response("_call_openai_approval_api", response)
        logger.info(
            f"[022] _call_openai_approval_api response: id={getattr(response, 'id', None)!r}, "
            f"output item types={[getattr(i, 'type', None) for i in (response.output or [])]!r}, "
            f"output_text={response.output_text!r}"
        )
        return response

    def _resolve_pending_approval(self, pending: PendingApproval, request: AIRequest,
                                  effective_chat_id: str, user_obj, user_role: str,
                                  sender: Optional[str], recipient: Optional[str], *,
                                  user_phone: Optional[str] = None, is_group: bool = False,
                                  chat_name: Optional[str] = None,
                                  sender_phone: Optional[str] = None) -> Optional[AIResponse]:
        """
        Resolve a pending document-creation MCP approval (Feature 022) using
        this turn's message as the yes/no reply.

        Returns:
            The final AIResponse if the user approved (the gated tool actually
            executes now). None if declined or unrecognized - the caller
            should then process this same message as a normal fresh turn
            (the decline itself is still explicitly reported to OpenAI so its
            server-side state for that response is closed out cleanly).
        """
        tools = self._assemble_tools(user_obj, request.request_id)
        is_affirmative = _is_affirmative_reply(request.user_prompt)
        logger.info(
            f"[022] _resolve_pending_approval: chat={effective_chat_id!r}, "
            f"pending={pending!r}, user_prompt={request.user_prompt!r}, "
            f"is_affirmative={is_affirmative}, tools_attached={bool(tools)}"
        )

        if is_affirmative:
            try:
                response = self._call_openai_approval_api(request, pending, approve=True, tools=tools)
            except (APITimeoutError, RateLimitError, APIError) as e:
                # No auto-retry on this call (see _call_openai_approval_api) -
                # a failure here means the approved action was NOT retried by
                # us, so it's a clean single-attempt failure, not a
                # duplication risk. Leave the pending approval in place so
                # the user's next "כן" is a fresh, single attempt.
                logger.error(
                    f"[022] Approval-resolution call failed for chat={effective_chat_id!r}, "
                    f"tool={pending.tool_name!r}, approval_request_id={pending.approval_request_id!r}: {e}",
                    exc_info=True
                )
                return self._create_fallback_response(request.request_id, APPROVAL_FAILED_TRY_AGAIN)

            executed_calls = [
                item for item in (response.output or [])
                if getattr(item, "type", None) == "mcp_call"
            ]
            # Count executions of the APPROVED tool specifically, not the
            # total mcp_call count - a single approval can legitimately
            # produce more than one mcp_call in the same response (e.g.
            # create_invoice followed by a natural download_invoice_pdf
            # follow-up, since the constitution requires every create_invoice
            # confirmation to include a download link unprompted). Counting
            # all mcp_calls as "duplication" wrongly flagged exactly that
            # legitimate 2-step sequence as a false positive (2026-08-03).
            # The real risk is the approved tool itself running more than
            # once - that's what must never happen.
            approved_tool_executions = [
                c for c in executed_calls if getattr(c, "name", None) == pending.tool_name
            ]
            if len(approved_tool_executions) > 1:
                # The approved action must never execute more than once.
                # Real, billed incidents (2026-08-03, at least twice, WITH
                # client-side retry already disabled the second time - see
                # _call_openai_approval_api) show this isn't only caused by
                # our own SDK retrying: something on OpenAI's/the remote MCP
                # round-trip's side can dispatch the already-approved tool
                # call more than once. By the time we see this response, any
                # real-world side effect (e.g. a Morning document) from EVERY
                # one of these calls has already happened server-side - nothing
                # here can undo it. This can never be silently treated as a
                # success, identical arguments or not: a document-creating
                # action executing twice is a real compliance problem, not
                # just a reporting inconvenience.
                logger.error(
                    f"[022] DUPLICATE EXECUTION DETECTED: approval resolution for "
                    f"chat={effective_chat_id!r}, tool={pending.tool_name!r}, "
                    f"approval_request_id={pending.approval_request_id!r} produced "
                    f"{len(approved_tool_executions)} executions of the approved tool "
                    f"in one response (expected exactly 1). All mcp_calls: {executed_calls!r}"
                )
                self.pending_approval_manager.clear(effective_chat_id)
                return self._create_fallback_response(request.request_id, APPROVAL_POSSIBLY_DUPLICATED)

            if not approved_tool_executions:
                # bugfix-028 B4(b): the approved tool ran ZERO times. The guard
                # above has always caught "more than once"; nothing caught "not
                # at all", and nothing counted failures across turns - so the
                # same ₪40,000 document was approved eight times, created never,
                # and the user was re-asked an identical question every time with
                # no hint that the previous attempt had failed.
                #
                # The pending approval is CLEARED rather than left in place: a
                # retry of the identical request would fail identically, and
                # leaving it pending is what produced the loop. The user is told
                # plainly, with whatever the tool actually said.
                failure_detail = ""
                for call in executed_calls:
                    output = getattr(call, "output", None)
                    if output:
                        failure_detail = f" ({str(output)[:200]})"
                        break
                    error_text = self._extract_mcp_error_text(call)
                    if error_text:
                        failure_detail = f" ({error_text[:200]})"
                        break
                logger.error(
                    f"[022] APPROVED TOOL NEVER RAN: chat={effective_chat_id!r}, "
                    f"tool={pending.tool_name!r}, approval_request_id={pending.approval_request_id!r} "
                    f"produced 0 executions of the approved tool (expected exactly 1). "
                    f"All mcp_calls: {executed_calls!r}"
                )
                self.pending_approval_manager.clear(effective_chat_id)
                return self._create_fallback_response(
                    request.request_id,
                    f"אישרת, אבל הפעולה לא בוצעה בפועל{failure_detail}. "
                    f"לא נוצר שום מסמך. נסי שוב או ספרי לי איך להמשיך."
                )

            self.pending_approval_manager.clear(effective_chat_id)
            logger.info(f"[022] Approved and cleared pending for chat={effective_chat_id!r}")
            return self._finalize_response(
                request, response, effective_chat_id, user_obj, user_role, sender, recipient, tools,
                user_phone=user_phone, is_group=is_group, chat_name=chat_name,
                sender_phone=sender_phone
            )

        # Not a recognized affirmative: decline, close out OpenAI's
        # server-side state, then let the caller process this message as a
        # normal fresh turn (it may itself be a new, unrelated request).
        logger.info(
            f"[022] '{request.user_prompt}' not recognized as affirmative - "
            f"declining pending approval for chat={effective_chat_id!r}"
        )
        try:
            self._call_openai_approval_api(request, pending, approve=False, tools=tools)
        except Exception as e:
            logger.error(
                f"Failed to submit decline for pending approval (chat={effective_chat_id}, "
                f"tool={pending.tool_name}): {e}", exc_info=True
            )
        self.pending_approval_manager.clear(effective_chat_id)
        logger.info(
            f"Pending MCP approval declined for chat={effective_chat_id}, "
            f"tool={pending.tool_name} - falling through to a fresh turn"
        )
        return None

    def _resolve_pending_local_tool_approval(
        self, pending: PendingLocalToolApproval, request: AIRequest,
        effective_chat_id: str, user_obj, user_role: str,
        sender: Optional[str], recipient: Optional[str],
    ) -> Optional[AIResponse]:
        """
        Resolve a pending local reminder tool call (Feature 054) using this
        turn's message as the yes/no reply - the local-tool equivalent of
        `_resolve_pending_approval`, but the approved action dispatches
        directly to `ReminderManager` (no `mcp_approval_response` round-trip;
        a local `function_call`'s arguments are already fully known, there is
        no OpenAI-side server state to resolve against).

        Returns:
            The final AIResponse if approved. None if declined/unrecognized -
            same contract as `_resolve_pending_approval`: the caller then
            processes this same message as a normal fresh turn.
        """
        is_affirmative = _is_affirmative_reply(request.user_prompt)
        logger.info(
            f"[054] _resolve_pending_local_tool_approval: chat={effective_chat_id!r}, "
            f"pending={pending!r}, user_prompt={request.user_prompt!r}, "
            f"is_affirmative={is_affirmative}"
        )

        if not is_affirmative:
            self.pending_local_tool_approval_manager.clear(effective_chat_id)
            logger.info(
                f"[054] Pending local-tool approval declined for chat={effective_chat_id!r} "
                "- falling through to a fresh turn"
            )
            return None

        # Manager-level re-check (TOCTOU-closing, not just the proposal-time
        # check) - a slow approval flow could let a proposed future time
        # become past, or a concurrent proposal could have already filled the
        # cap. Cleared either way: a failed approval is never left pending for
        # an identical retry to fail identically against (same reasoning as
        # bugfix-028 B4(b)'s zero-execution MCP handling).
        try:
            # cast: pending.arguments is Dict[str, Any] (from json.loads), so
            # .get() is typed Any to mypy - each ReminderManager method
            # validates the actual values at runtime regardless.
            args = pending.arguments
            scope = args.get("scope")
            if pending.tool_name == CREATE_REMINDER_TOOL["name"]:
                # created_by_phone/role must reflect the LITERAL sender of this
                # turn, not the RBAC-resolved user_obj/user_role - for a group
                # turn those are Feature 039's most-permissive-member
                # resolution (e.g. an admin, even when a lower-privileged
                # member actually sent the message), which is correct for
                # permissions/token-limits but wrong for traceability. Pulled
                # from request.original_message (2026-08-19 fix - see
                # AIRequest.original_message's docstring) rather than user_obj.
                if request.original_message:
                    literal_sender_phone = request.original_message.sender_id
                    literal_sender_role = user_role
                    if self.rbac_enabled and self.user_manager:
                        literal_user_obj = self.user_manager.get_user(literal_sender_phone)
                        if literal_user_obj:
                            literal_sender_role = literal_user_obj.role
                else:
                    # No original_message on this request (should not happen
                    # in production - defensive fallback only) - fall back to
                    # the previous, RBAC-resolved behavior rather than error.
                    literal_sender_phone = user_obj.phone if user_obj else (sender or effective_chat_id)
                    literal_sender_role = user_obj.role if user_obj else user_role
                result = self.reminder_manager.create_reminder(
                    message_text=cast(str, args.get("message_text")),
                    schedule_type=cast(str, args.get("schedule_type")),
                    one_time_due_at=args.get("one_time_due_at"),
                    recurrence=args.get("recurrence"),
                    created_by_phone=literal_sender_phone,
                    created_by_role=literal_sender_role,
                    delivery_chat_id=effective_chat_id,
                )
            elif pending.tool_name == MODIFY_REMINDER_TOOL["name"] and scope == "single_occurrence":
                result = self.reminder_manager.modify_single_occurrence(
                    reminder_id=cast(str, args.get("reminder_id")),
                    occurrence_date_hint=cast(str, args.get("occurrence_date_hint")),
                    new_message_text=args.get("new_message_text"),
                    new_due_at=args.get("new_due_at"),
                )
            elif pending.tool_name == MODIFY_REMINDER_TOOL["name"]:  # scope == "whole_series"
                result = self.reminder_manager.modify_whole_series(
                    reminder_id=cast(str, args.get("reminder_id")),
                    new_message_text=args.get("new_message_text"),
                    new_recurrence=args.get("new_recurrence"),
                    new_due_at=args.get("new_due_at"),
                )
            elif pending.tool_name == DELETE_REMINDER_TOOL["name"] and scope == "single_occurrence":
                result = self.reminder_manager.delete_single_occurrence(
                    reminder_id=cast(str, args.get("reminder_id")),
                    occurrence_date_hint=cast(str, args.get("occurrence_date_hint")),
                )
            elif pending.tool_name == DELETE_REMINDER_TOOL["name"]:  # scope == "whole_series"
                result = self.reminder_manager.delete_whole_series(
                    reminder_id=cast(str, args.get("reminder_id")),
                )
            else:
                raise InvalidRecurrenceError(
                    f"unresolvable pending tool_name/scope: {pending.tool_name!r}/{scope!r}"
                )
        except (ReminderPastDateError, ReminderCapExceededError, ReminderNotFoundError,
                InvalidRecurrenceError, OccurrenceNotFoundError) as e:
            logger.error(
                f"[054] Approved reminder action failed at persist time for chat="
                f"{effective_chat_id!r}, tool={pending.tool_name!r}: {e}", exc_info=True
            )
            self.pending_local_tool_approval_manager.clear(effective_chat_id)
            return self._create_fallback_response(request.request_id, REMINDER_ACTION_FAILED_TRY_AGAIN)

        self.pending_local_tool_approval_manager.clear(effective_chat_id)
        logger.info(f"[054] Approved and cleared pending local-tool approval for chat={effective_chat_id!r}")

        try:
            followup = self._call_openai_reminder_followup_api(request, pending, result)
            response_text = followup.output_text
            tokens_used = followup.usage.total_tokens
            prompt_tokens = followup.usage.input_tokens
            completion_tokens = followup.usage.output_tokens
            model_name = followup.model
        except Exception as e:
            logger.error(
                f"[054] Reminder confirmation follow-up call failed for chat="
                f"{effective_chat_id!r}: {e}", exc_info=True
            )
            response_text = ""
            tokens_used = prompt_tokens = completion_tokens = 0
            model_name = "error-fallback"

        if not response_text.strip():
            # Same "never leave the user with a silently empty reply" discipline
            # as LEDGER_FOLLOWUP_FAILED_TRY_AGAIN - the follow-up round-trip
            # failing/returning nothing must never surface as no reply at all,
            # even though the reminder itself WAS actually created/modified/
            # deleted successfully (unlike the ledger fallback's case).
            response_text = REMINDER_ACTION_FAILED_TRY_AGAIN
            logger.warning(
                f"[054] Reminder confirmation follow-up produced no reply for chat="
                f"{effective_chat_id!r} despite the action succeeding - using generic "
                "fallback text so the user never receives a silently empty reply."
            )

        if self.memory_enabled and self.session_manager and effective_chat_id and self.rbac_enabled and user_obj:
            try:
                self.session_manager.add_message_with_token_limit(
                    chat_id=effective_chat_id, role="user", content=request.user_prompt,
                    user_role=user_obj.role, token_limit=user_obj.token_limit,
                    sender=sender or effective_chat_id, message_id=request.message_id,
                )
                self.session_manager.add_message_with_token_limit(
                    chat_id=effective_chat_id, role="assistant", content=response_text,
                    user_role=user_obj.role, token_limit=user_obj.token_limit,
                    recipient=sender or effective_chat_id,
                )
            except Exception as e:
                logger.error(f"[054] Failed to store reminder-approval messages in session: {e}", exc_info=True)

        ai_response = AIResponse(
            request_id=request.request_id,
            response_text=response_text,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model_name,
            finish_reason="stop",
            timestamp=int(time.time()),
            is_truncated=False,
            offer_approval_buttons=False,
        )
        if len(response_text) > 4000:
            ai_response = ai_response.truncate_for_whatsapp()
        self.last_response = ai_response
        return ai_response

    def resolve_button_tap(
        self, message: WhatsAppMessage, selected_id: str, stanza_id: str,
    ) -> Optional[AIResponse]:
        """
        Feature 047: resolves a WhatsApp interactive-button tap against
        message.chat_id's pending approval (Feature 022), if the tap's
        stanza_id matches the message it was actually sent as
        (contracts/pending-approval-message-binding.md).

        Deliberately does NOT reimplement approve/decline resolution: once the
        stanza_id match below confirms this tap is live (not stale/superseded -
        the one check `get_response`/`_resolve_pending_approval` has no concept of,
        since neither knows about individual WhatsApp message ids), this
        synthesizes a plain "כן"/"לא" `AIRequest` and delegates to the existing
        `get_response`/`_resolve_pending_approval` pipeline verbatim - same
        duplicate-execution guards, same decline behavior (falls through to a
        fresh turn, exactly like a genuine typed "לא" does today - a button
        decline is byte-for-byte the same experience as a typed one, per US2's
        non-interference requirement).

        Takes the whole `message` (2026-08-19, user decision), not individual
        scalar fields pulled out of it by the caller - `chat_id`/`message_id`/
        `sender_id`/`sender_display_name`/`is_group`/`chat_name` all come from
        it directly (including the `is_group`/`chat_name`/`sender_phone` fields
        Feature 043's merge added to `get_response`'s own signature - derived
        here from `message` rather than accepted as yet more threaded params),
        and AIRequest.original_message carries the same object further
        downstream (e.g. into a reminder's created_by_phone) without yet
        another parameter threaded through
        get_response/_resolve_pending_local_tool_approval.

        Returns:
            None if there's no pending approval, or its sent_message_id doesn't
            equal stanza_id (stale/superseded tap) - per spec.md Clarifications,
            the caller must send nothing observable at all in this case. A real
            AIResponse otherwise.
        """
        chat_id = message.chat_id
        user_phone = message.sender_id
        sender = message.sender_display_name

        user_obj = None
        if self.rbac_enabled and self.user_manager and user_phone:
            user_obj = self.user_manager.get_user(user_phone)
            if user_obj.is_blocked:
                logger.warning(f"[047] Blocked user attempted to resolve a button tap: {user_phone!r}")
                return None

        # Reminders (Feature 054): checked MCP-first-then-local-tool, same
        # deterministic order as get_response's dual-check dispatch - at most
        # one of the two managers is ever populated for a given chat_id in
        # practice.
        pending = self.pending_approval_manager.get(chat_id) if user_obj else None
        local_pending = None
        if pending is None or pending.sent_message_id != stanza_id:
            pending = None
            local_pending = self.pending_local_tool_approval_manager.get(chat_id) if user_obj else None
            if local_pending is None or local_pending.sent_message_id != stanza_id:
                logger.info(
                    f"[047] Stale button tap ignored: chat={chat_id!r}, selected_id={selected_id!r}, "
                    f"stanza_id={stanza_id!r}, mcp_pending={pending!r}, local_pending={local_pending!r}"
                )
                return None
        # user_obj is guaranteed non-None here: (pending or local_pending) is only
        # ever non-None (one of the two branches above just confirmed it is) when
        # user_obj was truthy, per the ternaries a few lines up - explicit for
        # mypy, which can't infer that implication across the ternary on its own.
        assert user_obj is not None
        resolved_pending = pending or local_pending
        # Same reasoning as the user_obj assert above: one of the two branches
        # already confirmed (pending or local_pending) is non-None before
        # reaching here - explicit for mypy, which can't carry that
        # implication through the earlier if/else on its own.
        assert resolved_pending is not None

        approve = selected_id == BUTTON_ID_APPROVE
        logger.info(
            f"[047] Resolving pending approval via BUTTON TAP for chat={chat_id!r}, "
            f"tool={resolved_pending.tool_name!r}, selected_id={selected_id!r}, approve={approve}"
        )

        synthetic_request = AIRequest(
            user_prompt="כן" if approve else "לא",
            constitution=self._load_constitution(),
            max_tokens=self.config.ai_reply_max_tokens,
            model=self.config.ai_model,
            chat_id=chat_id,
            message_id=message.message_id,
            original_message=message,
        )
        return self.get_response(
            synthetic_request, chat_id=chat_id, user_role=user_obj.role,
            sender=sender, recipient=None, user_phone=user_phone,
            is_group=message.is_group, chat_name=message.chat_name,
            sender_phone=message.sender_id,
        )

    def _create_fallback_response(self, request_id: str, message: str) -> AIResponse:
        """
        Create a fallback AIResponse for error cases.

        Args:
            request_id: Original request ID
            message: Fallback message to send

        Returns:
            AIResponse with fallback content
        """
        return AIResponse(
            request_id=request_id,
            response_text=message,
            tokens_used=0,
            prompt_tokens=0,
            completion_tokens=0,
            model="error-fallback",
            finish_reason="error",
            timestamp=int(time.time()),
            is_truncated=False
        )

    # Memory System Integration Methods (Feature 002+007)

    def transfer_session_to_long_term_memory(self, session: Session) -> Dict:
        """
        Transfer an expired session to long-term memory.

        Workflow:
        1. Retrieve conversation history from session
        2. Ask AI to summarize the conversation
        3. Store summary in ChromaDB with metadata
        4. NO FILTERING - store ALL sessions regardless of length
        5. Graceful degradation: if AI fails, store raw conversation

        Args:
            session: Session object to transfer

        Returns:
            Dict with transfer status and details
        """
        if not self.memory_enabled or not self.memory_manager:
            logger.warning(f"Transfer requested but memory system disabled: {session.session_id}")
            return {"success": False, "reason": "memory_disabled"}

        try:
            # Get conversation history directly from session object
            conversation = self.session_manager.get_conversation_history_for_session(session)
            if not conversation:
                logger.warning(f"No conversation history for session {session.session_id}")
                return {"success": False, "reason": "empty_conversation"}

            # Try to summarize with AI
            summary_text = None
            used_fallback = False

            try:
                # Build summarization prompt
                conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
                summarizer_instructions = (
                    "You are a conversation summarizer that extracts both explicit and implicit "
                    "information. Start your summary by listing key facts as bullet points (e.g., "
                    "names, preferences, decisions, entities mentioned). Then provide context, "
                    "relationships, and logical deductions. Make information easily retrievable "
                    "for future questions. Keep summaries under 500 words."
                )

                summary_response = self.client.responses.create(
                    model=self.config.ai_model,
                    instructions=summarizer_instructions,
                    input=f"Summarize this conversation, leading with facts then inferences:\n\n{conv_text}",
                    max_output_tokens=1000
                )
                _log_raw_response(f"transfer_to_longterm_memory (session {session.session_id})", summary_response)

                summary_text = summary_response.output_text
                logger.info(f"AI summarized session {session.session_id}: {len(summary_text)} chars")

            except Exception as e:
                # Graceful degradation: use raw conversation
                logger.error(f"AI summarization failed for {session.session_id}: {e}. Using raw conversation fallback.")
                summary_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
                used_fallback = True

            # Store in ChromaDB
            collection_name = f"memory_{session.whatsapp_chat.replace('@c.us', '')}"
            logger.info(f"Starting ChromaDB storage for session {session.session_id} in collection {collection_name}")

            # Use whatsapp_chat directly as user_phone for RBAC filtering (includes @c.us)
            user_phone = session.whatsapp_chat

            metadata = {
                "type": "session_summary_fallback" if used_fallback else "session_summary",
                "session_id": session.session_id,
                "whatsapp_chat": session.whatsapp_chat,
                "user_phone": user_phone,  # Required for RBAC filtering (must match sender_id format)
                "session_start": session.created_at,
                "session_end": session.last_active,
                "message_count": len(session.message_ids),
                "summarization_failed": used_fallback
            }

            memory_id = self.memory_manager.remember(
                content=summary_text,
                collection_name=collection_name,
                metadata=metadata
            )

            logger.info(f"ChromaDB storage completed for session {session.session_id}: memory_id={memory_id}")

            # Verify storage
            collection = self.memory_manager.client.get_collection(name=collection_name)
            count = collection.count()
            logger.info(f"ChromaDB collection '{collection_name}' now has {count} item(s)")

            logger.info(f"Session {session.session_id} transferred to long-term memory: {memory_id}")

            return {
                "success": True,
                "memory_id": memory_id,
                "used_fallback": used_fallback,
                "summary_length": len(summary_text)
            }

        except Exception as e:
            logger.error(f"Failed to transfer session {session.session_id}: {e}", exc_info=True)
            return {"success": False, "reason": "transfer_error", "error": str(e)}

    def recover_orphaned_sessions(self) -> Dict:
        """
        STARTUP PROCEDURE: Recover sessions not transferred due to crashes/shutdowns.

        Scans for active sessions, checks expiration status:
        - Expired (>24h inactive) → transfer to long-term memory
        - Active (<24h inactive) → load to short-term memory

        Returns:
            Dict with recovery summary
        """
        if not self.memory_enabled or not self.session_manager:
            logger.info("Session recovery skipped: memory system disabled")
            return {"total_found": 0, "transferred_to_long_term": 0, "loaded_to_short_term": 0}

        try:
            orphaned_sessions = self.session_manager.find_orphaned_sessions()

            if not orphaned_sessions:
                logger.info("No orphaned sessions found - clean startup")
                return {"total_found": 0, "transferred_to_long_term": 0, "loaded_to_short_term": 0}

            logger.info(f"Found {len(orphaned_sessions)} orphaned sessions - starting recovery")

            long_term_sessions = []
            short_term_sessions = []
            failed_sessions = []

            for session in orphaned_sessions:
                try:
                    is_expired = self.session_manager.is_session_expired(session)

                    if is_expired:
                        # Transfer to long-term memory
                        result = self.transfer_session_to_long_term_memory(session)

                        if result.get("success"):
                            long_term_sessions.append(session.session_id)
                            logger.info(f"Recovered expired session to long-term: {session.session_id}")
                        else:
                            failed_sessions.append(session.session_id)
                            logger.error(f"Failed to transfer expired session: {session.session_id}")
                    else:
                        # Load to short-term memory (still active)
                        short_term_sessions.append(session.session_id)
                        logger.info(f"Recovered active session to short-term: {session.session_id}")

                except Exception as e:
                    logger.error(f"Error recovering session {session.session_id}: {e}", exc_info=True)
                    failed_sessions.append(session.session_id)

            logger.info(
                f"Session recovery complete: {len(long_term_sessions)} transferred, "
                f"{len(short_term_sessions)} loaded, {len(failed_sessions)} failed"
            )

            return {
                "total_found": len(orphaned_sessions),
                "transferred_to_long_term": len(long_term_sessions),
                "loaded_to_short_term": len(short_term_sessions),
                "failed": len(failed_sessions),
                "long_term_sessions": long_term_sessions,
                "short_term_sessions": short_term_sessions,
                "failed_sessions": failed_sessions
            }

        except Exception as e:
            logger.error(f"Session recovery failed: {e}", exc_info=True)
            return {"total_found": 0, "transferred_to_long_term": 0, "loaded_to_short_term": 0, "error": str(e)}
