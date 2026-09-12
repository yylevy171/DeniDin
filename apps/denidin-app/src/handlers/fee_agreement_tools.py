"""
Fee Agreement AI tool wiring (Feature 083).

Deliberately kept in its own module, separate from ai_handler.py (already
4,000+ lines and due its own refactor - not part of this feature per explicit
2026-09-12 user instruction: new tool-bearing logic for this feature goes
here, not inlined into ai_handler.py). This module owns everything that is
purely about the 3 fee-agreement tools themselves - their JSON schemas, RBAC
gating, and all DocTemplateEngine-facing logic (proposal validation,
human-facing approval-details text, turn-scoped GeneratedDocument
bookkeeping/cleanup). ai_handler.py wires this in via a handful of small,
additive delegating calls (mirroring how it already delegates to
ReminderManager/LedgerEventManager) - it never touches DocTemplateEngine
directly, and never grows its own copy of this logic.

Three tools, per the human-confirmed decision not to collapse verify+send:
- generate_fee_agreement: proposal-only, goes through the existing
  PendingLocalToolApproval gate (same UX as create_reminder) - approval
  gates the collected VALUES, not the finished document.
- verify_fee_agreement_document: read-only, dispatches immediately. Returns
  raw facts (leftover placeholders / missing values) - the actual accept/
  reject judgment is the model's own (REQ-083-04), not this tool's.
- send_fee_agreement_document: dispatches immediately, but refuses (as a
  tool-call error, not an exception) unless the document already passed
  verification in this same turn-scoped lifetime - the AI's own prior
  self-verification is the sole gate for the finished document, per the
  human-confirmed research.md #4 decision.
"""

import json
from typing import Any, Dict, List, Optional

from src.managers.doc_template_engine import DocTemplateEngine
from src.models.fee_agreement import GeneratedDocument
from src.models.user import Role
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Same two roles every other local-tool family in this app RBAC-gates on
# (REMINDER_AUTHORIZED_ROLES / LEDGER_QUERY_AUTHORIZED_ROLES in ai_handler.py).
FEE_AGREEMENT_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

GENERATE_FEE_AGREEMENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "generate_fee_agreement",
    "description": (
        "Propose generating a fee agreement document (הסכם שכר טרחה) from one "
        "of the firm's template variants, filled with values the human has "
        "explicitly provided in this conversation. Never invent, guess, or "
        "default a value not explicitly given - ask the human for anything "
        "missing instead. This only PROPOSES the document (subject to the "
        "same approval gate as creating a reminder) - it does not send "
        "anything. Not for invoices/receipts (those are Morning MCP tools) "
        "and not for reminders."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "variant_id": {
                "type": "string",
                "enum": [
                    "hourly_consultation", "retainer_agreement", "fixed_price_project",
                    "multi_component_agreement", "alternative_tracks",
                ],
                "description": "Which template variant matches what the human described.",
            },
            "values": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": (
                    "Every scalar placeholder this variant's template needs, "
                    "keyed by placeholder name (e.g. FIRM_NAME, DATE, "
                    "CLIENT_NAME, SCOPE_OF_WORK), each an explicit, "
                    "non-empty value the human actually provided."
                ),
            },
            "components": {
                "type": "array",
                "description": (
                    "Only for multi_component_agreement/alternative_tracks: "
                    "one entry per fee component/track, each an explicit "
                    "{label, terms} pair. Omit entirely for every other "
                    "variant."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "terms": {"type": "string"},
                    },
                    "required": ["label", "terms"],
                },
            },
        },
        "required": ["variant_id", "values"],
    },
}

VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "verify_fee_agreement_document",
    "description": (
        "Read back a just-generated (and human-approved) fee agreement "
        "document and report whether every placeholder was actually filled "
        "and every supplied value is really present in the text. Read-only, "
        "no approval needed. YOU (the model) must judge the result and "
        "decide whether it's actually clean before ever calling "
        "send_fee_agreement_document - this tool only reports facts, it "
        "does not decide pass/fail for you."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The document_id returned when generate_fee_agreement was approved.",
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
        "refused."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The document_id returned when generate_fee_agreement was approved.",
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
    GENERATE_FEE_AGREEMENT_TOOL["name"],
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

    def build_tools(self, user_obj, feature_enabled: bool) -> List[Dict]:
        """RBAC-gated (GODFATHER/ADMIN only) the same way reminder/ledger-query
        tools are, ADDITIONALLY gated by `config.feature_flags['fee_agreement_docs']`
        (default False - see models/config.py's `fee_agreements` field)."""
        if not feature_enabled:
            return []
        if user_obj is None or user_obj.role not in FEE_AGREEMENT_AUTHORIZED_ROLES:
            return []
        return [
            GENERATE_FEE_AGREEMENT_TOOL,
            VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL,
            SEND_FEE_AGREEMENT_DOCUMENT_TOOL,
        ]

    def validate_generate_proposal(self, args: Dict[str, Any]) -> Optional[str]:
        """Proposal-time-only validation (UX: reject immediately rather than
        proposing something that will fail at approval time) - mirrors
        _handle_reminder_creation_proposal's proposal-time cap/date checks.
        Re-validated for real at approval time regardless (TOCTOU-closing,
        same discipline as reminders). Returns a friendly error string if
        invalid, else None.
        """
        variant_id = args.get("variant_id")
        values = args.get("values")
        if not isinstance(variant_id, str) or not variant_id:
            return "לא צוין סוג הסכם (variant_id) - נסה שוב."
        if not isinstance(values, dict):
            return "לא צוינו הפרטים הנדרשים למסמך - נסה שוב."
        try:
            self.engine._get_variant(variant_id)  # noqa: SLF001 - internal, deliberate reuse
        except ValueError as e:
            logger.info(f"[083] generate_fee_agreement proposal rejected: {e}")
            return "סוג ההסכם שצוין אינו קיים - נסה שוב עם אחד המסלולים הקיימים."
        try:
            variant = self.engine._get_variant(variant_id)  # noqa: SLF001
            DocTemplateEngine._validate_values(variant, values)  # noqa: SLF001
            DocTemplateEngine._validate_components(variant, args.get("components"))  # noqa: SLF001
        except ValueError as e:
            logger.info(f"[083] generate_fee_agreement proposal rejected: {e}")
            return f"חסרים פרטים או שיש פרטים לא תקינים להצעת ההסכם: {e}"
        return None

    @staticmethod
    def build_approval_details(args: Dict[str, Any]) -> str:
        """Deterministic, human-facing approval summary built straight from
        the (already-validated) proposed arguments - same "state exactly
        what will happen" discipline as _build_reminder_approval_details."""
        lines = [f"מסמך שכר טרחה מסוג: {args.get('variant_id')}"]
        values = args.get("values") or {}
        for key, value in values.items():
            lines.append(f"- {key}: {value}")
        components = args.get("components") or []
        for entry in components:
            lines.append(f"- {entry.get('label')}: {entry.get('terms')}")
        return "\n".join(lines)

    def resolve_generate(self, args: Dict[str, Any]) -> GeneratedDocument:
        """Called only after human approval. Actually builds the .docx file
        and keeps the resulting GeneratedDocument for the same turn-scoped
        lifetime's subsequent verify/send calls."""
        doc = self.engine.generate(
            variant_id=args["variant_id"],
            values=args.get("values", {}),
            components=args.get("components"),
        )
        self._documents[doc.document_id] = doc
        logger.info(f"[083] generate_fee_agreement approved and generated: document_id={doc.document_id!r}")
        return doc

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
