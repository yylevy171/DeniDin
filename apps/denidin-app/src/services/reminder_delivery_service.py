"""
Reminder delivery service (Feature 054).

The single shared background mechanism that checks for due reminder occurrences
and delivers them as proactive WhatsApp messages - structurally similar in spirit
to services/cleanup_service.py's SessionCleanupThread/run_startup_cleanup shape
(one shared worker function, called both periodically and once at startup for
catch-up), but driven by APScheduler's BackgroundScheduler + a single
CronTrigger(minute='*/5') job instead of a hand-rolled sleep loop, so the sweep
is genuinely wall-clock-aligned (:00/:05/.../:55) rather than drifting from an
arbitrary process-start offset - see
specs/in-progress/054-reminders-functionality-mgmt/contracts/reminder-delivery.md.

Exactly one shared delivery mechanism for the whole process - never one job/
thread per reminder (the original design guardrail).
"""
from datetime import datetime, timedelta
from typing import Any, Optional

# type: ignore[import-untyped] on both - no stub package exists for apscheduler
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

from src.utils.logger import get_logger
from src.utils.time_utils import now_local
from src.utils.green_api_bot import send_proactive_message

logger = get_logger(__name__)

# Two different lookback bounds for the SAME shared _sweep_due_reminders
# worker, split 2026-08-18 (user decision, after a real test failure exposed
# the single-24h-bound design's actual tradeoff):
#
# - STARTUP_SWEEP_LOOKBACK (24h): used ONLY by run_startup_reminder_sweep's
#   one-time boot call. Generous on purpose - it's the only mechanism that
#   recovers reminders that became due while the process wasn't running at
#   all (crash, redeploy, container restart), and downtime can genuinely
#   span hours.
# - PERIODIC_SWEEP_LOOKBACK (1h): used by the recurring APScheduler tick
#   (every 5 min under normal operation). Deliberately narrow - a wide
#   window on every single tick means that if `fired_occurrences` bookkeeping
#   is ever wrong (a "sent" row that failed to persist correctly, for
#   whatever reason), the same already-delivered occurrence could be
#   silently re-picked-up and re-sent on every subsequent tick for as long
#   as the window stays open - up to 24h of repeated resends with the old
#   single-bound design. 1h is still generous enough to absorb a handful of
#   missed/slow ticks (the tick cadence itself is 5 min) without ever
#   reaching back to "yesterday."
#
# already_fired filtering (ReminderManager.get_due_occurrences) is what
# actually prevents re-delivery within either window when that bookkeeping
# IS correct - these bounds only cap how far back a single sweep query looks,
# and now also cap the blast radius if that bookkeeping is ever wrong.
STARTUP_SWEEP_LOOKBACK = timedelta(hours=24)
PERIODIC_SWEEP_LOOKBACK = timedelta(hours=1)

REMINDER_SWEEP_JOB_ID = "reminder_sweep"


def _deliver_one_occurrence(
    occurrence: Any, bot: Any, godfather_chat_id: str, reminder_manager: Any,
    session_manager: Any, user_manager: Any, godfather_phone: str, log_prefix: str,
) -> None:
    """Deliver a single due occurrence: send, record the firing, persist to
    session history. Split out of _sweep_due_reminders purely to keep that
    function's local-variable count down - no independent call site.
    """
    message_text = occurrence["message_text"]
    id_message = send_proactive_message(bot, godfather_chat_id, message_text)
    if id_message is None:
        logger.error(
            f"{log_prefix}Failed to deliver reminder {occurrence['reminder_id']!r} "
            f"(due {occurrence['occurrence_datetime'].isoformat()}) - left pending, "
            "will retry next sweep"
        )
        return

    try:
        reminder_manager.record_occurrence_fired(
            reminder_id=occurrence["reminder_id"],
            occurrence_datetime=occurrence["occurrence_datetime"],
            message_text_sent=message_text,
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            f"{log_prefix}Delivered reminder {occurrence['reminder_id']!r} but failed to "
            f"record the firing - it may be re-delivered on the next sweep: {e}", exc_info=True
        )

    if session_manager is not None:
        try:
            godfather_user = user_manager.get_user(godfather_phone)
            session_manager.add_message_with_token_limit(
                chat_id=godfather_chat_id, role="assistant", content=message_text,
                user_role=godfather_user.role, token_limit=godfather_user.token_limit,
                recipient=godfather_chat_id,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                f"{log_prefix}Failed to persist delivered reminder "
                f"{occurrence['reminder_id']!r} to session history: {e}", exc_info=True
            )

    logger.info(
        f"{log_prefix}Delivered reminder {occurrence['reminder_id']!r} to "
        f"{godfather_chat_id} (idMessage={id_message})"
    )


def _sweep_due_reminders(
    global_context: Any, bot: Any, log_prefix: str = "", now: Optional[datetime] = None,
    lookback: timedelta = PERIODIC_SWEEP_LOOKBACK,
) -> None:
    """Shared worker: find every not-yet-fired due occurrence across all active
    reminders and deliver it. Shared by both the periodic APScheduler job and
    run_startup_reminder_sweep's boot-time catch-up call - one implementation,
    two call sites, same pattern as cleanup_service.py's
    _process_session_cleanup.

    One-time and recurring reminders share the identical path here - no
    special-casing (ReminderManager.get_due_occurrences already unifies them).

    `now` is a testability seam only - production callers must never pass it
    (leaving it None yields the real now_local() below, unchanged). It lets a
    test simulate "the sweep tick that runs exactly at/around a real
    reminder's due time" deterministically - by reading back the reminder's
    actual persisted due time and passing simulated `now` values around it -
    instead of either waiting real wall-clock minutes or faking the OS clock
    under a live scheduler thread (which doesn't work - see
    reminder-delivery.md/tasks.md for why). This does not change what
    production runs; the real now_local() path is exercised identically to
    before whenever `now` is left unset.

    `lookback` defaults to PERIODIC_SWEEP_LOOKBACK (the periodic tick's real
    production value) - run_startup_reminder_sweep is the one caller that
    overrides it to STARTUP_SWEEP_LOOKBACK explicitly. A test wanting to
    simulate a startup catch-up sweep specifically (rather than an ordinary
    periodic tick) must pass STARTUP_SWEEP_LOOKBACK explicitly too.
    """
    reminder_manager = global_context.ai_handler.reminder_manager
    config = global_context.config

    now = now or now_local()
    try:
        due = reminder_manager.get_due_occurrences(now - lookback, now)
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"{log_prefix}Failed to query due reminder occurrences: {e}", exc_info=True)
        return

    if not due:
        return

    godfather_phone = getattr(config, "godfather_phone", None)
    if not godfather_phone:
        logger.error(
            f"{log_prefix}No godfather_phone configured - cannot deliver "
            f"{len(due)} due reminder occurrence(s)"
        )
        return
    # FR-008: always the godfather's own 1:1 chat, never a per-reminder field -
    # computed here once per sweep tick, regardless of which chat/role created
    # or last modified any given reminder.
    godfather_chat_id = f"{godfather_phone}@c.us"

    for occurrence in due:
        _deliver_one_occurrence(
            occurrence, bot, godfather_chat_id, reminder_manager,
            global_context.session_manager, global_context.ai_handler.user_manager,
            godfather_phone, log_prefix,
        )


def run_startup_reminder_sweep(global_context: Any, bot: Any) -> None:
    """Runs synchronously on the main thread during initialize_app(), BEFORE
    the periodic scheduler starts - catches anything that became due while the
    process wasn't running (container restart), mirroring
    cleanup_service.py's run_startup_cleanup precedent.

    The ONE call site that uses STARTUP_SWEEP_LOOKBACK (24h) rather than the
    periodic tick's narrower PERIODIC_SWEEP_LOOKBACK (1h) - see that
    constant's docstring above for why the two are split.
    """
    logger.info("[054] Running startup reminder sweep (catch-up for any missed window)")
    _sweep_due_reminders(global_context, bot, log_prefix="[STARTUP] ", lookback=STARTUP_SWEEP_LOOKBACK)


def start_reminder_scheduler(
    global_context: Any, bot: Any, sweep_interval_minutes: int = 5, trigger: Any = None
) -> BackgroundScheduler:
    """Creates, starts, and returns the single shared APScheduler instance for
    the reminder delivery sweep - exactly ONE job for the whole process, never
    one per reminder. Callers (denidin.py) MUST call run_startup_reminder_sweep
    BEFORE this (catch-up happens once, synchronously, before the periodic job
    exists), and MUST call .shutdown() on the returned scheduler on process exit.

    `trigger` is a testability seam only - production callers must never pass
    it (leaving it None yields the real wall-clock-aligned CronTrigger below,
    unchanged). It exists so a unit test can prove the real add_job()+
    BackgroundScheduler wiring genuinely invokes _sweep_due_reminders on its
    own, on a real (if compressed) trigger, without waiting up to 60 real
    seconds for a CronTrigger's minute boundary - e.g. a 2-second
    IntervalTrigger. This does not change what production runs; the default
    CronTrigger(minute=f"*/{sweep_interval_minutes}") path is exercised
    identically to before whenever trigger is left unset.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        # Explicit lookback=PERIODIC_SWEEP_LOOKBACK, even though it's also
        # the parameter's own default - this is the one production call site
        # that MUST use the periodic (1h) bound, never the startup (24h) one,
        # so it's spelled out rather than relying on the default holding.
        func=lambda: _sweep_due_reminders(global_context, bot, lookback=PERIODIC_SWEEP_LOOKBACK),
        trigger=trigger or CronTrigger(minute=f"*/{sweep_interval_minutes}"),
        id=REMINDER_SWEEP_JOB_ID,
        max_instances=1,  # a slow tick must not overlap the next one
    )
    scheduler.start()
    logger.info(
        f"[054] Reminder delivery scheduler started (every {sweep_interval_minutes} min, "
        "wall-clock-aligned)"
    )
    return scheduler
