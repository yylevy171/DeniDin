# User Stories: Morning-Sourced Ledger Events

**Feature**: 025-morning-sourced-ledger-events
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec approval
until present.

**Backfill note**: this spec predates the `user-stories.md`-mandatory convention (introduced
around Features 033/054) and was never backfilled at the time. Written now, during
`speckit.plan`, from `spec.md`'s Clarifications and `quickstart.md`'s manual-verification
scenarios — before `speckit.tasks` derives tasks from it, per METHODOLOGY.md §I's requirement
that tasks trace back to a Given-When-Then story, not skip straight from spec to tasks.

None of these stories add a new webhook/router entry point — this feature's only "external
entry point" is a scheduled background tick (APScheduler), not an inbound WhatsApp message.
Each story instead names the internal component call chain that MUST be wired correctly, per
CONSTITUTION §V's component-integration distinction.

---

## User Story 1 — A background sweep captures a Morning document DeniDin never saw in conversation (Priority: P1)

A document is created directly in Morning (Green Invoice), outside any DeniDin conversation
entirely — today, DeniDin has no way to ever discover this happened; the only two capture paths
(conversational text/image) never fire for it. This story is the core behavior the whole feature
exists for.

**Why this priority**: Every other story is a refinement or guard around this one working
correctly.

**Independent Test**: Create a document directly in the Morning sandbox (bypassing DeniDin).
Wait for/trigger one reconciliation sweep tick. Verify a new
`{data_root}/events/H{DDMMYY}{HHMM}{seq}.json` file exists with `source_type="חשבונית"` and the
five `accounting_document_*` fields correctly populated from that real document.

**Router/Integration Requirement**: `services/accounting_reconciliation_service.py`'s sweep
worker MUST call OpenAI's Responses API directly (its own dedicated prompt, not
`AIHandler.get_response`'s normal conversational path) with the Morning MCP tools +
`LEDGER_EVENT_TOOL` attached, then persist any resulting `capture_ledger_event` calls via
`LedgerEventManager.add_ledger_events_from_call` — through a NEW handler method, never through
`_handle_ledger_event_capture` (see contracts/ "Critical" notes).

**Acceptance Scenarios**:

1. **Given** a document exists in Morning with no matching DeniDin conversation, **When** a
   reconciliation sweep tick runs, **Then** a new `LedgerEvent` file is persisted with
   `source_type="חשבונית"`, `event_subtype="הפקה"`, `accounting_document_id`/`_number`/`_type`/
   `_status`/`_creation_date` all matching the real document, every הסכם/בנק-only field `null`,
   `schema_version=2`, `session_id="accounting-reconciliation"`, `message_id=null`.
2. **Given** the same sweep tick, **When** it completes, **Then** no WhatsApp message is sent to
   anyone (silent background capture — spec.md's design, not a conversational feature).

---

## User Story 2 — A document already captured is never re-captured on the next sweep (Priority: P1)

Every `list_invoices` call returns full document history each time — without dedup, the same
document would be re-proposed for capture on every subsequent tick.

**Why this priority**: Without this, the feature is actively harmful (duplicate/growing ledger
noise) rather than merely incomplete — must ship together with US1, not after it.

**Independent Test**: After US1's sweep captures a document, run a second sweep tick with no new
Morning activity. Verify no new file is created for the same document, and the sweep's log shows
it ran (not that it silently skipped entirely).

**Router/Integration Requirement**: `LedgerEventManager.scan_accounting_documents` MUST be
consulted both to derive the sweep's "since" watermark AND as a hard guard inside
`add_ledger_event` itself — the guard, not just the prompt's own date-window framing, is what
actually prevents a duplicate write (data-model.md).

**Acceptance Scenarios**:

1. **Given** a document already has a persisted `חשבונית` `LedgerEvent` (its `accounting_document_id`
   is in the known set), **When** a later sweep tick's OpenAI call nonetheless attempts to
   capture it again (e.g. because the prompt's own date framing wasn't perfectly precise),
   **Then** `add_ledger_event` refuses to persist it (logs a WARNING naming the duplicate id,
   returns `None`), and no second file is created.
2. **Given** two consecutive sweep ticks with zero new Morning documents in between, **When**
   both complete, **Then** exactly the same set of `חשבונית` files exists after both as existed
   after the first.

---

## User Story 3 — Multiple new documents in one window are all captured (Priority: P2)

A poll window may contain more than one new document (e.g. after a period of downtime, or simply
several documents created since the last tick).

**Why this priority**: Correctness under the common multi-document case — not needed for the
single-document happy path to be meaningfully demonstrable, but required before this is
trustworthy in real operation.

**Independent Test**: Create two new documents in the Morning sandbox before the next sweep tick.
Verify two new `חשבונית` files are persisted, one per document, each with the correct distinct
`accounting_document_id`.

**Router/Integration Requirement**: The reconciliation sweep's new handler method MUST accept
multiple `capture_ledger_event` calls within one turn as the normal, expected case — the
opposite of `_handle_ledger_event_capture`'s "more than one call = protocol violation, persist
nothing" rule, which stays correct and unchanged for its own (conversational) context.

**Acceptance Scenarios**:

1. **Given** two documents were created in Morning since the last known watermark, **When** one
   sweep tick runs, **Then** the OpenAI call's response contains two `capture_ledger_event`
   calls (one per document) and BOTH are persisted as separate `LedgerEvent` files — neither
   rejected as a "duplicate call in one turn."

---

## User Story 4 — An ordinary conversational Morning question is completely unaffected (Priority: P1)

This feature must not touch, weaken, or risk regressing the existing conversational-turn
suppression that was shipped specifically to fix the 2026-07-28/2026-08-02 incidents this
feature descends from.

**Why this priority**: A regression here silently reintroduces a real, previously-fixed bug
(empty replies on a real godfather turn) — must be verified alongside, not after, the new
capability ships.

**Independent Test**: From a godfather/admin phone, ask a real Morning question in normal
conversation (e.g. "list all payments for client X"). Verify a complete, correct conversational
reply arrives, and verify no new `dev_data/events/` file was created by that turn.

**Router/Integration Requirement**: `_handle_ledger_event_capture` (existing method) MUST remain
byte-for-byte unchanged in behavior — its same-turn-`mcp_call` suppression and one-call-per-turn
rule keep applying exactly as before to every real conversational turn.

**Acceptance Scenarios**:

1. **Given** a godfather asks a Morning question that causes `list_invoices`/`get_invoice_details`
   to run in the same turn, **When** the model (incorrectly, as it has before) attempts a
   `capture_ledger_event` call anyway, **Then** that call is suppressed exactly as today
   (nothing persisted, the follow-up round loses access to the tool, the model's real text reply
   is what the user receives) — the original 2026-07-28 empty-reply symptom does not reproduce.
2. **Given** the same turn, **When** it completes, **Then** no `LedgerEvent` file was created by
   it (that data path is this feature's job now, via the separate reconciliation sweep — not the
   conversational turn).

---

## User Story 5 — A sweep failure never silently skips a window (Priority: P2)

If a sweep tick fails partway (OpenAI error, Morning MCP unavailability), the next tick must
still cover the same ground — not silently advance past whatever was missed.

**Why this priority**: Correctness under real-world transient failure, not required for the
happy-path demo but required before this is trustworthy unattended.

**Independent Test**: Simulate a sweep-tick failure (e.g. temporarily point at an unreachable
Morning MCP URL for one tick). Verify the next successful tick still covers the full window back
to the last real captured document (not just from the failed tick's own attempted start).

**Router/Integration Requirement**: The sweep's watermark MUST be derived from
`scan_accounting_documents` (what's actually persisted), never from a separately-advanced
counter/timestamp that a failed tick could move forward without anything having been captured.

**Acceptance Scenarios**:

1. **Given** a sweep tick fails before persisting anything, **When** the next tick runs,
   **Then** its derived "since" watermark is identical to what the failed tick itself used (no
   documents were silently skipped).
