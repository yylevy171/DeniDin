"""Israel local time - the single time representation used everywhere (bugfix-037).

Until 2026-08-10 three representations coexisted, none of them labelled: log
lines in UTC (and only by accident - see below), `captured_at`/`message_timestamp`
in UTC with an explicit offset, and the ledger's `event_date`/`event_time`/
`event_id` in Israel local time with no offset. The same instant read as
`03:00:27` in one place and `06:00` in another, and a reviewer comparing an
`event_id` against a log line saw a 3-hour discrepancy that did not exist.

The resolution, by explicit user decision (2026-08-10): **everything is Israel
local time now. There is no UTC anywhere.** This matches the data the system
actually handles - Morning documents and bank-transfer screenshots state Israeli
local times, and Events.csv's date/time columns have always been local - so the
representation now matches the domain instead of being converted at the edges.

Rules this module exists to enforce:
- Every datetime is timezone-**aware**, in `Asia/Jerusalem`. Never naive: a naive
  local datetime breaks comparisons against stored values and silently gets DST
  wrong twice a year.
- Every persisted ISO-8601 timestamp therefore carries a real offset (`+03:00`
  in IDT, `+02:00` in IST), so each record is self-describing on its own.
- Values written before this change carry `+00:00`. They stay valid and compare
  correctly against new ones precisely because both sides are aware - this is a
  fix-forward change, nothing is migrated.

Unix epoch timestamps are unaffected by any of this (an epoch is an instant, not
a representation); `local_from_timestamp` is how one becomes a displayable local
datetime.

`apps/denidin-app/src/utils/time_utils.py` is the byte-identical twin of this
module, same as `logger.py` - the two apps must not
disagree about what time it is.
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Jerusalem")


def now_local() -> datetime:
    """Current time as an aware Asia/Jerusalem datetime.

    The replacement for `datetime.now(timezone.utc)` throughout both apps
    (CONSTITUTION §II, amended 2026-08-10). Never `datetime.now()` - that
    returns a naive value and is still forbidden.
    """
    return datetime.now(LOCAL_TZ)


def to_local(value: datetime) -> datetime:
    """Convert any datetime to Asia/Jerusalem.

    A naive input is assumed to already be local (the only representation this
    codebase produces now) rather than silently treated as UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TZ)
    return value.astimezone(LOCAL_TZ)


def local_from_timestamp(epoch_seconds: Union[int, float]) -> datetime:
    """An epoch timestamp (e.g. Green API's `timestamp`) as local time."""
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).astimezone(LOCAL_TZ)


def local_isoformat(value: Optional[datetime] = None) -> str:
    """ISO-8601 in local time, always carrying the real offset. Defaults to now."""
    return (value or now_local()).astimezone(LOCAL_TZ).isoformat()


# --- Day-bucketing helpers (Feature 070) -------------------------------------
# The rolling-window builder and the nightly daily-summary roll MUST agree on
# "which Israel-local calendar day does this instant belong to". These three
# helpers are the single implementation both use, so a message can never be
# in the window AND summarised, or in neither (REQ-MEM-003, spec Edge Cases).
# A pre-2026-08-10 message with a `+00:00` offset buckets correctly because
# `to_local` converts before `.date()` is taken.

def local_calendar_date(value: datetime) -> date:
    """The Israel-local calendar date of an instant. Total function - a naive
    input is treated as already-local (per `to_local`), an aware input is
    converted first."""
    return to_local(value).date()


def start_of_local_day(value: datetime) -> datetime:
    """Aware Asia/Jerusalem datetime at 00:00:00 of `local_calendar_date(value)`.

    Midnight is unambiguous on both DST-transition days (the spring-forward gap
    is at 02:00, the fall-back repeat is at 02:00), so no `fold` handling is
    needed here.
    """
    return datetime.combine(local_calendar_date(value), time.min, tzinfo=LOCAL_TZ)


def n_calendar_days_ago(n: int, now: Optional[datetime] = None) -> date:
    """The Israel-local calendar date `n` days before today (or before `now`).

    "The last 14 calendar days" (inclusive of today) is every message whose
    `local_calendar_date` is `>= n_calendar_days_ago(13)`. The nightly roll's
    "yesterday" is `n_calendar_days_ago(1)`.
    """
    base = local_calendar_date(now or now_local())
    return base - timedelta(days=n)
