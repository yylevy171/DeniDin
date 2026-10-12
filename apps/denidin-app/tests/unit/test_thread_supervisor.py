"""Feature 067 (REQ-RMH-036): ThreadSupervisor restarts dead threads, trips health on repeats."""
import logging

from src.services.thread_supervisor import ThreadSupervisor
from src.utils.bounded_queue import QueueSettings


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class Fake:
    def __init__(self, alive=True):
        self.alive = alive
        self.restarts = 0

    def restart(self):
        self.restarts += 1
        self.alive = True


def _sup(max_restarts=2, window=100.0, clock=None):
    return ThreadSupervisor(QueueSettings(thread_max_restarts=max_restarts, thread_restart_window_seconds=window),
                            clock=clock or Clock())


def test_alive_thread_untouched():
    f = Fake()
    sup = _sup()
    sup.register("dispatcher", lambda: f.alive, f.restart)
    assert sup.check() == [] and f.restarts == 0 and sup.all_alive()


def test_dead_thread_is_logged_critical_and_restarted(caplog):
    f = Fake(alive=False)
    sup = _sup()
    sup.register("dispatcher", lambda: f.alive, f.restart)
    with caplog.at_level(logging.CRITICAL):
        assert sup.check() == ["dispatcher"]
    assert f.restarts == 1 and f.alive
    assert any(r.levelno == logging.CRITICAL and "dispatcher" in r.getMessage() for r in caplog.records)


def test_repeated_deaths_in_window_make_unhealthy_and_old_ones_age_out():
    clock = Clock()
    f = Fake()
    sup = _sup(max_restarts=2, window=100, clock=clock)
    sup.register("actor", lambda: f.alive, f.restart)
    for _ in range(3):
        f.alive = False
        sup.check()
    assert not sup.healthy()
    clock.now += 101
    assert sup.healthy()


def test_failed_restart_is_unhealthy():
    sup = _sup()
    sup.register("actor", lambda: False, lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    sup.check()
    assert not sup.healthy()


def test_all_alive_false_when_a_thread_is_dead_now():
    f = Fake(alive=False)
    sup = _sup()
    sup.register("x", lambda: f.alive, f.restart)
    assert not sup.all_alive()
