# User Stories: Ledger Event Persistence

**Feature**: 033-ledger-event-persistence
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec approval until present.

Each story traces a complete flow from external entry point (a real WhatsApp message/image
arriving via Green API) through system processing to the resulting on-disk state, per
METHODOLOGY.md §I's "External Input → System Processing → Output/Response" requirement.
None of these stories add a new webhook/router entry point (Feature 024 already wired
`imageMessage`/text routing) — the "Router/Integration Requirement" for each story instead
names the internal component call that MUST be wired correctly, per CONSTITUTION §V's
component-integration distinction.

---

## User Story 1 — Text-path fee-agreement message persists to its own permanent file (Priority: P1)

A godfather/admin sends a WhatsApp text message stating a new fee agreement. Today, the
captured event is appended to `session.json`'s `pending_ledger_events` array — tied to
session lifecycle, not genuinely permanent, and only traceable to its source message via
timestamp cross-referencing. This story makes it a real, permanent, independently-stored
record.

**Why this priority**: This is the core behavior change the whole feature exists for —
every other story builds on this one working correctly.

**Independent Test**: Send a real text message containing a fee-agreement statement to a
godfather-role session; verify `data/events/{event_id}.json` is created with the correct
CSV-mapped schema, and `session.json` gains no `pending_ledger_events` entry (the field no
longer exists on `Session`).

**Router/Integration Requirement**: `AIHandler._handle_ledger_event_capture` MUST call the
new `LedgerEventManager.add_ledger_event(...)`, never `SessionManager.add_pending_ledger_event`
(removed).

**Acceptance Scenarios**:

1. **Given** a godfather sends "X 5,000₪ כתב הגנה" (a new, single-component fee agreement),
   **When** the model calls `capture_ledger_event` and the turn completes, **Then** a file
   `data/events/{event_id}.json` exists containing all 29 CSV-mapped fields per the data
   model, `session_id`/`whatsapp_chat`/`message_id`/`message_timestamp`/`sender`/`captured_at`
   are all correctly populated, and the reserved-null fields (`agreement_id`, `component_id`,
   `component_label`, `trigger_condition`, `split_partner`, `split_percent`, `due_date`, all 5
   `חשבונית.*` fields) are `null`.
2. **Given** the same turn, **When** the user's message is persisted to
   `data/sessions/{session_id}/messages/{message_id}.json`, **Then** that message's
   `ledger_event_ids` field contains exactly the new event's `event_id`.
3. **Given** `session.json` for that session, **When** inspected after the turn, **Then** it
   has no `pending_ledger_events` field at all (removed from the `Session` dataclass).
4. **Given** the same message also warrants a normal conversational reply (per constitution,
   capture happens *alongside*, never instead of, the reply), **When** the turn completes,
   **Then** the user still receives their ordinary reply text.

---

## User Story 2 — Image/media-path bank-deposit or fee-agreement event persists the same way (Priority: P1)

A godfather/admin sends a bank-transfer screenshot or an image of a signed fee agreement.
Today `MediaHandler.process_media_message` doesn't even receive the message's `message_id`
(not threaded from `WhatsAppHandler`), so image-path captures can never carry that
traceability field. This story closes that gap and routes image-path captures through the
same `LedgerEventManager` as the text path.

**Why this priority**: Equal priority to US1 — the constitution explicitly treats text and
image capture as two sources of the same mechanism (`LEDGER_EVENT_TOOL` is shared by both);
leaving one path un-migrated would defeat the point of the feature.

**Independent Test**: Send a real bank-transfer-confirmation image to a godfather-role
session; verify the resulting `data/events/{event_id}.json` has a non-null `message_id` and
the stored media-turn message's `ledger_event_ids` includes it.

**Router/Integration Requirement**: `WhatsAppHandler.handle_media_message` MUST pass
`message.message_id` through to `MediaHandler.process_media_message` (new parameter,
currently absent). `MediaHandler.process_media_message` MUST call ledger-event capture
*before* `_store_media_turn`, not after (current order), so the stored message can carry
`ledger_event_ids` at creation time rather than needing a later patch.

**Acceptance Scenarios**:

1. **Given** a godfather sends a bank-transfer screenshot showing a deposit, **When**
   `ImageExtractor`'s vision call returns a `capture_ledger_event` result, **Then** a file
   `data/events/{event_id}.json` is created with `source_type=בנק`, `event_subtype=הפקדה`,
   `event_id` prefixed `B`, and `message_id` equal to the real Green API notification's
   message id (not `null`).
2. **Given** the same turn, **When** the media-turn message is stored, **Then** its
   `ledger_event_ids` contains the new event's id, and this happens via the normal
   message-creation call (no separate update-after-the-fact write).
3. **Given** an image that captures nothing ledger-worthy (e.g. an ordinary document),
   **When** processed, **Then** no file is created under `data/events/` and the message's
   `ledger_event_ids` stays an empty list.

---

## User Story 3 — A multi-component message becomes multiple separate event files (Priority: P2)

A single message states several conditional/sequential fee components (e.g. "₪8,000 if a
suspension hearing, ₪20,000 for studying the file, +₪30,000 if it goes to trial"). The
underlying multi-call infrastructure already exists (Feature 024's
`extract_all_function_calls`); this story is about what happens to each call's result at
the *persistence* layer — each becomes its own file, not one file with three amounts
crammed together.

**Why this priority**: Directly fixes the "one combined event instead of N" defect found
2026-07-28 in the live-captured stray session that motivated this whole feature.

**Independent Test**: Send a message with 3 distinct fee components; verify 3 separate
files exist under `data/events/`, sharing the same source+local-date+minute `event_id`
prefix but with sequential single-digit `seq` (0, 1, 2), and the source message's
`ledger_event_ids` lists all 3.

**Router/Integration Requirement**: `AIHandler._handle_ledger_event_capture` already
resolves every `capture_ledger_event` call found in one turn (not just the first) — this
story requires that each resolved call becomes its own `LedgerEventManager.add_ledger_event`
invocation, not one combined call.

**Acceptance Scenarios**:

1. **Given** a turn where the model makes 3 `capture_ledger_event` calls, **When** the
   follow-up round-trip resolves all 3, **Then** 3 separate files exist under
   `data/events/`, each with its own `amount`, `description`, etc., and `event_id`s that
   share the same letter+`DDMMYY`+`HHMM` prefix with `seq` 0, 1, 2 respectively.
2. **Given** the same turn, **When** the source message is stored, **Then** its
   `ledger_event_ids` list has exactly 3 entries, in the same order the calls were resolved.

---

## User Story 4 — The one already-captured historical session migrates to the new format (Priority: P3)

Session `4454746c-350a-4fa7-a5ef-fda2c685b0d5` (`dev_data/sessions/`) holds 3 combined
events captured live on 2026-07-28, in the old shape, predating this feature. This is a
one-time data-migration story, not ongoing behavior.

**Why this priority**: Real data already exists in the wrong shape; leaving it un-migrated
means the very session that motivated this feature is itself inconsistent with it.

**Independent Test**: Run the migration once; verify exactly 6 new files exist under
`data/events/` (3 from the גיליאן דוידיאן agreement split by component, 2 from the שרית
יוגב/מרדכי רצבגר agreement split by component, 1 for the מלכה בן סעדון bank deposit), each
with `message_id: null` (never known for these), and that session's `session.json` no
longer has a `pending_ledger_events` field.

**Router/Integration Requirement**: None (offline one-time script, not a live message-
processing path) — but the script MUST use the same `LedgerEventManager.add_ledger_event`
code path as US1–US3 (not a separate ad-hoc writer), so the migrated files are guaranteed
schema-identical to ones captured normally.

**Acceptance Scenarios**:

1. **Given** the original 3 combined `pending_ledger_events` records, **When** the migration
   runs, **Then** 6 files exist under `data/events/`, split per component exactly as
   specified in `spec.md`'s Clarifications section.
2. **Given** those 6 files, **When** inspected, **Then** each has `message_id: null` and a
   correctly-derived `event_id` (local-time-based, no collisions with each other).
3. **Given** the migration completed, **When** `session.json` for
   `4454746c-350a-4fa7-a5ef-fda2c685b0d5` is inspected, **Then** it has no
   `pending_ledger_events` field.
