"""
Fee Agreement AI tool wiring (Feature 083).

Deliberately kept in its own module, separate from ai_handler.py (already
4,000+ lines and due its own refactor - not part of this feature per explicit
2026-09-12 user instruction: new tool-bearing logic for this feature goes
here, not inlined into ai_handler.py). This module owns everything that is
purely about the fee-agreement tools themselves - their JSON schemas, RBAC
gating, and all DocTemplateEngine-facing logic (turn-scoped GeneratedDocument
bookkeeping/cleanup). ai_handler.py wires this in via a handful of small,
additive delegating calls (mirroring how it already delegates to
ReminderManager/LedgerEventManager) - it never touches DocTemplateEngine
directly, and never grows its own copy of this logic.

2026-09-13 REDESIGN (explicit human correction - the original design below
had the code doing far too much and the AI far too little): "minimal code,
maximal AI." The AI is the actual document author, not a form-filler:

- get_fee_agreement_template: read-only, dispatches immediately. Returns a
  variant's reference body text (its current example structure/tone) so the
  AI can pattern its own writing on it - not something to fill in or reuse
  verbatim.
- render_fee_agreement_document: dispatches immediately, NO approval gate.
  Takes the AI's own, freely-composed FULL body text (any clauses, any
  numbering, everything) and drops it into the firm's fixed branded shell
  (logo/header/footer - never AI-editable). Code does not read, validate, or
  judge the content in any way.
- verify_fee_agreement_document: read-only, dispatches immediately. The only
  fact worth checking for free-composed text is whether a literal
  "{{...}}"-shaped token leaked in - the actual accept/reject judgment is
  still the model's own (REQ-083-04), not this tool's.
- send_fee_agreement_document: dispatches immediately, but refuses (as a
  tool-call error, not an exception) unless the document already passed
  verification in this same turn-scoped lifetime. No human approval tap
  anywhere in this flow (explicit human decision, 2026-09-13) - the AI's own
  self-verification is the sole gate, and revising is just calling
  render_fee_agreement_document again with edited text.
"""

from typing import Any, Dict, List, Optional

from src.managers.doc_template_engine import DocTemplateEngine
from src.models.fee_agreement import GeneratedDocument
from src.models.user import Role
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Same two roles every other local-tool family in this app RBAC-gates on
# (REMINDER_AUTHORIZED_ROLES / LEDGER_QUERY_AUTHORIZED_ROLES in ai_handler.py).
FEE_AGREEMENT_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

_VARIANT_ENUM = [
    "hourly_consultation", "multi_component_agreement", "alternative_tracks",
]

# 2026-09-14: per-variant classification guidance, inlined directly into the
# tool's own JSON schema description (not fetched via a separate call) - the
# AI must classify which of the 3 types it needs BEFORE calling
# get_fee_agreement_template, from this description alone. Kept in sync with
# manifest.json's own `selection_cues` (the human-facing/manifest source of
# truth); duplicated here in condensed form because JSON Schema enum
# descriptions can't be built per-value, only as one combined string.
_VARIANT_SELECTION_GUIDE = (
    "- hourly_consultation: a single, simple hourly-rate arrangement, "
    "optionally with an hour cap - one rate, one scope. "
    "- multi_component_agreement: 2+ distinct fee items applying TOGETHER "
    "(staged/milestone fees, a percentage/contingency bonus, an hourly "
    "add-on, a cost-share with a partner, a non-Client payer) - also covers "
    "a genuinely single flat fee for one defined scope, as ONE component. "
    "- alternative_tracks: the client is offered a CHOICE between two or "
    "more mutually-exclusive fee structures for the SAME engagement (e.g. "
    "'מסלול א/מסלול ב', 'אחד משני המסלולים') - only one is ever actually "
    "charged, distinct from multi_component_agreement where every component "
    "applies together."
)

GET_FEE_AGREEMENT_TEMPLATE_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "get_fee_agreement_template",
    "description": (
        "Fetch reference material for one fee-agreement template variant "
        "(הסכם שכר טרחה): the template's own body skeleton, a curated set of "
        "REAL fee-agreement excerpts this firm has actually sent (names/"
        "amounts obfuscated - the phrasing/structure/register are real), and "
        "a directive explaining what to do with both. This is REFERENCE "
        "material only - you then compose the entire real document body "
        "yourself (render_fee_agreement_document); never reuse this text "
        "verbatim, never copy a name/amount from an example into your own "
        "output, and never leave any '{{...}}'-looking token in what you "
        "write. The firm's letterhead (logo/header/footer) is never part of "
        "this - it's applied automatically and is never something you write "
        "or edit. Not for invoices/receipts (Morning MCP tools) and not for "
        "reminders.\n\nWhich variant to request:\n" + _VARIANT_SELECTION_GUIDE
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "variant_id": {
                "type": "string",
                "enum": _VARIANT_ENUM,
                "description": "Which template variant best matches what the human described - see the guide above.",
            },
        },
        "required": ["variant_id"],
    },
}

RENDER_FEE_AGREEMENT_DOCUMENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "render_fee_agreement_document",
    "description": (
        "Render a fee agreement document (הסכם שכר טרחה) from the substantive "
        "content you compose yourself - the scope of work, every numbered "
        "fee/payment clause, any conditions. Never invent, guess, or default "
        "a financial or legal detail the human did not explicitly give you - "
        "ask instead. Dispatches immediately, no approval needed - to revise "
        "after feedback, just call this again with your edited text (a new "
        "document_id is returned each time). The firm's letterhead "
        "(logo/header/footer), the document title, date, firm identity, and "
        "signature block are ALL applied automatically by code around "
        "whatever you write - never write any of those yourself (there is "
        "no field for them - they are not part of body_text at all), and "
        "never include a literal '{{...}}' placeholder token anywhere in "
        "your text. IMPORTANT - keep it to ONE PAGE: after rendering, "
        "verify_fee_agreement_document reports the document's real page "
        "count - a real fee agreement like this is always exactly one page; "
        "if it comes back as more than one, shorten/tighten your wording "
        "(shorter sentences, fewer separate clauses, no filler) and render "
        "again before sending. Light formatting is supported and expected, "
        "matching how a real signed agreement looks: a line starting with "
        "'## ' becomes a bold section heading; wrap any span in '**...**' "
        "for emphasis (e.g. amounts, deadlines) - use both sparingly, the "
        "way a real document does, not on every line."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "variant_id": {
                "type": "string",
                "enum": _VARIANT_ENUM,
                "description": "Which template variant's branded shell to render into.",
            },
            "client_name": {
                "type": "string",
                "description": (
                    "The client's exact name, as the user gave it - inserted "
                    "by code into the document's fixed header/signature "
                    "blocks. Never include this or the firm's own identity "
                    "inside body_text - both are handled automatically."
                ),
            },
            "body_text": {
                "type": "string",
                "description": (
                    "ONLY the substantive content between the fixed header "
                    "(title/date/parties) and fixed footer (signature) that "
                    "code already provides - the scope of work and every fee/"
                    "payment clause (correctly numbered - never a lone item "
                    "numbered א. with no ב. to follow; either number a real "
                    "sequence or don't number a single item at all). One "
                    "paragraph per line. Any amount must be one complete "
                    "phrase including currency and VAT status, e.g. '25,000 "
                    "₪ כולל מע\"מ' - never a bare number. Do NOT repeat the "
                    "client name, firm identity, date, or a signature line "
                    "here - those are added automatically."
                ),
            },
        },
        "required": ["variant_id", "client_name", "body_text"],
    },
}

VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "verify_fee_agreement_document",
    "description": (
        "Read back a just-rendered fee agreement document and report facts: "
        "whether any literal '{{...}}'-shaped placeholder token leaked into "
        "it. Read-only, no approval needed. YOU (the model) must judge the "
        "full result - is the text actually what you intended, complete, and "
        "correct, and does it read like a fee agreement that fits on one "
        "page (write concisely - trim wording, merge short clauses, drop "
        "anything non-essential) - before ever calling "
        "send_fee_agreement_document; this tool only reports facts, it does "
        "not decide pass/fail for you. (2026-09-15: no automated page-count "
        "check - LibreOffice is unavailable in the runtime container, so any "
        "such check would be permanently unable to run there; one-page "
        "discipline is achieved by writing concisely, not by a code-level "
        "measurement.) The fixed header (code-injected, never yours to write) "
        "must show the date BEFORE the title (\"הסכם שכר טרחה\") - as in a "
        "real formal Israeli legal letterhead - never after; flag it if the "
        "extracted text ever shows the title before the date."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The document_id returned by render_fee_agreement_document.",
            },
        },
        "required": ["document_id"],
    },
}

SEND_FEE_AGREEMENT_DOCUMENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "send_fee_agreement_document",
    "description": (
        "Send a fee agreement document to the client over WhatsApp, as a "
        "file attachment. Only call this AFTER calling "
        "verify_fee_agreement_document and confirming, in your own "
        "judgment, that the result was clean - calling this on a document "
        "that failed verification, or without verifying first, will be "
        "refused. No further human approval is needed - once you're "
        "satisfied, send it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The document_id returned by render_fee_agreement_document.",
            },
            "caption": {
                "type": "string",
                "description": "A short WhatsApp caption to send alongside the file.",
            },
        },
        "required": ["document_id", "caption"],
    },
}

FEE_AGREEMENT_TOOL_NAMES = {
    GET_FEE_AGREEMENT_TEMPLATE_TOOL["name"],
    RENDER_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
    VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
    SEND_FEE_AGREEMENT_DOCUMENT_TOOL["name"],
}


class FeeAgreementToolHandler:
    """Owns turn-scoped `GeneratedDocument` bookkeeping and every
    DocTemplateEngine-facing decision for the 3 fee-agreement tools.

    In-memory only, same rationale as PendingLocalToolApprovalManager /
    PendingApprovalManager: losing this on a process restart just means the
    human re-asks - nothing here is ever the sole record of anything (the
    .docx itself is a throwaway temp file, per data-model.md).
    """

    def __init__(self, engine: DocTemplateEngine) -> None:
        self.engine = engine
        self._documents: Dict[str, GeneratedDocument] = {}

    def build_tools(self, user_obj) -> List[Dict]:
        """RBAC-gated (GODFATHER/ADMIN only), same as reminder/ledger-query tools -
        no separate feature flag (2026-09-15: an earlier extra
        config.feature_flags['fee_agreement_docs'] gate was removed per explicit
        human instruction - it was never requested and left the feature silently
        unreachable in dev)."""
        if user_obj is None or user_obj.role not in FEE_AGREEMENT_AUTHORIZED_ROLES:
            return []
        return [
            GET_FEE_AGREEMENT_TEMPLATE_TOOL,
            RENDER_FEE_AGREEMENT_DOCUMENT_TOOL,
            VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL,
            SEND_FEE_AGREEMENT_DOCUMENT_TOOL,
        ]

    def handle_get_template(self, variant_id: Optional[str]) -> Dict[str, Any]:
        """Read-only, dispatches immediately - no approval gate, nothing to
        validate beyond the variant existing. Returns the template skeleton
        PLUS curated real-world examples and a directive (2026-09-14
        follow-up - see DocTemplateEngine.get_reference_materials)."""
        if not isinstance(variant_id, str) or not variant_id:
            return {"error": "variant_id is required."}
        try:
            materials = self.engine.get_reference_materials(variant_id)
        except ValueError as e:
            logger.info(f"[083] get_fee_agreement_template rejected: {e}")
            return {"error": str(e)}
        return {
            "variant_id": variant_id,
            "reference_body": materials["template_body"],
            "examples": materials["examples"],
            "directive": materials["directive"],
        }

    def handle_render(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches immediately - NO approval gate (2026-09-13 human
        decision: the AI is the document's author, not a form the human must
        approve field-by-field). Builds the .docx from the AI's own full body
        text and keeps the resulting GeneratedDocument for the same
        turn-scoped lifetime's subsequent verify/send calls (or a later
        revise-and-re-render call)."""
        variant_id = args.get("variant_id")
        client_name = args.get("client_name")
        body_text = args.get("body_text")
        if not isinstance(variant_id, str) or not variant_id:
            return {"error": "variant_id is required."}
        if not isinstance(client_name, str) or not client_name.strip():
            return {"error": "client_name is required and must be non-empty."}
        if not isinstance(body_text, str) or not body_text.strip():
            return {"error": "body_text is required and must be non-empty."}
        try:
            doc = self.engine.render_free_text(variant_id, client_name, body_text)
        except ValueError as e:
            logger.info(f"[083] render_fee_agreement_document rejected: {e}")
            return {"error": str(e)}
        self._documents[doc.document_id] = doc
        logger.info(f"[083] render_fee_agreement_document: document_id={doc.document_id!r}, variant_id={variant_id!r}")
        return {"document_id": doc.document_id}

    def handle_verify(self, document_id: Optional[str]) -> Dict[str, Any]:
        """Read-only. Returns the raw facts dict from DocTemplateEngine.verify()
        (see its own docstring - it never itself decides pass/fail), and, as
        defense-in-depth ONLY (not the sole gate - see module docstring),
        marks the GeneratedDocument verified=True when the facts are already
        clean. send_fee_agreement_document still independently re-checks this
        flag rather than trusting the model's own judgment call blindly."""
        doc = self._documents.get(document_id or "")
        if doc is None:
            return {"error": f"unknown or stale document_id: {document_id!r} - it may have already been sent, or this is a new turn with no such pending document."}
        result = self.engine.verify(doc)
        if result.get("clean"):
            doc.verified = True
        return result

    def handle_send(self, document_id: Optional[str], whatsapp_handler, chat_id: str, caption: str) -> Dict[str, Any]:
        """Dispatches immediately but refuses (a tool-call error dict, never
        a raised exception - the model must be able to see and react to
        this) unless the document already passed verification. Cleans up
        the temp file and the in-memory entry regardless of send outcome -
        never leaves either behind (SC-003)."""
        doc = self._documents.get(document_id or "")
        if doc is None:
            return {"error": f"unknown or stale document_id: {document_id!r}"}
        if not doc.verified:
            return {"error": "This document has not passed verification yet - call verify_fee_agreement_document first and confirm it is clean before sending."}
        try:
            sent = whatsapp_handler.send_document_response(doc, chat_id=chat_id, caption=caption)
            doc.sent = bool(sent)
            if not sent:
                return {"error": "שליחת המסמך נכשלה - נסה שוב מאוחר יותר."}
            return {"sent": True}
        finally:
            self._cleanup(document_id or "")

    def _cleanup(self, document_id: str) -> None:
        doc = self._documents.pop(document_id, None)
        if doc is None:
            return
        try:
            doc.temp_path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"[083] Failed to delete temp fee agreement file {doc.temp_path}: {e}")
