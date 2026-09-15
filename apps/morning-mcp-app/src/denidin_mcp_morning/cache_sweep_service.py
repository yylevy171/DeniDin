"""Periodic client-cache reconciliation sweep (Feature 072).

The single shared background mechanism that periodically fetches every real
Morning client (fetch_all_clients) and reconciles them into ClientCache -
catching renames/deletes made directly in Morning's own UI, which no
in-app event (add_client/update_client write-through, or a live
resolve_client_name miss) can ever observe on its own. Structurally mirrors
apps/denidin-app's service/*.py precedent (one shared APScheduler
BackgroundScheduler job, IntervalTrigger since the interval is a plain
user-configured minute count with no cron-step-range constraint to worry
about - see accounting_reconciliation_service.py's own docstring for why
IntervalTrigger, not CronTrigger, is the right choice for that shape).

Only started when feature_flags.morning_cache_enabled is true (server.py).
"""
from typing import Any, Optional

# type: ignore[import-untyped] - no stub package exists for apscheduler
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from .client_cache import ClientCache
from .morning_client import MorningClient
from .tools import fetch_all_clients
from .utils.logger import get_logger

logger = get_logger(__name__)

CACHE_SWEEP_JOB_ID = "client_cache_sweep"


def run_cache_sweep(client: MorningClient, cache: ClientCache, log_prefix: str = "") -> None:
    """One reconciliation tick: fetch every real Morning client, then
    reconcile the cache against that full roster. Synchronous - callers
    decide whether to run it once (startup catch-up) or on a timer."""
    clients = fetch_all_clients(client)
    cache.reconcile(clients)
    logger.info("%s[072] Client cache sweep reconciled %d client(s)", log_prefix, len(clients))


def run_startup_cache_sweep(client: MorningClient, cache: ClientCache) -> None:
    """Runs synchronously before the periodic scheduler starts - a cold
    cache (fresh container) is fully populated before the first request
    needs it, rather than waiting up to a full sweep interval."""
    logger.info("[072] Running startup client-cache sweep (catch-up)")
    run_cache_sweep(client, cache, log_prefix="[STARTUP] ")


def start_cache_sweep_scheduler(
    client: MorningClient,
    cache: ClientCache,
    interval_minutes: int,
    trigger: Any = None,
) -> Optional[BackgroundScheduler]:
    """Creates, starts, and returns the single shared APScheduler instance
    for the periodic client-cache sweep - exactly one job for the whole
    process. `trigger` is a testability seam only (production callers must
    never pass it - leaving it None yields the real IntervalTrigger).

    Returns None (no scheduler started) if `interval_minutes` is not a
    positive integer - mirrors accounting_reconciliation_service.py's
    update_freq_minutes<=0 convention."""
    if interval_minutes <= 0:
        logger.info(
            "[072] client_cache_sweep_interval_minutes<=0 - periodic cache "
            "sweep is inactive, no scheduler started"
        )
        return None

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: run_cache_sweep(client, cache),
        trigger=trigger or IntervalTrigger(minutes=interval_minutes),
        id=CACHE_SWEEP_JOB_ID,
        max_instances=1,  # a slow tick must not overlap the next one
    )
    scheduler.start()
    logger.info("[072] Client cache sweep scheduler started (every %d min)", interval_minutes)
    return scheduler
