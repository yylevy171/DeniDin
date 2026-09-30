"""
Capability Audit Log (Feature 063, added 2026-09-16).

INFO-level, structured record of every domain tool dispatch the Backbone
orchestrator actually makes - what capability, with what note, and what
actually happened (success/failure + the real detail text). Added after a
real incident: a `create_reminder` execution failure (CAPABILITIES_SANITY.md
T3/T4, 2026-09-16) was invisible anywhere except a bare python ERROR log line
buried in general app output - no structured record of the attempt existed,
and a billed test that should have failed on it passed anyway (its own
assertion was too weak to notice). The user's own framing: "It cant be that
the tool failed and the test passed. That just cant happen."

Complements `wire_log.py` (wire-level: what literally crossed the
WhatsApp boundary) with the layer in between - one capability dispatch, its
outcome, and why - so "why did this fail" is always answerable from logs
alone, without re-running anything. Call `log_capability_action` at exactly
one place, `BackboneOrchestrator._dispatch_orchestration_tool`'s
orchestration loop's local-tool dispatch - every domain capability, not just reminders,
routes through there, so this file needs no per-capability wiring.
"""
from typing import List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


def log_capability_action(capability: str, note: str, outcome: str, detail: Optional[str] = None) -> None:
    """Logs one domain tool dispatch's outcome.

    `outcome` is a short free-text label ('success', 'failure', 'exception') -
    not a rigid enum, just readable; classification is necessarily best-effort
    (capability handlers return plain strings, not a structured result type),
    so this is a diagnostic aid, not a source of truth to branch logic on.
    `detail` is the actual result/error text returned to the model, in full,
    never truncated - this IS what closes the loop between "the tool failed"
    and "the test/human can see exactly why" from logs alone.

    Never raises - audit logging must never be the reason a real turn fails.
    """
    try:
        logger.info(
            f"[CAPABILITY-AUDIT] capability={capability!r} outcome={outcome!r} "
            f"note={note!r} detail={detail!r}"
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[CAPABILITY-AUDIT] failed to log capability action: {e}", exc_info=True)


def log_loading_action(action: str, kind: str, requested: List[str], *, now_loaded_flows: List[str],
                       now_loaded_capabilities: List[str], planning_status: Optional[str] = None) -> None:
    """Logs one flow/capability load/unload/reset - the record of the model's
    own routing decisions ("why did it load THAT flow / skip this capability").

    `action` is 'load'/'unload'/'reset', `kind` is 'flow'/'capability'/'all',
    `requested` is exactly what the model asked for, and the two `now_loaded_*`
    lists are the full resulting sets. `planning_status` is the model's most
    recent `record_planning_status` text this turn (its own stated reasoning),
    when it has recorded one - logged at INFO so the decision and its stated
    why sit on one line. The DEBUG line repeats the full sets separately so
    INFO stays greppable and DEBUG is complete.

    Never raises - audit logging must never be the reason a real turn fails.
    """
    try:
        logger.info(
            f"[FLOW-AUDIT] action={action!r} kind={kind!r} requested={requested!r} "
            f"flows_now={now_loaded_flows!r} capabilities_now={now_loaded_capabilities!r} "
            f"planning_status={planning_status!r}"
        )
        logger.debug(
            f"[FLOW-DEBUG] {action} {kind}: requested={requested!r}; "
            f"loaded flows ({len(now_loaded_flows)})={now_loaded_flows!r}; "
            f"loaded capabilities ({len(now_loaded_capabilities)})={now_loaded_capabilities!r}"
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[FLOW-AUDIT] failed to log loading action: {e}", exc_info=True)
