"""Feature 067: /health carries ONE `intake_pipeline` check (queues + threads) that counts toward `status`."""
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


def _check(mon, sup):
    return build_health_check_fns(queue_monitor=mon, thread_supervisor=sup)["intake_pipeline"]()


def test_intake_pipeline_is_ok_when_everything_is_ok():
    _q, mon, sup = _parts()
    assert _check(mon, sup) is True


def test_intake_pipeline_fails_when_a_thread_is_dead():
    _q, mon, sup = _parts(thread_alive=False)
    assert _check(mon, sup) is False


def test_intake_pipeline_fails_when_a_queue_is_over_its_limit():
    q, mon, sup = _parts()
    q.dropped = 1
    q.put_or_raise(1)
    assert _check(mon, sup) is False


def test_it_is_a_status_check_not_a_report_only_field():
    _q, mon, sup = _parts()
    assert "intake_pipeline" in build_health_check_fns(queue_monitor=mon, thread_supervisor=sup)
    assert "intake_pipeline" not in build_health_info_fns()
    assert "intake_pipeline" not in build_health_check_fns()
