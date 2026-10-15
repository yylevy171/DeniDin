"""DeniDinDispatcher (Feature 067, REQ-RMH-023/024/032): the one thread that handles messages.

It pulls the next item from the ``IntakeCoordinator`` and calls the injected
``dispatch(type_message, notification)`` - the same callable the replay player uses - and
nothing else: it knows nothing about Green API, a router or an HTTP session. A failure while
handling one item is logged, then it sleeps ``error_sleep_seconds`` (5 s, as the poller
does) and carries on with the next one; the thread only ends on ``stop()``.
"""
import threading
from typing import Any, Callable, Optional

from src.intake.intake_coordinator import IntakeCoordinator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DeniDinDispatcher:
    def __init__(self, coordinator: IntakeCoordinator, dispatch: Callable[[str, Any], None],
                 error_sleep_seconds: float = 5.0, poll_seconds: float = 0.5) -> None:
        self._coordinator = coordinator
        self._dispatch = dispatch
        self._error_sleep = error_sleep_seconds
        self._poll = poll_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start (or restart, after a death) the dispatcher thread."""
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="denidin-dispatcher", daemon=True)
        self._thread.start()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        logger.info("DeniDinDispatcher started")
        while not self._stop.is_set():
            try:
                item = self._coordinator.next_work_item(timeout=self._poll)
                if item is None:
                    continue
                self._dispatch(item.type_message, item.notification)
            except Exception:  # pylint: disable=broad-except - an item error never ends the thread
                logger.error("DeniDinDispatcher: handling an item failed; continuing with the next",
                             exc_info=True)
                self._stop.wait(self._error_sleep)
        logger.info("DeniDinDispatcher stopped")
