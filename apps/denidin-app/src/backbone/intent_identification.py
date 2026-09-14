"""
The Intent Identification meta-capability (Feature 063) — the orchestrator's first
reasoning step every turn. Free-form output (not itself a CapabilityTag list — that's
Planning's job, per contracts/orchestration-loop.md step 1).
"""
import logging

from src.backbone.capability_tags import CapabilityTag

logger = logging.getLogger(__name__)


def identify_intent(orchestrator, request, *, is_media: bool = False) -> str:
    """Runs the Intent Identification step: Backbone + intent_identification.md's
    prompt, told whether this is a text or media message (media messages aren't
    parsed/extracted yet at this point — Intent Identification just knows "this is
    media", not what it contains, per contracts/orchestration-loop.md step 1).

    Returns the model's free-form statement of what the turn needs. On any error,
    returns a generic fallback string rather than raising — a failed Intent
    Identification call should not itself fail the turn; Planning's own fail-open
    behavior (planning.fail_open_plan) is the real safety net downstream.
    """
    message_kind = "a media message (not yet extracted)" if is_media else "a text message"
    try:
        return str(orchestrator.call_capability_step(
            tag=CapabilityTag.INTENT_IDENTIFICATION,
            request=request,
            accumulated_context=f"This turn is {message_kind}.",
        ))
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Intent Identification call failed: %s", exc)
        return "Unable to determine intent (Intent Identification call failed)."
