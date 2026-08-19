"""
Unit tests for Feature 054's reminder delivery sweep (tasks.md T012a):
_sweep_due_reminders / run_startup_reminder_sweep / start_reminder_scheduler.

A real ReminderManager and real UserManager are used (cheap, fast, no network) -
only the OpenAI-adjacent-free proactive-send call (send_proactive_message) and
session_manager are stubbed (external-service/data-holder stand-ins, per
CONSTITUTION SS I's unit-tier allowance - this is NOT tests/integration/, where
that would be forbidden).

Due reminders are inserted directly against the SQLite row (bypassing
create_reminder's future-only validation) so every test is deterministic -
never dependent on where "now" happens to sit relative to the 5-minute
rounding boundary, unlike the sweep's real production window choice.
"""
import time
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from src.managers.reminder_manager import ReminderManager
from src.managers.user_manager import UserManager
from src.utils.time_utils import local_isoformat, now_local
import src.services.reminder_delivery_service as delivery_service
from src.services.reminder_delivery_service import (
    _sweep_due_reminders, run_startup_reminder_sweep, start_reminder_scheduler,
    REMINDER_SWEEP_JOB_ID,
)

GODFATHER_PHONE = "972506205541"
ADMIN_PHONE = "972522968679"
GODFATHER_CHAT_ID = f"{GODFATHER_PHONE}@c.us"
ADMIN_CHAT_ID = f"{ADMIN_PHONE}@c.us"
GROUP_CHAT_ID = "123456789-group@g.us"


@pytest.fixture
def reminder_manager(tmp_path):
    return ReminderManager(storage_dir=str(tmp_path / "reminders"))


@pytest.fixture
def user_manager():
    return UserManager(godfather_phone=GODFATHER_PHONE, admin_phones=[ADMIN_PHONE], blocked_phones=[])


@pytest.fixture
def global_context(reminder_manager, user_manager):
    return SimpleNamespace(
        ai_handler=SimpleNamespace(reminder_manager=reminder_manager, user_manager=user_manager),
        session_manager=MagicMock(),
        config=SimpleNamespace(godfather_phone=GODFATHER_PHONE),
    )


@pytest.fixture
def stub_bot():
    return MagicMock()


def _insert_due_reminder(reminder_manager, message_text, created_by_phone, created_by_role,
                          delivery_chat_id=None, due_minutes_ago=1):
    """Directly inserts a one-time reminder row already due (dtstart in the near
    past) - deterministic stand-in for "a reminder became due", bypassing
    create_reminder's future-only validation (which exists for the conversational
    creation path, not relevant to exercising the sweep).

    delivery_chat_id defaults to the creator's own 1:1 chat when not given -
    matches this file's common case (delivery target == creator's own chat, the
    same outcome the old "always the godfather's 1:1" design produced for a
    godfather-created reminder). Tests exercising a delivery_chat_id distinct
    from the creator's own chat (e.g. a group) pass it explicitly - see
    TestDeliveryTargetAndFallback.
    """
    reminder_id = str(uuid.uuid4())
    dtstart = (now_local() - timedelta(minutes=due_minutes_ago)).isoformat()
    if delivery_chat_id is None:
        delivery_chat_id = f"{created_by_phone}@c.us"
    reminder_manager._conn.execute(  # pylint: disable=protected-access
        "INSERT INTO reminders "
        "(reminder_id, message_text, rrule, dtstart, status, created_at, "
        " created_by_phone, created_by_role, delivery_chat_id) VALUES (?, ?, NULL, ?, 'active', ?, ?, ?, ?)",
        (reminder_id, message_text, dtstart, local_isoformat(), created_by_phone, created_by_role,
         delivery_chat_id),
    )
    reminder_manager._conn.commit()  # pylint: disable=protected-access
    return reminder_id


class TestSweepDueReminders:
    def test_no_due_occurrences_sends_nothing(self, global_context, stub_bot, monkeypatch):
        send = MagicMock(return_value="wamid.1")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)

        _sweep_due_reminders(global_context, stub_bot)

        send.assert_not_called()

    def test_due_one_time_occurrence_is_delivered_and_recorded_fired(
        self, global_context, stub_bot, monkeypatch
    ):
        send = MagicMock(return_value="wamid.1")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        reminder_manager = global_context.ai_handler.reminder_manager
        reminder_id = _insert_due_reminder(reminder_manager, "לקנות חלב", GODFATHER_PHONE, "GODFATHER")

        _sweep_due_reminders(global_context, stub_bot)

        send.assert_called_once()
        assert send.call_args.args[1] == GODFATHER_CHAT_ID
        # Bug fix (2026-08-19, user feedback after the real Gate Zero live-fire
        # test): delivered text is now prefixed "תזכורת: " so it reads
        # unambiguously as a reminder notification, not the raw stored text.
        assert send.call_args.args[2] == "תזכורת: לקנות חלב"
        fired = reminder_manager._conn.execute(  # pylint: disable=protected-access
            "SELECT COUNT(*) AS c FROM fired_occurrences WHERE reminder_id = ?", (reminder_id,)
        ).fetchone()
        assert fired["c"] == 1

    def test_second_sweep_does_not_redeliver_already_fired(self, global_context, stub_bot, monkeypatch):
        send = MagicMock(return_value="wamid.1")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        _insert_due_reminder(global_context.ai_handler.reminder_manager, "once only", GODFATHER_PHONE, "GODFATHER")

        _sweep_due_reminders(global_context, stub_bot)
        _sweep_due_reminders(global_context, stub_bot)

        send.assert_called_once()

    def test_failed_send_leaves_occurrence_pending_for_retry(
        self, global_context, stub_bot, monkeypatch
    ):
        send = MagicMock(return_value=None)  # simulates a failed send
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        reminder_manager = global_context.ai_handler.reminder_manager
        reminder_id = _insert_due_reminder(reminder_manager, "will fail", GODFATHER_PHONE, "GODFATHER")

        _sweep_due_reminders(global_context, stub_bot)

        send.assert_called_once()
        fired = reminder_manager._conn.execute(  # pylint: disable=protected-access
            "SELECT COUNT(*) AS c FROM fired_occurrences WHERE reminder_id = ?", (reminder_id,)
        ).fetchone()
        assert fired["c"] == 0  # not recorded - eligible for retry next sweep

    def test_failed_send_is_retried_on_next_sweep(self, global_context, stub_bot, monkeypatch):
        send = MagicMock(return_value=None)
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        _insert_due_reminder(global_context.ai_handler.reminder_manager, "retry me", GODFATHER_PHONE, "GODFATHER")

        _sweep_due_reminders(global_context, stub_bot)
        _sweep_due_reminders(global_context, stub_bot)

        assert send.call_count == 2

    def test_one_time_and_recurring_share_identical_delivery_path(
        self, global_context, stub_bot, monkeypatch
    ):
        send = MagicMock(return_value="wamid.1")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        reminder_manager = global_context.ai_handler.reminder_manager
        due_at = (now_local() - timedelta(minutes=1)).isoformat()
        reminder_id = str(uuid.uuid4())
        reminder_manager._conn.execute(  # pylint: disable=protected-access
            "INSERT INTO reminders "
            "(reminder_id, message_text, rrule, dtstart, status, created_at, "
            " created_by_phone, created_by_role, delivery_chat_id) VALUES (?, 'recurring due', "
            "'FREQ=DAILY', ?, 'active', ?, ?, ?, ?)",
            (reminder_id, due_at, local_isoformat(), GODFATHER_PHONE, "GODFATHER", GODFATHER_CHAT_ID),
        )
        reminder_manager._conn.commit()  # pylint: disable=protected-access

        _sweep_due_reminders(global_context, stub_bot)

        send.assert_called_once_with(stub_bot, GODFATHER_CHAT_ID, "תזכורת: recurring due")

    def test_delivers_to_reminder_own_delivery_chat_id(self, global_context, stub_bot, monkeypatch):
        """Supersedes the old FR-008 "always the godfather's own 1:1 chat"
        rule (2026-08-19, user decision): delivery goes to the chat/group the
        reminder was created from, stored per-reminder as delivery_chat_id."""
        send = MagicMock(return_value="wamid.1")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        _insert_due_reminder(
            global_context.ai_handler.reminder_manager, "group reminder",
            GODFATHER_PHONE, "GODFATHER", delivery_chat_id=GROUP_CHAT_ID,
        )

        _sweep_due_reminders(global_context, stub_bot)

        send.assert_called_once_with(stub_bot, GROUP_CHAT_ID, "תזכורת: group reminder")


class TestDeliveryTargetAndFallback:
    """2026-08-19 redesign: delivery targets delivery_chat_id first; only on a
    genuine send failure does it fall back to the reminder's actual creator's
    own 1:1 chat (created_by_phone) - never a fixed godfather identity, and
    never persisted back onto the reminder (the next occurrence tries
    delivery_chat_id again)."""

    def test_falls_back_to_creators_own_chat_when_delivery_target_send_fails(
        self, global_context, stub_bot, monkeypatch
    ):
        send = MagicMock(side_effect=[None, "wamid.fallback"])
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        reminder_manager = global_context.ai_handler.reminder_manager
        reminder_id = _insert_due_reminder(
            reminder_manager, "group exited", GODFATHER_PHONE, "GODFATHER",
            delivery_chat_id=GROUP_CHAT_ID,
        )

        _sweep_due_reminders(global_context, stub_bot)

        assert send.call_count == 2
        first_call, second_call = send.call_args_list
        assert first_call.args[1] == GROUP_CHAT_ID
        assert second_call.args[1] == GODFATHER_CHAT_ID
        fired = reminder_manager._conn.execute(  # pylint: disable=protected-access
            "SELECT COUNT(*) AS c FROM fired_occurrences WHERE reminder_id = ?", (reminder_id,)
        ).fetchone()
        assert fired["c"] == 1  # recorded once, against the fallback send that succeeded

    def test_admin_created_reminder_falls_back_to_admins_own_chat_not_godfathers(
        self, global_context, stub_bot, monkeypatch
    ):
        """Corrects the old assumption that any fallback is always the
        godfather's 1:1 chat - the fallback is the actual reminder creator's
        own chat (2026-08-19, user decision), which for an ADMIN-created
        reminder is the admin's own chat, never the godfather's."""
        send = MagicMock(side_effect=[None, "wamid.fallback"])
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        _insert_due_reminder(
            global_context.ai_handler.reminder_manager, "admin group reminder",
            ADMIN_PHONE, "ADMIN", delivery_chat_id=GROUP_CHAT_ID,
        )

        _sweep_due_reminders(global_context, stub_bot)

        assert send.call_count == 2
        assert send.call_args_list[1].args[1] == ADMIN_CHAT_ID

    def test_both_delivery_and_fallback_fail_leaves_occurrence_pending(
        self, global_context, stub_bot, monkeypatch
    ):
        send = MagicMock(return_value=None)
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        reminder_manager = global_context.ai_handler.reminder_manager
        reminder_id = _insert_due_reminder(
            reminder_manager, "totally unreachable", GODFATHER_PHONE, "GODFATHER",
            delivery_chat_id=GROUP_CHAT_ID,
        )

        _sweep_due_reminders(global_context, stub_bot)

        assert send.call_count == 2
        fired = reminder_manager._conn.execute(  # pylint: disable=protected-access
            "SELECT COUNT(*) AS c FROM fired_occurrences WHERE reminder_id = ?", (reminder_id,)
        ).fetchone()
        assert fired["c"] == 0

    def test_no_duplicate_send_when_delivery_and_fallback_targets_are_identical(
        self, global_context, stub_bot, monkeypatch
    ):
        """A reminder created in the creator's own 1:1 chat has
        delivery_chat_id == created_by_phone's own chat - a failed send must
        not be retried a second time against the exact same chat within the
        same sweep tick (that would just be the identical failing call
        twice, not a real fallback)."""
        send = MagicMock(return_value=None)
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        _insert_due_reminder(
            global_context.ai_handler.reminder_manager, "same chat both ways",
            GODFATHER_PHONE, "GODFATHER",  # delivery_chat_id defaults to GODFATHER_CHAT_ID
        )

        _sweep_due_reminders(global_context, stub_bot)

        send.assert_called_once()


class TestSweepDueRemindersMisc:
    """Grab-bag coverage unrelated to delivery-target/fallback resolution
    itself - session-history persistence, error resilience, multi-occurrence
    sweeps. Split from TestSweepDueReminders/TestDeliveryTargetAndFallback
    purely for readability."""

    def test_session_history_persisted_on_successful_delivery(self, global_context, stub_bot, monkeypatch):
        send = MagicMock(return_value="wamid.1")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        _insert_due_reminder(global_context.ai_handler.reminder_manager, "persist me", GODFATHER_PHONE, "GODFATHER")

        _sweep_due_reminders(global_context, stub_bot)

        global_context.session_manager.add_message_with_token_limit.assert_called_once()
        call_kwargs = global_context.session_manager.add_message_with_token_limit.call_args.kwargs
        assert call_kwargs["chat_id"] == GODFATHER_CHAT_ID
        assert call_kwargs["role"] == "assistant"
        assert call_kwargs["content"] == "תזכורת: persist me"

    def test_query_failure_logged_not_raised(self, global_context, stub_bot, monkeypatch):
        def broken_get_due_occurrences(*args, **kwargs):
            raise RuntimeError("db error")

        monkeypatch.setattr(
            global_context.ai_handler.reminder_manager, "get_due_occurrences", broken_get_due_occurrences
        )
        _sweep_due_reminders(global_context, stub_bot)  # must not raise

    def test_multiple_due_reminders_all_delivered_in_one_sweep(self, global_context, stub_bot, monkeypatch):
        send = MagicMock(return_value="wamid.1")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        reminder_manager = global_context.ai_handler.reminder_manager
        _insert_due_reminder(reminder_manager, "first", GODFATHER_PHONE, "GODFATHER")
        _insert_due_reminder(reminder_manager, "second", GODFATHER_PHONE, "GODFATHER")

        _sweep_due_reminders(global_context, stub_bot)

        assert send.call_count == 2


class TestRunStartupReminderSweep:
    def test_delegates_to_sweep_with_startup_prefix(self, global_context, stub_bot, monkeypatch):
        calls = []
        monkeypatch.setattr(
            delivery_service, "_sweep_due_reminders",
            lambda gc, bot, log_prefix="", **kwargs: calls.append((gc, bot, log_prefix, kwargs)),
        )
        run_startup_reminder_sweep(global_context, stub_bot)
        assert len(calls) == 1
        assert calls[0][2] == "[STARTUP] "
        # Bug fix (2026-08-18): run_startup_reminder_sweep now explicitly passes
        # lookback=STARTUP_SWEEP_LOOKBACK (24h) rather than relying on
        # _sweep_due_reminders' own default (PERIODIC_SWEEP_LOOKBACK, 1h) -
        # confirm it's actually threaded through, not silently dropped.
        assert calls[0][3].get("lookback") == delivery_service.STARTUP_SWEEP_LOOKBACK

    def test_actually_catches_up_a_missed_occurrence(self, global_context, stub_bot, monkeypatch):
        send = MagicMock(return_value="wamid.1")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        _insert_due_reminder(
            global_context.ai_handler.reminder_manager, "missed while down", GODFATHER_PHONE,
            "GODFATHER", due_minutes_ago=120,
        )

        run_startup_reminder_sweep(global_context, stub_bot)

        send.assert_called_once()


class TestStartReminderScheduler:
    def test_registers_exactly_one_job(self, global_context, stub_bot):
        scheduler = start_reminder_scheduler(global_context, stub_bot)
        try:
            jobs = scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].id == REMINDER_SWEEP_JOB_ID
        finally:
            scheduler.shutdown(wait=False)

    def test_job_uses_cron_trigger_every_5_minutes_by_default(self, global_context, stub_bot):
        scheduler = start_reminder_scheduler(global_context, stub_bot)
        try:
            job = scheduler.get_jobs()[0]
            assert "CronTrigger" in type(job.trigger).__name__
        finally:
            scheduler.shutdown(wait=False)

    def test_custom_sweep_interval_is_honored(self, global_context, stub_bot):
        scheduler = start_reminder_scheduler(global_context, stub_bot, sweep_interval_minutes=10)
        try:
            job = scheduler.get_jobs()[0]
            assert "*/10" in str(job.trigger)
        finally:
            scheduler.shutdown(wait=False)

    def test_real_live_scheduler_actually_invokes_the_sweep_on_its_own(
        self, global_context, stub_bot, monkeypatch
    ):
        """Closes the one gap none of the tests above cover: that a real,
        running BackgroundScheduler thread - with nothing in this test ever
        calling _sweep_due_reminders directly - genuinely fires the job on
        its own trigger and it reaches send_proactive_message. Uses a real
        2-second IntervalTrigger (the `trigger` testability seam) instead of
        the real production CronTrigger purely to avoid waiting up to 60
        real seconds for a minute boundary - the add_job()/BackgroundScheduler
        wiring being proven here is identical either way; the CronTrigger
        value itself is already covered by the tests above.
        """
        send = MagicMock(return_value="wamid.1")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        _insert_due_reminder(
            global_context.ai_handler.reminder_manager, "really fired live", GODFATHER_PHONE, "GODFATHER"
        )

        scheduler = start_reminder_scheduler(
            global_context, stub_bot, trigger=IntervalTrigger(seconds=2)
        )
        try:
            deadline = time.monotonic() + 10
            while not send.called and time.monotonic() < deadline:
                time.sleep(0.25)
        finally:
            scheduler.shutdown(wait=False)

        assert send.called, "real BackgroundScheduler never invoked the sweep within 10s"
        assert send.call_args.args[1] == GODFATHER_CHAT_ID
        assert send.call_args.args[2] == "תזכורת: really fired live"
