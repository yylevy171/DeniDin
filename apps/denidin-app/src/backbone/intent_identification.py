"""
The Intent Identification meta-capability (Feature 063) — the orchestrator's first
reasoning step every turn. Free-form output (not itself a CapabilityTag list — that's
Planning's job, per contracts/orchestration-loop.md step 1).
"""
import logging
from typing import Any, Dict, List, Optional

from src.backbone.capability_tags import CapabilityTag
from src.constants.error_messages import BACKBONE_INTENT_IDENTIFICATION_FAILED

logger = logging.getLogger(__name__)


def identify_intent(orchestrator, request, allowed_tags: List[CapabilityTag], *,
                     is_media: bool = False,
                     media_extraction: Optional[Dict[str, Any]] = None) -> str:
    """Runs the Intent Identification step: Backbone (now including the full
    capability catalog as a static section - see orchestrator.build_instructions,
    2026-09-14) + intent_identification.md's prompt + this turn's own context.

    is_media/media_extraction (2026-09-14): media turns are extracted UP FRONT,
    before the orchestrator ever runs (denidin.py reuses the existing MediaHandler
    pipeline wholesale for real parity - file download/save/session-persistence/
    ledger-stash detection, REQ-063-03 - rather than re-running extraction a
    second time inside the plan). So Intent Identification is told the REAL
    extracted text/analysis when it's available, not just "this is media" -
    strictly better information than the original "not yet extracted" design,
    now that extraction has already genuinely happened by this point.

    allowed_tags is currently unused here directly - the capability catalog is
    now part of the Backbone's own static content (every call already carries
    it), not injected per-call - kept as a parameter for role-based catalog
    filtering once client-role scope is revisited (today: godfather/admin only,
    per explicit scope decision).

    Returns the model's free-form statement of what the turn needs — still never
    naming an internal capability tag itself (that stays Planning's job). On any
    error, returns a generic fallback string rather than raising — a failed
    Intent Identification call should not itself fail the turn; Planning's own
    fail-open behavior (planning.fail_open_plan) is the real safety net downstream.
    """
    del allowed_tags
    if is_media and media_extraction:
        extracted_text = media_extraction.get("extracted_text") or "(no text extracted)"
        analysis = media_extraction.get("document_analysis") or {}
        context = (
            f"This turn is a media message, already extracted.\n\n"
            f"Extracted text: {extracted_text}\n\nDocument analysis: {analysis}"
        )
    elif is_media:
        context = "This turn is a media message (not yet extracted)."
    else:
        context = "This turn is a text message."
    try:
        return str(orchestrator.call_capability_step(
            tag=CapabilityTag.INTENT_IDENTIFICATION,
            request=request,
            accumulated_context=context,
        ))
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Intent Identification call failed: %s", exc)
        return BACKBONE_INTENT_IDENTIFICATION_FAILED
