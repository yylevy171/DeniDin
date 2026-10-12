"""Feature 067: /health carries thread liveness (counts toward status) and queue booleans (report-only)."""
from src.services.health_server import build_health_check_fns, build_health_info_fns
from src.services.queue_monitor_service import QueueMonitor
from src.services.thread_supervisor import ThreadSupervisor
from src.utils.bounded_queue import BoundedQueue, QueueSettings


def test_threads_alive_check_present_only_with_supervisor():
    assert "threads_alive" not in build_health_check_fns()
    sup = ThreadSupervisor(QueueSettings())
    sup.register("t", lambda: False, lambda: None)
    assert build_health_check_fns(thread_supervisor=sup)["threads_alive"]() is False


def test_queue_fields_are_info_only():
    q = BoundedQueue("q", 1)
    mon = QueueMonitor(QueueSettings())
    mon.register(lambda: [q])
    info = build_health_info_fns(queue_monitor=mon)
    assert set(info) == {"queues_within_limits", "queues_not_stalled"}
    assert info["queues_within_limits"]() is True
    assert "queues_within_limits" not in build_health_check_fns()
