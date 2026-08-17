"""
Unit tests for ReminderManager (Feature 054: Reminders - Functionality and Management).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Covers tasks.md
Phase 2 (T004a): SQLite schema creation, one-time reminder creation, 5-minute rounding
(including the "rounds into the past" edge case), past-date rejection (checked after
rounding), RRULE string construction for every freq/end-condition combination, structural
rejection of a yearly frequency, and the 20-reminder cap.

This file intentionally imports a module that does not exist yet
(`src.managers.reminder_manager`) - it is expected to fail collection until T004b
implements it. See specs/in-progress/054-reminders-functionality-mgmt/data-model.md for
the full schema this exercises, and contracts/reminder-tool-schemas.md for the
`create_reminder` argument shape these tests construct `recurrence` dicts to match.

Scope note: this file tests RRULE *construction* (the string built from a recurrence
dict) and the SQLite schema/row shape - it does NOT test occurrence *resolution* via
`icalendar`/`recurring_ical_events` (that's T005a, a separate, later test file/task).
"""

import sqlite3
from datetime import timedelta

import pytest

from src.utils.time_utils import now_local, to_local

from src.managers.reminder_manager import (
    ReminderManager,
    ReminderPastDateError,
    ReminderCapExceededError,
    ReminderNotFoundError,
    InvalidRecurrenceError,
    round_to_five_minutes,
)


# --- Fixtures -----------------------------------------------------------------

@pytest.fixture
def storage_dir(tmp_path):
    return tmp_path / "reminders"


@pytest.fixture
def manager(storage_dir):
    return ReminderManager(storage_dir=str(storage_dir))


def _db_path(storage_dir):
    return storage_dir / "reminders.db"


def _connect(storage_dir):
    conn = sqlite3.connect(str(_db_path(storage_dir)))
    conn.row_factory = sqlite3.Row
    return conn


def _future(minutes: int):
    """An aware Asia/Jerusalem datetime `minutes` from now, ISO-formatted."""
    return (now_local() + timedelta(minutes=minutes)).isoformat()


def _weekly_recurrence(**overrides):
    base = {
        "interval": 1,
        "freq": "weekly",
        "weekdays": ["MO", "TH"],
        "month_day": None,
        "month_nth_weekday": None,
        "first_occurrence_at": _future(60 * 24 * 3),  # 3 days out, safely in the future
        "end_condition": "never",
        "end_count": None,
        "end_until": None,
    }
    base.update(overrides)
    return base


# --- Schema / constructor -------------------------------------------------------

class TestReminderManagerCore:
    """T004a: storage_dir creation, SQLite schema shape, constructor pattern."""

    def test_creates_storage_dir_if_missing(self, storage_dir):
        assert not storage_dir.exists()
        ReminderManager(storage_dir=str(storage_dir))
        assert storage_dir.is_dir()

    def test_creates_db_file(self, manager, storage_dir):
        assert _db_path(storage_dir).exists()

    def test_does_not_read_data_root_or_config_internally(self, storage_dir):
        # REQ-STORE-001-style discipline (matches LedgerEventManager/MediaFileManager):
        # the constructor only ever takes pre-composed values (storage_dir, and the
        # cap - both caller-composed from AppConfiguration.data_root/config.reminders
        # at construction time, e.g. ReminderManager(storage_dir=..., max_active_reminders=
        # config.reminders.get('max_active_reminders', 20))) - never an AppConfiguration
        # object or a bare "read config" call internally.
        import inspect
        sig = inspect.signature(ReminderManager.__init__)
        params = list(sig.parameters)
        assert params == ["self", "storage_dir", "max_active_reminders"]
        assert sig.parameters["max_active_reminders"].default == 20

    def test_max_active_reminders_is_configurable(self, storage_dir):
        manager = ReminderManager(storage_dir=str(storage_dir), max_active_reminders=2)
        manager.create_reminder(
            message_text="a", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.create_reminder(
            message_text="b", schedule_type="one_time", one_time_due_at=_future(70),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        with pytest.raises(ReminderCapExceededError):
            manager.create_reminder(
                message_text="c", schedule_type="one_time", one_time_due_at=_future(80),
                recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_reminders_table_schema(self, manager, storage_dir):
        conn = _connect(storage_dir)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(reminders)")}
        assert cols == {
            "reminder_id", "message_text", "rrule", "dtstart", "status",
            "created_at", "created_by_phone", "created_by_role",
        }
        conn.close()

    def test_reminder_exceptions_table_schema(self, manager, storage_dir):
        conn = _connect(storage_dir)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(reminder_exceptions)")}
        assert cols == {
            "id", "reminder_id", "recurrence_id", "dtstart_override",
            "summary_override", "status",
        }
        conn.close()

    def test_fired_occurrences_table_schema(self, manager, storage_dir):
        conn = _connect(storage_dir)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(fired_occurrences)")}
        assert cols == {
            "id", "reminder_id", "occurrence_datetime", "delivered_at", "message_text_sent",
        }
        conn.close()

    def test_reinitializing_against_existing_db_does_not_lose_data(self, storage_dir):
        m1 = ReminderManager(storage_dir=str(storage_dir))
        result = m1.create_reminder(
            message_text="test", schedule_type="one_time",
            one_time_due_at=_future(60), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        m2 = ReminderManager(storage_dir=str(storage_dir))
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT * FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        assert row is not None
        conn.close()


# --- Rounding --------------------------------------------------------------------

class TestRounding:
    """T004a: 5-minute rounding (ties round up), including the rounds-into-the-past case."""

    def test_exact_multiple_unchanged(self):
        dt = to_local(now_local().replace(minute=10, second=0, microsecond=0))
        assert round_to_five_minutes(dt) == dt

    def test_rounds_down_when_closer_to_previous_mark(self):
        dt = to_local(now_local().replace(minute=11, second=0, microsecond=0))
        rounded = round_to_five_minutes(dt)
        assert rounded.minute == 10 and rounded.second == 0

    def test_rounds_up_when_closer_to_next_mark(self):
        dt = to_local(now_local().replace(minute=13, second=0, microsecond=0))
        rounded = round_to_five_minutes(dt)
        assert rounded.minute == 15 and rounded.second == 0

    def test_tie_rounds_up(self):
        dt = to_local(now_local().replace(minute=12, second=30, microsecond=0))
        rounded = round_to_five_minutes(dt)
        assert rounded.minute == 15 and rounded.second == 0

    def test_rounding_crosses_hour_boundary(self):
        dt = to_local(now_local().replace(minute=58, second=0, microsecond=0))
        rounded = round_to_five_minutes(dt)
        assert rounded.minute == 0
        assert rounded.hour == (dt.hour + 1) % 24

    def test_preserves_tzinfo(self):
        dt = to_local(now_local().replace(minute=13, second=0, microsecond=0))
        rounded = round_to_five_minutes(dt)
        assert rounded.tzinfo is not None
        assert rounded.utcoffset() == dt.utcoffset()

    def test_always_strips_microseconds(self):
        # Regression guard (found 2026-08-16, live-verified): recurring_ical_events
        # returns the SAME anchor occurrence TWICE for a recurring VEVENT whose
        # DTSTART carries microseconds (one copy with, one truncated) - every
        # rounded datetime must be exactly clean, never left to float-arithmetic luck.
        dt = now_local().replace(microsecond=123456)
        assert round_to_five_minutes(dt).microsecond == 0

    def test_create_reminder_returns_rounded_due_at(self, manager):
        # 2 minutes out, seconds nonzero - should round to a clean 5-minute mark
        unrounded = now_local() + timedelta(minutes=7, seconds=30)
        result = manager.create_reminder(
            message_text="round me", schedule_type="one_time",
            one_time_due_at=unrounded.isoformat(), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        from datetime import datetime as _dt
        parsed = _dt.fromisoformat(result["due_at"])
        assert parsed.minute % 5 == 0 and parsed.second == 0


# --- One-time reminder creation ---------------------------------------------------

class TestOneTimeReminderCreation:
    """T004a: create_reminder for schedule_type='one_time'."""

    def test_persists_row_with_null_rrule(self, manager, storage_dir):
        result = manager.create_reminder(
            message_text="call the accountant", schedule_type="one_time",
            one_time_due_at=_future(60), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT * FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        conn.close()
        assert row["rrule"] is None
        assert row["message_text"] == "call the accountant"
        assert row["status"] == "active"
        assert row["created_by_phone"] == "972500000000"
        assert row["created_by_role"] == "GODFATHER"

    def test_reminder_id_is_unique_per_call(self, manager):
        r1 = manager.create_reminder(
            message_text="a", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        r2 = manager.create_reminder(
            message_text="b", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        assert r1["reminder_id"] != r2["reminder_id"]

    def test_does_not_mutate_caller_dict(self, manager):
        recurrence = None
        message_text = "immutable check"
        manager.create_reminder(
            message_text=message_text, schedule_type="one_time",
            one_time_due_at=_future(60), recurrence=recurrence,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        assert message_text == "immutable check"
        assert recurrence is None


# --- Past-date rejection (FR-005) --------------------------------------------------

class TestPastDateRejection:
    """T004a: past-date rejection, checked AFTER rounding."""

    def test_one_time_due_at_in_the_past_rejected(self, manager):
        past = (now_local() - timedelta(hours=1)).isoformat()
        with pytest.raises(ReminderPastDateError):
            manager.create_reminder(
                message_text="too late", schedule_type="one_time", one_time_due_at=past,
                recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_no_partial_row_persisted_on_rejection(self, manager, storage_dir):
        past = (now_local() - timedelta(hours=1)).isoformat()
        with pytest.raises(ReminderPastDateError):
            manager.create_reminder(
                message_text="too late", schedule_type="one_time", one_time_due_at=past,
                recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
            )
        conn = _connect(storage_dir)
        count = conn.execute("SELECT COUNT(*) AS c FROM reminders").fetchone()["c"]
        conn.close()
        assert count == 0

    def test_recurring_first_occurrence_in_past_rejected(self, manager):
        with pytest.raises(ReminderPastDateError):
            manager.create_reminder(
                message_text="weekly but starts yesterday", schedule_type="recurring",
                one_time_due_at=None,
                recurrence=_weekly_recurrence(
                    first_occurrence_at=(now_local() - timedelta(days=1)).isoformat()
                ),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_recurring_until_date_in_past_rejected(self, manager):
        with pytest.raises(ReminderPastDateError):
            manager.create_reminder(
                message_text="already-ended series", schedule_type="recurring",
                one_time_due_at=None,
                recurrence=_weekly_recurrence(
                    end_condition="until_date",
                    end_until=(now_local() - timedelta(days=1)).date().isoformat(),
                ),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )


# --- Cap enforcement (FR-006) -------------------------------------------------------

class TestCapEnforcement:
    """T004a: 20-active-reminder cap for the one reminder list."""

    def test_21st_reminder_raises(self, manager):
        for i in range(20):
            manager.create_reminder(
                message_text=f"reminder {i}", schedule_type="one_time",
                one_time_due_at=_future(60 + i), recurrence=None,
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )
        with pytest.raises(ReminderCapExceededError):
            manager.create_reminder(
                message_text="the 21st", schedule_type="one_time", one_time_due_at=_future(600),
                recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_20th_reminder_succeeds(self, manager):
        for i in range(19):
            manager.create_reminder(
                message_text=f"reminder {i}", schedule_type="one_time",
                one_time_due_at=_future(60 + i), recurrence=None,
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )
        result = manager.create_reminder(
            message_text="the 20th", schedule_type="one_time", one_time_due_at=_future(600),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        assert result["reminder_id"]

    def test_cancelled_reminders_do_not_count_toward_cap(self, manager, storage_dir):
        ids = []
        for i in range(20):
            r = manager.create_reminder(
                message_text=f"reminder {i}", schedule_type="one_time",
                one_time_due_at=_future(60 + i), recurrence=None,
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )
            ids.append(r["reminder_id"])
        # Directly cancel one (delete_whole_series is a later task - T019c; use raw SQL
        # here so this test doesn't accidentally depend on not-yet-written code).
        conn = _connect(storage_dir)
        conn.execute("UPDATE reminders SET status = 'cancelled' WHERE reminder_id = ?", (ids[0],))
        conn.commit()
        conn.close()
        result = manager.create_reminder(
            message_text="fits because one was cancelled", schedule_type="one_time",
            one_time_due_at=_future(700), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        assert result["reminder_id"]

    def test_admin_created_and_godfather_created_share_the_same_cap(self, manager):
        # FR-006: the cap is scoped to "the godfather" as a whole, not per acting identity.
        for i in range(10):
            manager.create_reminder(
                message_text=f"godfather {i}", schedule_type="one_time",
                one_time_due_at=_future(60 + i), recurrence=None,
                created_by_phone="972506205541", created_by_role="GODFATHER",
            )
        for i in range(10):
            manager.create_reminder(
                message_text=f"admin {i}", schedule_type="one_time",
                one_time_due_at=_future(200 + i), recurrence=None,
                created_by_phone="972522968679", created_by_role="ADMIN",
            )
        with pytest.raises(ReminderCapExceededError):
            manager.create_reminder(
                message_text="21st, regardless of who", schedule_type="one_time",
                one_time_due_at=_future(900), recurrence=None,
                created_by_phone="972522968679", created_by_role="ADMIN",
            )


# --- RRULE construction (FR-007) ----------------------------------------------------

class TestRRuleConstruction:
    """T004a: RRULE STRING construction from a recurrence dict - not occurrence
    resolution (that's T005a, via icalendar/recurring_ical_events)."""

    def test_daily_never_ending(self, manager, storage_dir):
        result = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None, interval=1,
                                           end_condition="never"),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT rrule FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        conn.close()
        assert "FREQ=DAILY" in row["rrule"]
        assert "COUNT" not in row["rrule"]
        assert "UNTIL" not in row["rrule"]

    def test_daily_with_interval(self, manager, storage_dir):
        result = manager.create_reminder(
            message_text="every 3 days", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None, interval=3),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT rrule FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        conn.close()
        assert "FREQ=DAILY" in row["rrule"]
        assert "INTERVAL=3" in row["rrule"]

    def test_weekly_with_weekdays(self, manager, storage_dir):
        result = manager.create_reminder(
            message_text="weekly MO/TH", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT rrule FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        conn.close()
        assert "FREQ=WEEKLY" in row["rrule"]
        assert "BYDAY=MO,TH" in row["rrule"]

    def test_weekly_requires_nonempty_weekdays(self, manager):
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="broken weekly", schedule_type="recurring", one_time_due_at=None,
                recurrence=_weekly_recurrence(weekdays=None),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="broken weekly", schedule_type="recurring", one_time_due_at=None,
                recurrence=_weekly_recurrence(weekdays=[]),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_monthly_fixed_day(self, manager, storage_dir):
        result = manager.create_reminder(
            message_text="15th of every month", schedule_type="recurring",
            one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="monthly", weekdays=None, month_day=15),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT rrule FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        conn.close()
        assert "FREQ=MONTHLY" in row["rrule"]
        assert "BYMONTHDAY=15" in row["rrule"]

    def test_monthly_nth_weekday(self, manager, storage_dir):
        result = manager.create_reminder(
            message_text="first Monday of every month", schedule_type="recurring",
            one_time_due_at=None,
            recurrence=_weekly_recurrence(
                freq="monthly", weekdays=None,
                month_nth_weekday={"n": 1, "weekday": "MO"},
            ),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT rrule FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        conn.close()
        assert "FREQ=MONTHLY" in row["rrule"]
        assert "BYDAY=1MO" in row["rrule"]

    def test_monthly_nth_weekday_last(self, manager, storage_dir):
        result = manager.create_reminder(
            message_text="last Friday of every month", schedule_type="recurring",
            one_time_due_at=None,
            recurrence=_weekly_recurrence(
                freq="monthly", weekdays=None,
                month_nth_weekday={"n": -1, "weekday": "FR"},
            ),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT rrule FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        conn.close()
        assert "BYDAY=-1FR" in row["rrule"]

    def test_monthly_requires_exactly_one_variant(self, manager):
        # Neither month_day nor month_nth_weekday
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="broken monthly", schedule_type="recurring", one_time_due_at=None,
                recurrence=_weekly_recurrence(freq="monthly", weekdays=None),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )
        # Both at once
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="broken monthly", schedule_type="recurring", one_time_due_at=None,
                recurrence=_weekly_recurrence(
                    freq="monthly", weekdays=None, month_day=1,
                    month_nth_weekday={"n": 1, "weekday": "MO"},
                ),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_end_condition_after_n(self, manager, storage_dir):
        result = manager.create_reminder(
            message_text="5 times", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(end_condition="after_n", end_count=5),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT rrule FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        conn.close()
        assert "COUNT=5" in row["rrule"]

    def test_after_n_requires_positive_count(self, manager):
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="broken count", schedule_type="recurring", one_time_due_at=None,
                recurrence=_weekly_recurrence(end_condition="after_n", end_count=None),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="broken count", schedule_type="recurring", one_time_due_at=None,
                recurrence=_weekly_recurrence(end_condition="after_n", end_count=0),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_end_condition_until_date(self, manager, storage_dir):
        until = (now_local() + timedelta(days=90)).date().isoformat()
        result = manager.create_reminder(
            message_text="until autumn", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(end_condition="until_date", end_until=until),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT rrule FROM reminders WHERE reminder_id = ?", (result["reminder_id"],)
        ).fetchone()
        conn.close()
        assert "UNTIL=" in row["rrule"]

    def test_until_date_requires_end_until(self, manager):
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="broken until", schedule_type="recurring", one_time_due_at=None,
                recurrence=_weekly_recurrence(end_condition="until_date", end_until=None),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_yearly_frequency_structurally_rejected(self, manager):
        # FR-007: yearly is not merely discouraged, it's not a legal value at all.
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="broken yearly", schedule_type="recurring", one_time_due_at=None,
                recurrence=_weekly_recurrence(freq="yearly", weekdays=None),
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_recurring_requires_recurrence_dict(self, manager):
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="missing recurrence", schedule_type="recurring",
                one_time_due_at=None, recurrence=None,
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )

    def test_one_time_requires_one_time_due_at(self, manager):
        with pytest.raises(InvalidRecurrenceError):
            manager.create_reminder(
                message_text="missing due_at", schedule_type="one_time",
                one_time_due_at=None, recurrence=None,
                created_by_phone="972500000000", created_by_role="GODFATHER",
            )


# --- Resolution logic (T005a): icalendar/recurring_ical_events integration -------------

class TestListActive:
    def test_returns_only_active_reminders(self, manager, storage_dir):
        keep = manager.create_reminder(
            message_text="keep", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        drop = manager.create_reminder(
            message_text="drop", schedule_type="one_time", one_time_due_at=_future(70),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        conn.execute("UPDATE reminders SET status = 'cancelled' WHERE reminder_id = ?", (drop["reminder_id"],))
        conn.commit()
        conn.close()
        active_ids = {r["reminder_id"] for r in manager.list_active()}
        assert keep["reminder_id"] in active_ids
        assert drop["reminder_id"] not in active_ids

    def test_empty_when_no_reminders(self, manager):
        assert manager.list_active() == []


class TestGetDueOccurrences:
    """T005a: resolution via icalendar/recurring_ical_events, verified live 2026-08-16
    (see research.md) before this code was written - in particular that the library does
    NOT suppress STATUS=CANCELLED on its own, which ReminderManager must filter itself."""

    def test_one_time_reminder_due_in_window(self, manager):
        due_at = now_local() + timedelta(minutes=10)
        rounded = round_to_five_minutes(due_at)
        manager.create_reminder(
            message_text="one-time due", schedule_type="one_time",
            one_time_due_at=due_at.isoformat(), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occs = manager.get_due_occurrences(rounded - timedelta(seconds=1), rounded + timedelta(minutes=5))
        assert len(occs) == 1
        assert occs[0]["message_text"] == "one-time due"
        assert occs[0]["occurrence_datetime"].tzinfo is not None

    def test_one_time_reminder_not_yet_due_excluded(self, manager):
        manager.create_reminder(
            message_text="far future", schedule_type="one_time",
            one_time_due_at=_future(60 * 24 * 30), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occs = manager.get_due_occurrences(now_local(), now_local() + timedelta(minutes=5))
        assert occs == []

    def test_cancelled_reminder_series_excluded(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="will be cancelled", schedule_type="one_time",
            one_time_due_at=_future(10), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        conn.execute("UPDATE reminders SET status = 'cancelled' WHERE reminder_id = ?", (r["reminder_id"],))
        conn.commit()
        conn.close()
        occs = manager.get_due_occurrences(now_local(), now_local() + timedelta(minutes=15))
        assert occs == []

    def test_recurring_occurrence_due_in_window(self, manager):
        first = round_to_five_minutes(now_local() + timedelta(days=1))
        manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None,
                                           first_occurrence_at=first.isoformat()),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occs = manager.get_due_occurrences(first - timedelta(seconds=1), first + timedelta(minutes=1))
        assert len(occs) == 1
        assert occs[0]["message_text"] == "daily"

    def test_single_occurrence_exception_reschedule_resolved(self, manager, storage_dir):
        first = round_to_five_minutes(now_local() + timedelta(days=1))
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None,
                                           first_occurrence_at=first.isoformat()),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        rescheduled = first + timedelta(hours=2)
        conn = _connect(storage_dir)
        conn.execute(
            "INSERT INTO reminder_exceptions "
            "(reminder_id, recurrence_id, dtstart_override, summary_override, status) "
            "VALUES (?, ?, ?, ?, 'CONFIRMED')",
            (r["reminder_id"], first.isoformat(), rescheduled.isoformat(), "daily (moved)"),
        )
        conn.commit()
        conn.close()
        # The original slot should now be empty...
        occs_original_slot = manager.get_due_occurrences(first - timedelta(seconds=1), first + timedelta(minutes=1))
        assert occs_original_slot == []
        # ...and the rescheduled slot should carry the overridden text.
        occs_new_slot = manager.get_due_occurrences(rescheduled - timedelta(seconds=1), rescheduled + timedelta(minutes=1))
        assert len(occs_new_slot) == 1
        assert occs_new_slot[0]["message_text"] == "daily (moved)"

    def test_single_occurrence_exception_cancellation_excluded(self, manager, storage_dir):
        first = round_to_five_minutes(now_local() + timedelta(days=1))
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None,
                                           first_occurrence_at=first.isoformat()),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        conn.execute(
            "INSERT INTO reminder_exceptions "
            "(reminder_id, recurrence_id, dtstart_override, summary_override, status) "
            "VALUES (?, ?, NULL, NULL, 'CANCELLED')",
            (r["reminder_id"], first.isoformat()),
        )
        conn.commit()
        conn.close()
        occs = manager.get_due_occurrences(first - timedelta(seconds=1), first + timedelta(minutes=1))
        assert occs == []
        # The NEXT day's occurrence (not cancelled) must still be there, untouched.
        second_day = first + timedelta(days=1)
        occs_next = manager.get_due_occurrences(second_day - timedelta(seconds=1), second_day + timedelta(minutes=1))
        assert len(occs_next) == 1

    def test_occurrence_datetime_tz_preserved(self, manager):
        due_at = now_local() + timedelta(minutes=10)
        rounded = round_to_five_minutes(due_at)
        manager.create_reminder(
            message_text="tz check", schedule_type="one_time",
            one_time_due_at=due_at.isoformat(), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occs = manager.get_due_occurrences(rounded - timedelta(seconds=1), rounded + timedelta(minutes=5))
        assert occs[0]["occurrence_datetime"].utcoffset() == rounded.utcoffset()

    def test_already_fired_occurrence_excluded_even_within_window(self, manager):
        due_at = now_local() + timedelta(minutes=10)
        rounded = round_to_five_minutes(due_at)
        r = manager.create_reminder(
            message_text="one-time due", schedule_type="one_time",
            one_time_due_at=due_at.isoformat(), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.record_occurrence_fired(r["reminder_id"], rounded, "one-time due")

        occs = manager.get_due_occurrences(rounded - timedelta(seconds=1), rounded + timedelta(minutes=5))
        assert occs == []

    def test_record_occurrence_fired_persists_row(self, manager, storage_dir):
        due_at = now_local() + timedelta(minutes=10)
        rounded = round_to_five_minutes(due_at)
        r = manager.create_reminder(
            message_text="one-time due", schedule_type="one_time",
            one_time_due_at=due_at.isoformat(), recurrence=None,
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.record_occurrence_fired(r["reminder_id"], rounded, "one-time due (sent)")

        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT * FROM fired_occurrences WHERE reminder_id = ?", (r["reminder_id"],)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["message_text_sent"] == "one-time due (sent)"
        assert row["delivered_at"] is not None

    def test_recurring_fires_one_occurrence_then_excludes_it_but_keeps_next_due(self, manager):
        # A generous lookback window (simulating the delivery sweep's own window
        # choice) must still only return the NOT-yet-fired occurrence.
        first = round_to_five_minutes(now_local() + timedelta(minutes=5))
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None,
                                           first_occurrence_at=first.isoformat()),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.record_occurrence_fired(r["reminder_id"], first, "daily")

        second_day = first + timedelta(days=1)
        occs = manager.get_due_occurrences(first - timedelta(hours=1), second_day + timedelta(minutes=1))
        assert len(occs) == 1
        assert occs[0]["occurrence_datetime"] == second_day

    def test_microsecond_bearing_dtstart_does_not_duplicate_occurrence(self, manager, storage_dir):
        # Regression guard (2026-08-16): even if a dtstart with microseconds
        # somehow ends up stored (bypassing round_to_five_minutes, e.g. via a
        # future direct-SQL code path), get_due_occurrences' read-boundary
        # stripping (_parse_local_no_micros) must still prevent the
        # recurring_ical_events double-anchor-occurrence bug from producing a
        # duplicate delivery.
        import uuid
        reminder_id = str(uuid.uuid4())
        dtstart_with_micros = now_local().replace(microsecond=654321) - timedelta(minutes=1)
        conn = _connect(storage_dir)
        conn.execute(
            "INSERT INTO reminders "
            "(reminder_id, message_text, rrule, dtstart, status, created_at, "
            " created_by_phone, created_by_role) VALUES (?, 'recurring', 'FREQ=DAILY', ?, "
            "'active', ?, '972500000000', 'GODFATHER')",
            (reminder_id, dtstart_with_micros.isoformat(), now_local().isoformat()),
        )
        conn.commit()
        conn.close()

        occs = manager.get_due_occurrences(now_local() - timedelta(hours=1), now_local())
        assert len(occs) == 1

    def test_never_ending_recurring_far_future_narrow_window_is_fast(self, manager):
        # T005a's efficiency check, at the ReminderManager layer (not just the raw
        # library, already confirmed directly - see research.md).
        import time
        first = round_to_five_minutes(now_local() + timedelta(minutes=5))
        manager.create_reminder(
            message_text="forever", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None,
                                           first_occurrence_at=first.isoformat(),
                                           end_condition="never"),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        far_future = first + timedelta(days=365 * 3)
        t0 = time.perf_counter()
        manager.get_due_occurrences(far_future, far_future + timedelta(minutes=5))
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0


# --- Modify (T017a) ----------------------------------------------------------------

class TestModifyWholeSeries:
    def test_one_time_reminder_message_text_updated(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="old text", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.modify_whole_series(r["reminder_id"], new_message_text="new text")
        conn = _connect(storage_dir)
        row = conn.execute("SELECT message_text FROM reminders WHERE reminder_id = ?", (r["reminder_id"],)).fetchone()
        conn.close()
        assert row["message_text"] == "new text"

    def test_one_time_reminder_due_at_updated(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="text", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        new_due = _future(120)
        manager.modify_whole_series(r["reminder_id"], new_due_at=new_due)
        conn = _connect(storage_dir)
        row = conn.execute("SELECT dtstart FROM reminders WHERE reminder_id = ?", (r["reminder_id"],)).fetchone()
        conn.close()
        assert row["dtstart"] != r["due_at"]

    def test_one_time_reminder_due_at_in_past_rejected(self, manager):
        r = manager.create_reminder(
            message_text="text", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        with pytest.raises(ReminderPastDateError):
            manager.modify_whole_series(
                r["reminder_id"], new_due_at=(now_local() - timedelta(hours=1)).isoformat()
            )

    def test_recurring_reminder_pattern_updated(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="daily standup", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.modify_whole_series(
            r["reminder_id"],
            new_recurrence=_weekly_recurrence(weekdays=["TU"], first_occurrence_at=_future(60 * 24)),
        )
        conn = _connect(storage_dir)
        row = conn.execute("SELECT rrule FROM reminders WHERE reminder_id = ?", (r["reminder_id"],)).fetchone()
        conn.close()
        assert "BYDAY=TU" in row["rrule"]

    def test_whole_series_edit_does_not_touch_existing_exceptions(self, manager, storage_dir):
        """The single most important assertion for this feature - FR-012."""
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occurrence_date = _weekly_recurrence()["first_occurrence_at"]
        manager.modify_single_occurrence(
            r["reminder_id"], occurrence_date_hint=occurrence_date, new_message_text="detached override"
        )
        manager.modify_whole_series(r["reminder_id"], new_message_text="whole series update")

        conn = _connect(storage_dir)
        exc = conn.execute(
            "SELECT summary_override FROM reminder_exceptions WHERE reminder_id = ?", (r["reminder_id"],)
        ).fetchone()
        master = conn.execute(
            "SELECT message_text FROM reminders WHERE reminder_id = ?", (r["reminder_id"],)
        ).fetchone()
        conn.close()
        assert exc["summary_override"] == "detached override"  # untouched by the whole-series edit
        assert master["message_text"] == "whole series update"

    def test_nonexistent_reminder_raises(self, manager):
        with pytest.raises(ReminderNotFoundError):
            manager.modify_whole_series("does-not-exist", new_message_text="x")

    def test_cancelled_reminder_raises(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="text", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        conn = _connect(storage_dir)
        conn.execute("UPDATE reminders SET status = 'cancelled' WHERE reminder_id = ?", (r["reminder_id"],))
        conn.commit()
        conn.close()
        with pytest.raises(ReminderNotFoundError):
            manager.modify_whole_series(r["reminder_id"], new_message_text="x")


class TestModifySingleOccurrence:
    def test_creates_exception_row_with_override_time_and_text(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occurrence_date = _weekly_recurrence()["first_occurrence_at"]
        new_due = _future(60 * 24 * 4)
        manager.modify_single_occurrence(
            r["reminder_id"], occurrence_date_hint=occurrence_date,
            new_message_text="moved", new_due_at=new_due,
        )
        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT * FROM reminder_exceptions WHERE reminder_id = ?", (r["reminder_id"],)
        ).fetchone()
        conn.close()
        assert row["summary_override"] == "moved"
        assert row["status"] == "CONFIRMED"
        assert row["dtstart_override"] is not None

    def test_does_not_touch_master_rrule(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        original_rrule_conn = _connect(storage_dir)
        original_rrule = original_rrule_conn.execute(
            "SELECT rrule FROM reminders WHERE reminder_id = ?", (r["reminder_id"],)
        ).fetchone()["rrule"]
        original_rrule_conn.close()

        occurrence_date = _weekly_recurrence()["first_occurrence_at"]
        manager.modify_single_occurrence(r["reminder_id"], occurrence_date_hint=occurrence_date, new_message_text="x")

        conn = _connect(storage_dir)
        row = conn.execute("SELECT rrule FROM reminders WHERE reminder_id = ?", (r["reminder_id"],)).fetchone()
        conn.close()
        assert row["rrule"] == original_rrule

    def test_rejects_one_time_reminder(self, manager):
        r = manager.create_reminder(
            message_text="text", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        with pytest.raises(InvalidRecurrenceError):
            manager.modify_single_occurrence(r["reminder_id"], occurrence_date_hint=_future(60), new_message_text="x")

    def test_past_new_due_at_rejected(self, manager):
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occurrence_date = _weekly_recurrence()["first_occurrence_at"]
        with pytest.raises(ReminderPastDateError):
            manager.modify_single_occurrence(
                r["reminder_id"], occurrence_date_hint=occurrence_date,
                new_due_at=(now_local() - timedelta(hours=1)).isoformat(),
            )

    def test_second_modify_of_same_occurrence_updates_not_duplicates(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occurrence_date = _weekly_recurrence()["first_occurrence_at"]
        manager.modify_single_occurrence(r["reminder_id"], occurrence_date_hint=occurrence_date, new_message_text="first edit")
        manager.modify_single_occurrence(r["reminder_id"], occurrence_date_hint=occurrence_date, new_message_text="second edit")

        conn = _connect(storage_dir)
        rows = conn.execute(
            "SELECT * FROM reminder_exceptions WHERE reminder_id = ?", (r["reminder_id"],)
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["summary_override"] == "second edit"


# --- Delete (T019a) ----------------------------------------------------------------

class TestDeleteWholeSeries:
    def test_marks_reminder_cancelled(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="text", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.delete_whole_series(r["reminder_id"])
        conn = _connect(storage_dir)
        row = conn.execute("SELECT status FROM reminders WHERE reminder_id = ?", (r["reminder_id"],)).fetchone()
        conn.close()
        assert row["status"] == "cancelled"

    def test_no_longer_counts_toward_cap(self, manager):
        r = manager.create_reminder(
            message_text="text", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.delete_whole_series(r["reminder_id"])
        assert manager.list_active() == []

    def test_cancels_pending_exceptions_but_leaves_fired_occurrences_untouched(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occurrence_date = _weekly_recurrence()["first_occurrence_at"]
        manager.modify_single_occurrence(r["reminder_id"], occurrence_date_hint=occurrence_date, new_message_text="moved")
        manager.record_occurrence_fired(
            r["reminder_id"], now_local() - timedelta(days=1), "already fired text"
        )

        manager.delete_whole_series(r["reminder_id"])

        conn = _connect(storage_dir)
        exc = conn.execute(
            "SELECT status FROM reminder_exceptions WHERE reminder_id = ?", (r["reminder_id"],)
        ).fetchone()
        fired = conn.execute(
            "SELECT * FROM fired_occurrences WHERE reminder_id = ?", (r["reminder_id"],)
        ).fetchone()
        conn.close()
        assert exc["status"] == "CANCELLED"
        assert fired is not None  # historical record untouched
        assert fired["message_text_sent"] == "already fired text"

    def test_nonexistent_reminder_raises(self, manager):
        with pytest.raises(ReminderNotFoundError):
            manager.delete_whole_series("does-not-exist")


class TestDeleteSingleOccurrence:
    def test_creates_cancelled_exception_row(self, manager, storage_dir):
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        occurrence_date = _weekly_recurrence()["first_occurrence_at"]
        manager.delete_single_occurrence(r["reminder_id"], occurrence_date_hint=occurrence_date)

        conn = _connect(storage_dir)
        row = conn.execute(
            "SELECT * FROM reminder_exceptions WHERE reminder_id = ?", (r["reminder_id"],)
        ).fetchone()
        conn.close()
        assert row["status"] == "CANCELLED"
        assert row["dtstart_override"] is None

    def test_rest_of_series_unaffected(self, manager):
        first = round_to_five_minutes(now_local() + timedelta(days=1))
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None, first_occurrence_at=first.isoformat()),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.delete_single_occurrence(r["reminder_id"], occurrence_date_hint=first.isoformat())

        second_day = first + timedelta(days=1)
        occs = manager.get_due_occurrences(second_day - timedelta(seconds=1), second_day + timedelta(minutes=1))
        assert len(occs) == 1

    def test_deleted_occurrence_itself_excluded_from_due(self, manager):
        first = round_to_five_minutes(now_local() + timedelta(days=1))
        r = manager.create_reminder(
            message_text="daily", schedule_type="recurring", one_time_due_at=None,
            recurrence=_weekly_recurrence(freq="daily", weekdays=None, first_occurrence_at=first.isoformat()),
            created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        manager.delete_single_occurrence(r["reminder_id"], occurrence_date_hint=first.isoformat())

        occs = manager.get_due_occurrences(first - timedelta(seconds=1), first + timedelta(minutes=1))
        assert occs == []

    def test_rejects_one_time_reminder(self, manager):
        r = manager.create_reminder(
            message_text="text", schedule_type="one_time", one_time_due_at=_future(60),
            recurrence=None, created_by_phone="972500000000", created_by_role="GODFATHER",
        )
        with pytest.raises(InvalidRecurrenceError):
            manager.delete_single_occurrence(r["reminder_id"], occurrence_date_hint=_future(60))
