"""
Ledger-event tool schemas (Feature 069, Feature 067 no-turn redesign): `capture_ledger_event`
(the Morning reconciliation sweep's tool), `report_ledger_recognition` (what the model calls
from inside the fee-agreement / deposit flows, see cap_ledger_capture) and the media "ledger
stash" text. There is no post-reply recognition step any more: the model reports an event
when it is complete, and the app records Morning documents itself.
"""
import copy
from typing import Any, Dict, List, Optional

from src.models.user import Role
from src.utils.logger import get_logger

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
                "enum": ["הסכם", "הפקדה", "חשבונית"],
                "description": (
                    "הסכם for a fee-agreement event, הפקדה for ANY incoming-funds event "
                    "(a bank transfer, a Bit or PayBox payment, a cheque, or cash - the "
                    "method goes in event_subtype), "
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
                "enum": ["יצירה", "בנק", "ביט", "פייבוקס", "צ׳ק", "מזומן", "הפקה"],
                "description": (
                    "For source_type=הסכם: always יצירה (a correction/cancellation/"
                    "payment-confirmation for an existing arrangement is still captured "
                    "as יצירה, describing the current state - see the constitution). "
                    "For source_type=הפקדה: the METHOD the money arrived by - בנק (bank "
                    "transfer/deposit), ביט, פייבוקס, צ׳ק (cheque) or מזומן (cash). For "
                    "source_type=חשבונית: pass "
                    "הפקה as a placeholder - it is IGNORED and overwritten by code with "
                    "the document's real Morning type (e.g. חשבונית מס, חשבונית זיכוי, "
                    "קבלה), read from the accounting_document_json payload. Applies to "
                    "the whole call - every component shares the same subtype."
                ),
            },
            "client_name": {
                "type": ["string", "null"],
                "description": (
                    "The client's name, verbatim. For source_type=הפקדה, this is the "
                    "depositor/account-holder (or Bit/PayBox payer, or cheque drawer) name shown on the "
                    "confirmation or screenshot ('שם חשבון מחויב' or the 'העברה מ-X' line) - "
                    "always put it here, never in payer_name, which does not apply to הפקדה "
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
                    "ALWAYS null for source_type=הפקדה - a bank deposit's account-holder name "
                    "goes in client_name, never here; there is no payer/client distinction "
                    "for a הפקדה event."
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
                    "anywhere. Required (non-null) for source_type=הסכם; always null for הפקדה. "
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
                    "The bank's NUMBER (e.g. '31'), never its name - only for source_type=הפקדה, "
                    "always null for הסכם. A deposit screenshot's extracted text gives you the "
                    "number, not a name - never guess or invent a bank name to fill this in. "
                    "Null if the screenshot doesn't state it clearly."
                ),
            },
            "bank_branch": {
                "type": ["string", "null"],
                "description": "The bank branch number, only for source_type=הפקדה, always null for הסכם.",
            },
            "bank_account": {
                "type": ["string", "null"],
                "description": "The bank account number, only for source_type=הפקדה, always null for הסכם.",
            },
            "check_number": {
                "type": ["string", "null"],
                "description": (
                    "The cheque's own number (מספר צ'ק), only for source_type=הפקדה with "
                    "event_subtype=צ׳ק; null for every other event."
                ),
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
                    "this JSON by code. ALWAYS null for הסכם/הפקדה."
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
                                "source_type=הסכם; always null for הפקדה."
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
                                "instructions. (2) for a source_type=הפקדה component - OPTIONAL "
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
                                "ש...') - only for source_type=הסכם, always null for הפקדה and "
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
            "reference_hint", "bank_number", "bank_branch", "bank_account", "check_number",
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
                "description": "verdict='declined' only: הסכם or הפקדה. Null otherwise.",
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


_DEPOSIT_STASH_HEADLINE = {
    "בנק": "📸 התקבלה תמונה של אסמכתת העברה/הפקדה בנקאית.",
    "ביט": "📸 התקבלה תמונה של אישור תשלום בביט.",
    "פייבוקס": "📸 התקבלה תמונה של אישור תשלום בפייבוקס.",
    "צ׳ק": "📸 התקבלה תמונה של צ'ק.",
    "מזומן": "התקבל תשלום במזומן.",
}


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

    `source_type` ∈ {"הפקדה", "הסכם"} (a הפקדה's method is `analysis["event_subtype"]`);
    `source_medium` ∈ {"image", "document"}.
    """
    a = analysis or {}
    is_doc = source_medium == "document"
    lines: List[str] = []

    if source_type == "הפקדה":
        # A הפקדה event always carries exactly one component (component_count: 1);
        # amount and txn_date live on it, not at the top level.
        comp = (a.get("components") or [{}])[0]
        method = a.get("event_subtype") or "בנק"
        lines.append(_DEPOSIT_STASH_HEADLINE.get(method, _DEPOSIT_STASH_HEADLINE["בנק"]))
        lines.append(f"אמצעי תשלום: {_stash_val(method)}")
        lines.append(f"סכום: {_stash_val(comp.get('amount'))}")
        lines.append(f"תאריך הפקדה: {_stash_val(comp.get('txn_date'))}")
        if method in ("בנק", "צ׳ק"):
            lines.append(f"מספר בנק: {_stash_val(a.get('bank_number'))}")
            lines.append(f"מספר סניף: {_stash_val(a.get('bank_branch'))}")
            lines.append(f"מספר חשבון: {_stash_val(a.get('bank_account'))}")
        if method == "צ׳ק":
            lines.append(f"מספר צ'ק: {_stash_val(a.get('check_number'))}")
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
