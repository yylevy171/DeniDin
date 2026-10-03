"""
Media Analysis capability (Feature 063) — the 7th domain capability, folding in what
was previously two standalone files (`prompts/image_analysis.txt`, `prompts/docx_analysis.txt`)
outside any capability structure at all.

Reuses the existing `src/handlers/extractors/{image,pdf,docx}_extractor.py` classes
(REQ-063-03: "imported, not duplicated"). An extractor takes the DeniDin object and
uses its `ai_manager` (REQ-063-08) - here, the backbone itself: its extraction prompt
prefix is empty and its inline ledger capture a no-op (real capture happens through
DeniDin's shared post-turn recognition once the turn is persisted).
This capability's own job is extraction only.
"""
import json
import logging
from typing import Any, Dict, Tuple

from src.constants.error_messages import BACKBONE_NO_MEDIA_ATTACHED

logger = logging.getLogger(__name__)


def _build_extractor(media_type: str, extractor_context: Any):
    # pylint: disable=import-outside-toplevel
    if media_type == "image":
        from src.handlers.extractors.image_extractor import ImageExtractor
        return ImageExtractor(extractor_context)
    if media_type == "pdf":
        from src.handlers.extractors.pdf_extractor import PDFExtractor
        return PDFExtractor(extractor_context)
    if media_type == "docx":
        from src.handlers.extractors.docx_extractor import DOCXExtractor
        return DOCXExtractor(extractor_context)
    raise ValueError(f"Unsupported media_type for extraction: {media_type!r}")


def _record_extracted_text(backbone, turn_context: Dict[str, Any], extracted_text: str) -> None:
    """Fills the extracted text into the turn's already-stored media message the moment
    it's known (2026-09-30), same field the legacy media path sets; "" normalizes to None
    (Message.extracted_text contract)."""
    backbone.denidin.update_message(turn_context.get("chat_id"), turn_context.get("message_id"),
                                    extracted_text=extracted_text or None)


def _format_result(result: Dict[str, Any]) -> Tuple[str, str]:
    """The analyze_media tool output for the model, plus the text to store on the
    media message. Carries everything the extractors return that the model needs
    to choose what to do next - doc_type, fields, missing_required_fields
    (image/PDF) or document_analysis (DOCX) - not just the text. extracted_text
    falls back to raw_response when the structured text is empty, the extractors'
    own "never leave the user with nothing" fallback (bugfix-028 B5)."""
    extracted_text = result.get("extracted_text") or result.get("raw_response") or ""
    payload: Dict[str, Any] = {"extracted_text": extracted_text}
    for key in ("doc_type", "fields", "missing_required_fields", "document_analysis", "warnings"):
        if result.get(key):
            payload[key] = result[key]
    # A DOCX the reader classified as a fee agreement (its deterministic "הסכם"
    # signal) is doc_type "agreement" - the type cap_media_analysis routes to
    # flow_fee_agreement_provided_by_user (Item17, 2026-10-01).
    if "doc_type" not in payload and (result.get("document_analysis") or {}).get("document_type") == "הסכם":
        payload["doc_type"] = "agreement"
    return json.dumps(payload, ensure_ascii=False, indent=2), extracted_text


def dispatch_direct_tool_call(backbone, tool_name: str, args: Dict[str, Any],
                               turn_context: Dict[str, Any]) -> str:
    """Executes one `analyze_media` call directly on the ongoing chain
    (2026-09-24 "resolution" redesign - no separate "use" step, no note).

    turn_context["media"] (REQ-063-04a): the turn's RAW, not-yet-extracted file
    (request.media); the real vision/PDF/DOCX extraction only happens here, when the
    model calls the tool, via the unmodified extractor classes (same MIME dispatch
    `MediaHandler` uses), chosen by the file's own media_type."""
    del tool_name, args
    media = turn_context.get("media")
    if media is None or media.media_type is None:
        return BACKBONE_NO_MEDIA_ATTACHED
    extractor = _build_extractor(media.media_type, backbone.denidin)
    result = extractor.analyze_media(media, caption=turn_context.get("caption", ""),
                                     today_timestamp=turn_context.get("timestamp"))

    output, extracted_text = _format_result(result)
    _record_extracted_text(backbone, turn_context, extracted_text)
    return output
