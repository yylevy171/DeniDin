"""Feature 067 (REQ-RMH-034/035): QueueMonitor warnings, rate limit, health booleans."""
import logging

from src.services.queue_monitor_service import QueueMonitor, start_queue_monitor_scheduler, QUEUE_MONITOR_JOB_ID
from src.utils.bounded_queue import BoundedQueue, QueueSettings


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def _monitor(queues, clock=None):
    mon = QueueMonitor(QueueSettings(stall_seconds=30), clock=clock or Clock())
    mon.register(lambda: queues)
    return mon


def test_warns_when_size_reaches_warning_size(caplog):
    q = BoundedQueue("intake:c1", 10, warn_size=2)
    q.put_or_raise(1)
    q.put_or_raise(2)
    with caplog.at_level(logging.WARNING):
        _monitor([q]).check()
    assert any("QUEUE GROWING" in r.getMessage() and "intake:c1" in r.getMessage() for r in caplog.records)


def test_warns_when_stalled(caplog):
    clock = Clock()
    q = BoundedQueue("session", 10)
    q.put_or_raise(1)
    q.last_progress_at = clock.now - 100
    with caplog.at_level(logging.WARNING):
        _monitor([q], clock).check()
    assert any("QUEUE STALLED" in r.getMessage() for r in caplog.records)


def test_warnings_are_rate_limited_per_queue_and_kind(caplog):
    clock = Clock()
    q = BoundedQueue("session", 10, warn_size=1)
    q.put_or_raise(1)
    mon = _monitor([q], clock)
    with caplog.at_level(logging.WARNING):
        mon.check()
        mon.check()
        clock.now += 61
        mon.check()
    assert sum("QUEUE GROWING" in r.getMessage() for r in caplog.records) == 2


def test_info_depths_only_when_non_empty(caplog):
    q = BoundedQueue("session", 10)
    mon = _monitor([q])
    with caplog.at_level(logging.INFO):
        mon.check()
        assert not any("queue depths" in r.getMessage() for r in caplog.records)
        q.put_or_raise(1)
        mon.check()
    assert any("queue depths" in r.getMessage() and "session=1/10" in r.getMessage() for r in caplog.records)


def test_health_booleans():
    clock = Clock()
    q = BoundedQueue("q", 2)
    mon = _monitor([q], clock)
    assert mon.within_limits() and mon.not_stalled()
    q.put_or_raise(1)
    q.put_or_raise(2)  # full
    assert not mon.within_limits()
    q.last_progress_at = clock.now - 100
    assert not mon.not_stalled()


def test_dropped_item_marks_not_within_limits():
    q = BoundedQueue("q", 1)
    q.put_or_raise(1)
    try:
        q.put_or_raise(2)
    except Exception:  # noqa: BLE001
        pass
    q.get_nowait()
    assert not _monitor([q]).within_limits()


def test_sources_are_re_evaluated_each_check():
    queues = []
    mon = _monitor(queues)
    assert mon.within_limits()
    q = BoundedQueue("late", 1)
    q.put_or_raise(1)
    queues.append(q)
    assert not mon.within_limits()


def test_scheduler_registers_job():
    sched = start_queue_monitor_scheduler(_monitor([]), QueueSettings())
    try:
        assert sched.get_job(QUEUE_MONITOR_JOB_ID) is not None
    finally:
        sched.shutdown(wait=False)
