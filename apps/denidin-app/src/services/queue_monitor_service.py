"""Queue monitor (Feature 067, REQ-RMH-034/035).

Periodically inspects every registered ``BoundedQueue`` (the worker queue and the
SessionManager actor queue): WARNING when a queue reaches its
warning size or has items waiting with nothing taken for ``stall_seconds`` (rate
limited per queue and kind), and an INFO line with the numbers whenever any queue is
non-empty. ``/health`` reads the two booleans (``within_limits``, ``not_stalled``).
"""
import logging
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from src.utils.bounded_queue import BoundedQueue, QueueSettings

logger = logging.getLogger(__name__)

QUEUE_MONITOR_JOB_ID = "queue_monitor"
WARNING_REPEAT_SECONDS = 60.0

QueueSource = Callable[[], Iterable[BoundedQueue]]


class QueueMonitor:
    def __init__(self, settings: QueueSettings, clock: Callable[[], float] = time.monotonic) -> None:
        self._settings = settings
        self._clock = clock
        self._sources: List[QueueSource] = []
        self._last_warned: Dict[Tuple[str, str], float] = {}

    def register(self, source: QueueSource) -> None:
        """``source()`` returns the queues to inspect (re-evaluated every check, so
        queues created later - a new chat - are picked up)."""
        self._sources.append(source)

    def _queues(self) -> List[BoundedQueue]:
        found: List[BoundedQueue] = []
        for source in self._sources:
            found.extend(source())
        return found

    def _warn(self, queue_name: str, kind: str, message: str) -> None:
        now = self._clock()
        last = self._last_warned.get((queue_name, kind))
        if last is not None and now - last < WARNING_REPEAT_SECONDS:
            return
        self._last_warned[(queue_name, kind)] = now
        logger.warning(message)

    def check(self) -> None:
        depths: List[str] = []
        for q in self._queues():
            size = q.size()
            if size:
                depths.append(f"{q.name}={size}/{q.maxsize} (high {q.high_water}, dropped {q.dropped})")
            if q.is_over_warn_size():
                self._warn(q.name, "size", f"QUEUE GROWING: {q.name} holds {size} of {q.maxsize} (warning at {q.warn_size})")
            if q.is_stalled(self._settings.stall_seconds, self._clock()):
                self._warn(q.name, "stall",
                           f"QUEUE STALLED: {q.name} holds {size} item(s) and nothing was taken for "
                           f"more than {self._settings.stall_seconds:g}s")
        if depths:
            logger.info("queue depths: %s", "; ".join(depths))

    def within_limits(self) -> bool:
        """No queue is full and none has dropped an item."""
        return all(q.has_room() and q.dropped == 0 for q in self._queues())

    def not_stalled(self) -> bool:
        now = self._clock()
        return not any(q.is_stalled(self._settings.stall_seconds, now) for q in self._queues())


def start_queue_monitor_scheduler(monitor: QueueMonitor, settings: QueueSettings,
                                  scheduler: Optional[Any] = None) -> BackgroundScheduler:
    """Runs ``monitor.check`` every ``queue_check_interval_seconds`` on a BackgroundScheduler."""
    sched = scheduler or BackgroundScheduler()
    sched.add_job(monitor.check, IntervalTrigger(seconds=settings.queue_check_interval_seconds),
                  id=QUEUE_MONITOR_JOB_ID, replace_existing=True, max_instances=1, coalesce=True)
    if scheduler is None:
        sched.start()
    return sched
