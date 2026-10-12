"""Feature 067: /health carries ONE report-only `intake_pipeline` value (queues + threads)."""
from src.services.health_server import build_health_check_fns, build_health_info_fns
from src.services.queue_monitor_service import QueueMonitor
from src.services.thread_supervisor import ThreadSupervisor
from src.utils.bounded_queue import BoundedQueue, QueueSettings


def _parts(thread_alive=True):
    q = BoundedQueue("q", 1)
    mon = QueueMonitor(QueueSettings())
    mon.register(lambda: [q])
    sup = ThreadSupervisor(QueueSettings())
    sup.register("t", lambda: thread_alive, lambda: None)
    return q, mon, sup


def test_intake_pipeline_is_ok_when_everything_is_ok():
    _q, mon, sup = _parts()
    assert build_health_info_fns(queue_monitor=mon, thread_supervisor=sup)["intake_pipeline"]() is True


def test_intake_pipeline_fails_when_a_thread_is_dead():
    _q, mon, sup = _parts(thread_alive=False)
    assert build_health_info_fns(queue_monitor=mon, thread_supervisor=sup)["intake_pipeline"]() is False


def test_intake_pipeline_fails_when_a_queue_is_over_its_limit():
    q, mon, sup = _parts()
    q.dropped = 1
    q.put_or_raise(1)
    assert build_health_info_fns(queue_monitor=mon, thread_supervisor=sup)["intake_pipeline"]() is False


def test_it_is_report_only_and_the_old_three_fields_are_gone():
    _q, mon, sup = _parts()
    info = build_health_info_fns(queue_monitor=mon, thread_supervisor=sup)
    assert set(info) == {"intake_pipeline"}
    assert "intake_pipeline" not in build_health_check_fns()
