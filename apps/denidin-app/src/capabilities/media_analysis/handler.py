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
events) — REQ-063-04a's actual design routes extracted text back through the plan
(e.g. a following `ledger_capture` step decides what to do with it), so silently
re-running the legacy shortcut inline would double up with that. Real Ledger
Events — Capture wiring is tracked in tasks.md's Deferred section; this capability's
own job is extraction only.
"""
import logging
from typing import Any, Dict, Optional

from src.backbone.capability_tags import CapabilityTag

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
            "media_analysis capability: inline ledger capture deferred to a "
            "following plan step (tasks.md Deferred) — extraction only here."
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
    """Media Analysis step: dispatches to the right unmodified extractor by MIME
    type (same dispatch `MediaHandler` uses today), returns the extracted text +
    document analysis as this step's output for the plan's following steps to use."""
    del accumulated_context, note
    media = turn_context.get("media")
    media_type = turn_context.get("media_type")
    if media is None or media_type is None:
        return "No media attached to this turn — nothing to extract."

    context_shim = _ExtractorContextShim(orchestrator)
    extractor = _build_extractor(media_type, context_shim)
    result = extractor.analyze_media(media, caption=turn_context.get("caption", ""),
                                      today_timestamp=request.timestamp)

    extracted_text = result.get("extracted_text", "")
    analysis = result.get("document_analysis", {})
    return f"Extracted text: {extracted_text}\n\nDocument analysis: {analysis}"
