"""Nightly daily-summary roll (Feature 070, US2).

Structurally mirrors ``services/reminder_delivery_service.py`` /
``services/accounting_reconciliation_service.py``: one shared worker function
called both periodically (APScheduler ``BackgroundScheduler`` + ``CronTrigger``
at 02:00 Israel-local) and once at startup for catch-up, a ``trigger`` testability
seam, ``_sweep_*(global_context, *, now=None, lookback_days=None, log_prefix="")``,
**wired in ``denidin.py __main__`` only** (D1), errors never escape the job.

Per chat, per past calendar day within the lookback window: summarize that day's
messages into **exactly one** ChromaDB ``daily_summary`` record via the sanitizing
``MemoryManager.remember()`` path (no raw ``client.get_collection()`` anywhere -
bugfix-035 H1), idempotent via ``RollMarkerStore`` (``PRIMARY KEY(chat, date)``,
claim-first ``claimed`` -> ``committed``). Empty days get a marker and make no
OpenAI call. A bounded startup catch-up sweep
(``memory.roll.catchup_lookback_days``) covers days missed while down; anything
older than that is the US4 backfill's responsibility.

Retry semantics (contract §"Retry semantics"): there is **no per-item retry
counter**. A ``(chat, date)`` that fails to ``commit`` is left un-committed and
retried on every subsequent nightly tick (``lookback_days=2``) and every startup
sweep (``lookback_days=catchup_lookback_days``), until it ages past the lookback -
then only the backfill will touch it.
"""
from datetime import timedelta
from typing import Any, Optional

# no stub package exists for apscheduler - import-untyped ignored per import
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

from src.handlers.summarizer import summarize_conversation
from src.managers.memory_collections import collection_name_for_chat
from src.utils.logger import get_logger
from src.utils.time_utils import LOCAL_TZ, local_calendar_date, now_local

logger = get_logger(__name__)

DAILY_ROLL_JOB_ID = "daily_summary_roll"

# The periodic tick looks back 2 days (yesterday + 1-day slack for a tick that
# slips past midnight). Narrow on purpose - blast-radius cap if a marker write
# ever fails. The startup sweep uses catchup_lookback_days instead.
_PERIODIC_LOOKBACK_DAYS = 2

_DEFAULT_CATCHUP_LOOKBACK_DAYS = 21
_BACKSTOP_TOKENS = 100000


def _roll_config(global_context: Any) -> dict:
    return (global_context.config.memory or {}).get("roll", {}) or {}


def _window_days(global_context: Any) -> int:
    return int((global_context.config.memory or {}).get("session", {}).get("window_days", 14))


def _roll_one_chat_day(global_context: Any, chat: str, date, *, source: str, log_prefix: str) -> None:
    """Roll exactly one (chat, calendar-date) into a daily_summary record.
    Raises on an unrecoverable failure (summary/remember) - the caller's
    per-(chat, date) try/except logs it and leaves the marker un-committed for
    the next sweep to retry."""
    ai_handler = global_context.ai_handler
    store = ai_handler.roll_marker_store
    date_str = date.isoformat()

    if store.is_rolled(chat, date_str):
        return
    if not store.try_claim(chat, date_str, source):
        return

    session = global_context.session_manager.get_session(chat)
    messages = global_context.session_manager.get_messages_for_local_date(session, date)

    if not messages:
        store.commit(chat, date_str, message_count=0, memory_id=None)
        logger.info("%sdaily-roll: %s %s empty - marker only, no summary", log_prefix, chat, date_str)
        return

    summary = summarize_conversation(ai_handler.client, ai_handler.config.ai_model, messages)
    collection_name = collection_name_for_chat(chat)
    collection = ai_handler.memory_manager.get_or_create_collection(collection_name)
    try:
        collection.delete(where={"$and": [
            {"type": {"$eq": "daily_summary"}},
            {"chat": {"$eq": chat}},
            {"date": {"$eq": date_str}},
        ]})
    except Exception as e:  # pylint: disable=broad-except
        logger.warning("%sdaily-roll: pre-delete of an existing summary failed (%s) - continuing", log_prefix, e)

    memory_id = ai_handler.memory_manager.remember(
        summary,
        collection_name,
        metadata={
            "type": "daily_summary",
            "chat": chat,
            "date": date_str,
            "scope": "PRIVATE",
            "user_phone": chat,
            "message_count": len(messages),
            "source": source,
        },
    )
    store.commit(chat, date_str, message_count=len(messages), memory_id=memory_id)
    logger.info(
        "%sdaily-roll: %s %s -> daily_summary %s (%d messages)",
        log_prefix, chat, date_str, memory_id, len(messages),
    )


def _sweep_daily_roll(
    global_context: Any,
    *,
    now=None,
    lookback_days: Optional[int] = None,
    log_prefix: str = "",
) -> None:
    now = now or now_local()
    today = local_calendar_date(now)
    if lookback_days is None:
        lookback_days = _PERIODIC_LOOKBACK_DAYS
    source = "catch-up" if log_prefix.strip().upper().startswith("[STARTUP") else "daily-roll"

    # Candidate dates: yesterday .. lookback_days back (never today - the current
    # day is still in the verbatim window and not yet complete).
    dates = [today - timedelta(days=k) for k in range(1, lookback_days + 1)]

    session_manager = global_context.session_manager
    try:
        chats = session_manager.known_chats()
    except Exception as e:  # pylint: disable=broad-except
        logger.error("%sdaily-roll: could not enumerate chats: %s", log_prefix, e, exc_info=True)
        return

    for chat in chats:
        for date in dates:
            try:
                _roll_one_chat_day(global_context, chat, date, source=source, log_prefix=log_prefix)
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    "%sdaily-roll: %s %s failed - left un-committed, will retry: %s",
                    log_prefix, chat, date.isoformat(), e, exc_info=True,
                )
        # Once per chat, after the roll loop: physically archive aged / backstopped
        # messages (US3). Never deletes - rename into archived/. Per-chat try/except.
        try:
            session = session_manager.get_session(chat)
            session_manager.archive_aged_and_backstopped_messages(
                session,
                now=now,
                window_days=_window_days(global_context),
                max_backstop_tokens=_BACKSTOP_TOKENS,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("%sdaily-roll: archive step for %s failed: %s", log_prefix, chat, e, exc_info=True)


def run_startup_daily_roll_sweep(global_context: Any) -> None:
    """Synchronous, main-thread, called in ``__main__`` before
    ``start_daily_roll_scheduler``. Catches up on every past day within
    ``catchup_lookback_days`` that was missed while the process was down."""
    lookback = int(_roll_config(global_context).get("catchup_lookback_days", _DEFAULT_CATCHUP_LOOKBACK_DAYS))
    logger.info("[070] Running startup daily-summary roll sweep (catch-up, lookback=%d days)", lookback)
    _sweep_daily_roll(global_context, lookback_days=lookback, log_prefix="[STARTUP] ")


def start_daily_roll_scheduler(
    global_context: Any, *, roll_hour: int = 2, trigger: Any = None
) -> BackgroundScheduler:
    """Create, start, and return the single shared scheduler for the nightly
    roll - exactly one job for the whole process. ``roll_hour`` from
    ``config.memory['roll']['hour']`` (default 2). ``trigger`` is a testability
    seam only - production callers must never pass it (a short
    ``IntervalTrigger`` in tests). ``CronTrigger(hour=N, minute=0)`` is
    wall-clock-aligned and valid for any hour 0-23 (unlike an interval minute
    field - real bug 2026-08-21)."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: _sweep_daily_roll(global_context, lookback_days=_PERIODIC_LOOKBACK_DAYS),
        trigger=trigger or CronTrigger(hour=roll_hour, minute=0, timezone=LOCAL_TZ),
        id=DAILY_ROLL_JOB_ID,
        max_instances=1,
    )
    scheduler.start()
    logger.info("[070] Daily-summary roll scheduler started (%02d:00 %s)", roll_hour, LOCAL_TZ)
    return scheduler
