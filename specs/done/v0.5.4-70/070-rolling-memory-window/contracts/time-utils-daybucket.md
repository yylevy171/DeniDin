# Contract: `time_utils` day-bucketing helpers

**Module**: `apps/denidin-app/src/utils/time_utils.py` **+ its byte-identical twin**
`apps/morning-mcp-app/src/denidin_mcp_morning/utils/time_utils.py` (the two files must stay
identical — same rule as `logger.py`).

No such helper exists today; callers inline `now_local().date()`. The window builder and the roll
job MUST use these so their day-bucketing is provably identical (REQ-MEM-003, spec Edge Cases).

All operate on aware `Asia/Jerusalem` datetimes (`LOCAL_TZ`). A naive input is treated as already
local (matches `to_local`).

---

## `local_calendar_date(dt: datetime) -> datetime.date`

- `return to_local(dt).date()`.
- The canonical "which calendar day is this instant" function. A `+00:00` legacy timestamp and a
  `+03:00` current timestamp both bucket correctly because `to_local` converts first.

## `start_of_local_day(dt: datetime) -> datetime`

- Aware `Asia/Jerusalem` datetime at `00:00:00` of `local_calendar_date(dt)`.
- `return datetime.combine(local_calendar_date(dt), time.min, tzinfo=LOCAL_TZ)`.
- DST: on a spring-forward day `00:00` exists (the gap is at `02:00`); on a fall-back day `00:00`
  is unambiguous. No `fold` handling needed at midnight.

## `n_calendar_days_ago(n: int, now: Optional[datetime] = None) -> datetime.date`

- `base = local_calendar_date(now or now_local())`; `return base - timedelta(days=n)`.
- "Last 14 calendar days" (inclusive of today) = every message with
  `local_calendar_date(msg_ts) >= n_calendar_days_ago(13)`.
- The nightly roll's "yesterday" = `n_calendar_days_ago(1, now)`.

---

## Boundary rules (must be consistent across window + roll)

| Question | Rule |
|---|---|
| Message exactly at local midnight `2026-09-01T00:00:00+03:00` | Belongs to `2026-09-01` (the later day). `.date()` gives `2026-09-01`. |
| Message exactly 14 days ago at `00:00` | `local_calendar_date` == `n_calendar_days_ago(13)` → **in** the window (inclusive lower bound). One day older → out of the window, and it is (or will be) summarized. |
| A message belongs to | **exactly one** calendar day (`local_calendar_date` is a total function) and is **either** in the window **or** eligible for a daily summary — never both, never neither. |
| Roll runs at `02:00:00` while a "yesterday" message lands at `01:59:59` | The `01:59:59` message's `local_calendar_date` is still yesterday → included in yesterday's summary. A message at `00:00:05` today is today's → stays in the window. |
| DST roll night | `CronTrigger(hour=2, minute=0, timezone=LOCAL_TZ)` fires once; "yesterday" via `n_calendar_days_ago(1)` is unambiguous regardless. |

Unit test `test_session_manager_window.py` covers: legacy `+00:00` bucketing, the midnight
boundary, the 14-day boundary, and a future-dated message.
