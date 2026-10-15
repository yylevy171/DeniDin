"""Feature 102 (T001A): the .ics builder - the shapes verified on a real Android phone in Gate Zero 2
(specs/repo/features/102-calendar-reminders-as-whatsapp-events/spec.md section 2)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import icalendar
import pytest

from src.utils.reminder_ics import (
    CalendarEntry, CalendarException, ICS_TZID, REMINDER_ICS_SUMMARY_PREFIX, build_ics, ics_file_name,
)

TZ = ZoneInfo("Asia/Jerusalem")


def _entry(**overrides):
    fields = dict(reminder_id="rem-aaaa-1111", message_text="לשלם לספק", dtstart="2026-10-20T11:00:00+03:00",
                  rrule=None, sequence=0, exceptions=())
    fields.update(overrides)
    return CalendarEntry(**fields)


def _events(ics_bytes):
    cal = icalendar.Calendar.from_ical(ics_bytes)
    return cal, [c for c in cal.walk() if c.name == "VEVENT"]


def test_constants():
    assert REMINDER_ICS_SUMMARY_PREFIX == "דנידין תזכורת: "
    assert ICS_TZID == "Asia/Jerusalem"


class TestOneTime:
    def test_event_shape(self):
        cal, events = _events(build_ics([_entry()]))
        assert str(cal["METHOD"]) == "PUBLISH" and str(cal["VERSION"]) == "2.0"
        assert len(events) == 1
        event = events[0]
        assert str(event["UID"]) == "rem-aaaa-1111"
        assert str(event["SUMMARY"]) == "דנידין תזכורת: לשלם לספק"
        assert int(event["SEQUENCE"]) == 0
        assert "RRULE" not in event

    def test_zero_duration_start_equals_end(self):
        _, (event,) = _events(build_ics([_entry()]))
        assert event["DTSTART"].dt == event["DTEND"].dt
        assert event["DTSTART"].dt == datetime(2026, 10, 20, 11, 0, tzinfo=TZ)

    def test_no_alarm_and_no_embedded_timezone_component(self):
        raw = build_ics([_entry()])
        assert b"BEGIN:VALARM" not in raw
        assert b"BEGIN:VTIMEZONE" not in raw  # the embedded definition shifted recurring updates on Android

    def test_times_carry_the_tzid_parameter(self):
        raw = build_ics([_entry()]).decode("utf-8")
        assert "DTSTART;TZID=Asia/Jerusalem:20261020T110000" in raw
        assert "DTEND;TZID=Asia/Jerusalem:20261020T110000" in raw

    def test_stored_offset_is_converted_to_israel_wall_clock(self):
        raw = build_ics([_entry(dtstart="2026-10-20T08:00:00+00:00")]).decode("utf-8")
        assert "DTSTART;TZID=Asia/Jerusalem:20261020T110000" in raw

    def test_sequence_is_written(self):
        _, (event,) = _events(build_ics([_entry(sequence=4)]))
        assert int(event["SEQUENCE"]) == 4

    def test_hebrew_text_round_trips(self):
        _, (event,) = _events(build_ics([_entry(message_text="דיון בבית משפט השלום - כהן")]))
        assert str(event["SUMMARY"]) == "דנידין תזכורת: דיון בבית משפט השלום - כהן"


class TestRecurring:
    def test_master_carries_the_rrule(self):
        raw = build_ics([_entry(rrule="FREQ=WEEKLY;COUNT=4")]).decode("utf-8")
        assert "RRULE:FREQ=WEEKLY;COUNT=4" in raw

    def test_series_across_the_clock_change_keeps_wall_clock_time(self):
        # created in summer time (+03:00), the series crosses 25 Oct 2026: the file states the wall-clock time once
        # and the phone expands it - nothing in the file may pin a UTC offset
        raw = build_ics([_entry(dtstart="2026-10-20T11:00:00+03:00", rrule="FREQ=WEEKLY;COUNT=4")]).decode("utf-8")
        assert "DTSTART;TZID=Asia/Jerusalem:20261020T110000" in raw
        assert "+0300" not in raw and "+0200" not in raw

    def test_cancelled_exception_becomes_an_exdate(self):
        exceptions = (CalendarException("2026-11-03T11:00:00+02:00", None, None, "CANCELLED"),)
        raw = build_ics([_entry(rrule="FREQ=WEEKLY;COUNT=4", exceptions=exceptions)]).decode("utf-8")
        assert "EXDATE;TZID=Asia/Jerusalem:20261103T110000" in raw
        _, events = _events(raw.encode("utf-8"))
        assert len(events) == 1  # a skip is not an override event

    def test_moved_occurrence_becomes_an_override_event(self):
        exceptions = (CalendarException("2026-10-27T11:00:00+02:00", "2026-10-27T16:00:00+02:00", None, "CONFIRMED"),)
        cal, events = _events(build_ics([_entry(rrule="FREQ=WEEKLY;COUNT=4", exceptions=exceptions, sequence=2)]))
        assert len(events) == 2
        override = [e for e in events if "RECURRENCE-ID" in e][0]
        assert str(override["UID"]) == "rem-aaaa-1111"
        assert override["RECURRENCE-ID"].dt == datetime(2026, 10, 27, 11, 0, tzinfo=TZ)
        assert override["DTSTART"].dt == datetime(2026, 10, 27, 16, 0, tzinfo=TZ)
        assert override["DTEND"].dt == override["DTSTART"].dt
        assert int(override["SEQUENCE"]) == 2
        assert str(override["SUMMARY"]) == "דנידין תזכורת: לשלם לספק"

    def test_override_with_its_own_text(self):
        exceptions = (CalendarException("2026-10-27T11:00:00+02:00", None, "טקסט אחר", "CONFIRMED"),)
        _, events = _events(build_ics([_entry(rrule="FREQ=WEEKLY;COUNT=4", exceptions=exceptions)]))
        override = [e for e in events if "RECURRENCE-ID" in e][0]
        assert str(override["SUMMARY"]) == "דנידין תזכורת: טקסט אחר"
        assert override["DTSTART"].dt == override["RECURRENCE-ID"].dt  # no time override: stays where it was

    def test_skip_and_move_in_one_file(self):
        exceptions = (
            CalendarException("2026-10-27T11:00:00+02:00", "2026-10-27T16:00:00+02:00", None, "CONFIRMED"),
            CalendarException("2026-11-03T11:00:00+02:00", None, None, "CANCELLED"),
        )
        raw = build_ics([_entry(rrule="FREQ=WEEKLY;COUNT=4", exceptions=exceptions)]).decode("utf-8")
        _, events = _events(raw.encode("utf-8"))
        assert len(events) == 2 and "EXDATE" in raw


class TestCancel:
    def test_cancel_method_and_status(self):
        cal, (event,) = _events(build_ics([_entry(sequence=3)], method="CANCEL"))
        assert str(cal["METHOD"]) == "CANCEL"
        assert str(event["STATUS"]) == "CANCELLED"
        assert int(event["SEQUENCE"]) == 3 and str(event["UID"]) == "rem-aaaa-1111"

    def test_cancel_of_a_series_keeps_the_rrule_and_drops_overrides(self):
        exceptions = (CalendarException("2026-10-27T11:00:00+02:00", "2026-10-27T16:00:00+02:00", None, "CONFIRMED"),)
        cal, events = _events(build_ics([_entry(rrule="FREQ=WEEKLY;COUNT=4", exceptions=exceptions)], method="CANCEL"))
        assert len(events) == 1 and "RRULE" in events[0] and "RECURRENCE-ID" not in events[0]


class TestSeveralReminders:
    def test_one_calendar_one_event_per_reminder_each_with_its_own_uid(self):
        entries = [_entry(reminder_id="a"), _entry(reminder_id="b", rrule="FREQ=DAILY;COUNT=3"), _entry(reminder_id="c")]
        _, events = _events(build_ics(entries))
        assert [str(e["UID"]) for e in events] == ["a", "b", "c"]


class TestRejections:
    def test_empty_entries(self):
        with pytest.raises(ValueError):
            build_ics([])

    def test_unknown_method(self):
        with pytest.raises(ValueError):
            build_ics([_entry()], method="REQUEST")

    def test_unparseable_dtstart(self):
        with pytest.raises(ValueError):
            build_ics([_entry(dtstart="not-a-date")])


class TestFileNames:
    def test_single_reminder(self):
        assert ics_file_name([_entry(reminder_id="abcdef12-3456")], date(2026, 10, 15)) == "reminder_abcdef12.ics"

    def test_several_reminders(self):
        assert ics_file_name([_entry(), _entry(reminder_id="b")], date(2026, 10, 15)) == "reminders_20261015.ics"

    def test_names_are_ascii(self):
        assert ics_file_name([_entry(reminder_id="שלום-1234567")], date(2026, 10, 15)).isascii() is True
