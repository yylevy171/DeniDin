"""Thread supervisor (Feature 067, REQ-RMH-036).

Something has to notice when the dispatcher thread or the SessionManager actor thread
dies - otherwise the poller keeps storing and queuing while nothing is ever handled.
Each supervised thread registers an ``is_alive`` probe and a ``restart`` callable; a
dead thread is logged CRITICAL and restarted (the queues survive, so nothing queued is
lost). More than ``supervisor_max_restarts`` deaths inside ``supervisor_window_seconds``
makes ``healthy()`` False, which ``/health`` reports so the existing prober restarts
the container.
"""
import logging
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from src.utils.bounded_queue import QueueSettings

logger = logging.getLogger(__name__)

THREAD_SUPERVISOR_JOB_ID = "thread_supervisor"


class ThreadSupervisor:
    def __init__(self, settings: QueueSettings, clock: Callable[[], float] = time.monotonic) -> None:
        self._settings = settings
        self._clock = clock
        self._threads: Dict[str, Dict[str, Callable[[], Any]]] = {}
        self._deaths: Deque[float] = deque()
        self._restart_failed = False

    def register(self, name: str, is_alive: Callable[[], bool], restart: Callable[[], None]) -> None:
        self._threads[name] = {"is_alive": is_alive, "restart": restart}

    def check(self) -> List[str]:
        """Restart every dead thread; returns the names found dead."""
        dead: List[str] = []
        for name, probes in self._threads.items():
            if probes["is_alive"]():
                continue
            dead.append(name)
            self._deaths.append(self._clock())
            logger.critical("THREAD DIED: %s - restarting it", name)
            try:
                probes["restart"]()
            except Exception:  # pylint: disable=broad-except
                self._restart_failed = True
                logger.critical("THREAD RESTART FAILED: %s", name, exc_info=True)
        self._trim()
        return dead

    def _trim(self) -> None:
        horizon = self._clock() - self._settings.supervisor_window_seconds
        while self._deaths and self._deaths[0] < horizon:
            self._deaths.popleft()

    def healthy(self) -> bool:
        """False after a failed restart or too many deaths in the window."""
        self._trim()
        if self._restart_failed:
            return False
        return len(self._deaths) <= self._settings.supervisor_max_restarts

    def all_alive(self) -> bool:
        """Health check: every supervised thread is alive now AND the death budget holds."""
        return self.healthy() and all(p["is_alive"]() for p in self._threads.values())


def start_thread_supervisor_scheduler(supervisor: ThreadSupervisor, settings: QueueSettings,
                                      scheduler: Optional[Any] = None) -> BackgroundScheduler:
    sched = scheduler or BackgroundScheduler()
    sched.add_job(supervisor.check, IntervalTrigger(seconds=settings.supervisor_interval_seconds),
                  id=THREAD_SUPERVISOR_JOB_ID, replace_existing=True, max_instances=1, coalesce=True)
    if scheduler is None:
        sched.start()
    return sched
