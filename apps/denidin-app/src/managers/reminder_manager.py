"""
ReminderManager - Reminder Persistence and Recurrence Construction (Feature 054).

Owns {data_root}/reminders/reminders.db - a small SQLite database (not the
per-entity-JSON-file pattern LedgerEventManager uses; reminders are mutable and
query-heavy in a way that pattern doesn't serve well - see
specs/in-progress/054-reminders-functionality-mgmt/data-model.md for the full
schema and rationale).

There is conceptually ONE reminder list, owned by "the godfather" - GODFATHER and
ADMIN both fully manage it via the existing RBAC gate (no per-user ownership
filtering anywhere in this module). `created_by_phone`/`created_by_role` are
traceability-only fields, never consulted for access/cap decisions.

Recurrence is stored as a real RFC5545 RRULE string on the `reminders` row -
this module is responsible for CONSTRUCTING and VALIDATING that string from a
recurrence dict (matching contracts/reminder-tool-schemas.md's `create_reminder`
argument shape). Resolving concrete due occurrences from it (via `icalendar`/
`recurring_ical_events`) is a separate concern, added in a later phase.
"""

import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import icalendar
import recurring_ical_events  # type: ignore[import-untyped]  # no stub package exists

from src.utils.logger import get_logger
from src.utils.time_utils import LOCAL_TZ, local_isoformat, now_local, to_local

logger = get_logger(__name__)

_VALID_FREQ = {"daily", "weekly", "monthly"}
_VALID_WEEKDAYS = {"MO", "TU", "WE", "TH", "FR", "SA", "SU"}
_VALID_END_CONDITIONS = {"never", "after_n", "until_date"}


class ReminderError(Exception):
    """Base class for reminder validation/business-rule failures."""


class ReminderPastDateError(ReminderError):
    """Raised when a reminder's due date/time (after rounding) is not in the future."""


class ReminderCapExceededError(ReminderError):
    """Raised when creating a reminder would exceed the active-reminder cap."""


class ReminderNotFoundError(ReminderError):
    """Raised when a reminder_id doesn't match any active reminder (modify/delete)."""


class InvalidRecurrenceError(ReminderError):
    """Raised when a recurrence dict (or the one_time/recurring shape itself) is malformed."""


def round_to_five_minutes(dt: datetime) -> datetime:
    """Round an aware datetime to the nearest 5 minutes (ties round up).

    Always returns an Asia/Jerusalem-aware datetime, regardless of the input's
    own tzinfo (naive input is treated as already-local, per time_utils.to_local).
    """
    dt = to_local(dt)
    epoch = dt.timestamp()
    remainder = epoch % 300
    if remainder == 0:
        rounded_epoch = epoch
    elif remainder < 150:
        rounded_epoch = epoch - remainder
    else:
        rounded_epoch = epoch + (300 - remainder)
    # Explicit microsecond=0, not left to float arithmetic alone: a rounded-to-
    # 5-minutes datetime should be exactly clean, and live-verified 2026-08-16
    # that recurring_ical_events returns the SAME anchor occurrence TWICE (once
    # with microseconds, once truncated) when DTSTART carries any - so this
    # isn't just cosmetic, it prevents a real duplicate-delivery bug at the
    # source rather than relying on a downstream dedup.
    return datetime.fromtimestamp(rounded_epoch, tz=LOCAL_TZ).replace(microsecond=0)


def _parse_iso(value: str, *, field_name: str) -> datetime:
    try:
        return to_local(datetime.fromisoformat(value))
    except (TypeError, ValueError) as e:
        raise InvalidRecurrenceError(f"{field_name} is not a valid ISO-8601 datetime: {value!r}") from e


def _parse_local_no_micros(value: str) -> datetime:
    """Parse a stored ISO datetime for icalendar/recurring_ical_events construction,
    always stripping microseconds - defends against a real, live-verified library
    quirk (2026-08-16): recurring_ical_events returns the SAME anchor occurrence
    TWICE for a recurring VEVENT whose DTSTART carries microseconds (one copy with,
    one truncated). Every stored dtstart/recurrence_id/dtstart_override SHOULD
    already be microsecond-free (round_to_five_minutes explicitly clears it), this
    is defense-in-depth at the read boundary regardless, matching this codebase's
    existing "defend at the boundary, don't trust the input" discipline.
    """
    return to_local(datetime.fromisoformat(value)).replace(microsecond=0)


def _validate_freq_and_interval(recurrence: Dict[str, Any]) -> "tuple[str, int]":
    freq = recurrence.get("freq")
    if freq not in _VALID_FREQ:
        raise InvalidRecurrenceError(
            f"freq must be one of {sorted(_VALID_FREQ)}, got {freq!r} "
            "(yearly is not a supported value - FR-007)"
        )
    interval = recurrence.get("interval", 1)
    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 1:
        raise InvalidRecurrenceError(f"interval must be a positive integer, got {interval!r}")
    return freq, interval


def _build_weekly_part(recurrence: Dict[str, Any]) -> str:
    weekdays = recurrence.get("weekdays")
    if not weekdays:
        raise InvalidRecurrenceError("weekdays is required (non-empty) when freq='weekly'")
    invalid = set(weekdays) - _VALID_WEEKDAYS
    if invalid:
        raise InvalidRecurrenceError(f"invalid weekday(s): {sorted(invalid)}")
    return f"BYDAY={','.join(weekdays)}"


def _build_monthly_part(recurrence: Dict[str, Any]) -> str:
    month_day = recurrence.get("month_day")
    month_nth_weekday = recurrence.get("month_nth_weekday")
    has_day = month_day is not None
    has_nth = month_nth_weekday is not None
    if has_day == has_nth:  # neither, or both
        raise InvalidRecurrenceError(
            "exactly one of month_day/month_nth_weekday is required when freq='monthly'"
        )
    if has_day:
        if not isinstance(month_day, int) or not 1 <= month_day <= 31:
            raise InvalidRecurrenceError(f"month_day must be 1-31, got {month_day!r}")
        return f"BYMONTHDAY={month_day}"
    # has_nth is True here (has_day is False, and the has_day == has_nth check
    # above already ruled out "both False") - so month_nth_weekday is not None,
    # but mypy can't follow that cross-variable boolean equality narrowing,
    # hence this explicit (unreachable in practice) guard.
    if month_nth_weekday is None:
        raise InvalidRecurrenceError("month_nth_weekday is required here")
    n = month_nth_weekday.get("n")
    weekday = month_nth_weekday.get("weekday")
    if n not in (1, 2, 3, 4, -1) or weekday not in _VALID_WEEKDAYS:
        raise InvalidRecurrenceError(f"invalid month_nth_weekday: {month_nth_weekday!r}")
    return f"BYDAY={n}{weekday}"


def _build_end_condition_part(recurrence: Dict[str, Any]) -> Optional[str]:
    end_condition = recurrence.get("end_condition")
    if end_condition not in _VALID_END_CONDITIONS:
        raise InvalidRecurrenceError(
            f"end_condition must be one of {sorted(_VALID_END_CONDITIONS)}, got {end_condition!r}"
        )
    if end_condition == "after_n":
        end_count = recurrence.get("end_count")
        if not isinstance(end_count, int) or isinstance(end_count, bool) or end_count < 1:
            raise InvalidRecurrenceError(f"end_count must be a positive integer, got {end_count!r}")
        return f"COUNT={end_count}"
    if end_condition == "until_date":
        end_until = recurrence.get("end_until")
        if not end_until:
            raise InvalidRecurrenceError("end_until is required when end_condition='until_date'")
        try:
            until_date = date.fromisoformat(end_until)
        except (TypeError, ValueError) as e:
            raise InvalidRecurrenceError(f"end_until is not a valid ISO-8601 date: {end_until!r}") from e
        if until_date < now_local().date():
            raise ReminderPastDateError(f"end_until {end_until} is in the past")
        return f"UNTIL={until_date.strftime('%Y%m%dT235959')}"
    return None  # end_condition == "never"


def _build_rrule(recurrence: Dict[str, Any]) -> str:
    """Build an RFC5545 RRULE string from a recurrence dict, validating it first.

    Matches contracts/reminder-tool-schemas.md's `create_reminder.recurrence` shape.
    Split into per-concern helpers (freq/interval, weekly, monthly, end-condition) -
    each one independently unit-tested, this function just composes them in order.
    """
    freq, interval = _validate_freq_and_interval(recurrence)
    parts = [f"FREQ={freq.upper()}"]
    if interval != 1:
        parts.append(f"INTERVAL={interval}")

    if freq == "weekly":
        parts.append(_build_weekly_part(recurrence))
    elif freq == "monthly":
        parts.append(_build_monthly_part(recurrence))

    end_part = _build_end_condition_part(recurrence)
    if end_part:
        parts.append(end_part)

    return ";".join(parts)


class ReminderManager:
    """Owns {data_root}/reminders/reminders.db - the one shared reminder list."""

    def __init__(self, storage_dir: str, max_active_reminders: int = 20):
        """
        Args:
            storage_dir: Directory for reminder storage. Callers MUST compose this
                from AppConfiguration.data_root at construction time
                (Path(config.data_root) / "reminders"), matching LedgerEventManager's
                pattern.
            max_active_reminders: The active-reminder cap (FR-006). Callers MUST
                compose this from config.reminders.get('max_active_reminders', 20) -
                never read from config internally, same discipline as storage_dir.
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_active_reminders = max_active_reminders
        self._db_path = self.storage_dir / "reminders.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        logger.info(
            f"ReminderManager initialized: db_path={self._db_path}, "
            f"max_active_reminders={max_active_reminders}"
        )

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                reminder_id TEXT PRIMARY KEY,
                message_text TEXT NOT NULL,
                rrule TEXT,
                dtstart TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                created_by_phone TEXT NOT NULL,
                created_by_role TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reminder_exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id TEXT NOT NULL REFERENCES reminders(reminder_id),
                recurrence_id TEXT NOT NULL,
                dtstart_override TEXT,
                summary_override TEXT,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fired_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id TEXT NOT NULL REFERENCES reminders(reminder_id),
                occurrence_datetime TEXT NOT NULL,
                delivered_at TEXT NOT NULL,
                message_text_sent TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def _count_active(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM reminders WHERE status = 'active'"
        ).fetchone()
        return int(row["c"])

    def create_reminder(
        self,
        message_text: str,
        schedule_type: str,
        one_time_due_at: Optional[str],
        recurrence: Optional[Dict[str, Any]],
        created_by_phone: str,
        created_by_role: str,
    ) -> Dict[str, str]:
        """Validate, round, and persist a new reminder. Returns {"reminder_id", "due_at"}.

        Raises InvalidRecurrenceError / ReminderPastDateError / ReminderCapExceededError
        on any validation failure - no partial row is ever persisted.
        """
        rrule_str, dtstart = self.resolve_schedule(schedule_type, one_time_due_at, recurrence)

        if self._count_active() >= self.max_active_reminders:
            raise ReminderCapExceededError(
                f"active-reminder cap of {self.max_active_reminders} reached"
            )

        reminder_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO reminders "
            "(reminder_id, message_text, rrule, dtstart, status, created_at, "
            " created_by_phone, created_by_role) VALUES (?, ?, ?, ?, 'active', ?, ?, ?)",
            (
                reminder_id, message_text, rrule_str, dtstart.isoformat(),
                local_isoformat(), created_by_phone, created_by_role,
            ),
        )
        self._conn.commit()

        logger.info(
            f"Created reminder {reminder_id} ({'recurring' if rrule_str else 'one-time'}), "
            f"due_at={dtstart.isoformat()}, created_by={created_by_phone!r}/{created_by_role!r}"
        )
        return {"reminder_id": reminder_id, "due_at": dtstart.isoformat()}

    @staticmethod
    def resolve_schedule(
        schedule_type: str,
        one_time_due_at: Optional[str],
        recurrence: Optional[Dict[str, Any]],
    ) -> "tuple[Optional[str], datetime]":
        """Validate + round a proposed schedule WITHOUT persisting or checking the cap.

        Returns (rrule_str_or_None, rounded_dtstart). Raises InvalidRecurrenceError/
        ReminderPastDateError exactly like create_reminder - shared by create_reminder
        itself (avoiding duplicated validation logic) and by AIHandler at PROPOSAL
        time (before the approval gate), so the approval summary shown to the user
        already reflects the exact rounded time that will be persisted on approval,
        per FR-005/the 5-minute-rounding design decision. create_reminder re-runs
        this again at actual persist time (called fresh, not cached) - a deliberate
        TOCTOU-closing re-check, not redundant duplication (see
        contracts/local-tool-approval-gate.md).
        """
        if schedule_type not in ("one_time", "recurring"):
            raise InvalidRecurrenceError(
                f"schedule_type must be 'one_time' or 'recurring', got {schedule_type!r}"
            )

        if schedule_type == "one_time":
            if not one_time_due_at:
                raise InvalidRecurrenceError(
                    "one_time_due_at is required when schedule_type='one_time'"
                )
            rrule_str = None
            dtstart = round_to_five_minutes(_parse_iso(one_time_due_at, field_name="one_time_due_at"))
            if dtstart <= now_local():
                raise ReminderPastDateError(
                    f"one_time_due_at {dtstart.isoformat()} is not in the future (after rounding)"
                )
        else:
            if not recurrence:
                raise InvalidRecurrenceError("recurrence is required when schedule_type='recurring'")
            rrule_str = _build_rrule(recurrence)
            first_occurrence_at = recurrence.get("first_occurrence_at")
            if not first_occurrence_at:
                raise InvalidRecurrenceError(
                    "recurrence.first_occurrence_at is required when schedule_type='recurring'"
                )
            dtstart = round_to_five_minutes(
                _parse_iso(first_occurrence_at, field_name="recurrence.first_occurrence_at")
            )
            if dtstart <= now_local():
                raise ReminderPastDateError(
                    f"recurrence.first_occurrence_at {dtstart.isoformat()} is not in the "
                    "future (after rounding)"
                )
        return rrule_str, dtstart

    def list_active(self) -> List[Dict[str, Any]]:
        """All active reminders, for list_reminders (FR-013) / disambiguation.

        Cancelled reminders are never returned.
        """
        rows = self._conn.execute(
            "SELECT reminder_id, message_text, rrule, dtstart, created_by_phone, "
            "created_by_role FROM reminders WHERE status = 'active' ORDER BY dtstart"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_reminder(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        """Public single-reminder lookup (active only), returns None if not found -
        for approval-summary display and pre-validation before proposing a modify/
        delete, distinct from _get_active_reminder_row (raises, used internally by
        the actual modify/delete methods once the action is approved).
        """
        row = self._conn.execute(
            "SELECT reminder_id, message_text, rrule, dtstart, created_by_phone, "
            "created_by_role FROM reminders WHERE reminder_id = ? AND status = 'active'",
            (reminder_id,),
        ).fetchone()
        return dict(row) if row else None

    def _reconstruct_calendar(self, reminder_row: sqlite3.Row) -> "icalendar.Calendar":
        """Build an icalendar.Calendar with the master VEVENT plus one override VEVENT
        per stored reminder_exceptions row - the input recurring_ical_events resolves.
        """
        cal = icalendar.Calendar()

        master = icalendar.Event()
        master.add("UID", reminder_row["reminder_id"])
        master.add("SUMMARY", reminder_row["message_text"])
        master.add("DTSTART", _parse_local_no_micros(reminder_row["dtstart"]))
        if reminder_row["rrule"]:
            master.add("RRULE", icalendar.vRecur.from_ical(reminder_row["rrule"]))
        cal.add_component(master)

        exceptions = self._conn.execute(
            "SELECT * FROM reminder_exceptions WHERE reminder_id = ?",
            (reminder_row["reminder_id"],),
        ).fetchall()
        for exc in exceptions:
            recurrence_id_dt = _parse_local_no_micros(exc["recurrence_id"])
            override = icalendar.Event()
            override.add("UID", reminder_row["reminder_id"])
            override.add("RECURRENCE-ID", recurrence_id_dt)
            override_dtstart = (
                _parse_local_no_micros(exc["dtstart_override"])
                if exc["dtstart_override"] else recurrence_id_dt
            )
            override.add("DTSTART", override_dtstart)
            override.add("SUMMARY", exc["summary_override"] or reminder_row["message_text"])
            override.add("STATUS", exc["status"])
            cal.add_component(override)

        return cal

    def get_due_occurrences(
        self, window_start: datetime, window_end: datetime
    ) -> List[Dict[str, Any]]:
        """Occurrences due in [window_start, window_end) across all active reminders,
        excluding any that have already fired (see record_occurrence_fired) - this is
        what makes it safe for the delivery sweep to use a generous lookback window
        (catching up on a missed sweep) without re-delivering something already sent.

        Each result is {"reminder_id", "occurrence_datetime", "message_text"}.
        recurring_ical_events does NOT suppress STATUS=CANCELLED occurrences on its own
        (live-verified 2026-08-16, see research.md) - filtered out here explicitly.
        """
        window_start = to_local(window_start)
        window_end = to_local(window_end)
        results: List[Dict[str, Any]] = []
        for row in self._conn.execute("SELECT * FROM reminders WHERE status = 'active'").fetchall():
            already_fired = {
                r["occurrence_datetime"]
                for r in self._conn.execute(
                    "SELECT occurrence_datetime FROM fired_occurrences WHERE reminder_id = ?",
                    (row["reminder_id"],),
                ).fetchall()
            }
            cal = self._reconstruct_calendar(row)
            for occ in recurring_ical_events.of(cal).between(window_start, window_end):
                if str(occ.get("STATUS", "")) == "CANCELLED":
                    continue
                occurrence_dt = occ["DTSTART"].dt
                if occurrence_dt.isoformat() in already_fired:
                    continue
                results.append({
                    "reminder_id": row["reminder_id"],
                    "occurrence_datetime": occurrence_dt,
                    "message_text": str(occ.get("SUMMARY", row["message_text"])),
                })
        return results

    def record_occurrence_fired(
        self, reminder_id: str, occurrence_datetime: datetime, message_text_sent: str
    ) -> None:
        """Append a fired_occurrences row - called by the delivery sweep immediately
        after a successful send. Idempotent in effect (not in storage - a duplicate
        call would insert a second row), but the caller only ever calls this once per
        successful send; get_due_occurrences' already-fired filter is what actually
        prevents re-delivery on a later sweep, not this method refusing a duplicate.
        """
        self._conn.execute(
            "INSERT INTO fired_occurrences "
            "(reminder_id, occurrence_datetime, delivered_at, message_text_sent) "
            "VALUES (?, ?, ?, ?)",
            (reminder_id, to_local(occurrence_datetime).isoformat(), local_isoformat(), message_text_sent),
        )
        self._conn.commit()
        logger.info(
            f"Recorded fired occurrence for reminder {reminder_id} "
            f"(occurrence_datetime={occurrence_datetime.isoformat()})"
        )

    def _get_active_reminder_row(self, reminder_id: str) -> sqlite3.Row:
        row = self._conn.execute(
            "SELECT * FROM reminders WHERE reminder_id = ? AND status = 'active'", (reminder_id,)
        ).fetchone()
        if row is None:
            raise ReminderNotFoundError(f"no active reminder with reminder_id={reminder_id!r}")
        return cast(sqlite3.Row, row)

    def modify_whole_series(
        self,
        reminder_id: str,
        new_message_text: Optional[str] = None,
        new_recurrence: Optional[Dict[str, Any]] = None,
        new_due_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Modify a reminder's message text and/or schedule going forward (FR-012
        whole-series scope). Applies identically to a one-time reminder (there's
        only one "series" of one occurrence - `new_due_at` is how its due time
        changes) and a recurring one (`new_recurrence` replaces the RRULE/first
        occurrence going forward). Never touches `reminder_exceptions` rows - the
        permanence rule (a Detached/exception occurrence, once created, never
        reverts to following the plain rule again).
        """
        row = self._get_active_reminder_row(reminder_id)
        updates: Dict[str, Any] = {}

        if new_message_text:
            updates["message_text"] = new_message_text

        if row["rrule"] is not None:
            if new_recurrence is not None:
                rrule_str, dtstart = self.resolve_schedule("recurring", None, new_recurrence)
                updates["rrule"] = rrule_str
                updates["dtstart"] = dtstart.isoformat()
        else:
            if new_due_at is not None:
                _, dtstart = self.resolve_schedule("one_time", new_due_at, None)
                updates["dtstart"] = dtstart.isoformat()

        if not updates:
            return {"reminder_id": reminder_id, "changed": False}

        set_clause = ", ".join(f"{col} = ?" for col in updates)
        self._conn.execute(
            f"UPDATE reminders SET {set_clause} WHERE reminder_id = ?",
            (*updates.values(), reminder_id),
        )
        self._conn.commit()
        logger.info(f"Modified whole series for reminder {reminder_id}: {list(updates)}")
        return {"reminder_id": reminder_id, "changed": True, **updates}

    def _upsert_exception(
        self, reminder_id: str, recurrence_id: datetime, *,
        dtstart_override: Optional[datetime], summary_override: Optional[str], status: str,
    ) -> None:
        recurrence_id_iso = recurrence_id.isoformat()
        existing = self._conn.execute(
            "SELECT id FROM reminder_exceptions WHERE reminder_id = ? AND recurrence_id = ?",
            (reminder_id, recurrence_id_iso),
        ).fetchone()
        dtstart_override_iso = dtstart_override.isoformat() if dtstart_override else None
        if existing:
            self._conn.execute(
                "UPDATE reminder_exceptions SET dtstart_override = ?, summary_override = ?, "
                "status = ? WHERE id = ?",
                (dtstart_override_iso, summary_override, status, existing["id"]),
            )
        else:
            self._conn.execute(
                "INSERT INTO reminder_exceptions "
                "(reminder_id, recurrence_id, dtstart_override, summary_override, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (reminder_id, recurrence_id_iso, dtstart_override_iso, summary_override, status),
            )
        self._conn.commit()

    def modify_single_occurrence(
        self,
        reminder_id: str,
        occurrence_date_hint: str,
        new_message_text: Optional[str] = None,
        new_due_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Modify a single occurrence of a recurring reminder (FR-012 single-
        occurrence scope) - creates or updates a `reminder_exceptions` row
        (Detached occurrence), never touching the master RRULE or any sibling
        occurrence. Permanent relative to the series: a later whole-series edit
        never overwrites this row (see modify_whole_series).
        """
        row = self._get_active_reminder_row(reminder_id)
        if row["rrule"] is None:
            raise InvalidRecurrenceError(
                "single-occurrence modify only applies to a recurring reminder"
            )
        recurrence_id_dt = _parse_local_no_micros(occurrence_date_hint)

        dtstart_override = None
        if new_due_at is not None:
            _, dtstart_override = self.resolve_schedule("one_time", new_due_at, None)

        self._upsert_exception(
            reminder_id, recurrence_id_dt,
            dtstart_override=dtstart_override, summary_override=new_message_text,
            status="CONFIRMED",
        )
        logger.info(
            f"Modified single occurrence for reminder {reminder_id} "
            f"(recurrence_id={recurrence_id_dt.isoformat()})"
        )
        return {
            "reminder_id": reminder_id,
            "occurrence_date": recurrence_id_dt.isoformat(),
            "new_due_at": dtstart_override.isoformat() if dtstart_override else None,
        }

    def delete_whole_series(self, reminder_id: str) -> Dict[str, Any]:
        """Cancel a reminder entirely (FR-012 whole-series scope): marks the
        `reminders` row cancelled and cancels every remaining pending exception -
        `fired_occurrences` (historical record) is never touched.
        """
        self._get_active_reminder_row(reminder_id)  # raises ReminderNotFoundError if absent
        self._conn.execute(
            "UPDATE reminders SET status = 'cancelled' WHERE reminder_id = ?", (reminder_id,)
        )
        self._conn.execute(
            "UPDATE reminder_exceptions SET status = 'CANCELLED' "
            "WHERE reminder_id = ? AND status = 'CONFIRMED'",
            (reminder_id,),
        )
        self._conn.commit()
        logger.info(f"Deleted whole series for reminder {reminder_id}")
        return {"reminder_id": reminder_id, "status": "cancelled"}

    def delete_single_occurrence(self, reminder_id: str, occurrence_date_hint: str) -> Dict[str, Any]:
        """Cancel a single occurrence of a recurring reminder (FR-012 single-
        occurrence scope) - the rest of the series is unaffected and continues
        firing on schedule.
        """
        row = self._get_active_reminder_row(reminder_id)
        if row["rrule"] is None:
            raise InvalidRecurrenceError(
                "single-occurrence delete only applies to a recurring reminder"
            )
        recurrence_id_dt = _parse_local_no_micros(occurrence_date_hint)
        self._upsert_exception(
            reminder_id, recurrence_id_dt,
            dtstart_override=None, summary_override=None, status="CANCELLED",
        )
        logger.info(
            f"Deleted single occurrence for reminder {reminder_id} "
            f"(recurrence_id={recurrence_id_dt.isoformat()})"
        )
        return {"reminder_id": reminder_id, "occurrence_date": recurrence_id_dt.isoformat()}
