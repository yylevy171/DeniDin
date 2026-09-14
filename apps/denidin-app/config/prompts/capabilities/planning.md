# Capability: Planning (meta)

Given Intent Identification's output and the list of capabilities available to
this role, build an ordered plan of capability steps to execute.

Respond with ONLY a JSON object of this exact shape:
```json
{"steps": [{"capability": "<tag>", "note": "<short free-text note for that step>"}]}
```

Rules:
- `capability` must be exactly one of the capability tags you were told are
  available — never one you weren't offered, and never `intent_identification`
  or `planning` themselves (those are not plan steps).
- Order matters: a later step may depend on an earlier step's result (e.g. media
  extraction before deciding whether the extracted text is a ledger event).
- `steps` may be an empty list — this is the correct output for small talk or any
  turn that needs no further action beyond what Intent Identification already
  determined.
- Never invent a step "just in case" — only include a capability the turn
  genuinely needs.
- A vague "what do I have [tomorrow/today/on a date]" turn (no explicit
  "calendar", no explicit "תזכורות"/"reminders") that Intent Identification
  flagged as ambiguous, for a role that has `reminders_read` available, plans
  a `reminders_read` step — do not plan zero steps and do not answer as if
  this were a calendar request; there is no calendar capability, and treating
  the phrasing as one silently drops the only real answer available
  (bugfix-042 documents the mirror-image failure: reminders being reached for
  when it should NOT have been — this rule is the other direction of the same
  boundary needing to be explicit, not implicit).
