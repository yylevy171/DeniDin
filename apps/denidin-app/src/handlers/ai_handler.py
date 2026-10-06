"""
AIHandler - Handles OpenAI API interactions with retry logic and error handling
Phase 5: US3 - Error Handling & Resilience
Phase 5 (002+007): Memory system integration
Phase 6: RBAC (Role-Based Access Control)
"""
import contextvars
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, cast, Optional, List, Dict

from openai import APITimeoutError, RateLimitError, APIError
from src.models.message import (
    WhatsAppMessage, AIRequest, AIResponse,
    NO_REPLY_SENTINEL as _NO_REPLY_SENTINEL, should_reply_for,
)
from src.utils.logger import get_logger, read_version, DEFAULT_VERSION_FILE
from src.utils.time_utils import now_local, local_from_timestamp
from src.utils.wire_log import audit_wire, debug_wire
from src.core.ai_manager import AIManager, MORNING_READ_MCP_TOOLS, MORNING_WRITE_MCP_TOOLS
from src.managers.ledger_event_manager import is_incomplete_capture
from src.managers.ledger_event_recognizer import (
    LEDGER_EVENT_TOOL, LEDGER_QUERY_AUTHORIZED_ROLES,
)
from src.utils.function_calls import (
    extract_all_function_calls, extract_function_call, extract_function_call_id,
)
from src.managers.pending_approval_manager import (
    PendingApprovalManager, PendingApproval, BUTTON_ID_APPROVE
)
from src.managers.reminder_manager import (
    ReminderPastDateError, ReminderCapExceededError, ReminderNotFoundError,
    InvalidRecurrenceError, OccurrenceNotFoundError,
)
from src.handlers.fee_agreement_tools import (
    GET_FEE_AGREEMENT_TEMPLATE_TOOL,
    RENDER_FEE_AGREEMENT_DOCUMENT_TOOL,
    VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL, SEND_FEE_AGREEMENT_DOCUMENT_TOOL,
)
from src.managers.pending_local_tool_approval_manager import (
    PendingLocalToolApprovalManager, PendingLocalToolApproval,
)
from src.models.user import Role
from src.tool_actions.messaging_actions import (
    build_react_to_message_payload, resolve_react_to_message_target, send_progress_update_message,
)
from src.tool_actions.reminder_actions import (
    build_list_reminders_summary, execute_reminder_action, resolve_literal_sender,
    format_reminder_schedule as _format_reminder_schedule,
)
from src.tool_actions.tool_schemas import (
    CREATE_REMINDER_TOOL, LIST_REMINDERS_TOOL, MODIFY_REMINDER_TOOL, DELETE_REMINDER_TOOL,
    SEND_PROGRESS_UPDATE_TOOL, QUERY_LEDGER_EVENTS_TOOL, REACT_TO_MESSAGE_TOOL,
)
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
# fact. `audit_wire`/`debug_wire` (src/utils/wire_log.py) are called directly
# at every responses.create() call site in this app, and in
# accounting_reconciliation_service.py/image_extractor.py (2026-09-24: those
# two now import wire_log.py directly too, not this module's aliases -
# there is exactly one audit_wire and one debug_wire in this codebase, no
# per-module re-export). Deliberately verbose, deliberately everywhere: "I
# want logs of EVERYTHING so we can get to the bottom of what is going on"
# (disk space is explicitly not a constraint here). Never raises - a
# logging failure must never break the actual call it's describing.
#
# (2026-09-30 merge note: origin/master still carried the pre-consolidation
# `_log_outgoing_request`/`_log_raw_response` RAWLOG helpers this comment used
# to describe - dropped here in favor of the wire_log.py consolidation this
# branch already completed; nothing on master called them anymore that this
# branch's own equivalents don't already cover.)

# Roles authorized to have the Morning MCP invoicing tools attached (Feature 018)
MORNING_MCP_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

# Roles authorized to have the reminder tools attached (Feature 054) - there is
# exactly one reminder list, owned by "the godfather"; ADMIN manages it too via
# this app's existing blanket-access pattern, not a reminder-specific rule.
REMINDER_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

# Roles authorized to have the query_ledger_events tool attached (Feature 044) -
# defined with the ledger recognition, which is gated by the same predicate.

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

# Feature 080 (REQ-080-04, research.md R3 as revised during implementation): the active
# turn's TelemetryBuilder, if any. Set once at the top of single_turn() (try/finally around
# the whole turn), read by every instrumented responses.create()/tool-dispatch call site via
# .get() (defaults to None - "no telemetry this call", the correct behavior whenever the
# feature flag is off or telemetry_manager was never configured). Thread-local by default
# (Python's contextvars are NOT shared across threads unless explicitly propagated), and this
# codebase processes each request synchronously on its own thread - never asyncio - so this
# is correctly scoped per in-flight request despite AIHandler serving concurrent chats. This
# is deliberately NOT a plain module-level mutable dict/global, which really would leak
# across concurrent chats on different threads.
_active_telemetry_builder: "contextvars.ContextVar[Optional[Any]]" = contextvars.ContextVar(
    "denidin_active_telemetry_builder", default=None
)

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
APPROVAL_REQUIRED_MCP_TOOLS = MORNING_WRITE_MCP_TOOLS

# The remaining Morning MCP tools (read-only client/invoice lookups) -
# explicitly listed as "never" require approval. Confirmed empirically
# (2026-07-23, real E2E run) that a `require_approval` filter with ONLY an
# "always" key does NOT leave unlisted tools defaulting to no-approval as
# assumed from docs/smoke-testing - `download_invoice_pdf` (not in
# APPROVAL_REQUIRED_MCP_TOOLS) still came back as a pending
# mcp_approval_request. Being fully explicit about both sides of the filter
# avoids relying on that unconfirmed default.
NO_APPROVAL_MCP_TOOLS = MORNING_READ_MCP_TOOLS


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

def _find_referenced_document_details(original_internal_morning_id: Optional[str],
                                      mcp_calls: List[Dict[str, Any]]) -> Optional[str]:
    """bugfix-038: find a get_invoice_details call, already executed earlier
    in this SAME turn, whose internal_morning_id argument matches original_internal_morning_id -
    and return its raw output (the referenced document's own real data, as
    Morning returned it - JSON per the 2026-09-04 contract; the caller parses
    it via `_format_referenced_document_for_approval`).

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


def _format_referenced_document_for_approval(details_json: str) -> Optional[str]:
    """Render the referenced document as the readable Hebrew Part 1 block of a
    Group B approval prompt (bugfix-038), from get_invoice_details' JSON output
    (the 2026-09-04 JSON-only Morning contract - that output is machine JSON now,
    never prose, and must never reach the user verbatim). Shows the fields the
    prose version used to - document type, number, client, date, amount, status -
    and never `internal_morning_id` (constitution: that id must never be shown).
    Returns None on anything unparseable, so the caller simply omits Part 1
    rather than showing a broken block. Never raises (response hot path)."""
    try:
        doc = json.loads(details_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(doc, dict):
        return None
    lines = []
    if doc.get("type_name"):
        lines.append(f"סוג מסמך: {doc['type_name']}")
    if doc.get("display_number"):
        lines.append(f"מספר מסמך: {doc['display_number']}")
    if doc.get("client_name"):
        lines.append(f"לקוח: {doc['client_name']}")
    if doc.get("document_date"):
        lines.append(f"תאריך: {_format_date_for_display(doc['document_date'])}")
    amount = doc.get("amount")
    if amount is not None:
        if isinstance(amount, float) and amount.is_integer():
            amount = int(amount)
        lines.append(f"סכום: {amount} ₪")
    if doc.get("status_label"):
        lines.append(f"סטטוס: {doc['status_label']}")
    return "\n".join(lines) if lines else None


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

    bugfix-038: for the "Group B" reference tools (`_GROUP_B_REFERENCE_TOOLS`),
    the approval gains a PART 1 preceding the block above - the referenced
    document's own real data (document type, number, client, date, amount,
    status), rendered by `_format_referenced_document_for_approval` from the
    get_invoice_details JSON output found via `_find_referenced_document_details`
    correlating `original_internal_morning_id` against a get_invoice_details call
    already executed earlier in this SAME turn (`mcp_calls`); never the internal
    id. Absent for every other tool, and absent for Group B tools too when no
    matching lookup is found or its output can't be parsed (accepted risk - see
    those functions' docstrings).

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
            formatted_reference = _format_referenced_document_for_approval(reference_details)
            if formatted_reference:
                reference_block = f"📄 המסמך המקושר:\n{formatted_reference}\n\n"

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


class AIHandler(AIManager):
    """
    The legacy AI implementation (flag off): one OpenAI Responses API call per turn
    against the runtime constitution, with its own approval-gate state. Built by
    initialize_app only when the backbone flag is off (REQ-063-08); DeniDin's data is
    handed in, never built here.
    """

    def __init__(self, denidin: Any):
        """
        Args:
            denidin: the DeniDin object (see AIManager).
        """
        super().__init__(denidin)
        config = self.config

        # Feature 034 (REQ-VER-005): read once at construction, not per-call - a version
        # can't change mid-process (research.md Decision 4), unlike today's date below.
        self._app_version = read_version(DEFAULT_VERSION_FILE)

        # Constitution loading state (mtime-based caching)
        self._constitution_content: Optional[str] = None
        self._constitution_mtime: Optional[float] = None

        session_config = (config.memory or {}).get('session', {})
        # Feature 070: rolling verbatim window length (Israel-local calendar days)
        self.window_days = session_config.get('window_days', 14)
        # Token limits for conversation retrieval, per role
        self.max_tokens_by_role = session_config.get('max_tokens_by_role', {
            'client': 4000,
            'godfather': 100000
        })
        longterm_config = (config.memory or {}).get('longterm', {})
        self.memory_collection_name = longterm_config.get('collection_name', 'godfather_memory')
        self.memory_top_k = longterm_config.get('top_k_results', 5)
        # Feature 070: the single per-turn recall must surface enough daily_summary
        # records to cover the pre-window history - see contracts/ai-handler-recall.md.
        self.daily_summary_top_k = longterm_config.get('daily_summary_top_k', 10)
        self.memory_min_similarity = longterm_config.get('min_similarity', 0.7)

        # Feature 022: tracks, per chat_id, an MCP document-creation call
        # currently held pending the user's explicit approval. In-memory only
        # (see PendingApprovalManager docstring for why).
        self.pending_approval_manager = PendingApprovalManager()
        # Local-tool approval gate (create_reminder/modify_reminder/delete_reminder)
        # - a separate, parallel manager to pending_approval_manager, never merged
        # into it (CONSTITUTION test-immutability protects Feature 047's existing
        # approval-gate tests; PendingApproval is structurally MCP-specific - see
        # contracts/local-tool-approval-gate.md).
        self.pending_local_tool_approval_manager = PendingLocalToolApprovalManager()

        logger.debug(
            f"AIHandler initialized with models: text={config.ai_model}, "
            f"vision={config.ai_vision_model}, embedding={config.ai_embedding_model}"
        )

    # ------------------------------------------------------------------
    # Feature 080 (REQ-080-04): telemetry instrumentation helpers.
    # ------------------------------------------------------------------

    def _timed_llm_call(self, call_fn: Callable[[], Any], *, context: str = "responses.create") -> Any:
        """Wraps one responses.create() call site with an explicit retry for the OpenAI SDK's
        own retry gap (2026-09-30 - see AIManager.call_model_with_retry's docstring),
        plus timing + token accounting, recorded into the active turn's TelemetryBuilder
        (contextvars - see _active_telemetry_builder's module docstring), if any. Times success
        AND failure alike (a timed-out/errored call still consumed wall-clock time and must
        count, per contracts/telemetry-recorder.md) - the original call's own exception (after
        the explicit retry above is exhausted) propagates unchanged; this never adds new failure
        modes. Telemetry recording is a complete no-op when no telemetry builder is active -
        the exact common case when the feature flag is off; the explicit retry always applies.
        2026-10-01: delegates to AIManager.timed_model_call (shared with the backbone)."""
        return self.timed_model_call(_active_telemetry_builder.get(), call_fn, context=context)

    def _timed_tool_call(self, tool_name: str, call_fn: Callable[[], Any], *, is_morning_tool: bool = False) -> Any:
        """Same contract as _timed_llm_call, for local function-tool dispatch and remote MCP
        tool-call handling - see contracts/telemetry-recorder.md's record_tool_call().
        2026-10-01: delegates to AIManager.timed_tool_call (shared with the backbone)."""
        return self.timed_tool_call(_active_telemetry_builder.get(), tool_name, call_fn,
                                    is_morning_tool=is_morning_tool)

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
                logger.debug(f"Constitution loaded: {filename} "
                             f"({len(self._constitution_content)} chars, mtime: {current_mtime})")

            # If constitution is empty after loading, fallback to system_message
            if not self._constitution_content:
                logger.warning(f"Constitution file is empty: {filepath}, using system_message fallback")
                return ""

            return self._apply_feature_080_constitution_gate(self._constitution_content)

        except Exception as e:
            logger.error(f"Failed to load constitution file {filepath}: {e}", exc_info=True)
            return ""

    def _apply_feature_080_constitution_gate(self, content: str) -> str:
        """Feature 080: the "Proactive Progress Updates" section is wrapped in
        `<!-- FEATURE_080_PROGRESS_UPDATES_START/END -->` HTML-comment markers in
        runtime_constitution.md. The feature flag that used to gate this on/off has been
        removed (2026-09-12, explicit operator instruction - never gated by request) -
        the directive is always active now; this just strips the now-inert markers
        themselves, leaving the directive text in place.
        """
        start_marker = "<!-- FEATURE_080_PROGRESS_UPDATES_START -->"
        end_marker = "<!-- FEATURE_080_PROGRESS_UPDATES_END -->"
        if start_marker not in content or end_marker not in content:
            return content  # markers absent - nothing to gate, return as-is
        return content.replace(start_marker, "").replace(end_marker, "")

    def _request_constitution(self, user_prompt: str, chat_id: Optional[str],
                              user_phone: Optional[str]) -> str:
        """The legacy request carries its instructions: the runtime constitution, plus
        the recalled long-term memories for this message (shared recall -
        AIManager.recall_memory_context)."""
        constitution = self._load_constitution()
        if self.memory_enabled and self.memory_manager:
            memory_context = self.recall_memory_context(
                query=user_prompt, chat_id=chat_id,
                top_k=self.daily_summary_top_k, min_similarity=self.memory_min_similarity,
                user_phone=user_phone if self.rbac_enabled else None,
            )
            if memory_context:
                constitution += "\n\n" + memory_context
        return constitution

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

        connection = self.morning_mcp_connection(correlation_id, user_obj.role)
        if connection is None:
            return None
        mcp_config = connection[2]

        # Feature 022 (extended by Feature 026): any tool in APPROVAL_REQUIRED_MCP_TOOLS
        # requires explicit human approval before it executes; everything in
        # NO_APPROVAL_MCP_TOOLS proceeds immediately. Both sides of the filter are
        # listed explicitly - see NO_APPROVAL_MCP_TOOLS's comment for why.
        return [self.morning_mcp_entry(
            connection,
            server_label=mcp_config.get('morning_server_label', 'morning-invoices'),
            require_approval={
                "always": {"tool_names": list(APPROVAL_REQUIRED_MCP_TOOLS)},
                "never": {"tool_names": list(NO_APPROVAL_MCP_TOOLS)},
            },
        )]

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

    def _build_progress_update_tools(self) -> List[Dict]:
        """Feature 080: send_progress_update - always attached (the feature flag that
        used to gate this has been removed, 2026-09-12, explicit operator instruction),
        not RBAC-gated either (every role can have a slow turn), unlike the other
        _build_*_tools above - see _assemble_tools."""
        return [SEND_PROGRESS_UPDATE_TOOL]

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
        fee_agreement_tools = (
            self.fee_agreement_tools.build_tools(user_obj)
            if self.rbac_enabled else []
        )
        # Feature 080: send_progress_update is NOT RBAC-gated - every role can attach it.
        progress_update_tools = self._build_progress_update_tools()
        # Reminder tools deliberately go LAST (2026-08-19, user decision after a
        # real cross-feature confusion incident): Morning's tools are one opaque
        # `mcp` entry needing runtime discovery, so reminder tools - individually
        # inlined `function` entries - were the most directly-visible tools in the
        # list whenever they came right after it. Position isn't the only fix
        # (see the tool descriptions' own explicit negative scoping above), but
        # reduces whatever residual bias position/primacy contributes.
        # query_ledger_events goes alongside reminder tools (also inlined
        # `function` entries, same visibility reasoning), before reminders.
        # Feature 084 (WhatsApp reactions): react_to_message is attached
        # unconditionally, to every role, regardless of RBAC being enabled at
        # all - reacting carries no financial/data-integrity/disclosure risk,
        # unlike every other tool assembled above (contracts/
        # react-to-message-tool-schema.md).
        combined = (
            (morning_tools or []) + ledger_query_tools + reminder_tools + fee_agreement_tools
            + progress_update_tools + [REACT_TO_MESSAGE_TOOL]
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

        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution, today_timestamp=request.timestamp),
            "input": input_items,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        audit_wire("openai", "out", "_call_openai_api (initial call)", kwargs)
        debug_wire("openai", "out", "_call_openai_api (initial call)", kwargs)
        response = self._timed_llm_call(lambda: self.client.responses.create(**kwargs))
        audit_wire("openai", "in", "_call_openai_api (initial call)", response)
        debug_wire("openai", "in", "_call_openai_api (initial call)", response)
        return response

    def single_turn(self, request: AIRequest, chat_id: Optional[str] = None, *,
                     user_role: Optional[str] = None, sender: Optional[str] = None,
                     recipient: Optional[str] = None, user_phone: Optional[str] = None,
                     is_group: bool = False, chat_name: Optional[str] = None,
                     sender_phone: Optional[str] = None) -> AIResponse:
        """Feature 080 (REQ-080-04): thin telemetry wrapper around _get_response_impl (the
        real logic, unchanged below). 2026-09-30 consolidation: the telemetry lifecycle
        itself (construct one TelemetryBuilder per turn, record the finished RequestTelemetry
        row on the way out - success OR exception alike, complete no-op when
        self.telemetry_manager is None) is now the ONE shared
        AIManager.telemetry_span implementation, also used by
        Backbone.single_turn - the two were byte-for-byte identical in shape
        before this change, just stored the active builder differently (this class's
        module-level contextvar vs. the backbone's instance attribute), which
        telemetry_span is agnostic to.

        A send_progress_update tool call sends through DeniDin
        (DeniDin.send_progress_update), in the turn in progress in this chat."""
        effective_chat_id = chat_id or request.chat_id
        with self.telemetry_span(request.request_id, effective_chat_id) as builder:
            telemetry_token = _active_telemetry_builder.set(builder)
            try:
                return self._get_response_impl(
                    request, chat_id=chat_id, user_role=user_role or 'godfather', sender=sender,
                    recipient=recipient, user_phone=user_phone, is_group=is_group,
                    chat_name=chat_name, sender_phone=sender_phone,
                )
            finally:
                _active_telemetry_builder.reset(telemetry_token)

    def _get_response_impl(self, request: AIRequest, chat_id: Optional[str] = None,
                     user_role: str = 'godfather', sender: Optional[str] = None,
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
            f"[022] single_turn: effective_chat_id={effective_chat_id!r}, "
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
            outcome = ("an AIResponse (approved)" if resolved is not None
                       else "None (declined - falling through to a normal turn)")
            logger.info(f"[022] _resolve_pending_approval returned {outcome}")
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
                    local_pending, request, effective_chat_id, user_obj, user_role, sender, recipient,
                    user_phone=user_phone, is_group=is_group, chat_name=chat_name,
                    sender_phone=sender_phone,
                )
                if local_resolved is not None:
                    return local_resolved

        # Retrieve conversation history if memory enabled (Feature 070 rolling window,
        # shared with the Backbone - AIManager.load_rolling_window).
        conversation_history = None
        if self.memory_enabled and self.session_manager and effective_chat_id:
            if self.rbac_enabled and user_obj:
                max_tokens = user_obj.token_limit
            else:
                max_tokens = self.max_tokens_by_role.get(user_role, 4000)
            conversation_history = self.load_rolling_window(
                effective_chat_id,
                window_days=self.window_days, max_tokens=max_tokens,
                exclude_message_ids=[request.message_id],
            ) or None

        try:
            # Morning MCP tools (Feature 018, RBAC-gated) + the ledger-event tool
            # (Feature 024, always attached) merged into one tools list.
            tools = self._assemble_tools(user_obj, request.request_id)

            # Call OpenAI Responses API with retry logic, conversation history, and
            # whichever tools apply this turn
            response = self._call_openai_api(request, conversation_history=conversation_history, tools=tools)

            return self._finalize_response(
                request, response, effective_chat_id, sender, tools,
            )

        except APITimeoutError as e:
            logger.error(
                f"OpenAI API timeout for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._fallback_response_for(
                request, effective_chat_id, user_obj, user_role, sender, user_phone, sender_phone,
                is_group, chat_name,
                "Sorry, I'm having trouble connecting to my AI service. Please try again later."
            )

        except RateLimitError as e:
            logger.error(
                f"OpenAI rate limit exceeded for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._fallback_response_for(
                request, effective_chat_id, user_obj, user_role, sender, user_phone, sender_phone,
                is_group, chat_name,
                "I'm currently at capacity. Please try again in a minute."
            )

        except APIError as e:
            logger.error(
                f"OpenAI API error for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._fallback_response_for(
                request, effective_chat_id, user_obj, user_role, sender, user_phone, sender_phone,
                is_group, chat_name,
                "Sorry, I encountered an error processing your request. Please try again."
            )

        except Exception as e:
            logger.error(
                f"Unexpected error in single_turn for request {request.request_id}: {e}",
                exc_info=True
            )
            return self._fallback_response_for(
                request, effective_chat_id, user_obj, user_role, sender, user_phone, sender_phone,
                is_group, chat_name,
                "Sorry, I encountered an unexpected error. Please try again."
            )

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

    def _compute_get_fee_agreement_template_outputs(
        self, response,
    ) -> Optional[List[Dict[str, Any]]]:
        """Pure computation half of get_fee_agreement_template dispatch (no
        API call) - see _handle_get_fee_agreement_template and
        _dispatch_all_local_tools for why this is split out."""
        call_id = extract_function_call_id(response, GET_FEE_AGREEMENT_TEMPLATE_TOOL["name"])
        if call_id is None:
            return None
        args = extract_function_call(response, GET_FEE_AGREEMENT_TEMPLATE_TOOL["name"]) or {}
        result = self.fee_agreement_tools.handle_get_template(args.get("variant_id"))
        return [{"call_id": call_id, "payload": result}]

    def _handle_get_fee_agreement_template(
        self, request: AIRequest, response, tools: Optional[List[Dict]]
    ):
        """Fee Agreement Document Generation (Feature 083, 2026-09-13
        redesign): get_fee_agreement_template is read-only, dispatched
        immediately - same shape as _handle_list_reminders. No approval gate
        anywhere in this feature any more (explicit human decision).

        Standalone single-tool-type entry point, kept for direct callers/tests
        exercising this tool in isolation - the main dispatch loop instead goes
        through _dispatch_all_local_tools (bugfix 2026-09-13, see its docstring)."""
        outputs = self._compute_get_fee_agreement_template_outputs(response)
        if outputs is None:
            return None
        try:
            return self._call_openai_fee_agreement_followup_api(
                request, response.id, outputs[0]["call_id"], outputs[0]["payload"], tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[083] get_fee_agreement_template follow-up call failed: {e}", exc_info=True)
            return None

    def _compute_render_fee_agreement_document_outputs(
        self, response,
    ) -> Optional[List[Dict[str, Any]]]:
        """Pure computation half of render_fee_agreement_document dispatch (no
        API call) - see _handle_render_fee_agreement_document and
        _dispatch_all_local_tools for why this is split out."""
        call_id = extract_function_call_id(response, RENDER_FEE_AGREEMENT_DOCUMENT_TOOL["name"])
        if call_id is None:
            return None
        args = extract_function_call(response, RENDER_FEE_AGREEMENT_DOCUMENT_TOOL["name"]) or {}
        result = self.fee_agreement_tools.handle_render(args)
        return [{"call_id": call_id, "payload": result}]

    def _handle_render_fee_agreement_document(
        self, request: AIRequest, response, tools: Optional[List[Dict]]
    ):
        """Fee Agreement Document Generation (Feature 083, 2026-09-13
        redesign): render_fee_agreement_document dispatches immediately, no
        approval gate - the AI is the document's author (its own full body
        text), not a form the human must approve field-by-field. Revising
        after feedback is just calling this again with edited text.

        Standalone single-tool-type entry point, kept for direct callers/tests
        exercising this tool in isolation - the main dispatch loop instead goes
        through _dispatch_all_local_tools (bugfix 2026-09-13, see its docstring)."""
        outputs = self._compute_render_fee_agreement_document_outputs(response)
        if outputs is None:
            return None
        try:
            return self._call_openai_fee_agreement_followup_api(
                request, response.id, outputs[0]["call_id"], outputs[0]["payload"], tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[083] render_fee_agreement_document follow-up call failed: {e}", exc_info=True)
            return None

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
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution),
            "input": output_items,
            "previous_response_id": previous_response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        logger.info(f"[054] _call_openai_list_reminders_followup_api: call_id={call_id!r}")
        audit_wire("openai", "out", "_call_openai_list_reminders_followup_api", kwargs)
        debug_wire("openai", "out", "_call_openai_list_reminders_followup_api", kwargs)
        response = self._timed_llm_call(lambda: self.client.responses.create(**kwargs))
        audit_wire("openai", "in", "_call_openai_list_reminders_followup_api", response)
        debug_wire("openai", "in", "_call_openai_list_reminders_followup_api", response)
        return response

    def _compute_list_reminders_outputs(self, response) -> Optional[List[Dict[str, Any]]]:
        """Pure computation half of list_reminders dispatch (no API call) - see
        _handle_list_reminders and _dispatch_all_local_tools for why this is split
        out. Returns a single-item outputs list, or None if no list_reminders call
        is present in `response`."""
        call_id = extract_function_call_id(response, LIST_REMINDERS_TOOL["name"])
        if call_id is None:
            return None

        summary = build_list_reminders_summary(self.reminder_manager)
        return [{"call_id": call_id, "payload": {"reminders": summary}}]

    def _handle_list_reminders(self, request: AIRequest, response, tools: Optional[List[Dict]]):
        """Reminders (Feature 054): list_reminders (FR-013) is read-only, dispatched
        immediately (unlike create/modify/delete_reminder), same as
        capture_ledger_event - needs a follow-up round-trip for the same reason
        (reasoning models emit function_call OR message, never both in one turn).

        Standalone single-tool-type entry point, kept for direct callers/tests
        exercising list_reminders in isolation - the main dispatch loop instead
        goes through _dispatch_all_local_tools, which also picks up any OTHER
        tool type's calls co-occurring in the same response (bugfix 2026-09-13:
        this method alone would silently orphan them, since OpenAI rejects a
        follow-up unless EVERY pending call from that response gets an output).

        Returns the follow-up response (whose output_text/usage should replace the
        original response's), or None if no list_reminders call was made this turn,
        or if the follow-up call itself failed.
        """
        outputs = self._compute_list_reminders_outputs(response)
        if outputs is None:
            return None
        call_id = outputs[0]["call_id"]
        summary = outputs[0]["payload"]["reminders"]
        try:
            return self._call_openai_list_reminders_followup_api(
                request, response.id, call_id, summary, tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[054] list_reminders follow-up call failed: {e}", exc_info=True)
            return None

    def _call_openai_send_progress_update_followup_api(
        self, request: AIRequest, previous_response_id: str, call_id: str,
        sent: bool, tools: Optional[List[Dict]] = None,
    ):
        """Reports send_progress_update's own result back as that call's
        function_call_output, same pattern as _call_openai_list_reminders_followup_api -
        send_progress_update dispatches immediately, so no PendingLocalToolApproval is
        involved and no later turn is needed."""
        output_items = [{
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps({"sent": sent}, ensure_ascii=False),
        }]
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution),
            "input": output_items,
            "previous_response_id": previous_response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        logger.info(f"[080] _call_openai_send_progress_update_followup_api: call_id={call_id!r}")
        audit_wire("openai", "out", "_call_openai_send_progress_update_followup_api", kwargs)
        debug_wire("openai", "out", "_call_openai_send_progress_update_followup_api", kwargs)
        response = self._timed_llm_call(lambda: self.client.responses.create(**kwargs))
        audit_wire("openai", "in", "_call_openai_send_progress_update_followup_api", response)
        debug_wire("openai", "in", "_call_openai_send_progress_update_followup_api", response)
        return response

    def _compute_send_progress_update_outputs(
        self, request: AIRequest, response,
    ) -> Optional[List[Dict[str, Any]]]:
        """Pure(ish) computation half of send_progress_update dispatch (the actual
        WhatsApp send is a real side effect, but no OpenAI API call is made here) -
        see _handle_send_progress_update and _dispatch_all_local_tools for why this
        is split out. Returns a single-item outputs list, or None if no
        send_progress_update call is present in `response`."""
        call_id = extract_function_call_id(response, SEND_PROGRESS_UPDATE_TOOL["name"])
        if call_id is None:
            return None

        args = extract_function_call(response, SEND_PROGRESS_UPDATE_TOOL["name"]) or {}
        text = args.get("text")
        sent = send_progress_update_message(
            self.denidin, _active_telemetry_builder.get(), request.chat_id, text,
        )
        # The progress message is stored in the session by the send itself
        # (DeniDin.send_progress_update), the moment it's sent - nothing to track here.
        return [{"call_id": call_id, "payload": {"sent": sent}}]

    def _handle_send_progress_update(self, request: AIRequest, response, tools: Optional[List[Dict]]):
        """Feature 080 (REQ-080-02): send_progress_update is read-only from the ledger's
        perspective (writes nothing persistent except telemetry), dispatched immediately
        - same shape as _handle_list_reminders. The actual WhatsApp send happens here,
        through DeniDin.send_progress_update (nothing is sent when no turn is in progress in
        the chat, e.g. a test calling single_turn directly - the turn still proceeds
        normally via the follow-up call below).

        Standalone single-tool-type entry point, kept for direct callers/tests
        exercising send_progress_update in isolation - the main dispatch loop instead
        goes through _dispatch_all_local_tools (bugfix 2026-09-13, see its docstring).

        Returns the follow-up response (whose output_text/usage should replace the original
        response's), or None if no send_progress_update call was made this turn, or if the
        follow-up call itself failed."""
        outputs = self._compute_send_progress_update_outputs(request, response)
        if outputs is None:
            return None
        call_id = outputs[0]["call_id"]
        sent = outputs[0]["payload"]["sent"]
        try:
            return self._call_openai_send_progress_update_followup_api(
                request, response.id, call_id, sent, tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[080] send_progress_update follow-up call failed: {e}", exc_info=True)
            return None

    def _call_openai_fee_agreement_followup_api(
        self, request: AIRequest, previous_response_id: str, call_id: str,
        payload: Dict[str, Any], tools: Optional[List[Dict]] = None,
    ):
        """Reports verify_fee_agreement_document's or send_fee_agreement_document's
        result back as that call's function_call_output, via a follow-up chained
        to the SAME turn's response.id - same single-item shape as
        _call_openai_list_reminders_followup_api (both dispatch immediately, no
        PendingLocalToolApproval involved). Standalone single-tool-type entry
        point only - the main dispatch loop instead goes through
        _dispatch_all_local_tools (bugfix 2026-09-13, see its docstring: a
        response may legitimately carry a fee-agreement call ALONGSIDE another
        tool type's call, e.g. query_ledger_events, and this single-item
        follow-up would leave the other one unanswered, which OpenAI rejects
        outright)."""
        output_items = [{
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps(payload, ensure_ascii=False),
        }]
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution),
            "input": output_items,
            "previous_response_id": previous_response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        logger.info(f"[083] _call_openai_fee_agreement_followup_api: call_id={call_id!r}, payload={payload!r}")
        audit_wire("openai", "out", "_call_openai_fee_agreement_followup_api", kwargs)
        debug_wire("openai", "out", "_call_openai_fee_agreement_followup_api", kwargs)
        response = self._timed_llm_call(lambda: self.client.responses.create(**kwargs))
        audit_wire("openai", "in", "_call_openai_fee_agreement_followup_api", response)
        debug_wire("openai", "in", "_call_openai_fee_agreement_followup_api", response)
        return response

    def _compute_verify_fee_agreement_document_outputs(
        self, response,
    ) -> Optional[List[Dict[str, Any]]]:
        """Pure computation half of verify_fee_agreement_document dispatch (no
        API call) - see _handle_verify_fee_agreement_document and
        _dispatch_all_local_tools for why this is split out."""
        call_id = extract_function_call_id(response, VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL["name"])
        if call_id is None:
            return None
        args = extract_function_call(response, VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL["name"]) or {}
        result = self.fee_agreement_tools.handle_verify(args.get("document_id"))
        return [{"call_id": call_id, "payload": result}]

    def _handle_verify_fee_agreement_document(
        self, request: AIRequest, response, tools: Optional[List[Dict]]
    ):
        """Fee Agreement Document Generation (Feature 083): verify_fee_agreement_document
        is read-only, dispatched immediately - same shape as _handle_list_reminders.

        Standalone single-tool-type entry point, kept for direct callers/tests
        exercising this tool in isolation - the main dispatch loop instead goes
        through _dispatch_all_local_tools (bugfix 2026-09-13, see its docstring).

        Returns the follow-up response, or None if no such call was made this
        turn, or if the follow-up call itself failed."""
        outputs = self._compute_verify_fee_agreement_document_outputs(response)
        if outputs is None:
            return None
        try:
            return self._call_openai_fee_agreement_followup_api(
                request, response.id, outputs[0]["call_id"], outputs[0]["payload"], tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[083] verify_fee_agreement_document follow-up call failed: {e}", exc_info=True)
            return None

    def _compute_send_fee_agreement_document_outputs(
        self, response, effective_chat_id: Optional[str],
    ) -> Optional[List[Dict[str, Any]]]:
        """Pure(ish) computation half of send_fee_agreement_document dispatch
        (the actual WhatsApp send is a real side effect, but no OpenAI API
        call is made here) - see _handle_send_fee_agreement_document and
        _dispatch_all_local_tools for why this is split out."""
        call_id = extract_function_call_id(response, SEND_FEE_AGREEMENT_DOCUMENT_TOOL["name"])
        if call_id is None:
            return None
        args = extract_function_call(response, SEND_FEE_AGREEMENT_DOCUMENT_TOOL["name"]) or {}
        if effective_chat_id is None or self.fee_agreement_tools is None:
            result: Dict[str, Any] = {"error": "לא ניתן לשלוח מסמך בהקשר הנוכחי."}
        else:
            result = self.fee_agreement_tools.handle_send(
                args.get("document_id"), effective_chat_id, args.get("caption", ""),
            )
        return [{"call_id": call_id, "payload": result}]

    def _handle_send_fee_agreement_document(
        self, request: AIRequest, response, tools: Optional[List[Dict]],
        effective_chat_id: Optional[str],
    ):
        """Fee Agreement Document Generation (Feature 083): send_fee_agreement_document
        dispatches immediately but refuses (a tool-call error in the returned
        payload, never a raised exception) unless the document already passed
        verification - see fee_agreement_tools.handle_send's own docstring.

        Standalone single-tool-type entry point, kept for direct callers/tests
        exercising this tool in isolation - the main dispatch loop instead goes
        through _dispatch_all_local_tools (bugfix 2026-09-13, see its docstring)."""
        outputs = self._compute_send_fee_agreement_document_outputs(response, effective_chat_id)
        if outputs is None:
            return None
        try:
            return self._call_openai_fee_agreement_followup_api(
                request, response.id, outputs[0]["call_id"], outputs[0]["payload"], tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[083] send_fee_agreement_document follow-up call failed: {e}", exc_info=True)
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
        kwargs: Dict[str, Any] = {
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
        audit_wire("openai", "out", "_call_openai_query_ledger_events_followup_api", kwargs)
        debug_wire("openai", "out", "_call_openai_query_ledger_events_followup_api", kwargs)
        response = self._timed_llm_call(lambda: self.client.responses.create(**kwargs))
        audit_wire("openai", "in", "_call_openai_query_ledger_events_followup_api", response)
        debug_wire("openai", "in", "_call_openai_query_ledger_events_followup_api", response)
        return response

    def _compute_query_ledger_events_outputs(self, response) -> Optional[List[Dict[str, Any]]]:
        """Pure computation half of query_ledger_events dispatch (no API call) -
        see _handle_query_ledger_events and _dispatch_all_local_tools for why this
        is split out. Returns an outputs list (one entry per call - a turn may
        legitimately contain several), or None if no query_ledger_events call is
        present in `response`."""
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
        return outputs

    def _handle_query_ledger_events(self, request: AIRequest, response, tools: Optional[List[Dict]]):
        """Feature 044 (research.md Decision 10): query_ledger_events is
        read-only, dispatched immediately (like list_reminders) - needs a
        follow-up round-trip for the same reasoning-model
        function_call-OR-message limitation.

        Standalone single-tool-type entry point, kept for direct callers/tests
        exercising query_ledger_events in isolation - the main dispatch loop
        instead goes through _dispatch_all_local_tools (bugfix 2026-09-13, see
        its docstring).

        Returns the follow-up response (whose output_text/usage should
        replace the original response's), or None if no query_ledger_events
        call was made this turn, or if the follow-up call itself failed.
        """
        outputs = self._compute_query_ledger_events_outputs(response)
        if outputs is None:
            return None
        try:
            return self._call_openai_query_ledger_events_followup_api(
                request, response.id, outputs, tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[044] query_ledger_events follow-up call failed: {e}", exc_info=True)
            return None

    def _resolve_react_to_message_target(
        self, request: AIRequest, effective_chat_id: Optional[str], explicit_message_id: Optional[str],
    ) -> Optional[str]:
        """Feature 084's message_id resolution fallback chain - see
        src/tool_actions/messaging_actions.py::resolve_react_to_message_target."""
        return resolve_react_to_message_target(
            self.session_manager, request, effective_chat_id, explicit_message_id
        )

    def _call_openai_react_to_message_followup_api(
        self, request: AIRequest, previous_response_id: str,
        outputs: List[Dict[str, Any]], tools: Optional[List[Dict]] = None,
    ):
        """Reports EVERY react_to_message call's own result back as its own
        function_call_output, via a follow-up chained to the SAME turn's
        response.id - multi-item batched, same shape as
        _call_openai_query_ledger_events_followup_api (a turn could plausibly
        call react_to_message more than once, e.g. reacting to the current
        message AND flipping an earlier one)."""
        output_items = [
            {
                "type": "function_call_output",
                "call_id": item["call_id"],
                "output": json.dumps(item["payload"], ensure_ascii=False),
            }
            for item in outputs
        ]
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution, today_timestamp=request.timestamp),
            "input": output_items,
            "previous_response_id": previous_response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        call_ids = [item["call_id"] for item in outputs]
        logger.info(f"[084] _call_openai_react_to_message_followup_api: call_ids={call_ids!r}")
        audit_wire("openai", "out", "_call_openai_react_to_message_followup_api", kwargs)
        debug_wire("openai", "out", "_call_openai_react_to_message_followup_api", kwargs)
        response = self.client.responses.create(**kwargs)
        audit_wire("openai", "in", "_call_openai_react_to_message_followup_api", response)
        debug_wire("openai", "in", "_call_openai_react_to_message_followup_api", response)
        return response

    def _compute_react_to_message_outputs(
        self, request: AIRequest, response, effective_chat_id: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Pure(ish) computation half of react_to_message dispatch (the actual
        reaction send is a real side effect, but no OpenAI API call is made here) -
        see _handle_react_to_message and _dispatch_all_local_tools for why this is
        split out. Uses extract_all_function_calls: a turn may legitimately call
        this more than once (react to current message AND flip an earlier one).
        Returns an outputs list, or None if no react_to_message call is present in
        `response`."""
        calls = extract_all_function_calls(response, REACT_TO_MESSAGE_TOOL["name"])
        if not calls:
            return None

        outputs = []
        for call in calls:
            if call["arguments"] is None:
                logger.warning(
                    f"[084] react_to_message call {call['call_id']!r} had unparseable "
                    "arguments (likely truncated) - reporting an isolated error for this "
                    "call only"
                )
                outputs.append({
                    "call_id": call["call_id"],
                    "payload": {"status": "failed", "reason": "arguments could not be parsed"},
                })
                continue

            outputs.append({
                "call_id": call["call_id"],
                "payload": build_react_to_message_payload(
                    self.denidin, request, effective_chat_id, call["arguments"], call["call_id"],
                ),
            })
        return outputs

    def _handle_react_to_message(
        self, request: AIRequest, response, tools: Optional[List[Dict]],
        effective_chat_id: Optional[str] = None,
    ):
        """Feature 084: react_to_message is cosmetic/reversible, dispatched
        immediately (like list_reminders/query_ledger_events) - needs a
        follow-up round-trip for the same function_call-OR-message reasoning-
        model limitation.

        Never raises past this method - a reaction failure is logged
        (REQ-084-007) and reported to the model as {"status": "failed"}, never
        propagated to break the turn.

        Standalone single-tool-type entry point, kept for direct callers/tests
        exercising react_to_message in isolation (including the reminder-approval
        confirmation follow-up path, which loops this call directly rather than
        going through _dispatch_all_local_tools). Any OTHER call site handling a
        response that could ALSO carry a different tool type's calls alongside
        react_to_message should go through _dispatch_all_local_tools instead
        (bugfix 2026-09-13, see its docstring) - this method alone only resolves
        react_to_message's own calls and would leave any other pending call in
        the same response unaddressed, which OpenAI rejects outright.

        Returns the follow-up response, or None if no react_to_message call
        was made this turn, or if the follow-up call itself failed.
        """
        outputs = self._compute_react_to_message_outputs(request, response, effective_chat_id)
        if outputs is None:
            return None
        try:
            return self._call_openai_react_to_message_followup_api(
                request, response.id, outputs, tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[084] react_to_message follow-up call failed: {e}", exc_info=True)
            return None

    def _call_openai_combined_local_tools_followup_api(
        self, request: AIRequest, previous_response_id: str,
        outputs: List[Dict[str, Any]], tools: Optional[List[Dict]] = None,
    ):
        """Reports EVERY immediate-dispatch local tool call from one response back
        in a SINGLE follow-up, one function_call_output item per call_id - see
        _dispatch_all_local_tools for why this must be one combined call rather
        than one call per tool type."""
        output_items = [
            {
                "type": "function_call_output",
                "call_id": item["call_id"],
                "output": json.dumps(item["payload"], ensure_ascii=False),
            }
            for item in outputs
        ]
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution, today_timestamp=request.timestamp),
            "input": output_items,
            "previous_response_id": previous_response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        call_ids = [item["call_id"] for item in outputs]
        logger.info(f"[LOOP] _call_openai_combined_local_tools_followup_api: call_ids={call_ids!r}")
        audit_wire("openai", "out", "_call_openai_combined_local_tools_followup_api", kwargs)
        debug_wire("openai", "out", "_call_openai_combined_local_tools_followup_api", kwargs)
        response = self._timed_llm_call(lambda: self.client.responses.create(**kwargs))
        audit_wire("openai", "in", "_call_openai_combined_local_tools_followup_api", response)
        debug_wire("openai", "in", "_call_openai_combined_local_tools_followup_api", response)
        return response

    def _dispatch_all_local_tools(
        self, request: AIRequest, response, tools: Optional[List[Dict]],
        effective_chat_id: Optional[str] = None,
    ):
        """Bugfix (2026-09-13, real production incident): collects pending
        immediate-dispatch local-tool calls of EVERY known type from `response`
        and resolves them together in ONE follow-up call.

        Root cause this fixes: OpenAI's Responses API rejects a follow-up
        outright ("No tool output found for function call ...") unless outputs
        for EVERY pending function_call from that response are included - not
        just the ones the caller happens to be reporting. Before this fix, each
        tool type (query_ledger_events, list_reminders, send_progress_update,
        react_to_message) ran its own siloed follow-up via its own _handle_X
        method, checked one at a time in a loop that `continue`d the instant any
        ONE of them fired. That was safe only as long as a response never
        contained calls of TWO different types at once. Feature 084's
        react_to_message tool is unconditionally attached to every single turn
        (REQ-084, cosmetic/reversible, no RBAC gate) and is exactly the kind of
        call a model naturally bundles alongside a "real" action in the same
        response - the first live test of Feature 080 + Feature 084 together hit
        this immediately: a response containing both a list_reminders call and
        two react_to_message calls caused BOTH single-type handlers to fail in
        turn (each omitting the other's call_id(s)), and the loop silently fell
        back to a pre-tool-call narration ("checking Morning now...") as if it
        were the final answer - the real lookup never happened.

        Every immediate-dispatch tool type must be reflected here - this is the
        ONLY safe way to resolve a response's local-tool calls once more than
        one such tool can be attached at a time (which, per Feature 084's
        unconditional attachment, is now true for every single turn).

        Returns the combined follow-up response, or None if `response` carries
        no pending call of any known immediate-dispatch tool type, or if the
        combined follow-up call itself failed."""
        outputs: List[Dict[str, Any]] = []

        ledger_outputs = self._compute_query_ledger_events_outputs(response)
        if ledger_outputs:
            outputs.extend(ledger_outputs)

        reminders_outputs = self._compute_list_reminders_outputs(response)
        if reminders_outputs:
            outputs.extend(reminders_outputs)

        progress_outputs = self._compute_send_progress_update_outputs(request, response)
        if progress_outputs:
            outputs.extend(progress_outputs)

        react_outputs = self._compute_react_to_message_outputs(request, response, effective_chat_id)
        if react_outputs:
            outputs.extend(react_outputs)

        # Fee Agreement Document Generation (Feature 083, 2026-09-13 redesign):
        # all 4 tools dispatch immediately - no PendingLocalToolApproval
        # anywhere in this feature. get_fee_agreement_template/
        # render_fee_agreement_document are the AI's own drafting loop (fetch
        # a reference, author the full body, render); verify/send close it
        # out. Every one of these must go through this combined dispatch too
        # (bugfix 2026-09-13/2026-09-14) - a real billed run hit exactly the
        # incident this method's docstring describes with
        # get_fee_agreement_template co-occurring alongside query_ledger_events
        # in the same response.
        get_template_outputs = self._compute_get_fee_agreement_template_outputs(response)
        if get_template_outputs:
            outputs.extend(get_template_outputs)

        render_outputs = self._compute_render_fee_agreement_document_outputs(response)
        if render_outputs:
            outputs.extend(render_outputs)

        verify_fee_agreement_outputs = self._compute_verify_fee_agreement_document_outputs(response)
        if verify_fee_agreement_outputs:
            outputs.extend(verify_fee_agreement_outputs)

        send_fee_agreement_outputs = self._compute_send_fee_agreement_document_outputs(
            response, effective_chat_id
        )
        if send_fee_agreement_outputs:
            outputs.extend(send_fee_agreement_outputs)

        if not outputs:
            return None

        try:
            return self._call_openai_combined_local_tools_followup_api(
                request, response.id, outputs, tools
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[LOOP] combined local-tool follow-up call failed: {e}", exc_info=True)
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
        2026-10-01: the AIManager.mcp_error_text (also the backbone's).
        """
        return AIManager.mcp_error_text(call)

    @staticmethod
    def _extract_mcp_call_items(response) -> List[Dict[str, Any]]:
        """Pull every `mcp_call`-type item off one API response's `.output`,
        in the same shape `_finalize_response` has always reported
        (name/error/arguments/output). Factored out (2026-09-15 fix) so a
        remote MCP tool call can be picked up from WHICHEVER round of a turn
        it actually executed in - see `_run_local_tool_dispatch_loop`'s own
        `accumulated_mcp_calls` for why a single-round extraction at the end
        of a turn is not enough.

        `error` is normalized to a plain string here (2026-09-15 fix,
        real billed failure): the SDK's own `item.error` is usually a
        business-level string (e.g. a tool-side refusal), but on a genuine
        network-level failure (e.g. a 503 from the MCP tunnel) it can be a
        raw exception object instead (`HTTPError(...)`). Left un-normalized,
        that object flows straight into `mcp_calls` and eventually into
        `SessionManager.add_message`'s `json.dump(asdict(message), ...)`
        (no `default=str` there) and crashes with `TypeError: Object of
        type HTTPError is not JSON serializable`. Nothing downstream of
        this extraction point should ever have to know `item.error` might
        not be a string - normalize once, here, at the boundary.
        2026-10-01: delegates to the AIManager.extract_mcp_call_items,
        also used by the backbone."""
        return AIManager.extract_mcp_call_items(response)

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

        Bug fix (2026-09-15): `mcp_calls` used to be re-derived by
        `_finalize_response` from a single response (`current_response`,
        whichever round this loop last settled on) - so an MCP call that
        genuinely executed in an EARLIER round (e.g. the dedicated approval
        round that ran `add_client`) silently vanished from the turn's
        reported `mcp_calls` if a LATER round then ran for an unrelated
        reason (e.g. a `react_to_message` follow-up), because that earlier
        round's `mcp_call` item is not present in the final round's
        `response.output`. Fixed by accumulating `mcp_call` items across
        EVERY round as the loop goes - the same pattern already used here for
        token deltas and (structurally) `ledger_event_ids` - instead of
        re-deriving them from one response at the end.

        Returns (final_response, extra_tokens, extra_prompt_tokens,
        extra_completion_tokens, usage_response, ledger_event_ids,
        accumulated_mcp_calls) - the three "extra_*" fields are deltas to ADD
        to the caller's own running totals (which already include the turn's
        original response.usage), never absolute totals themselves.
        `usage_response` is whichever response's usage/finish_reason is
        authoritative (the last one that actually produced a follow-up, or
        the original if none did).

        `accumulated_mcp_calls` (2026-09-15 fix): a remote MCP tool call
        (add_client, create_invoice, ...) is a tool call like any other -
        this loop already re-runs and re-follows-up local tools across every
        round without losing earlier rounds' results (that's its whole
        point); an MCP call executed in one round must be preserved the same
        way, not just whatever the FINAL round's own response happens to
        carry. Before this fix, an MCP call that executed in an early round
        (e.g. the approval round itself) silently vanished from the turn's
        reported mcp_calls the moment ANY later round ran for an unrelated
        reason (a local tool call this turn also happened to make) - a real,
        billed failure (test_fee_agreement_generation_flow.py's
        _seed_client-driven add_client flow) is what surfaced this: the
        client genuinely got added, the model even said so in its own reply,
        but the turn's mcp_calls came back empty because a react_to_message
        follow-up round ran afterward and became `current_response`. Fixed
        the same way the backbone handles everything else here: accumulate
        as you go, across every round, not just the last one.
        """
        current_response = response
        usage_response = response
        extra_tokens = extra_prompt_tokens = extra_completion_tokens = 0
        ledger_event_ids: List[str] = []
        accumulated_mcp_calls: List[Dict[str, Any]] = self._extract_mcp_call_items(response)
        for _loop_round in range(MAX_LOCAL_TOOL_LOOP_ITERATIONS):
            # Bugfix (2026-09-13): every immediate-dispatch local tool type
            # (query_ledger_events, list_reminders, send_progress_update,
            # react_to_message) is resolved together in ONE combined follow-up
            # via _dispatch_all_local_tools, rather than one siloed follow-up
            # per tool type - see that method's docstring for the real
            # production incident this fixes (react_to_message is
            # unconditionally attached to every turn, so a response containing
            # it ALONGSIDE any other tool type used to always fail: OpenAI
            # rejects a follow-up unless outputs for EVERY pending call in that
            # response are included, and each single-type handler only knew
            # about its own).
            # Feature 080 (REQ-080-04): the local tool dispatch AND its own internal
            # follow-up responses.create() call (already separately counted by
            # _timed_llm_call) both fall inside this timed span - tool_total_execution_ms
            # and llm_total_inference_time_ms are not strictly additive to
            # total_duration_ms for a turn that uses a local tool, a known/accepted v1
            # limitation (total_duration_ms itself is measured independently and stays
            # accurate regardless).
            local_tools_followup = self._timed_tool_call(
                "local_tools",
                lambda: self._dispatch_all_local_tools(request, current_response, tools, effective_chat_id),
            )
            if local_tools_followup is not None:
                current_response = local_tools_followup
                usage_response = local_tools_followup
                extra_tokens += local_tools_followup.usage.total_tokens
                extra_prompt_tokens += local_tools_followup.usage.input_tokens
                extra_completion_tokens += local_tools_followup.usage.output_tokens
                accumulated_mcp_calls.extend(self._extract_mcp_call_items(local_tools_followup))
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
            accumulated_mcp_calls,
        )

    def _attach_ledger_event_ids(self, chat_id: Optional[str], message_id: Optional[str],
                                 ledger_event_ids) -> None:
        """Fills this turn's captured ledger event ids (Feature 033) into the user message,
        which was already stored the moment it arrived (2026-09-30 - the reply is stored
        when sent, with its mcp_calls). Never raises."""
        if ledger_event_ids:
            self.denidin.update_message(chat_id, message_id, ledger_event_ids=list(ledger_event_ids))


    def _finalize_response(self, request: AIRequest, response, effective_chat_id: Optional[str],
                           sender: Optional[str], tools: Optional[List[Dict]]) -> AIResponse:
        """
        Shared post-API-call logic: extract mcp_calls, detect a new pending
        approval (Feature 022), fill ledger_event_ids into the already-stored user
        message, build the final AIResponse. Used by both the normal turn path and the pending-approval
        resolution path in `single_turn`/`_resolve_pending_approval`.
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
            accumulated_mcp_calls,
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

        # Fee Agreement Document Generation (Feature 083, 2026-09-13 redesign):
        # no proposal/approval step exists any more for this feature -
        # get_fee_agreement_template/render_fee_agreement_document both
        # dispatch immediately from inside _run_local_tool_dispatch_loop,
        # same as verify/send. Nothing to do here.

        # bugfix-045-followup (2026-08-27): this used to need its own
        # all_output_items union of response.output + a same-turn ledger-
        # capture followup's output, to fix the exact scenario the bugfix-045
        # near-duplicate-name regression test exposed (a capture_ledger_event
        # follow-up round ALSO proposing an approval-gated Morning tool, e.g.
        # add_client, whose mcp_approval_request then went undetected).
        #
        # 2026-09-15 correction: the "superseded, already fixed" claim
        # previously written here was WRONG - `response = current_response`
        # only ever reflects the LOOP'S LAST round. That's fine for
        # DETECTING a pending approval that only surfaces late, but it
        # silently drops an mcp_call that already EXECUTED in an earlier
        # round the moment any later round runs for an unrelated reason
        # (real, billed failure, test_fee_agreement_generation_flow.py's
        # add_client seeding: the approval round genuinely executed
        # add_client, a further local-tool round then ran for something
        # else entirely, and the turn's reported mcp_calls came back empty
        # even though the model's own reply said the client was added). An
        # MCP call is a tool call like any other kind this loop tracks -
        # `_run_local_tool_dispatch_loop` now accumulates every round's
        # mcp_call items as it goes (`accumulated_mcp_calls`), the same way
        # it already accumulates token deltas, instead of re-deriving
        # mcp_calls from a single response.output at the end.
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
        # call) - never logged/returned with secrets, just tool I/O. Accumulated
        # across every round of this turn (see _run_local_tool_dispatch_loop's
        # `accumulated_mcp_calls`), not just re-derived from the LAST round's
        # own response.output - a real, executed mcp_call must never vanish
        # just because a later, unrelated round also ran this same turn.
        mcp_calls = accumulated_mcp_calls
        if mcp_calls:
            logger.info(f"MCP calls for request {request.request_id}: {mcp_calls}")
            # Feature 080 (REQ-080-04): record each Morning MCP tool call for the
            # tool_calls_count/morning_api_request_times_ms breakdown. Duration is
            # deliberately 0 here - OpenAI's Responses API executes a remote MCP tool
            # call server-side, INSIDE the responses.create() call itself (already
            # captured by _timed_llm_call's own timing), so there is no separate,
            # observable per-tool duration to measure from this side of the API. A
            # future Morning-side timing improvement (out of scope here - see plan.md's
            # "no changes to apps/morning-mcp-app" note) could attach real durations;
            # until then this correctly reports count/name, not a fabricated duration.
            # 2026-10-01: the shared AIManager.record_mcp_tool_calls, also used by
            # the backbone.
            self.record_mcp_tool_calls(_active_telemetry_builder.get(), mcp_calls)
        # Invoicing tools offered, a confirmation-sounding reply, no mcp_call: log a
        # possible fabricated success (shared AIManager helper, 2026-10-01).
        self.log_possible_hallucinated_confirmation(request.request_id, response_text, bool(tools), mcp_calls)

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
        # the sentinel as its entire response - the caller (denidin.py) then sends,
        # and therefore stores, nothing. The user's message was stored on receipt.
        should_reply = should_reply_for(response_text)

        self._attach_ledger_event_ids(effective_chat_id, request.message_id, ledger_event_ids)

        # Create response object.
        # Responses API has no per-choice finish_reason; derive from
        # incomplete_details when present, else "stop". Uses usage_response
        # (the ledger follow-up call when one happened, else the original
        # call) so finish_reason/model reflect whichever turn actually
        # produced response_text.
        finish_reason = self.finish_reason_of(usage_response)

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

        # Cut to WhatsApp's limit when longer (shared AIManager helper).
        ai_response = self.fit_for_whatsapp(ai_response)

        return ai_response

    def _call_openai_reminder_followup_api(
        self, request: AIRequest, pending: PendingLocalToolApproval, result: Dict[str, Any],
        tools: Optional[List[Dict]] = None,
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

        `tools` (Feature 084 fix, 2026-09-12): this call used to omit `tools`
        entirely, meaning it went out with an EMPTY tool list - `react_to_message`
        was structurally unreachable on the exact turn that reports a reminder's
        real resolution, no matter what the constitution said. A confirmed real
        miss found via the reaction-judgment tuning harness: a reminder approval
        resolved successfully and the model could never react to it, only ever
        embed an emoji character in the reply text (or, worse, once the wording
        ruled that out too, drop all signal of the resolution entirely). Mirrors
        `_call_openai_react_to_message_followup_api`'s own `tools` param.
        """
        output_items = [{
            "type": "function_call_output",
            "call_id": pending.call_id,
            "output": json.dumps({"status": "success", **result}, ensure_ascii=False),
        }]
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution),
            "input": output_items,
            "previous_response_id": pending.response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        logger.info(f"[054] _call_openai_reminder_followup_api: call_id={pending.call_id!r}, result={result!r}")
        audit_wire("openai", "out", "_call_openai_reminder_followup_api", kwargs)
        debug_wire("openai", "out", "_call_openai_reminder_followup_api", kwargs)
        response = self._timed_llm_call(lambda: self.client.responses.create(**kwargs))
        audit_wire("openai", "in", "_call_openai_reminder_followup_api", response)
        debug_wire("openai", "in", "_call_openai_reminder_followup_api", response)
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
        kwargs: Dict[str, Any] = {
            "model": self.config.ai_model,
            "instructions": self._build_instructions(constitution, today_timestamp=today_timestamp),
            "input": [{"role": "user", "content": text}],
            "tools": [LEDGER_EVENT_TOOL],
            "max_output_tokens": self.config.ai_reply_max_tokens,
        }

        logger.info("[024] capture_ledger_events_from_text: classifying extracted image text")
        audit_wire("openai", "out", "capture_ledger_events_from_text", kwargs)
        debug_wire("openai", "out", "capture_ledger_events_from_text", kwargs)
        response = self._timed_llm_call(lambda: self.client.responses.create(**kwargs))
        audit_wire("openai", "in", "capture_ledger_events_from_text", response)
        debug_wire("openai", "in", "capture_ledger_events_from_text", response)
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
            retry_kwargs: Dict[str, Any] = dict(kwargs)
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
            audit_wire("openai", "out", "capture_ledger_events_from_text (retry)", retry_kwargs)
            debug_wire("openai", "out", "capture_ledger_events_from_text (retry)", retry_kwargs)
            response = self._timed_llm_call(lambda: self.client.responses.create(**retry_kwargs))
            audit_wire("openai", "in", "capture_ledger_events_from_text (retry)", response)
            debug_wire("openai", "in", "capture_ledger_events_from_text (retry)", response)
            ledger_calls = extract_all_function_calls(response, LEDGER_EVENT_TOOL["name"])
            ledger_events = [c["arguments"] for c in ledger_calls]
            logger.info(
                f"[024] capture_ledger_events_from_text retry response: "
                f"id={getattr(response, 'id', None)!r}, "
                f"ledger_events_captured={len(ledger_events)}, ledger_events={ledger_events!r}"
            )

        return ledger_events

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
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution, today_timestamp=request.timestamp),
            "input": [approval_item],
            "previous_response_id": pending.response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        logger.info(f"[022] _call_openai_approval_api: approve={approve}, kwargs={kwargs!r}")
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
        response = self._timed_llm_call(lambda: self.client.with_options(max_retries=0).responses.create(**kwargs))
        audit_wire("openai", "in", "_call_openai_approval_api", response)
        debug_wire("openai", "in", "_call_openai_approval_api", response)
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
        is_affirmative = self.is_affirmative_reply(request.user_prompt)
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
                return self._fallback_response_for(
                    request, effective_chat_id, user_obj, user_role, sender, user_phone,
                    sender_phone, is_group, chat_name, APPROVAL_FAILED_TRY_AGAIN)

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
            # 2026-10-01: counted by the AIManager.tally_write_executions
            # (also the backbone's approved-turn guard).
            executions = self.tally_write_executions(executed_calls, [pending.tool_name])
            if executions.duplicated:
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
                    f"{executions.counts[pending.tool_name]} executions of the approved tool "
                    f"in one response (expected exactly 1). All mcp_calls: {executed_calls!r}"
                )
                self.pending_approval_manager.clear(effective_chat_id)
                return self._fallback_response_for(
                    request, effective_chat_id, user_obj, user_role, sender, user_phone,
                    sender_phone, is_group, chat_name, APPROVAL_POSSIBLY_DUPLICATED)

            if not executions.ran_any:
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
                logger.error(
                    f"[022] APPROVED TOOL NEVER RAN: chat={effective_chat_id!r}, "
                    f"tool={pending.tool_name!r}, approval_request_id={pending.approval_request_id!r} "
                    f"produced 0 executions of the approved tool (expected exactly 1). "
                    f"All mcp_calls: {executed_calls!r}"
                )
                self.pending_approval_manager.clear(effective_chat_id)
                return self._fallback_response_for(
                    request, effective_chat_id, user_obj, user_role, sender, user_phone,
                    sender_phone, is_group, chat_name,
                    self.approved_write_not_run_message(
                        executions.failure_detail, self.write_subject([pending.tool_name])),
                )

            self.pending_approval_manager.clear(effective_chat_id)
            logger.info(f"[022] Approved and cleared pending for chat={effective_chat_id!r}")
            return self._finalize_response(
                request, response, effective_chat_id, sender, tools,
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
        sender: Optional[str], recipient: Optional[str], *,
        user_phone: Optional[str] = None, is_group: bool = False,
        chat_name: Optional[str] = None, sender_phone: Optional[str] = None,
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
        is_affirmative = self.is_affirmative_reply(request.user_prompt)
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
            literal_sender_phone = None
            literal_sender_role = None
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
                    literal_sender_phone, literal_sender_role = resolve_literal_sender(
                        request.original_message.sender_id, user_role,
                        self.user_manager if self.rbac_enabled else None,
                    )
                else:
                    # No original_message on this request (should not happen
                    # in production - defensive fallback only) - fall back to
                    # the previous, RBAC-resolved behavior rather than error.
                    literal_sender_phone = user_obj.phone if user_obj else (sender or effective_chat_id)
                    literal_sender_role = user_obj.role if user_obj else user_role
            result = execute_reminder_action(
                self.reminder_manager, pending.tool_name, args,
                created_by_phone=literal_sender_phone,
                created_by_role=literal_sender_role,
                delivery_chat_id=effective_chat_id,
            )
        except (ReminderPastDateError, ReminderCapExceededError, ReminderNotFoundError,
                InvalidRecurrenceError, OccurrenceNotFoundError) as e:
            logger.error(
                f"[054] Approved reminder action failed at persist time for chat="
                f"{effective_chat_id!r}, tool={pending.tool_name!r}: {e}", exc_info=True
            )
            self.pending_local_tool_approval_manager.clear(effective_chat_id)
            return self._fallback_response_for(
                request, effective_chat_id, user_obj, user_role, sender, user_phone,
                sender_phone, is_group, chat_name, REMINDER_ACTION_FAILED_TRY_AGAIN)

        self.pending_local_tool_approval_manager.clear(effective_chat_id)
        logger.info(f"[054] Approved and cleared pending local-tool approval for chat={effective_chat_id!r}")

        try:
            # Feature 084 fix (2026-09-12): _assemble_tools already includes
            # react_to_message unconditionally regardless of RBAC (see its own
            # docstring) - same call as the main turn path (single_turn) uses,
            # so this follow-up call is no longer sent with an empty tool list.
            followup_tools = self._assemble_tools(user_obj, request.request_id)
            followup = self._call_openai_reminder_followup_api(request, pending, result, tools=followup_tools)
            # Feature 084 fix (2026-09-12, same finding as above): now that
            # react_to_message is actually attached here, the model may spend
            # this ENTIRE response on that function_call alone (a real, correct
            # resolution reaction - ✅ on the reminder that just got created),
            # leaving output_text empty even though nothing failed. That's the
            # same "function_call OR message" reasoning-model shape every other
            # local-tool call site already handles.
            # Bugfix (2026-09-13): this used to loop _handle_react_to_message
            # alone, which only resolves react_to_message's own calls - any
            # OTHER tool type (query_ledger_events, list_reminders,
            # send_progress_update) co-occurring in the same response would be
            # left unaddressed and OpenAI would reject the follow-up outright
            # (the same production incident _dispatch_all_local_tools' docstring
            # describes). Every immediate-dispatch tool type can plausibly show
            # up here too, so this goes through the same combined dispatcher,
            # capped the same way _run_local_tool_dispatch_loop caps its own loop.
            tokens_used = followup.usage.total_tokens
            prompt_tokens = followup.usage.input_tokens
            completion_tokens = followup.usage.output_tokens
            for _round in range(MAX_LOCAL_TOOL_LOOP_ITERATIONS):
                local_tools_followup = self._dispatch_all_local_tools(
                    request, followup, followup_tools, effective_chat_id,
                )
                if local_tools_followup is None:
                    break
                followup = local_tools_followup
                tokens_used += followup.usage.total_tokens
                prompt_tokens += followup.usage.input_tokens
                completion_tokens += followup.usage.output_tokens
            response_text = followup.output_text
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

        # Nothing to store here: the reply is stored when it's sent (2026-09-30).

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
        ai_response = self.fit_for_whatsapp(ai_response)
        return ai_response

    def record_sent_message_id(self, chat_id: str, message_id: str) -> None:
        """Binds a just-sent approval-buttons message to whichever pending approval
        this chat has (Feature 047/054): a pending approval is EITHER an MCP one or a
        local-tool one (e.g. create/modify/delete reminder) - never both for the same
        chat. attach_sent_message_id() is a documented no-op (logged, never raises) on
        whichever manager has nothing pending, so calling both is safe."""
        self.pending_approval_manager.attach_sent_message_id(chat_id, message_id)
        self.pending_local_tool_approval_manager.attach_sent_message_id(chat_id, message_id)

    def extraction_prompt_prefix(self) -> str:
        """The media extractors prepend the runtime constitution to their own
        extraction prompt on the legacy path."""
        return self._load_constitution()

    def resolve_button_tap(
        self, message: WhatsAppMessage, selected_id: str, stanza_id: str, *,
        user_role: Optional[str] = None,
    ) -> Optional[AIResponse]:
        """
        Feature 047: resolves a WhatsApp interactive-button tap against
        message.chat_id's pending approval (Feature 022), if the tap's
        stanza_id matches the message it was actually sent as
        (contracts/pending-approval-message-binding.md).

        Deliberately does NOT reimplement approve/decline resolution: once the
        stanza_id match below confirms this tap is live (not stale/superseded -
        the one check `single_turn`/`_resolve_pending_approval` has no concept of,
        since neither knows about individual WhatsApp message ids), this
        synthesizes a plain "כן"/"לא" `AIRequest` and delegates to the existing
        `single_turn`/`_resolve_pending_approval` pipeline verbatim - same
        duplicate-execution guards, same decline behavior (falls through to a
        fresh turn, exactly like a genuine typed "לא" does today - a button
        decline is byte-for-byte the same experience as a typed one, per US2's
        non-interference requirement).

        Takes the whole `message` (2026-08-19, user decision), not individual
        scalar fields pulled out of it by the caller - `chat_id`/`message_id`/
        `sender_id`/`sender_display_name`/`is_group`/`chat_name` all come from
        it directly (including the `is_group`/`chat_name`/`sender_phone` fields
        Feature 043's merge added to `single_turn`'s own signature - derived
        here from `message` rather than accepted as yet more threaded params),
        and AIRequest.original_message carries the same object further
        downstream (e.g. into a reminder's created_by_phone) without yet
        another parameter threaded through
        single_turn/_resolve_pending_local_tool_approval.

        Returns:
            None if there's no pending approval, or its sent_message_id doesn't
            equal stanza_id (stale/superseded tap) - per spec.md Clarifications,
            the caller must send nothing observable at all in this case. A real
            AIResponse otherwise.
        """
        # The legacy tap resolves the role itself.
        del user_role
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
        # deterministic order as single_turn's dual-check dispatch - at most
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
        return self.single_turn(
            synthetic_request, chat_id=chat_id, user_role=user_obj.role,
            sender=sender, recipient=None, user_phone=user_phone,
            is_group=message.is_group, chat_name=message.chat_name,
            sender_phone=message.sender_id,
        )

    def _fallback_response_for(self, request: AIRequest, effective_chat_id: Optional[str],
                              user_obj, user_role: str, sender: Optional[str],
                              user_phone: Optional[str], sender_phone: Optional[str],
                              is_group: bool, chat_name: Optional[str],
                              message: str) -> AIResponse:
        """Builds the fallback AIResponse for an error the user is about to be told about.
        2026-09-30: nothing to store here any more - the user's message was stored on receipt
        and the fallback text is stored when it's actually sent."""
        del effective_chat_id, user_obj, user_role, sender, user_phone, sender_phone
        del is_group, chat_name
        return self._create_fallback_response(request.request_id, message)

    def _create_fallback_response(self, request_id: str, message: str) -> AIResponse:
        """2026-09-30 consolidation: delegates to AIManager.build_fallback_response,
        the one shared implementation also used by Backbone._create_fallback_response
        - the two were byte-identical AIResponse shapes before this change."""
        return AIManager.build_fallback_response(request_id, message)
