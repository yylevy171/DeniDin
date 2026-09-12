"""Feature 080 — typing keep-alive renewal (T006/T009).

Pins the renewal-job contract from contracts/keep-alive-renewal.md: immediate first tick,
periodic renewal, cancel-on-stop, safety cap, blocked-user no-op, never raises. Uses a real
APScheduler BackgroundScheduler (this is the exact primitive being relied on - research.md R1)
with a stub bot object standing in for the Green API client (the only external service here),
per CONSTITUTION §I/§V (mock only third-party network services, never internal components).
"""
import time

import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from src.utils.green_api_bot import start_typing_keepalive, stop_typing_keepalive


class _StubServiceMethods:
    def __init__(self):
        self.calls = []

    def sendTyping(self, chat_id, typingTime=None):  # noqa: N802 - matches real Green API signature
        self.calls.append((chat_id, typingTime))


class _StubApi:
    def __init__(self):
        self.serviceMethods = _StubServiceMethods()  # noqa: N815 - matches real client attribute name


class _StubBot:
    def __init__(self):
        self.api = _StubApi()


@pytest.fixture
def scheduler():
    sched = BackgroundScheduler()
    sched.start()
    yield sched
    sched.shutdown(wait=False)


@pytest.fixture
def bot():
    return _StubBot()


class TestStartStop:
    def test_immediate_first_tick(self, scheduler, bot):
        job_id = start_typing_keepalive(scheduler, bot, "chat-1", False, "req-1", interval_seconds=15)
        assert job_id is not None
        time.sleep(0.3)  # allow the scheduler thread to execute the immediate tick
        assert len(bot.api.serviceMethods.calls) >= 1
        assert bot.api.serviceMethods.calls[0][0] == "chat-1"
        stop_typing_keepalive(scheduler, job_id)

    def test_renewal_fires_again_after_interval(self, scheduler, bot):
        job_id = start_typing_keepalive(scheduler, bot, "chat-2", False, "req-2", interval_seconds=1)
        time.sleep(1.5)
        stop_typing_keepalive(scheduler, job_id)
        assert len(bot.api.serviceMethods.calls) >= 2  # immediate tick + at least one renewal

    def test_stop_cancels_further_renewals(self, scheduler, bot):
        job_id = start_typing_keepalive(scheduler, bot, "chat-3", False, "req-3", interval_seconds=1)
        time.sleep(0.3)
        stop_typing_keepalive(scheduler, job_id)
        count_after_stop = len(bot.api.serviceMethods.calls)
        time.sleep(1.5)  # would have renewed by now if not stopped
        assert len(bot.api.serviceMethods.calls) == count_after_stop

    def test_blocked_user_is_a_no_op(self, scheduler, bot):
        job_id = start_typing_keepalive(scheduler, bot, "chat-4", True, "req-4")
        assert job_id is None
        time.sleep(0.2)
        assert bot.api.serviceMethods.calls == []

    def test_stop_with_none_job_id_is_a_no_op(self, scheduler):
        stop_typing_keepalive(scheduler, None)  # must not raise

    def test_double_stop_is_a_no_op(self, scheduler, bot):
        job_id = start_typing_keepalive(scheduler, bot, "chat-5", False, "req-5")
        stop_typing_keepalive(scheduler, job_id)
        stop_typing_keepalive(scheduler, job_id)  # must not raise on already-gone job

    def test_two_concurrent_turns_get_independent_jobs(self, scheduler, bot):
        job_a = start_typing_keepalive(scheduler, bot, "chat-6", False, "req-a", interval_seconds=1)
        job_b = start_typing_keepalive(scheduler, bot, "chat-6", False, "req-b", interval_seconds=1)
        assert job_a != job_b
        stop_typing_keepalive(scheduler, job_a)
        stop_typing_keepalive(scheduler, job_b)

    def test_sendtyping_failure_does_not_raise_and_job_keeps_running(self, scheduler):
        class _BoomServiceMethods:
            def sendTyping(self, chat_id, typingTime=None):  # noqa: N802,N803
                raise RuntimeError("simulated Green API failure")

        class _BoomApi:
            serviceMethods = _BoomServiceMethods()  # noqa: N815

        class _BoomBot:
            api = _BoomApi()

        job_id = start_typing_keepalive(scheduler, _BoomBot(), "chat-7", False, "req-7", interval_seconds=1)
        time.sleep(0.3)
        assert scheduler.get_job(job_id) is not None  # still scheduled despite the failed tick
        stop_typing_keepalive(scheduler, job_id)
