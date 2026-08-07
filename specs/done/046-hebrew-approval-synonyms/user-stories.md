# User Stories: Accept "מאשר"/"מאשרת" as Approval Answers

**Feature**: 046-hebrew-approval-synonyms
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec
approval until present.
**Status**: CLARIFIED (2026-08-07) — root cause confirmed as a hard-coded keyword gate in
`ai_handler.py`'s `_AFFIRMATIVE_REPLIES` set, not a model-judgment gap. Ready for `plan.md`.

---

## Background (why this feature exists)

A user request (2026-08-07): replying "מאשר" (masculine "I confirm") or "מאשרת" (feminine "I
confirm") to one of DeniDin's pending-action approval prompts (e.g. "ליצור חשבונית ל... —
לאשר?") should be treated the same as replying "כן" — i.e. it should execute the pending
action — but this is not reliably happening today.

## User Story 1 — Replying "מאשר"/"מאשרת" executes a pending action (Priority: P1)

A godfather/admin is shown a pending-action approval prompt (e.g. for `create_invoice`,
`add_client`, `update_client`, or any other tool call that comes back pending per
`config/runtime_constitution.md`'s approval gate). They reply with "מאשר" (if masculine) or
"מאשרת" (if feminine) instead of "כן". DeniDin should recognize this as approval and execute
the pending action, exactly as if they had replied "כן".

**Why this priority**: This is the entire ask.

**Independent Test**: A unit test calling `_is_affirmative_reply()` (`ai_handler.py:182-195`)
directly with `"מאשר"` and `"מאשרת"` (plus casing/whitespace/leading-token variants, consistent
with how existing entries like `"כן"` are tested) asserting `True` — deterministic, no OpenAI
call needed (confirmed via code-path trace during `speckit.clarify`, see spec.md Q1/Q4).
End-to-end confirmation (a real pending tool call, replied to with "מאשר", actually executing)
remains a good `billed`-tier smoke check but is not required to prove correctness of the fix
itself, since the mechanism is a pure deterministic function.

**Acceptance Scenarios**:

1. **Given** `_AFFIRMATIVE_REPLIES` includes `"מאשר"`, **When** `_is_affirmative_reply("מאשר")`
   is called, **Then** it returns `True`.
2. **Given** `_AFFIRMATIVE_REPLIES` includes `"מאשרת"`, **When**
   `_is_affirmative_reply("מאשרת")` is called, **Then** it returns `True` — gender of the verb
   form makes no behavioral difference.
3. **Given** a pending `create_invoice` (or any other pending tool call) approval prompt,
   **When** the user replies "מאשר" or "מאשרת" in a real conversation, **Then** the pending
   action executes — same behavior as replying "כן" produces today (end-to-end confirmation,
   `billed`-tier).

---

## Explicitly Out of Scope

- Any language other than Hebrew.
- Any change to the approval mechanism itself (single-message-turn execution, no double-asking)
  — that behavior is unchanged; this feature is only about which Hebrew words the model
  recognizes as the affirmative reply.
