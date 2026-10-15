# Contract: the `.ics` file DeniDin generates

Every shape below was verified on the PM's Android phone (Gate Zero 2, `spec.md` section 2).

## Common
- `BEGIN:VCALENDAR`, `VERSION:2.0`, `PRODID:-//DeniDin//Reminders//HE`, `METHOD:PUBLISH|CANCEL`.
- **No `VTIMEZONE` component. No `VALARM`.** Every `DTSTART`/`DTEND`/`EXDATE`/`RECURRENCE-ID` is
  `;TZID=Asia/Jerusalem:<local wall time>`.
- Per reminder: `UID` = `reminder_id`, `SEQUENCE` = the claimed `ics_sequence`, `DTSTAMP` = now (UTC `Z`).
- `SUMMARY` = `דנידין תזכורת: ` + the reminder text (override `VEVENT`s: the override text, else the master's).
- Zero duration: `DTEND` equals `DTSTART`.

## Operations
| Operation | Components |
| :-- | :-- |
| create / modify whole / on-demand, one-time | one `VEVENT` |
| same, recurring | master `VEVENT` with `RRULE`, plus an `EXDATE` per cancelled occurrence, plus one override `VEVENT` per non-cancelled exception (`RECURRENCE-ID` = the original occurrence) |
| delete (whole) | `METHOD:CANCEL`; master `VEVENT` with `STATUS:CANCELLED` (and its `RRULE` if recurring), no overrides |
| several reminders at once | one calendar, the above for each reminder, each with its own `UID` |

## File names (ASCII)
- one reminder: `reminder_<first 8 chars of reminder_id>.ics`
- several: `reminders_<YYYYMMDD>.ics` (Israel local date)
- caption: empty. (The confirmation text carries the words.)

## Builder API (`src/utils/reminder_ics.py`)
```python
REMINDER_ICS_SUMMARY_PREFIX = "דנידין תזכורת: "
ICS_TZID = "Asia/Jerusalem"

@dataclass(frozen=True)
class CalendarException:
    recurrence_id: str          # ISO, as stored
    dtstart_override: Optional[str]
    summary_override: Optional[str]
    status: str                 # "CANCELLED" -> EXDATE, anything else -> override VEVENT

@dataclass(frozen=True)
class CalendarEntry:
    reminder_id: str
    message_text: str
    dtstart: str                # ISO, as stored
    rrule: Optional[str]
    sequence: int
    exceptions: Tuple[CalendarException, ...] = ()

def build_ics(entries: Sequence[CalendarEntry], method: str = "PUBLISH") -> bytes: ...
def ics_file_name(entries: Sequence[CalendarEntry], today: date) -> str: ...
```
`method` other than `PUBLISH`/`CANCEL`, an empty `entries`, or an unparseable `dtstart` raises `ValueError`.
