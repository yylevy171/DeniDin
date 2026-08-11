"""
AIHandler - Handles OpenAI API interactions with retry logic and error handling
Phase 5: US3 - Error Handling & Resilience
Phase 5 (002+007): Memory system integration
Phase 6: RBAC (Role-Based Access Control)
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast, Optional, List, Dict

from openai import OpenAI, APITimeoutError, RateLimitError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type
)
from src.models.config import AppConfiguration
from src.models.message import (
    WhatsAppMessage, AIRequest, AIResponse,
    NO_REPLY_SENTINEL as _NO_REPLY_SENTINEL,
)
from src.utils.logger import get_logger, read_version, DEFAULT_VERSION_FILE
from src.utils.time_utils import now_local
from src.managers.session_manager import SessionManager, Session
from src.managers.memory_manager import MemoryManager
from src.managers.ledger_event_manager import LedgerEventManager, is_incomplete_capture
from src.managers.user_manager import UserManager
from src.managers.pending_approval_manager import PendingApprovalManager, PendingApproval
from src.models.user import Role
from src.handlers.morning_mcp_locator import MorningMcpLocator
from src.constants.error_messages import (
    APPROVAL_FAILED_TRY_AGAIN, APPROVAL_POSSIBLY_DUPLICATED, LEDGER_FOLLOWUP_FAILED_TRY_AGAIN
)

logger = get_logger(__name__)

# Roles authorized to have the Morning MCP invoicing tools attached (Feature 018)
MORNING_MCP_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

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
# now dispatches directly to create_receipt/close_transaction_account/
# create_credit_note instead, which are already covered here.
# close_transaction_account (feature 023) creates a real Morning document
# the same way - gated for the same reason. add_client/update_client
# (feature 026) are real, persisted client-record writes - same category.
APPROVAL_REQUIRED_MCP_TOOLS = (
    "create_invoice",
    "create_transaction_account",
    "create_combo_document",
    "create_credit_note",
    "create_receipt",
    "close_transaction_account",
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

    Never includes `original_invoice_id` (a raw internal UUID) - the
    constitution's "never ask for or mention invoice_id" rule applies here
    too, so create_credit_note/create_receipt/close_transaction_account
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
        if tool_name == "close_transaction_account":
            return f"לסגור את חשבון העסקה שזוהה בשיחה{_amount_suffix()} — לאשר?"
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
    "close_transaction_account": "חשבונית מס/קבלה (סגירת חשבון עסקה)",
}

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


def _build_pending_approval_details(tool_name: str, arguments_json: str) -> str:
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

    Never raises: it runs on the response-handling hot path.
    """
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except (json.JSONDecodeError, TypeError):
        args = {}
    if not isinstance(args, dict):
        args = {}

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

    return "\n".join(lines) + f"\n\n{APPROVAL_QUESTION}"


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
        "the same agreement."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "source_type": {
                "type": "string",
                "enum": ["הסכם", "בנק"],
                "description": "הסכם for a fee-agreement event, בנק for a bank deposit/transfer.",
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
                "enum": ["יצירה", "הפקדה"],
                "description": (
                    "For source_type=הסכם: always יצירה (a correction/cancellation/"
                    "payment-confirmation for an existing arrangement is still captured "
                    "as יצירה, describing the current state - see the constitution). "
                    "For source_type=בנק: always הפקדה. Applies to the whole call - "
                    "every component shares the same subtype."
                ),
            },
            "client_name": {"type": ["string", "null"], "description": "The client's name, verbatim."},
            "payer_name": {
                "type": ["string", "null"],
                "description": (
                    "The paying entity, ONLY if different from client_name (e.g. an "
                    "insurer/union routing payment). Watch specifically for 'דרך X' / "
                    "'באמצעות X' / 'via X' / 'through X' near a client's name (often its "
                    "own line right after the client name) - a strong, common signal "
                    "that X is the payer, not part of agreement_label/description."
                ),
            },
            "agreement_label": {
                "type": ["string", "null"],
                "description": (
                    "Short human-readable Hebrew label for the matter/agreement as a whole "
                    "(e.g. 'ערעור לארצי', 'תביעת נזיקין נגד מדינה') - a few words, not a full "
                    "sentence. Required (non-null) for source_type=הסכם; always null for בנק."
                ),
            },
            "replaces_hint": {
                "type": ["string", "null"],
                "description": "Free-text description of a prior arrangement this corrects/cancels, ONLY if identifiable from this conversation - never a guess.",
            },
            "reference_hint": {
                "type": ["string", "null"],
                "description": "Free-text loose reference to a related (not replaced) prior matter, if any.",
            },
            "raw_message_excerpt": {
                "type": "string",
                "description": "Verbatim source text (or a precise description of the image) this capture is based on - the hard pointer for later verification.",
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
                        "description": {"type": ["string", "null"], "description": "The matter/engagement for this component, verbatim or closely paraphrased."},
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
                        "notes": {"type": ["string", "null"], "description": "Any ambiguity or uncertainty about THIS component worth flagging for the human reviewer, including how it relates to other components (e.g. additive vs. alternative)."},
                    },
                    "required": [
                        "component_label", "description", "amount", "percent", "percent_base",
                        "hours", "hourly_rate", "txn_date", "vat_status", "notes",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "source_type", "event_subtype", "client_name", "payer_name", "agreement_label",
            "replaces_hint", "reference_hint", "raw_message_excerpt", "component_count",
            "components",
        ],
        "additionalProperties": False,
    },
}


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
            storage_dir=str(Path(config.data_root) / "events")
        )

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
            timestamp=message.timestamp
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

    @staticmethod
    def _build_ledger_event_tool() -> List[Dict]:
        """The Ledger Event Recognition tool (runtime_constitution.md) - a local
        function tool, always attached in the text path (no RBAC/role restriction,
        unlike the Morning MCP tools; no remote server, unlike them either)."""
        return [LEDGER_EVENT_TOOL]

    def _assemble_tools(self, user_obj, correlation_id: str) -> Optional[List[Dict]]:
        """Merge the (RBAC-gated) Morning MCP tools with the (always-on) ledger-event
        tool into one `tools` list - both can be attached in the same turn. Returns
        None (not an empty list) when nothing applies, matching the Responses API's
        own convention for "no tools this call"."""
        morning_tools = self._build_morning_mcp_tools(user_obj, correlation_id) if self.rbac_enabled else None
        combined = (morning_tools or []) + self._build_ledger_event_tool()
        return combined or None

    def _build_instructions(self, constitution: str) -> str:
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
        """
        # Give the model the actual current date. It has no clock of its own —
        # its training cutoff makes it default to a stale "current year", which
        # produced real wrong-year invoice lookups (e.g. resolving "7 בפברואר"
        # to 2023). This is appended at reply time, computed per call in UTC
        # (CONSTITUTION §II) — NOT templated into the constitution file.
        today = now_local().strftime("%Y-%m-%d")
        return (
            f"{constitution}\n\n---\n"
            f"THE CURRENT DATE IS {today} (UTC). Treat this as the authoritative "
            f"\"today\" when resolving any relative or partial date the user gives "
            f"(a day/month with no year, \"היום\", \"אתמול\", etc.) — never fall "
            f"back on a year from your training data.\n"
            f"YOUR CURRENT VERSION IS {self._app_version}. If asked what version you are "
            f"running (in any language), state this exact value."
        )

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        stop=stop_after_attempt(2),  # Initial attempt + 1 retry = 2 total
        wait=wait_fixed(1),  # 1 second wait between retries
        reraise=True
    )
    def _call_openai_api(self, request: AIRequest, conversation_history: Optional[List[Dict]] = None,
                         tools: Optional[List[Dict]] = None):
        """
        Make the actual OpenAI Responses API call with retry logic.
        Retries ONCE (max 2 attempts) on transient failures, waits 1 second.

        Args:
            request: AI request to send
            conversation_history: Optional conversation history to include
            tools: Optional Responses API `tools` list (e.g. Morning MCP server)

        Returns:
            OpenAI Responses API response

        Raises:
            RateLimitError: After 2 attempts (1 retry)
            APITimeoutError: After 2 attempts (1 retry)
            APIError: After 2 attempts (1 retry)
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
            "instructions": self._build_instructions(request.constitution),
            "input": input_items,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        # kwargs is built dynamically (tools conditionally added) so its inferred
        # type (dict[str, object]) never lines up with any single overload of the
        # SDK's heavily-overloaded create() - safe to ignore, the actual value
        # types are correct for the Responses API.
        response = self.client.responses.create(**kwargs)  # type: ignore[call-overload]

        return response

    def get_response(self, request: AIRequest, chat_id: Optional[str] = None,
                     user_role: str = 'client', sender: Optional[str] = None,
                     recipient: Optional[str] = None, user_phone: Optional[str] = None) -> AIResponse:
        """
        Get AI response for a request with error handling and fallbacks.
        Includes memory system integration for session storage.

        Args:
            request: AI request to process
            chat_id: Optional chat ID for session management (uses request.chat_id if not provided)
            user_role: User role for token limits ('client' or 'godfather') - DEPRECATED when RBAC enabled
            sender: WhatsApp sender ID for message storage
            recipient: WhatsApp recipient ID for message storage
            user_phone: User's phone number for RBAC (uses sender if not provided)

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
                pending, request, effective_chat_id, user_obj, user_role, sender, recipient
            )
            logger.info(
                f"[022] _resolve_pending_approval returned "
                f"{'an AIResponse (approved)' if resolved is not None else 'None (declined - falling through to a normal turn)'}"
            )
            if resolved is not None:
                return resolved
        else:
            logger.info(f"[022] No pending approval for chat={effective_chat_id!r} - normal turn processing")

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
                request, response, effective_chat_id, user_obj, user_role, sender, recipient, tools
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

    def _handle_ledger_event_capture(self, request: AIRequest, response, effective_chat_id: Optional[str],
                                     sender: Optional[str], tools: Optional[List[Dict]]):
        """
        Ledger Event Recognition (runtime_constitution.md) - a real OpenAI function call.
        Reasoning models emit `function_call`(s) OR a final `message` in one turn, never
        both, so response_text is always empty on the turn that calls this tool - a real
        second round-trip (previous_response_id + function_call_output, same pattern as
        `_call_openai_approval_api`) is required to get the model's actual reply, which
        also lets it confirm the captured fields back to the user (Feature 024).

        (Revised bugfix-018, 2026-08-04) runtime_constitution.md's Ledger Event
        Recognition (Step 4) instructs the model to call capture_ledger_event AT
        MOST ONCE per message, covering every genuinely distinct component of
        that message's event in that one call's `components` array (REQ-DATA-004,
        2026-07-30) - there is no longer a legitimate case where more than one
        call in a single turn is correct (an earlier version of this docstring
        claimed "two genuinely unrelated clients" was a valid multi-call case;
        the constitution never actually carved out that exception, and nothing
        in the code enforced it, which is exactly what let a real, unrelated
        model malfunction reach this code unchecked - see below). More than one
        call in a turn is always treated as a PROTOCOL VIOLATION: none of the
        calls are trusted, not even a well-formed one, and nothing is persisted.
        A single call whose `arguments` failed to parse (see
        `extract_all_function_calls`) is treated the same way - rejected, not
        salvaged or guessed at.

        Root cause of the real incident this guards against (2026-07-30,
        req_0f4656c9bd90): the model emitted 17 near-identical
        capture_ledger_event calls in one turn for a message that needed zero.
        That many large-schema parallel calls exceeded max_output_tokens
        mid-generation - OpenAI's Responses API does not error in that case, it
        returns HTTP 200 with response.status="incomplete"/
        incomplete_details.reason="max_output_tokens" and includes whatever was
        mid-generation at the cutoff, including a function_call whose
        `arguments` string is simply truncated (unterminated JSON, not
        semantically corrupt). The old code silently dropped that one
        unparseable call from the follow-up submission - but OpenAI still
        considered its call_id pending (it WAS emitted, just not finished), so
        the follow-up was rejected with 400 ("No tool output found for function
        call ..."), and with no fallback text, the user got a silently empty
        WhatsApp reply despite billed tokens. Every call_id from the original
        turn - rejected or not - must always get a `function_call_output` in
        the follow-up, or OpenAI rejects the whole thing.

        Every REAL capture (single call, well-formed) is persisted regardless
        of the follow-up's outcome - a structured capture must never be lost
        even if the confirmation reply fails.

        Returns (followup, event_ids): followup is the follow-up response (whose
        output_text/usage should replace the original response's) if at least one
        ledger event was captured and the round-trip succeeded, else None (nothing
        to capture, or the round-trip failed). event_ids is the list of new
        LedgerEvent ids actually persisted this turn (Feature 033), in call order -
        empty when suppressed or nothing captured - for the caller to thread into
        the source message's Message.ledger_event_ids (REQ-TRACE-003).

        Suppressed when Morning MCP was the data source this turn (2026-07-28): a
        real godfather "list all my invoices" turn had the model reading its own
        list_invoices tool output back and mistaking existing Morning documents for
        new fee-agreement text, calling capture_ledger_event on data that already
        lives in Morning - then losing its own final reply entirely when the
        follow-up round-trip called the tool again instead of answering (it still
        had capture_ledger_event available). Morning-sourced documents ARE a real,
        distinct ledger-event source in principle (list_invoices/get_invoice_details
        can surface documents created outside DeniDin entirely) but capturing them
        properly is a separate, not-yet-built feature - see
        specs/backlog/025-morning-sourced-ledger-events. Until then: don't persist,
        and don't let the follow-up call capture_ledger_event again either (strip it
        from that round's tools) so the model is forced to finally produce its text
        reply instead of repeating the same mistake.

        (Revised 2026-08-02, real billed incident - user directive: "Morning events
        should NOT trigger ledger events at all") The detection MUST also catch
        `mcp_approval_request` items, not just `mcp_call` - an approval-required
        Morning tool (create_combo_document, add_client, etc., Feature 022's
        APPROVAL_REQUIRED_MCP_TOOLS) shows up as `mcp_approval_request` on the turn
        that proposes it, never `mcp_call`, since nothing has executed yet. Checking
        `mcp_call` alone missed this entirely: a real run had a two-word field-filling
        reply ("עבור ייעוץ") sent mid-approval-flow for create_combo_document
        misclassified as TWO spurious `capture_ledger_event` calls, entangled with
        (and breaking) the pending-approval round-trip itself (empty bot reply, the
        next "כן" no longer resolved as an approval).
        """
        ledger_calls = extract_all_function_calls(response, LEDGER_EVENT_TOOL["name"])
        if not ledger_calls:
            return None, []

        morning_mcp_used_this_turn = any(
            getattr(item, "type", None) in ("mcp_call", "mcp_approval_request")
            for item in (getattr(response, "output", None) or [])
        )

        # bugfix-018: more than one call in a turn is always a protocol
        # violation (runtime_constitution.md Step 4 - "at most once per
        # message"); a single call whose arguments didn't parse is equally
        # untrustworthy. Either way, nothing is persisted and every call_id
        # gets an explicit rejection rather than being silently dropped or
        # guessed at.
        protocol_violation = len(ledger_calls) > 1
        single_call_unparseable = len(ledger_calls) == 1 and ledger_calls[0]["arguments"] is None
        rejected = protocol_violation or single_call_unparseable

        followup = None
        resolvable_calls = [c for c in ledger_calls if c["call_id"] is not None]
        if resolvable_calls:
            followup_tools = tools
            if morning_mcp_used_this_turn:
                followup_tools = [
                    t for t in (tools or []) if t.get("name") != LEDGER_EVENT_TOOL["name"]
                ] or None
            rejection_reason = None
            if protocol_violation:
                rejection_reason = (
                    f"You called capture_ledger_event {len(ledger_calls)} times in this "
                    "turn. The rules require calling it at most once per message, "
                    "covering every genuinely distinct component of that message's "
                    "event in that one call. All calls from this turn are discarded - "
                    "nothing was captured. Do not repeat this."
                )
            elif single_call_unparseable:
                rejection_reason = (
                    "Your capture_ledger_event call's arguments could not be parsed as "
                    "valid JSON (most likely truncated mid-generation). This call is "
                    "discarded - nothing was captured. Do not resubmit it in this form."
                )
            try:
                followup = self._call_openai_ledger_followup_api(
                    request, response.id, resolvable_calls, followup_tools,
                    suppressed=morning_mcp_used_this_turn,
                    rejection_reason=rejection_reason,
                )
            except Exception as e:
                logger.error(
                    f"Ledger-event follow-up call failed for request {request.request_id}: {e}",
                    exc_info=True
                )
        if len(resolvable_calls) < len(ledger_calls):
            logger.warning(
                f"{len(ledger_calls) - len(resolvable_calls)} ledger-event function_call(s) "
                f"had no call_id for request {request.request_id} - skipped in follow-up round-trip"
            )

        event_ids: List[str] = []
        if morning_mcp_used_this_turn:
            logger.info(
                f"[024] Suppressing {len(ledger_calls)} ledger-event capture(s) for request "
                f"{request.request_id} - Morning MCP was this turn's data source, not yet a "
                f"supported ledger-event source (specs/backlog/025-morning-sourced-ledger-events)"
            )
        elif rejected:
            logger.warning(
                f"[bugfix-018] Rejecting {len(ledger_calls)} capture_ledger_event call(s) "
                f"for request {request.request_id} - "
                f"{'more than one call in a single turn' if protocol_violation else 'unparseable arguments (likely truncated)'} "
                "violates the at-most-once-per-message rule; nothing persisted"
            )
        elif self.ledger_event_manager and effective_chat_id:
            session = self.session_manager.get_session(effective_chat_id)
            # Exactly one well-formed call reaches here (protocol_violation/
            # single_call_unparseable above already filtered out every other
            # case) - add_ledger_events_from_call owns the flatten +
            # agreement_id + persist-each-component logic for that one call's
            # `components` array (REQ-DATA-004, 2026-07-30).
            for call in ledger_calls:
                try:
                    new_event_ids = self.ledger_event_manager.add_ledger_events_from_call(
                        session_id=session.session_id,
                        whatsapp_chat=effective_chat_id,
                        call_arguments=call["arguments"],
                        message_id=request.message_id,
                        message_timestamp=request.timestamp,
                        sender=sender or effective_chat_id,
                    )
                    event_ids.extend(new_event_ids)
                except Exception as e:
                    logger.error(f"Failed to persist ledger event(s): {e}", exc_info=True)

        return followup, event_ids

    def _finalize_response(self, request: AIRequest, response, effective_chat_id: Optional[str],
                           user_obj, user_role: str, sender: Optional[str],
                           recipient: Optional[str], tools: Optional[List[Dict]]) -> AIResponse:
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

        followup, ledger_event_ids = self._handle_ledger_event_capture(
            request, response, effective_chat_id, sender, tools
        )
        if followup is not None:
            response_text = followup.output_text
            tokens_used += followup.usage.total_tokens
            prompt_tokens += followup.usage.input_tokens
            completion_tokens += followup.usage.output_tokens
            usage_response = followup
        elif not response_text.strip() and any(
            getattr(item, "type", None) == "function_call"
            and getattr(item, "name", None) == LEDGER_EVENT_TOOL["name"]
            for item in (response.output or [])
        ):
            # bugfix-018 safety net: this turn called capture_ledger_event (so
            # output_text was always going to be empty - see
            # _handle_ledger_event_capture's docstring), but the follow-up
            # round-trip that produces the real reply never came back
            # (rejected/failed/errored). Never leave the user with a silently
            # empty WhatsApp message just because that second call didn't
            # succeed - same pattern as the pending-approval fallback below.
            response_text = LEDGER_FOLLOWUP_FAILED_TRY_AGAIN
            logger.warning(
                f"Ledger-event follow-up did not produce a reply for request "
                f"{request.request_id} - using generic fallback text so the user "
                "never receives a silently empty reply."
            )

        logger.info(
            f"[022] _finalize_response: response.id={getattr(response, 'id', None)!r}, "
            f"effective_chat_id={effective_chat_id!r}, "
            f"output item types={[getattr(i, 'type', None) for i in (response.output or [])]!r}, "
            f"output_text={response_text!r}"
        )

        # Extract Morning MCP tool calls, if any (REQ-SEC-002 audit logging;
        # also lets E2E tests verify tool usage without a second AI call).
        # Includes arguments/output for diagnosability (e.g. confirming
        # which invoice_id the model actually passed to a follow-up tool
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
            f"[022] approval_requests found in response.output: {len(approval_requests)} "
            f"(effective_chat_id={effective_chat_id!r})"
        )
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
            details = _build_pending_approval_details(ar.name, ar.arguments)
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
                # RBAC: Use token limit enforcement if enabled
                # Feature 039: SessionManager.add_message* always forces recipient=None
                # for role="user" and sender=None for role="assistant" (redundant with
                # role, which already distinguishes them) - the "AI" sentinel is retired,
                # so it's no longer passed here. `sender` (the resolved display name,
                # threaded in from the caller) becomes the user message's sender and the
                # assistant reply's recipient - who said it, and who it was for.
                if self.rbac_enabled and user_obj:
                    # Store user message with token limit
                    self.session_manager.add_message_with_token_limit(
                        chat_id=effective_chat_id,
                        role="user",
                        content=request.user_prompt,
                        user_role=user_obj.role,
                        token_limit=user_obj.token_limit,
                        sender=sender or effective_chat_id,
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
                            recipient=sender or effective_chat_id
                        )
                else:
                    # Existing behavior: regular add_message without token limits
                    self.session_manager.add_message(
                        chat_id=effective_chat_id,
                        role="user",
                        content=request.user_prompt,
                        user_role=user_role or "client",
                        sender=sender or effective_chat_id,
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
                            recipient=sender or effective_chat_id  # Reply goes to original sender
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
            mcp_calls=mcp_calls
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

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        reraise=True
    )
    def _call_openai_ledger_followup_api(self, request: AIRequest, previous_response_id: str,
                                         ledger_calls: List[Dict],
                                         tools: Optional[List[Dict]] = None,
                                         suppressed: bool = False,
                                         rejection_reason: Optional[str] = None):
        """
        Report EVERY captured ledger event's fields back as its own `capture_ledger_event`
        function's result, via a follow-up Responses API call chained to the original
        call with `previous_response_id` (same pattern as `_call_openai_approval_api`).

        Reasoning models emit `function_call`(s) OR a final `message` in one turn, never
        both (confirmed against OpenAI's own reasoning + function-calling guidance) - so
        the turn that calls `capture_ledger_event` always leaves `output_text` empty.
        This second turn is what actually produces the user-facing reply, and is told
        the captured fields so it can confirm what it recorded (Feature 024).

        ledger_calls: list of {"arguments": dict, "call_id": str} - ALL capture_ledger_event
        calls from the previous turn, not just one. OpenAI rejects the follow-up outright
        if any pending function call from that turn is left without a resolved output, so
        this must supply one `function_call_output` item per call, in the same request -
        including any call being rejected below, never just omitted.

        suppressed: True when Morning MCP was this turn's data source (see
        _handle_ledger_event_capture's docstring) - reports "not_captured" instead of
        "captured" so the model doesn't believe something was recorded, and `tools`
        should already have capture_ledger_event stripped out by the caller so it
        can't just call it again instead of finally answering.

        rejection_reason: bugfix-018 - set when the whole turn's call(s) are being
        rejected as a protocol violation (more than one call in a turn, or a single
        call whose arguments didn't parse - see _handle_ledger_event_capture). Every
        call_id gets this exact "rejected" status/reason, deliberately blunt: these
        calls are never partially honored or guessed at, so the model must not
        believe anything was captured. Mutually exclusive with `suppressed` (the
        caller never sets both).
        """
        if rejection_reason is not None:
            output_payload = {"status": "rejected", "reason": rejection_reason}
        elif suppressed:
            output_payload = {
                "status": "not_captured",
                "reason": "This data comes from Morning (already tracked there), not a new ledger event.",
            }
        else:
            output_payload = None  # per-call "captured" payload, built below

        output_items = [
            {
                "type": "function_call_output",
                "call_id": call["call_id"],
                "output": json.dumps(
                    output_payload if output_payload is not None
                    else {"status": "captured", **call["arguments"]},
                    ensure_ascii=False,
                ),
            }
            for call in ledger_calls
        ]
        kwargs = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution),
            "input": output_items,
            "previous_response_id": previous_response_id,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        call_ids = [call["call_id"] for call in ledger_calls]
        logger.info(f"[024] _call_openai_ledger_followup_api: call_ids={call_ids!r}")
        # See _call_openai_api's comment: dynamically-built kwargs never match a
        # single create() overload.
        response = self.client.responses.create(**kwargs)  # type: ignore[call-overload]
        logger.info(
            f"[024] _call_openai_ledger_followup_api response: id={getattr(response, 'id', None)!r}, "
            f"output item types={[getattr(i, 'type', None) for i in (response.output or [])]!r}, "
            f"output_text={response.output_text!r}"
        )
        return response

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        reraise=True
    )
    def capture_ledger_events_from_text(self, text: str) -> List[Dict]:
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
        no further round-trip (unlike `_call_openai_ledger_followup_api`) is needed.

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
        """
        if not text:
            return []

        constitution = self._load_constitution()
        kwargs = {
            "model": self.config.ai_model,
            "instructions": self._build_instructions(constitution),
            "input": [{"role": "user", "content": text}],
            "tools": [LEDGER_EVENT_TOOL],
            "max_output_tokens": self.config.ai_reply_max_tokens,
        }

        logger.info("[024] capture_ledger_events_from_text: classifying extracted image text")
        # See _call_openai_api's comment: dynamically-built kwargs never match a
        # single create() overload.
        response = self.client.responses.create(**kwargs)  # type: ignore[call-overload]
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
            response = self.client.responses.create(**retry_kwargs)  # type: ignore[call-overload]
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
        kwargs = {
            "model": request.model,
            "instructions": self._build_instructions(request.constitution),
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
        # never retry itself. This method is also deliberately NOT wrapped in
        # the @retry(...) tenacity decorator used elsewhere in this file - a
        # bugfix-022 incident recurred even with max_retries=0 because that
        # decorator was still transparently retrying this whole method (a
        # second real API call) on RateLimitError/APITimeoutError/APIError.
        # No retry of this call is ever safe, at any layer.
        response = self.client.with_options(max_retries=0).responses.create(**kwargs)  # type: ignore[call-overload]
        logger.info(
            f"[022] _call_openai_approval_api response: id={getattr(response, 'id', None)!r}, "
            f"output item types={[getattr(i, 'type', None) for i in (response.output or [])]!r}, "
            f"output_text={response.output_text!r}"
        )
        return response

    def _resolve_pending_approval(self, pending: PendingApproval, request: AIRequest,
                                  effective_chat_id: str, user_obj, user_role: str,
                                  sender: Optional[str], recipient: Optional[str]) -> Optional[AIResponse]:
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
                request, response, effective_chat_id, user_obj, user_role, sender, recipient, tools
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
