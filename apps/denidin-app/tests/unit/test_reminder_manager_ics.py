"""Feature 102 (T002A): ReminderManager's calendar-file support - the persisted per-reminder SEQUENCE counter
(its own `reminder_ics_sequences` table, no ALTER TABLE), `claim_ics_sequence`, `get_for_calendar`,
`list_for_calendar`."""
from datetime import timedelta

import pytest

from src.managers.reminder_manager import ReminderManager, ReminderNotFoundError
from src.utils.time_utils import now_local
from tests.denidin_test_support import make_reminder_manager

PHONE, ROLE, CHAT = "972500000000", "GODFATHER", "972500000000@c.us"


@pytest.fixture
def manager(tmp_path):
    return make_reminder_manager(storage_dir=str(tmp_path / "reminders"))


def _one_time(manager, text="לשלם לספק", days=2):
    due = (now_local() + timedelta(days=days)).replace(second=0, microsecond=0)
    return manager.create_reminder(text, "one_time", due.isoformat(), None, PHONE, ROLE, CHAT)["reminder_id"]


def _daily(manager, text="לשתות מים"):
    first = (now_local() + timedelta(days=3)).replace(minute=0, second=0, microsecond=0)
    recurrence = {"interval": 1, "freq": "daily", "weekdays": None, "month_day": None, "month_nth_weekday": None,
                  "first_occurrence_at": first.isoformat(), "end_condition": "never", "end_count": None,
                  "end_until": None}
    reminder_id = manager.create_reminder(text, "recurring", None, recurrence, PHONE, ROLE, CHAT)["reminder_id"]
    return reminder_id, first


class TestSequenceTable:
    def test_the_reminders_table_itself_is_untouched(self, manager):
        columns = {row["name"] for row in manager._conn.execute("PRAGMA table_info(reminders)")}
        assert "ics_sequence" not in columns  # no ALTER TABLE: the counter has a table of its own

    def test_a_new_reminder_starts_at_zero(self, manager):
        assert manager.get_for_calendar(_one_time(manager))["ics_sequence"] == 0

    def test_database_from_before_the_feature_works_and_keeps_its_rows(self, manager):
        reminder_id = _one_time(manager)
        manager._conn.execute("DROP TABLE reminder_ics_sequences")  # the shape every existing prod DB has
        manager._conn.commit()

        restarted = ReminderManager(manager.denidin)

        assert restarted.get_reminder(reminder_id)["message_text"] == "לשלם לספק"
        assert restarted.claim_ics_sequence(reminder_id) == 0

    def test_repeated_starts_do_not_reset_the_counter(self, manager):
        reminder_id = _one_time(manager)
        manager.claim_ics_sequence(reminder_id)
        ReminderManager(manager.denidin)
        ReminderManager(manager.denidin)
        assert manager.claim_ics_sequence(reminder_id) == 1


class TestClaimIcsSequence:
    def test_counts_up_per_reminder_starting_at_zero(self, manager):
        reminder_id = _one_time(manager)
        assert [manager.claim_ics_sequence(reminder_id) for _ in range(3)] == [0, 1, 2]

    def test_each_reminder_has_its_own_counter(self, manager):
        first, second = _one_time(manager, "א"), _one_time(manager, "ב")
        manager.claim_ics_sequence(first)
        manager.claim_ics_sequence(first)
        assert manager.claim_ics_sequence(second) == 0

    def test_survives_a_restart(self, manager):
        reminder_id = _one_time(manager)
        manager.claim_ics_sequence(reminder_id)
        assert ReminderManager(manager.denidin).claim_ics_sequence(reminder_id) == 1

    def test_works_for_a_cancelled_reminder(self, manager):
        reminder_id = _one_time(manager)
        manager.claim_ics_sequence(reminder_id)
        manager.delete_whole_series(reminder_id)
        assert manager.claim_ics_sequence(reminder_id) == 1  # the CANCEL file still needs a higher sequence

    def test_unknown_reminder_raises(self, manager):
        with pytest.raises(ReminderNotFoundError):
            manager.claim_ics_sequence("no-such-reminder")


class TestGetForCalendar:
    def test_active_one_time_reminder(self, manager):
        reminder_id = _one_time(manager)
        entry = manager.get_for_calendar(reminder_id)
        assert entry["reminder_id"] == reminder_id and entry["message_text"] == "לשלם לספק"
        assert entry["rrule"] is None and entry["exceptions"] == []
        assert entry["ics_sequence"] == 0 and entry["dtstart"]

    def test_reading_does_not_claim_a_sequence(self, manager):
        reminder_id = _one_time(manager)
        manager.get_for_calendar(reminder_id)
        manager.get_for_calendar(reminder_id)
        assert manager.claim_ics_sequence(reminder_id) == 0

    def test_cancelled_reminder_is_still_returned(self, manager):
        reminder_id = _one_time(manager)
        manager.delete_whole_series(reminder_id)
        assert manager.get_for_calendar(reminder_id)["reminder_id"] == reminder_id

    def test_unknown_reminder_is_none(self, manager):
        assert manager.get_for_calendar("no-such-reminder") is None

    def test_exceptions_are_included(self, manager):
        reminder_id, first = _daily(manager)
        moved_day = (first + timedelta(days=1)).date().isoformat()
        skipped_day = (first + timedelta(days=2)).date().isoformat()
        manager.modify_single_occurrence(reminder_id, moved_day, new_due_at=(first + timedelta(days=1, hours=2)).isoformat())
        manager.delete_single_occurrence(reminder_id, skipped_day)

        entry = manager.get_for_calendar(reminder_id)

        assert entry["rrule"].startswith("FREQ=DAILY")
        statuses = sorted(exc["status"] for exc in entry["exceptions"])
        assert statuses == ["CANCELLED", "CONFIRMED"]
        moved = [exc for exc in entry["exceptions"] if exc["status"] == "CONFIRMED"][0]
        assert moved["dtstart_override"] and moved["recurrence_id"]


class TestListForCalendar:
    def test_active_only_in_the_given_order(self, manager):
        a, b, c = _one_time(manager, "א"), _one_time(manager, "ב"), _one_time(manager, "ג")
        manager.delete_whole_series(b)
        result = manager.list_for_calendar([c, b, a])
        assert [entry["reminder_id"] for entry in result] == [c, a]

    def test_unknown_ids_are_left_out(self, manager):
        a = _one_time(manager)
        assert [e["reminder_id"] for e in manager.list_for_calendar(["nope", a])] == [a]

    def test_entries_carry_exceptions_and_sequence(self, manager):
        reminder_id, first = _daily(manager)
        manager.delete_single_occurrence(reminder_id, (first + timedelta(days=1)).date().isoformat())
        (entry,) = manager.list_for_calendar([reminder_id])
        assert entry["exceptions"][0]["status"] == "CANCELLED" and entry["ics_sequence"] == 0
