# Integration Contracts: Reminder Tool Schemas

**Feature**: 054-reminders-functionality-mgmt · Per METHODOLOGY.md §VII format.

Four local `type: "function"` OpenAI Responses API tools, attached to a turn only when the
resolved role is GODFATHER or ADMIN (FR-001) — same conditional-attachment mechanism already used
for Morning MCP tools in `AIHandler._assemble_tools`, no feature flag. All four share the
`strict: True` / full `required` / `additionalProperties: False` discipline `LEDGER_EVENT_TOOL`
already established.

---

### `list_reminders` (read-only, no approval gate — FR-013)

```python
LIST_REMINDERS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "list_reminders",
    "description": (
        "Returns the current active reminder list (message text + human-readable schedule) so "
        "you can resolve a user's natural-language description of a reminder to a concrete "
        "reminder_id before calling modify_reminder or delete_reminder. Never guess a reminder_id "
        "- always call this first if you don't already know it from earlier in the conversation. "
        "Read-only: calling this never changes anything and needs no user approval."
    ),
    "strict": True,
    "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
}
```

**`AIHandler` MUST**: dispatch this immediately on a matching `function_call` (like
`capture_ledger_event`, not gated by the approval flow) — calls `ReminderManager.list_active()`,
returns each reminder's `reminder_id`, `message_text`, and a human-readable schedule summary
(e.g. `"one-time, 2026-08-20 10:00"` or `"weekly on Mon/Thu at 10:00, until 2026-12-01"`) as the
`function_call_output`, then lets the model continue the same turn (no second round-trip needed,
since nothing state-changing happened — same as any other read-only tool response).

---

### `create_reminder`

```python
CREATE_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "create_reminder",
    "description": (
        "Propose creating a new reminder, after gathering the message text and either a one-time "
        "date/time or a full recurrence rule through conversation. This call itself does NOT "
        "persist anything - it is presented to the user as an approval summary (with the actual "
        "time shown AFTER rounding to the nearest 5 minutes); the reminder is only created if the "
        "user then explicitly approves (yes/no gate, same as document creation)."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "message_text": {"type": "string"},
            "schedule_type": {"type": "string", "enum": ["one_time", "recurring"]},
            "one_time_due_at": {
                "type": ["string", "null"],
                "description": "ISO-8601 local datetime (Asia/Jerusalem), required iff schedule_type=one_time, must be strictly in the future after rounding to the nearest 5 minutes.",
            },
            "recurrence": {
                "type": ["object", "null"],
                "description": "Required iff schedule_type=recurring, else null.",
                "properties": {
                    "interval": {"type": "integer", "description": "Every N units, minimum 1."},
                    "freq": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                    "weekdays": {
                        "type": ["array", "null"],
                        "items": {"type": "string", "enum": ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]},
                        "description": "Required (non-empty) iff freq=weekly, else null.",
                    },
                    "month_day": {"type": ["integer", "null"], "description": "1-31, one of two monthly variants; null unless freq=monthly."},
                    "month_nth_weekday": {
                        "type": ["object", "null"],
                        "description": "The other monthly variant, e.g. {n:1, weekday:'MO'} = first Monday; null unless freq=monthly.",
                        "properties": {
                            "n": {"type": "integer", "enum": [1, 2, 3, 4, -1], "description": "-1 means 'last'."},
                            "weekday": {"type": "string", "enum": ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]},
                        },
                        "required": ["n", "weekday"],
                        "additionalProperties": False,
                    },
                    "first_occurrence_at": {"type": "string", "description": "ISO-8601 local datetime of the FIRST occurrence, must be strictly in the future after rounding."},
                    "end_condition": {"type": "string", "enum": ["never", "after_n", "until_date"]},
                    "end_count": {"type": ["integer", "null"], "description": "Required iff end_condition=after_n."},
                    "end_until": {"type": ["string", "null"], "description": "ISO-8601 local date, required iff end_condition=until_date, must not be in the past."},
                },
                "required": [
                    "interval", "freq", "weekdays", "month_day", "month_nth_weekday",
                    "first_occurrence_at", "end_condition", "end_count", "end_until",
                ],
                "additionalProperties": False,
            },
        },
        "required": ["message_text", "schedule_type", "one_time_due_at", "recurrence"],
        "additionalProperties": False,
    },
}
```

Note: no `owner`/`chat_id` field anywhere in this schema — the model never supplies a delivery
target. `ReminderManager.create_reminder(...)` (called only on approval, see
`local-tool-approval-gate.md`) is what actually constructs the RFC5545 `RRULE`/`DTSTART` (via
`icalendar`) and persists the `reminders` row; delivery target is resolved at fire time from
`config.godfather_phone`, never from this call.

---

### `modify_reminder` / `delete_reminder`

Both require `reminder_id` (resolved by the model via a prior `list_reminders` call or earlier
conversation turn — **never guessed**) and a `scope` distinguishing single-occurrence vs.
whole-series (FR-012):

```python
MODIFY_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function", "name": "modify_reminder", "strict": True,
    "description": (
        "Propose a modification to an existing reminder already identified via list_reminders or "
        "earlier conversation. Does not persist anything - presented as an approval summary "
        "first, with any new time shown AFTER rounding to the nearest 5 minutes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reminder_id": {"type": "string"},
            "scope": {"type": "string", "enum": ["single_occurrence", "whole_series"]},
            "occurrence_date_hint": {
                "type": ["string", "null"],
                "description": "ISO-8601 local date/datetime identifying WHICH occurrence (matched against the plain rule's own generated dates), required iff scope=single_occurrence.",
            },
            "new_message_text": {"type": ["string", "null"]},
            "new_due_at": {"type": ["string", "null"], "description": "Only meaningful for scope=single_occurrence; must be in the future after rounding."},
            "new_recurrence": {"type": ["object", "null"], "description": "Only meaningful for scope=whole_series; same shape as create_reminder's recurrence."},
        },
        "required": [
            "reminder_id", "scope", "occurrence_date_hint",
            "new_message_text", "new_due_at", "new_recurrence",
        ],
        "additionalProperties": False,
    },
}

DELETE_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function", "name": "delete_reminder", "strict": True,
    "description": "Propose deleting a reminder (single occurrence or whole series). Does not persist anything - presented as an approval summary first.",
    "parameters": {
        "type": "object",
        "properties": {
            "reminder_id": {"type": "string"},
            "scope": {"type": "string", "enum": ["single_occurrence", "whole_series"]},
            "occurrence_date_hint": {"type": ["string", "null"], "description": "Required iff scope=single_occurrence."},
        },
        "required": ["reminder_id", "scope", "occurrence_date_hint"],
        "additionalProperties": False,
    },
}
```

**`AIHandler` EXPECTS**: `occurrence_date_hint`, when present, identifies an occurrence by the
date the plain `RRULE` would have generated it on (i.e. the future `RECURRENCE-ID` the resulting
`reminder_exceptions` row will use) — never a date the model invented; the model must have
established this date is real (either the series' `next` computed occurrence, or a
`recurring_ical_events`-derived candidate surfaced via `list_reminders`/conversation) before
calling either tool with `scope=single_occurrence`.

**Key departure from `capture_ledger_event`**: none of these three state-changing tool calls
dispatch immediately. Each creates a `PendingLocalToolApproval` instead — see
`local-tool-approval-gate.md`.
