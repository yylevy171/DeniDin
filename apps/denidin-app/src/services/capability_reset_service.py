"""
Capability idle-reset service (Feature 063, 2026-09-24 "resolution" redesign).

A background scheduled task - NOT triggered by any inbound message - that
returns idle chats to the plain backbone: any chat whose loaded capabilities
(`Session.active_capabilities` / `Session.active_flows`) are non-empty and whose last activity
(`Session.last_active`, refreshed on every message sent OR received) is older
than `config.capabilities_reset_minutes` gets both sets cleared. No
notification is sent to anyone and none is needed: instructions AND tools are
rebuilt fresh from the persisted set on every model call, so the model's next
real turn simply sees a plain backbone.

Structurally mirrors services/accounting_reconciliation_service.py (own
BackgroundScheduler + IntervalTrigger, `<= 0` means inactive - no scheduler
started). The interval here is fixed at one minute (the sweep's own
granularity); `capabilities_reset_minutes` is the IDLE THRESHOLD, not the
polling period. Top-level config field, deliberately not a feature flag.
"""
from datetime import datetime, timedelta
from typing import Any, Optional

# apscheduler ships no type stubs - hence the import-untyped ignore on its imports.
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from src.utils.logger import get_logger
from src.utils.time_utils import now_local

logger = get_logger(__name__)

CAPABILITY_RESET_JOB_ID = "capability_idle_reset_sweep"
SWEEP_INTERVAL_MINUTES = 1


def sweep_idle_capabilities(session_manager: Any, idle_minutes: int,
                             now: Optional[datetime] = None) -> int:
    """Clears the loaded flow and capability sets of every chat idle for at least
    `idle_minutes`. Returns how many chats were reset. Never raises - one bad
    session must not stop the rest of the sweep."""
    now = now or now_local()
    threshold = timedelta(minutes=idle_minutes)
    reset_count = 0
    for chat_id in session_manager.known_chats():
        try:
            session = session_manager.get_session(chat_id)
            if not session.active_capabilities and not session.active_flows:
                continue
            last_active = datetime.fromisoformat(session.last_active)
            if now - last_active < threshold:
                continue
            loaded_capabilities = list(session.active_capabilities)
            loaded_flows = list(session.active_flows)
            session_manager.set_active_capabilities(chat_id, [])
            session_manager.set_active_flows(chat_id, [])
            reset_count += 1
            logger.info(
                "[063] Idle reset: chat=%s unloaded flows=%s capabilities=%s after %s idle (threshold %d min)",
                chat_id, loaded_flows, loaded_capabilities, now - last_active, idle_minutes,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("[063] Idle reset failed for chat=%s: %s", chat_id, exc, exc_info=True)
    return reset_count


def start_capability_reset_scheduler(global_context: Any, reset_minutes: int,
                                      trigger: Any = None) -> Optional[BackgroundScheduler]:
    """Creates, starts, and returns the single shared scheduler for the idle
    sweep, or None when `reset_minutes` <= 0 (feature inactive, nothing
    started). `trigger` is a testability seam only (same convention as the
    other services) - production callers never pass it."""
    if reset_minutes <= 0:
        logger.info("[063] capabilities_reset_minutes=0 (or unset) - idle capability reset is inactive")
        return None
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: sweep_idle_capabilities(global_context.session_manager, reset_minutes),
        trigger=trigger or IntervalTrigger(minutes=SWEEP_INTERVAL_MINUTES),
        id=CAPABILITY_RESET_JOB_ID,
        max_instances=1,
    )
    scheduler.start()
    logger.info("[063] Idle capability reset scheduler started (threshold=%d min)", reset_minutes)
    return scheduler
