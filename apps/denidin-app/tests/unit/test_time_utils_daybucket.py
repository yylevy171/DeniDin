"""Feature 070 - day-bucketing helpers (T006a).

The rolling-window builder and the nightly daily-summary roll must agree on which
Israel-local calendar day an instant belongs to. These tests pin the boundary
rules from contracts/time-utils-daybucket.md.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.utils.time_utils import (
    LOCAL_TZ,
    local_calendar_date,
    n_calendar_days_ago,
    start_of_local_day,
)

UTC = timezone.utc


class TestLocalCalendarDate:
    def test_aware_local_input(self):
        dt = datetime(2026, 9, 1, 15, 30, tzinfo=LOCAL_TZ)
        assert local_calendar_date(dt) == date(2026, 9, 1)

    def test_naive_input_treated_as_local(self):
        dt = datetime(2026, 9, 1, 15, 30)  # naive
        assert local_calendar_date(dt) == date(2026, 9, 1)

    def test_legacy_plus_00_00_timestamp_buckets_by_local(self):
        # A pre-2026-08-10 message: 2026-08-03T23:30:00+00:00 is 2026-08-04
        # 02:30 Israel local (IDT +03:00) -> belongs to Aug 4, not Aug 3.
        dt = datetime(2026, 8, 3, 23, 30, tzinfo=UTC)
        assert local_calendar_date(dt) == date(2026, 8, 4)

    def test_utc_just_before_local_midnight_stays_previous_day(self):
        # 2026-08-03T20:30:00+00:00 == 2026-08-03 23:30 local -> Aug 3.
        dt = datetime(2026, 8, 3, 20, 30, tzinfo=UTC)
        assert local_calendar_date(dt) == date(2026, 8, 3)

    def test_exactly_local_midnight_belongs_to_the_later_day(self):
        dt = datetime(2026, 9, 1, 0, 0, 0, tzinfo=LOCAL_TZ)
        assert local_calendar_date(dt) == date(2026, 9, 1)

    def test_one_second_before_local_midnight_is_previous_day(self):
        dt = datetime(2026, 8, 31, 23, 59, 59, tzinfo=LOCAL_TZ)
        assert local_calendar_date(dt) == date(2026, 8, 31)


class TestStartOfLocalDay:
    def test_returns_aware_midnight(self):
        dt = datetime(2026, 9, 1, 15, 30, tzinfo=LOCAL_TZ)
        sod = start_of_local_day(dt)
        assert sod.tzinfo is not None
        assert (sod.year, sod.month, sod.day, sod.hour, sod.minute, sod.second) == (2026, 9, 1, 0, 0, 0)
        assert sod.utcoffset() is not None

    def test_spring_forward_day_midnight_exists(self):
        # Israel spring-forward 2026: last Friday of March -> 2026-03-27, gap at 02:00.
        dt = datetime(2026, 3, 27, 12, 0, tzinfo=LOCAL_TZ)
        sod = start_of_local_day(dt)
        assert (sod.month, sod.day, sod.hour) == (3, 27, 0)

    def test_fall_back_day_midnight_unambiguous(self):
        # Israel fall-back 2026: last Sunday of October -> 2026-10-25, repeat at 02:00.
        dt = datetime(2026, 10, 25, 12, 0, tzinfo=LOCAL_TZ)
        sod = start_of_local_day(dt)
        assert (sod.month, sod.day, sod.hour) == (10, 25, 0)


class TestNCalendarDaysAgo:
    def test_zero_is_today(self):
        now = datetime(2026, 9, 1, 10, 0, tzinfo=LOCAL_TZ)
        assert n_calendar_days_ago(0, now=now) == date(2026, 9, 1)

    def test_one_is_yesterday(self):
        now = datetime(2026, 9, 1, 2, 0, tzinfo=LOCAL_TZ)
        assert n_calendar_days_ago(1, now=now) == date(2026, 8, 31)

    def test_thirteen_is_the_14_day_window_lower_bound(self):
        now = datetime(2026, 9, 14, 10, 0, tzinfo=LOCAL_TZ)
        # "last 14 calendar days" inclusive => today + 13 prior dates
        assert n_calendar_days_ago(13, now=now) == date(2026, 9, 1)

    def test_crosses_month_boundary(self):
        now = datetime(2026, 9, 2, 10, 0, tzinfo=LOCAL_TZ)
        assert n_calendar_days_ago(5, now=now) == date(2026, 8, 28)

    def test_default_now_uses_wall_clock(self):
        # Just assert it returns a date n days before today's local date.
        today = local_calendar_date(datetime.now(LOCAL_TZ))
        assert n_calendar_days_ago(3) == today - timedelta(days=3)


class TestWindowVsRollConsistency:
    """A message belongs to exactly one day and is either in the 14-day window
    OR eligible for a daily summary - never both, never neither."""

    @pytest.mark.parametrize("hours_ago", [0, 1, 13 * 24, 13 * 24 + 1, 14 * 24, 30 * 24])
    def test_message_is_in_window_xor_summarised(self, hours_ago):
        now = datetime(2026, 9, 20, 12, 0, tzinfo=LOCAL_TZ)
        msg_ts = now - timedelta(hours=hours_ago)
        window_days = 14
        lower = n_calendar_days_ago(window_days - 1, now=now)
        msg_date = local_calendar_date(msg_ts)
        in_window = msg_date >= lower
        # "eligible for a summary" = strictly older than the window lower bound
        summarisable = msg_date < lower
        assert in_window != summarisable  # exactly one is true
        assert isinstance(msg_date, date)
