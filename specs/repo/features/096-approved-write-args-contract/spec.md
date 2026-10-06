# Feature 096: Approved-Write Arguments Contract

**Feature Branch**: `feature/096-approved-write-args-contract`
**Status**: Backlog - parked until the problem is seen in real life (see "Trigger" below)
**Origin**: Feature 063 legacy-parity audit, item C1 (2026-10-04)
**Depends on**: Feature 063 (Dynamic Capability Backbone, `feature_flags.enable_capability_backbone`)

## 1. Problem

On the legacy path, what the user approved and what ran were the same tool call by
construction: OpenAI held the model's `create_invoice(args)` call
(`require_approval: "always"`), the approval text was built from those exact `args`, and
"כן" approved that held call - so exactly those `args` ran (`ai_handler.py:2321-2373`,
`2605-2787`; reminders: `PendingLocalToolApproval`, `ai_handler.py:1139-1203`, `2789-2952`).

On the backbone, nothing ties the approval to the write:

1. The model asks with `approval_with_yes_no_buttons`, whose only argument is `text`
   (`src/backbone/resolution_tools.py`). The app answers that call with `"ok"` at once and
   stores nothing about the write - only the buttons message id, for Feature 047's
   stale-tap guard.
2. A tap becomes a plain `"כן"` user message (`Backbone.resolve_button_tap`). On that turn
   the model makes the write call again, from scratch, rebuilding the arguments from the
   conversation.

So, in principle:

- **(a)** The executed arguments can differ from what the user saw - a changed client
  name (ST14's kind of drift), amount, VAT treatment or document type.
- **(b)** The approval text can leave out a field the write actually uses.
- **(c)** A write can run with no approval at all - only the prompts forbid it.

Today's guards (`Backbone._apply_write_guards`) only notice afterwards and append a note
(duplicate execution / nothing executed). A Morning write cannot be undone once it ran.

## 2. Trigger - why this is parked

**Not to be implemented until a real case is observed** (operator decision, 2026-10-04):
a real turn - prod, dev, or a billed/expensive test - where the write that ran on "כן"
differed from what the user was shown, or omitted something shown, or ran without a yes.
When such a case is found, attach its debug trace here (`debug_exact_calls`) and move this
spec to `specs/in-progress/`.

## 3. Constraints

- **Who calls Morning does not change.** OpenAI remains the only caller of the Morning MCP
  server; denidin-app never calls it directly.
- **Today's wiring stays.** The model still asks with `approval_with_yes_no_buttons`
  (`cap_approval_with_buttons`), still writes its own approval text, and the flows keep
  their current shape. No return to legacy's "call the write and the app asks" design.
- Backbone only; the legacy path is untouched.

## 4. Proposed design (for discussion - not approved)

### 4.1 The JSON contract

- `approval_with_yes_no_buttons` gains the write it asks about:
  `{text, write_tool, write_arguments}`. Under the tool's `strict: true` schema a free-form
  object isn't allowed, so `write_arguments` is a JSON **string** the app parses.
- The app stores `{write_tool, write_arguments}` on the session next to
  `approval_message_id` (the "pending approved write").
- Under the model's text, the app appends a **details block rendered from
  `write_arguments`** (legacy bugfix-028 B3), so the user approves the real arguments, not
  only the model's summary of them. Covers (b).

### 4.2 On "כן"

- The model is given the approved `{write_tool, write_arguments}` as JSON, so it copies
  rather than rebuilds. (On its own this only reduces drift; it enforces nothing.)
- The app checks every write call on that turn against the approved one:
  - **Reminders (local tools):** the app runs them itself, so a mismatching call is refused
    **before** it runs. Real enforcement.
  - **Morning writes:** see 4.3.
- A write on a turn with no pending approved write is refused (local) / flagged (Morning).
  Covers (c).

### 4.3 Morning writes - two options (decision needed)

- **Option A - detect only.** Morning write tools stay `require_approval: "never"`; OpenAI
  calls Morning before the app sees the call, so a mismatch can only be reported afterwards
  (a note, like today's guards).
- **Option B - hold on the "כן" turn only.** On that turn alone, the Morning write tools are
  attached with `require_approval: "always"`. OpenAI stops before calling Morning and
  returns an `mcp_approval_request`; the app compares its arguments to the approved JSON and
  answers `mcp_approval_response` with `approve: true` only on a match. OpenAI is still the
  one that calls Morning. The model and the flows never see the hold. Prevents (a) and (c).

### 4.4 Unchanged

The duplicate-execution guard stays: holding a call does not stop OpenAI from running an
approved call twice (legacy saw this, 2026-08-03).

## 5. Open questions

1. Option A or Option B for Morning writes.
2. Comparison rules: exact JSON equality, or normalized (whitespace, number formatting,
   NFC/bidi marks in names, key order)?
3. On a mismatch: decline and tell the model to retry with the approved arguments, or stop
   and tell the user?
4. Flows that approve more than one write at once (if any) - one approval per write, or a
   list in the contract?
5. This reverses the 2026-09-16 decision to keep approval stateless (one pending approved
   write per chat on the session) - confirm.

## 6. Acceptance scenarios

To be drafted in user-experience terms and approved by the operator before `speckit.plan`
(METHODOLOGY §VI), once this spec leaves the backlog.
