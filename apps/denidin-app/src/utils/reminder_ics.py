"""
Feature 102: builds the iCalendar (.ics) file DeniDin sends alongside a reminder
(specs/repo/features/102-calendar-reminders-as-whatsapp-events/contracts/ics-file-format.md).

Every shape here was verified on a real Android phone (Gate Zero 2): an event that mirrors a DeniDin
reminder - zero duration, no alert, the "דנידין תזכורת: " prefix - with update/cancel keyed by UID +
SEQUENCE, recurring series, single-occurrence moves (override VEVENT) and skips (EXDATE).

Times carry `TZID=Asia/Jerusalem` and NO embedded VTIMEZONE component: the library-generated
VTIMEZONE shifted every occurrence of an updated recurring series one hour early on Android.
Pure functions - no I/O, no database, no clock except the DTSTAMP.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import icalendar

from src.utils.time_utils import now_local

REMINDER_ICS_SUMMARY_PREFIX = "דנידין תזכורת: "
ICS_TZID = "Asia/Jerusalem"
_TZ = ZoneInfo(ICS_TZID)
_METHODS = ("PUBLISH", "CANCEL")
_PRODID = "-//DeniDin//Reminders//HE"
_CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class CalendarException:
    """One stored single-occurrence change (a `reminder_exceptions` row)."""

    recurrence_id: str  # ISO, as stored: the original occurrence
    dtstart_override: Optional[str]
    summary_override: Optional[str]
    status: str  # "CANCELLED" -> EXDATE, anything else -> an override VEVENT


@dataclass(frozen=True)
class CalendarEntry:
    """One reminder, as the file describes it."""

    reminder_id: str
    message_text: str
    dtstart: str  # ISO, as stored
    rrule: Optional[str]
    sequence: int
    exceptions: Tuple[CalendarException, ...] = ()


def _to_israel(iso_text: str) -> datetime:
    """A stored ISO value as an aware Asia/Jerusalem datetime (naive values are taken to be Israel local)."""
    try:
        parsed = datetime.fromisoformat(iso_text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"not an ISO datetime: {iso_text!r}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_TZ)
    return parsed.astimezone(_TZ)


def _summary(text: str) -> str:
    return f"{REMINDER_ICS_SUMMARY_PREFIX}{text}"


def _base_event(uid: str, summary: str, start: datetime, sequence: int, stamp: datetime) -> icalendar.Event:
    event = icalendar.Event()
    event.add("uid", uid)
    event.add("dtstamp", stamp)
    event.add("sequence", sequence)
    event.add("dtstart", start)
    event.add("dtend", start)  # a reminder is an alarm: zero duration
    event.add("summary", summary)
    return event


def _master_event(entry: CalendarEntry, method: str, stamp: datetime) -> icalendar.Event:
    event = _base_event(entry.reminder_id, _summary(entry.message_text), _to_israel(entry.dtstart),
                        entry.sequence, stamp)
    if entry.rrule:
        event.add("rrule", icalendar.vRecur.from_ical(entry.rrule))
    if method == "CANCEL":
        event.add("status", _CANCELLED)
        return event
    skipped = [_to_israel(exc.recurrence_id) for exc in entry.exceptions if exc.status == _CANCELLED]
    if skipped:
        event.add("exdate", skipped)
    return event


def _override_event(entry: CalendarEntry, exc: CalendarException, stamp: datetime) -> icalendar.Event:
    original = _to_israel(exc.recurrence_id)
    start = _to_israel(exc.dtstart_override) if exc.dtstart_override else original
    event = _base_event(entry.reminder_id, _summary(exc.summary_override or entry.message_text),
                        start, entry.sequence, stamp)
    event.add("recurrence-id", original)
    return event


def build_ics(entries: Sequence[CalendarEntry], method: str = "PUBLISH") -> bytes:
    """One calendar with an event per reminder (each with its own UID).

    `PUBLISH` (create / change / on-demand): the master of each reminder, with an EXDATE per skipped
    occurrence and an override VEVENT per moved one. `CANCEL` (delete): the master only, STATUS:CANCELLED.
    Raises ValueError for no entries, an unknown method or an unparseable stored datetime."""
    if method not in _METHODS:
        raise ValueError(f"method must be one of {_METHODS}, got {method!r}")
    if not entries:
        raise ValueError("a calendar file needs at least one reminder")
    stamp = now_local().astimezone(timezone.utc)
    calendar = icalendar.Calendar()
    calendar.add("prodid", _PRODID)
    calendar.add("version", "2.0")
    calendar.add("method", method)
    for entry in entries:
        calendar.add_component(_master_event(entry, method, stamp))
        if method == "PUBLISH":
            for exc in entry.exceptions:
                if exc.status != _CANCELLED:
                    calendar.add_component(_override_event(entry, exc, stamp))
    return calendar.to_ical()


def ics_file_name(entries: Sequence[CalendarEntry], today: date) -> str:
    """ASCII file name: reminder_<id8>.ics for one reminder, reminders_<YYYYMMDD>.ics for several."""
    if len(entries) == 1:
        short_id = re.sub(r"[^A-Za-z0-9]", "", entries[0].reminder_id)[:8] or "calendar"
        return f"reminder_{short_id}.ics"
    return f"reminders_{today.strftime('%Y%m%d')}.ics"
