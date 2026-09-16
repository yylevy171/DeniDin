"""
The Planning meta-capability (Feature 063) — data-model.md's `Plan` entity + the
RBAC-filtered capability set computed before Planning runs, plus the actual Planning
step (one followup OpenAI call, Backbone + planning.md + Intent Identification's
output + available_capabilities_for_planning).

See contracts/orchestration-loop.md step 2 and data-model.md's "Plan" /
"RBAC-filtered capability set" sections.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from src.backbone.capability_tags import CapabilityTag, is_valid_domain_capability
from src.models.user import Role

logger = logging.getLogger(__name__)

# RBAC-gated domain capabilities — mirrors AIHandler._assemble_tools' existing RBAC
# checks (invoicing/ledger/reminders are godfather/admin-only today). media_analysis
# follows the same media-message RBAC any role already has today (no new restriction).
_GODFATHER_ADMIN_ONLY_CAPABILITIES = (
    CapabilityTag.INVOICING_WRITE,
    CapabilityTag.INVOICING_READ,
    CapabilityTag.LEDGER_CAPTURE,
    CapabilityTag.LEDGER_QUERY,
    CapabilityTag.REMINDERS_WRITE,
    CapabilityTag.REMINDERS_READ,
)
_ALWAYS_ALLOWED_CAPABILITIES = (CapabilityTag.MEDIA_ANALYSIS,)


def role_allowed_capabilities(role: Role) -> List[CapabilityTag]:
    """The domain capabilities this role may be offered by Planning. Computed BEFORE
    Planning is invoked (data-model.md) — Planning is only ever told about capabilities
    the role can actually execute, rather than proposing freely and being filtered
    after the fact."""
    allowed = list(_ALWAYS_ALLOWED_CAPABILITIES)
    if role in (Role.GODFATHER, Role.ADMIN):
        allowed.extend(_GODFATHER_ADMIN_ONLY_CAPABILITIES)
    return allowed


@dataclass(frozen=True)
class PlanStep:
    capability: CapabilityTag
    note: str = ""


@dataclass(frozen=True)
class Plan:
    """Planning's output. `steps` may be empty (Backbone-only turn) but is never
    None. Only ever contains DOMAIN CapabilityTags — Intent Identification/Planning
    are always the implicit first two steps of every turn and are never named here."""

    steps: List[PlanStep] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.steps) == 0


def parse_plan(raw: Optional[dict], allowed_tags: List[CapabilityTag]) -> Plan:
    """Parses/validates a Planning call's JSON output into a `Plan`.

    - An unrecognized/non-domain capability tag is dropped, logged as a WARNING
      (data-model.md's validation rule) — never executed, never silently expands
      what a turn receives.
    - A step naming a capability this role isn't allowed (not in `allowed_tags`) is
      dropped, logged as a WARNING — defense in depth; Planning is only ever told
      about the role's allowed capabilities in the first place, so this should be rare.
    - Malformed/missing input (not a dict, no "steps" key, "steps" not a list) is
      treated as a Planning failure by the caller (see `build_plan`'s fail-open path),
      not handled here.
    """
    if not raw or not isinstance(raw, dict):
        raise ValueError("Planning output is not a JSON object")
    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list):
        raise ValueError("Planning output missing a 'steps' list")

    allowed_set = set(allowed_tags)
    steps: List[PlanStep] = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            logger.warning("Planning step is not an object, dropping: %r", raw_step)
            continue
        capability_value = str(raw_step.get("capability") or "")
        if not is_valid_domain_capability(capability_value):
            logger.warning("Planning named an unrecognized/non-domain capability, dropping: %r", capability_value)
            continue
        tag = CapabilityTag(capability_value)
        if tag not in allowed_set:
            logger.warning("Planning named a capability this role isn't allowed, dropping: %s", tag.value)
            continue
        steps.append(PlanStep(capability=tag, note=str(raw_step.get("note", ""))))

    return Plan(steps=steps)


def fail_open_plan(allowed_tags: List[CapabilityTag]) -> Plan:
    """On a Planning call failure (timeout, malformed JSON after retry): execute
    every domain capability the role has access to, in canonical order — equivalent
    to today's always-everything constitution — rather than fail closed to an empty
    plan (data-model.md). Caller is responsible for logging this as an ERROR."""
    from src.backbone.capability_tags import CAPABILITY_INFO, CapabilityKind

    ordered_allowed = [
        info.tag for info in CAPABILITY_INFO
        if info.kind == CapabilityKind.DOMAIN and info.tag in allowed_tags
    ]
    return Plan(steps=[PlanStep(capability=tag, note="fail-open") for tag in ordered_allowed])


def build_plan(orchestrator, request, intent_text: str, allowed_tags: List[CapabilityTag], *,
                is_media: bool = False) -> Plan:
    """The actual Planning step: one followup OpenAI call (Backbone - now including
    the full capability catalog as a static section, 2026-09-14, see
    orchestrator.build_instructions - + planning.md's prompt + Intent
    Identification's output + this role's own allowed tag names), parsed into a
    `Plan`. Fails open (see `fail_open_plan`) on any error.

    allowed_tags is still passed as a short, role-filtered list of bare tag names
    here (not full descriptions - those are already in the Backbone's own static
    catalog every call carries) - this is Planning's actual RBAC-narrowing input:
    "which of these already-described domains can THIS role's plan actually use
    this turn," not a re-description of what each one means.

    is_media (2026-09-15, closing a real gap - a billed test caught Planning
    adding a spurious media_analysis step for a PLAIN TEXT turn): Planning
    previously had zero ground truth about whether this turn actually has media
    attached - it only ever saw Intent Identification's free-form prose, which
    is not a reliable signal, plus a misleading ordering example in planning.md
    that biased the model toward media_analysis whenever a message merely
    described something extraction-shaped (e.g. a name + an amount). Stating
    this plainly, as a fact rather than inferred prose, is the actual fix -
    planning.md's own rule then tells the model to trust it."""
    try:
        media_status = (
            "This turn has media attached." if is_media
            else "This turn has NO media attached - it is a plain text message."
        )
        raw_text = orchestrator.call_capability_step(
            tag=CapabilityTag.PLANNING,
            request=request,
            accumulated_context=(
                f"Intent Identification determined: {intent_text}\n\n"
                f"{media_status}\n\n"
                f"Capabilities available to this role this turn: "
                f"{', '.join(t.value for t in allowed_tags)}\n\n"
                "Respond with a JSON object: {\"steps\": [{\"capability\": <tag>, \"note\": <str>}, ...]} "
                "(steps may be empty)."
            ),
        )
        raw = json.loads(raw_text)
        return parse_plan(raw, allowed_tags)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Planning call failed, falling open to every allowed capability: %s", exc)
        return fail_open_plan(allowed_tags)
