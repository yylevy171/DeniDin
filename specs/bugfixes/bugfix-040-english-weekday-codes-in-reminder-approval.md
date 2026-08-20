# Bugfix Spec: Recurring reminder approval shows raw English RRULE weekday codes, not Hebrew

## Bug ID
bugfix-040-english-weekday-codes-in-reminder-approval

## Title
A recurring reminder's approval summary (and later, its confirmation/description text) shows
the literal RFC5545 `BYDAY` codes (`SU,MO,TU,WE,TH,FR`) verbatim instead of Hebrew day names -
a hard violation of the runtime constitution's "ALWAYS respond in Hebrew only" rule.

## Priority
**P2** — cosmetic/localization, not a functional break (the reminder still fires correctly on
the right days), but it's a direct, visible violation of a hard constitution rule in a
user-facing approval message every recurring-by-weekday reminder produces.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root cause before test-gap analysis.

## Date Opened
2026-08-20

## Reported By
yaronlev171, live: setting a daily reminder for every day except Saturday. The approval
summary showed the weekdays as `SU,MO,TU,WE,TH,FR` in English instead of Hebrew.

## Affected Area
- `apps/denidin-app/src/handlers/ai_handler.py` — `_format_reminder_schedule` (~line 917),
  specifically the `BYDAY` branch (~line 938-939).

## Root cause

`_format_reminder_schedule` builds the reminder approval/confirmation text. Every other RRULE
component it renders is translated to Hebrew (`FREQ` via `freq_labels`, `COUNT`/`UNTIL` phrased
in Hebrew prose) - but `BYDAY` is not:

```python
extra = ""
if "BYDAY" in parts:
    extra = f", בימים {parts['BYDAY']}"
```

`parts['BYDAY']` is the raw RRULE string value (e.g. `"SU,MO,TU,WE,TH,FR"`), interpolated
directly into the Hebrew sentence with no translation step at all - unlike `FREQ`, which has an
explicit `freq_labels` dict, `BYDAY` has no equivalent mapping.

## Expected

Each two-letter RFC5545 weekday code must be translated to the corresponding single Hebrew
day-letter before display, matching the standard Israeli convention for referring to weekdays
by letter (Sunday = day 1 of the week):

| RRULE code | Hebrew |
|---|---|
| `SU` | א |
| `MO` | ב |
| `TU` | ג |
| `WE` | ד |
| `TH` | ה |
| `FR` | ו |
| `SA` | ש (Shabbat - not ז, the literal 7th-letter, per Israeli convention) |

E.g. `BYDAY=SU,MO,TU,WE,TH,FR` (every day except Saturday) must render as `ימים א,ב,ג,ד,ה,ו`, not
`ימים SU,MO,TU,WE,TH,FR`.

## Related Work
- `_format_reminder_schedule` is explicitly documented as "display-only... not a full RFC5545
  renderer" - the persisted `rrule` string itself (source of truth for actual firing, via
  `ReminderManager`/`recurring_ical_events`) is correctly untouched by this bug; only the
  human-facing rendering is wrong.
- Feature 054 (`specs/done/v0.5.0/054-reminders-functionality-mgmt/`) - the feature this
  function was built for.
