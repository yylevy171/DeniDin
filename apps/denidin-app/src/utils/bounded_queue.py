"""Bounded, observable queue used by every cross-thread hand-off (Feature 067).

One queue technology for the whole feature (REQ-RMH-025): a thin wrapper around
``queue.Queue(maxsize)`` - whose internal locks are the only locks allowed - that
adds the hard limit (REQ-RMH-033: a full queue raises ``QueueLimitExceeded`` and the
item is dropped), and the numbers the monitor needs for warnings (REQ-RMH-034/035).
"""
import logging
import queue
import time
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class QueueLimitExceeded(Exception):
    """A queue was full: the item was dropped (REQ-RMH-033)."""


@dataclass(frozen=True)
class QueueSettings:
    """The ``message_queues`` config block, defaults applied (Feature 067)."""

    intake_max_per_chat: int = 50
    intake_max_total: int = 100
    session_max: int = 50
    warn_fraction: float = 0.3
    stall_seconds: float = 120.0
    monitor_interval_seconds: float = 2.0
    supervisor_interval_seconds: float = 60.0
    supervisor_max_restarts: int = 1
    supervisor_window_seconds: float = 100.0
    session_call_timeout_seconds: float = 10.0
    slow_call_seconds: float = 5.0

    @classmethod
    def from_config(cls, config: Any) -> "QueueSettings":
        block = getattr(config, "message_queues", None) or {}
        known = {name: block[name] for name in cls.__dataclass_fields__ if name in block}
        return cls(**known)

    def warn_size(self, maxsize: int) -> int:
        return max(1, int(maxsize * self.warn_fraction))


class BoundedQueue(Generic[T]):
    """``queue.Queue`` with a hard limit and the counters the monitor reads."""

    def __init__(self, name: str, maxsize: int, warn_size: Optional[int] = None) -> None:
        if maxsize < 1:
            raise ValueError(f"queue {name!r}: maxsize must be >= 1")
        self.name = name
        self.maxsize = maxsize
        self.warn_size = warn_size if warn_size is not None else max(1, maxsize // 2)
        self._queue: "queue.Queue[T]" = queue.Queue(maxsize=maxsize)
        self.dropped = 0
        self.high_water = 0
        self.last_progress_at = time.monotonic()

    def put_or_raise(self, item: T, item_id: str = "") -> None:
        """Enqueue ``item`` or raise ``QueueLimitExceeded`` (dropping it, ERROR log)."""
        was_empty = self._queue.qsize() == 0
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            self.note_drop(item_id)
            raise QueueLimitExceeded(f"queue {self.name!r} is full ({self.maxsize})") from None
        if was_empty:
            self.last_progress_at = time.monotonic()
        self.high_water = max(self.high_water, self._queue.qsize())

    def note_drop(self, item_id: str = "") -> None:
        """Record (ERROR log + counter) that an item was dropped because this queue is full."""
        self.dropped += 1
        logger.error(
            "QUEUE LIMIT EXCEEDED: queue=%s size=%d limit=%d item=%s - item dropped (dropped so far: %d)",
            self.name, self._queue.qsize(), self.maxsize, item_id or "?", self.dropped)

    def put_control(self, item: T) -> None:
        """Enqueue a control item (shutdown sentinel) ignoring the limit, blocking if full."""
        self._queue.put(item)

    def get(self, timeout: Optional[float] = None) -> T:
        """Blocking get; raises ``queue.Empty`` on timeout."""
        item = self._queue.get(timeout=timeout)
        self.last_progress_at = time.monotonic()
        return item

    def get_nowait(self) -> T:
        item = self._queue.get_nowait()
        self.last_progress_at = time.monotonic()
        return item

    def size(self) -> int:
        return self._queue.qsize()

    def has_room(self) -> bool:
        return self._queue.qsize() < self.maxsize

    def is_over_warn_size(self) -> bool:
        return self._queue.qsize() >= self.warn_size

    def is_stalled(self, stall_seconds: float, now: Optional[float] = None) -> bool:
        """Items are waiting but nothing has been taken for ``stall_seconds``."""
        if self._queue.qsize() == 0:
            return False
        current = time.monotonic() if now is None else now
        return current - self.last_progress_at > stall_seconds
