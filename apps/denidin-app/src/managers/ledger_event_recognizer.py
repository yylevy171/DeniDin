"""
Ledger-event recognition (Feature 069), its own class (REQ-063-08): the post-turn
recognition call that decides whether a godfather/admin round finished a ledger-worthy
event, plus the ledger tool schemas and the media "ledger stash" text. Runs after
every turn's reply is sent, whichever AI implementation produced it - so it lives
outside both. Moved out of handlers/ai_handler.py with behavior unchanged.
"""
import copy
import functools
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from src.core.ai_manager import AIManager
from src.managers.ledger_event_manager import is_incomplete_capture
from src.managers.session_manager import Session
from src.models.user import Role
from src.tool_actions.tool_schemas import QUERY_LEDGER_EVENTS_TOOL
from src.utils.function_calls import extract_all_function_calls
from src.utils.logger import get_logger
from src.utils.time_utils import now_local, to_local
from src.utils.wire_log import audit_wire, debug_wire

logger = get_logger(__name__)

# Ledger Event Querying (Feature 044) - and the post-turn recognition, gated by the
# same predicate - are GODFATHER/ADMIN only.
LEDGER_QUERY_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)


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
                    "(the whole {...} object for that one document, as a single string) - "
                    "the background reconciliation sweep's document listing, OR the "
                    "successful create_* result from the turn the operator had you issue "
                    "the document. Do not summarise it, reorder it, translate it, drop "
                    "fields, or fill anything in yourself - every value is read out of "
                    "this JSON by code. ALWAYS null for הסכם/בנק."
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
                        "percent": {"type": ["string", "null"], "description": (
                            "A stated percentage figure for this component, if any "
                            "(e.g. success-fee percentage).")},
                        "percent_base": {"type": ["string", "null"], "description": (
                            "What this component's percent applies to, if stated.")},
                        "hours": {"type": ["string", "null"], "description": (
                            "Stated hours, for an hourly work-log component.")},
                        "hourly_rate": {"type": ["string", "null"], "description": (
                            "Stated hourly rate for this component, if any.")},
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
                                "was forwarded). Null in every other case. For a "
                                "source_type=הסכם component this means: non-null ONLY in case "
                                "(1), an hourly work-log - an agreement's own signing/"
                                "execution date ('נחתם ביום ...') is NEVER txn_date. Never a "
                                "substitute for the real message timestamp - that stays "
                                "whatever it actually is, independent of this field."
                            ),
                        },
                        "vat_status": {
                            "type": "string",
                            "enum": ["כולל", "לא כולל", "לא צוין"],
                            "description": ("VAT-inclusive, VAT-exclusive, or not stated for THIS "
                                            "component - never assumed."),
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
                                "for it to apply. A percentage success-fee (its fee is "
                                "contingent on the outcome, e.g. 'מכל סכום שייפסק') and a "
                                "per-occurrence fee ('עבור כל ישיבת הוכחות') ARE conditional - "
                                "state the clause here. A plain fixed retainer is NOT: "
                                "due-date / payment-timing wording ('לתשלום עם חתימת ההסכם', "
                                "'ישולם תוך 30 יום') is never a trigger_condition, and never "
                                "invent one the source did not state."
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
        "their email?\") is client-record maintenance, never a ledger event. "
        "verdict='none' should also set `none_reason` to a short phrase naming why "
        "(e.g. 'client unresolved - no MCP evidence', 'ordinary conversation', "
        "'missing amount') - this is logged for debugging a silently dropped event "
        "later and is never surfaced to the operator."
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
            "none_reason": {
                "type": ["string", "null"],
                "description": (
                    "verdict='none' only: a short phrase naming why this round wasn't "
                    "captured (e.g. 'client unresolved - no MCP evidence', 'ordinary "
                    "conversation', 'missing amount'). Logged for debugging a silently "
                    "dropped event later - never surfaced to the operator. Null otherwise."
                ),
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
        # A בנק event always carries exactly one component (component_count: 1);
        # amount and txn_date live on it, not at the top level.
        comp = (a.get("components") or [{}])[0]
        lines.append("📸 התקבלה תמונה של אסמכתת העברה/הפקדה בנקאית.")
        lines.append(f"פעולה: {_stash_val(a.get('event_subtype') or 'הפקדה')}")
        lines.append(f"סכום: {_stash_val(comp.get('amount'))}")
        lines.append(f"תאריך הפקדה: {_stash_val(comp.get('txn_date'))}")
        lines.append(f"מספר בנק: {_stash_val(a.get('bank_number'))}")
        lines.append(f"מספר סניף: {_stash_val(a.get('bank_branch'))}")
        lines.append(f"מספר חשבון: {_stash_val(a.get('bank_account'))}")
        lines.append(f"לקוח משלם: {_stash_val(a.get('client_name'))}")
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


class LedgerEventRecognizer:
    """The post-turn ledger recognition (Feature 069). Built by initialize_app and
    owned by DeniDin; uses DeniDin's sessions, ledger and users plus the OpenAI client."""

    def __init__(self, denidin: Any):
        """`denidin`: the DeniDin object (REQ-063-08) - its config, OpenAI client,
        sessions, ledger events and users, each read from it at use time."""
        self.denidin = denidin
        # mtime-cached config/ledger_recognition_prompt.md (see _load_recognition_prompt)
        self._recognition_prompt_content: Optional[str] = None
        self._recognition_prompt_mtime: Optional[float] = None

    @property
    def client(self) -> Any:
        return self.denidin.ai_client

    @property
    def config(self) -> Any:
        return self.denidin.config

    @property
    def session_manager(self) -> Any:
        return getattr(self.denidin, "session_manager", None)

    @property
    def ledger_event_manager(self) -> Any:
        return getattr(self.denidin, "ledger_event_manager", None)

    @property
    def user_manager(self) -> Any:
        return getattr(self.denidin, "user_manager", None)

    def recognize_after_turn(self, *, chat_id: str, sender_phone: Optional[str], reply_text: str,
                             turn_mcp_calls: Optional[List[Dict]]) -> None:
        """After a godfather/admin conversational turn's reply has been sent, run the ONE
        text-only recognition call + the zero-AI ledgerer. Gated by the same RBAC
        predicate that gates `query_ledger_events`.

        Best-effort and fully self-contained: any failure is logged and swallowed
        (FR-069-006) - the operator's reply is already out and must not change by one
        byte because ledger bookkeeping hit a problem."""
        if self.session_manager is None or self.ledger_event_manager is None:
            return
        try:
            user = self.user_manager.get_user(sender_phone) if (sender_phone and self.user_manager) else None
            if user is None or user.role not in LEDGER_QUERY_AUTHORIZED_ROLES:
                return

            session = self.session_manager.get_session(chat_id)
            if not session.message_ids:
                return
            completing_message_id = session.message_ids[-1]

            verdict = self.recognize_ledger_event(
                session=session,
                reply_text=reply_text,
                turn_mcp_calls=turn_mcp_calls or [],
            )
            self.ledger_event_manager.persist_recognized_event(verdict, session, completing_message_id)
        except Exception as exc:  # noqa: BLE001 - deliberate: never surface to the operator
            logger.error(f"[069] post-turn ledger recognition failed (swallowed): {exc}", exc_info=True)

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

        Only the last `ledger_recognition_context_window_hours` of the chat -
        measured back from the NEWEST message in the session, not wall-clock
        `now` - is included (older messages excluded). Anchoring on the newest
        message keeps the WhatsApp-export player working: its replayed messages
        carry their real (possibly weeks-old) conversation timestamps, and a
        `now - 1h` cutoff would drop the whole replayed chat. Live is
        unaffected - the newest message's timestamp is ~now.

        Each windowed line is `<message_id> [<role>] <content>`, with a
        `[✓ captured as <ids>]` marker for a message that already produced a
        ledger event, its attachment's extracted text, and the Morning MCP calls
        persisted on that message's turn (arguments + real result). The reply
        just sent and this turn's own MCP calls follow.
        """
        window_hours = float(
            getattr(self.config, "ledger_recognition_context_window_hours", 1.0) or 1.0
        )
        loaded = [
            (mid, self.session_manager.load_message(session, mid))
            for mid in session.message_ids
        ]
        loaded = [(mid, msg) for mid, msg in loaded if msg is not None]
        msg_times = [
            ts for _mid, msg in loaded
            if (ts := self._parse_message_timestamp(getattr(msg, "timestamp", None))) is not None
        ]
        if not msg_times:
            return []
        cutoff = max(msg_times) - timedelta(hours=window_hours)

        lines = [
            f"THE CONVERSATION WINDOW (the last {window_hours:g}h, oldest first) - "
            "'<message_id> [<role>] <content>':"
        ]
        excluded = 0
        for mid, msg in loaded:
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
        audit_wire("openai", "out", "recognize_ledger_event", kwargs)
        debug_wire("openai", "out", "recognize_ledger_event", kwargs)
        response = AIManager.call_model_with_retry(
            lambda: self.client.responses.create(**kwargs), context="recognize_ledger_event")
        audit_wire("openai", "in", "recognize_ledger_event", response)
        debug_wire("openai", "in", "recognize_ledger_event", response)
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
            audit_wire("openai", "out", "recognize_ledger_event (query round)", follow_kwargs)
            debug_wire("openai", "out", "recognize_ledger_event (query round)", follow_kwargs)
            response = AIManager.call_model_with_retry(
                functools.partial(self.client.responses.create, **follow_kwargs),
                context="recognize_ledger_event")
            audit_wire("openai", "in", "recognize_ledger_event (query round)", response)
            debug_wire("openai", "in", "recognize_ledger_event (query round)", response)
        # If the model produced no report call at all (only text, or it spent its
        # query budget without reporting), that is a plain `none` - not a retry case.
        if not extract_all_function_calls(response, RECOGNITION_TOOL_NAME):
            logger.info("[069] recognition verdict=none (no report_ledger_recognition call at all)")
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
            audit_wire("openai", "out", "recognize_ledger_event (retry)", retry_kwargs)
            debug_wire("openai", "out", "recognize_ledger_event (retry)", retry_kwargs)
            response = AIManager.call_model_with_retry(
            lambda: self.client.responses.create(**retry_kwargs), context="recognize_ledger_event")
            audit_wire("openai", "in", "recognize_ledger_event (retry)", response)
            debug_wire("openai", "in", "recognize_ledger_event (retry)", response)
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
            logger.info("[069] recognition verdict=none (unparseable/absent report call after retry)")
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
        logger.info(f"[069] recognition verdict=none reason={args.get('none_reason')!r}")
        return {"verdict": "none"}
