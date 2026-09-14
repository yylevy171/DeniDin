"""
The Intent Identification meta-capability (Feature 063) — the orchestrator's first
reasoning step every turn. Free-form output (not itself a CapabilityTag list — that's
Planning's job, per contracts/orchestration-loop.md step 1).
"""
import logging
from typing import List

from src.backbone.capability_tags import CapabilityTag, capability_catalog_text

logger = logging.getLogger(__name__)


def identify_intent(orchestrator, request, allowed_tags: List[CapabilityTag], *,
                     is_media: bool = False) -> str:
    """Runs the Intent Identification step: Backbone + intent_identification.md's
    prompt, told whether this is a text or media message (media messages aren't
    parsed/extracted yet at this point — Intent Identification just knows "this is
    media", not what it contains, per contracts/orchestration-loop.md step 1) AND,
    since 2026-09-14, the role's own allowed-capability catalog (name + one-line
    domain description, from capability_tags.capability_catalog_text) — so it can
    recognize which existing domain a request touches without that recognition
    being hardcoded per-capability into this prompt file by hand. Fixes a real
    billed-test failure: with zero visibility into what capabilities even exist,
    this step answered a past-agreement lookup itself (wrongly, "not found") rather
    than recognizing it as Ledger Query's domain — a general gap, not specific to
    that one capability, so the fix is general too (every role-allowed capability's
    description, not a hand-picked example).

    Returns the model's free-form statement of what the turn needs — still never
    naming an internal capability tag itself (that stays Planning's job); the
    catalog is context for recognizing the domain, not vocabulary for the output.
    On any error, returns a generic fallback string rather than raising — a failed
    Intent Identification call should not itself fail the turn; Planning's own
    fail-open behavior (planning.fail_open_plan) is the real safety net downstream.
    """
    message_kind = "a media message (not yet extracted)" if is_media else "a text message"
    catalog = capability_catalog_text(allowed_tags)
    context = f"This turn is {message_kind}."
    if catalog:
        context += (
            "\n\nDomains of capability available to this role this turn (for "
            "recognizing what the request needs — never name these internally by "
            "tag in your own output):\n" + catalog
        )
    try:
        return str(orchestrator.call_capability_step(
            tag=CapabilityTag.INTENT_IDENTIFICATION,
            request=request,
            accumulated_context=context,
        ))
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Intent Identification call failed: %s", exc)
        return "Unable to determine intent (Intent Identification call failed)."
