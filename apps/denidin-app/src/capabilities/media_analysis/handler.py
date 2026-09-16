"""
Media Analysis capability (Feature 063) — the 7th domain capability, folding in what
was previously two standalone files (`prompts/image_analysis.txt`, `prompts/docx_analysis.txt`)
outside any capability structure at all.

Reuses the existing, unmodified `src/handlers/extractors/{image,pdf,docx}_extractor.py`
classes (REQ-063-03: "imported, not duplicated") via a small duck-typing shim, since
those classes are written against `AIHandler`'s interface
(`denidin_context.ai_handler.client` / `._load_constitution()` /
`.capture_ledger_events_from_text()`), not against the new orchestrator directly.

Scope note: the extractors' own inline ledger-capture side effect
(`ai_handler.capture_ledger_events_from_text`) is stubbed here (logged, returns no
events) — REQ-063-04a's actual design routes extracted text back through the plan,
and real capture happens automatically via `denidin.py`'s shared, unmodified
`_run_post_turn_ledger_recognition` once the turn is persisted (see
`src/capabilities/ledger_events/handler.py::capture()`'s own docstring for the
full reasoning) — silently re-running the legacy shortcut inline here would risk
double-capturing the same event. This capability's own job is extraction only.
"""
import logging
from typing import Any, Dict, Optional

from src.backbone.capability_tags import CapabilityTag
from src.constants.error_messages import BACKBONE_NO_MEDIA_ATTACHED

logger = logging.getLogger(__name__)


class _ExtractorAIHandlerShim:
    """Duck-types the subset of AIHandler's interface handlers/extractors/*.py
    actually call, so the unmodified extractor classes can run against the new
    orchestrator instead of the legacy AIHandler."""

    def __init__(self, orchestrator):
        self._orchestrator = orchestrator
        self.client = orchestrator.client

    def _load_constitution(self) -> str:
        return str(self._orchestrator.load_backbone()) + "\n\n" + str(
            self._orchestrator.load_capability_prompt(CapabilityTag.MEDIA_ANALYSIS)
        )

    def capture_ledger_events_from_text(self, text: str, today_timestamp: Optional[int] = None):
        del text, today_timestamp
        logger.info(
            "media_analysis capability: inline ledger capture skipped here — "
            "capture happens automatically via the shared post-turn recognition "
            "mechanism once this turn is persisted (see ledger_events/handler.py)."
        )
        return []


class _ExtractorContextShim:
    def __init__(self, orchestrator):
        self.config = orchestrator.config
        self.ai_handler = _ExtractorAIHandlerShim(orchestrator)


def _build_extractor(media_type: str, context_shim: "_ExtractorContextShim"):
    # pylint: disable=import-outside-toplevel
    if media_type == "image":
        from src.handlers.extractors.image_extractor import ImageExtractor
        return ImageExtractor(context_shim)
    if media_type == "pdf":
        from src.handlers.extractors.pdf_extractor import PDFExtractor
        return PDFExtractor(context_shim)
    if media_type == "docx":
        from src.handlers.extractors.docx_extractor import DOCXExtractor
        return DOCXExtractor(context_shim)
    raise ValueError(f"Unsupported media_type for extraction: {media_type!r}")


def extract(orchestrator, request, accumulated_context: str, note: str,
            turn_context: Dict[str, Any]) -> str:
    """Media Analysis step: returns the extracted text + document analysis as this
    step's output for the plan's following steps to use.

    media/media_type (2026-09-15, the real design - REQ-063-04a, corrects the
    2026-09-14 shortcut this docstring used to describe): denidin.py's flag-on
    media dispatch hands the orchestrator RAW, not-yet-extracted media - Planning
    is what actually decides whether this turn's plan even includes a
    media_analysis step. This is now the normal case in production: dispatches
    to the right unmodified extractor class via turn_context["media"]/
    ["media_type"], same MIME-type dispatch `MediaHandler` uses today.

    media_extraction: an ALREADY-computed extraction result, when a caller has
    one to hand instead (e.g. a unit test fixture, or a future caller that
    front-loads extraction for its own reasons) - a pass-through, formatting the
    already-computed result rather than paying for a second real vision/AI call
    on the same media. media/media_type and media_extraction are mutually
    exclusive in practice (mirrors orchestrator.get_response's own docstring)."""
    del accumulated_context, note
    media_extraction = turn_context.get("media_extraction")
    if media_extraction:
        extracted_text = media_extraction.get("extracted_text", "")
        analysis = media_extraction.get("document_analysis", {})
        return f"Extracted text: {extracted_text}\n\nDocument analysis: {analysis}"

    media = turn_context.get("media")
    media_type = turn_context.get("media_type")
    if media is None or media_type is None:
        return BACKBONE_NO_MEDIA_ATTACHED

    context_shim = _ExtractorContextShim(orchestrator)
    extractor = _build_extractor(media_type, context_shim)
    result = extractor.analyze_media(media, caption=turn_context.get("caption", ""),
                                      today_timestamp=request.timestamp)

    extracted_text = result.get("extracted_text", "")
    analysis = result.get("document_analysis", {})
    return f"Extracted text: {extracted_text}\n\nDocument analysis: {analysis}"
