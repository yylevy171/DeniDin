# Tasks: WhatsApp Reply/Quote Reference Resolution

**Input**: Design documents from `specs/backlog/032-whatsapp-reply-reference-resolution/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅ (revised 2026-08-04
— `resolved_reference` carries full structured `LedgerEvent` records, not bare ids;
`content`/`ledger_events` mutually exclusive), contracts/ ✅, quickstart.md ✅

---

**IMPORTANT**: This task list MUST comply with:
- **CONSTITUTION.md** (§I-III): Config-only (NO env vars), UTC timestamps, Git workflow with feature branches
- **METHODOLOGY.md** (§VI): TDD with human approval gates — Tests MUST be approved before implementation

**Critical TDD Requirements**:
- ⚠️ **EVERY TEST task (`a`) requires HUMAN APPROVAL before its CODE task (`b`) starts**
- ⚠️ **Once approved, tests are IMMUTABLE without explicit human re-approval**

---

## Test Tiers Used By This Feature (finalized 2026-08-04, user-approved)

- **`expensive` (2 new tests)**: real, end-to-end round trips that necessarily involve a real
  vision-model call, so the whole test is `expensive` regardless of what any individual step
  needs — per CLAUDE.md's strict expensive-tier discipline (explicit approval every run, one
  at a time, never rerun after reaching OpenAI without fresh approval, read
  `logs/test_logs/` before re-running).
  1. **Real agreement-image round trip**: send a real fee-agreement image → real
     `ImageExtractor` vision call → real `capture_ledger_event` (`source_type=הסכם`) →
     reply to that message asking a question only answerable from the captured amount/client
     → verify the real follow-up response correctly reflects the structured `LedgerEvent`
     fields resolved into context (not a re-derived/hallucinated value from raw OCR text).
  2. **Real bank-image round trip**: same shape, a real bank-deposit screenshot →
     `source_type=בנק` → reply asking about the deposited amount/date → verify correctness.
     Bank events are always image-sourced (no text-only bank capture path exists), so this
     is not reachable via a text-only test.
- **`billed` (2 new tests)**: text-only, cheap, freely runnable, no approval gate.
  1. **Text-based agreement reply**: capture a fee-agreement event from a plain TEXT message
     (no image), reply to it asking a question answerable only from the captured structured
     fields, verify the real response is correct — proves structured-field resolution works
     end-to-end without needing the image path.
  2. **Ordinary no-ledger-event reply (baseline)**: reply to a message with no captured
     `LedgerEvent`, with an ordinary message — whatever a real user would actually send (a
     question, a follow-up, small talk — NOT a contrived/adversarial prompt) — verify the
     response is a normal reply, identical in character to pre-feature behavior: no
     hallucinated agreement/amount data, no spurious `capture_ledger_event` call.
- **Everything else** (US1 Scenarios 1, 4, 6\*, 7, 8 and all of US2) is unit/integration-level,
  no real OpenAI call needed — `create_ai_request` only *builds* the request object
  (`ai_handler.py:600-693`); assertions inspect the constructed request / stored JSON directly.
  \*Scenario 6 (media message with failed/missing extraction) was confirmed
  (2026-08-04) to need no billed coverage — it's a pure fallback/no-crash check with no
  distinct model-visible behavior worth spending a real call on.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- **[T###a]**: Write tests (REQUIRES HUMAN APPROVAL before T###b)
- **[T###b]**: Implement code (BLOCKED until T###a approved, tests are IMMUTABLE)

## Path Conventions

Single project — `apps/denidin-app/src/`, `apps/denidin-app/tests/` (all paths below are
relative to `apps/denidin-app/`).

---

## Phase 1: Setup

- [ ] T001 Confirm on branch `feature/032-whatsapp-reply-reference-resolution`, off latest `master`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data model changes every user story depends on — MUST complete before US1/US2 work.

- [ ] T002a [P] Write tests for `WhatsAppMessage.from_notification`'s new fields in
  `tests/unit/test_message_model.py`: `whatsapp_id_message` captured from
  `event['idMessage']`; `quoted_stanza_id` captured from
  `messageData.extendedTextMessageData.quotedMessage.stanzaId` when present; both `None` for
  a non-reply `textMessage`; existing `text_content`/bugfix-008 flattening behavior completely
  unchanged (regression guard)
- [ ] T002b [P] Add `whatsapp_id_message`/`quoted_stanza_id` fields + capture logic to
  `WhatsAppMessage`/`from_notification` in `src/models/message.py` (BLOCKED until T002a approved)

- [ ] T003a [P] Write tests for `Message`'s new fields in `tests/unit/test_session_manager.py`:
  `whatsapp_id_message`/`resolved_reference` default to `None`; JSON round-trip; an old
  (pre-feature) message file without these fields still loads correctly
- [ ] T003b [P] Add `whatsapp_id_message`/`resolved_reference` fields to `Message` dataclass in
  `src/managers/session_manager.py` (BLOCKED until T003a approved)

- [ ] T004a [P] Write tests for a new `LedgerEventManager.get_event(event_id)` read method in
  `tests/unit/test_ledger_event_manager.py`: returns the full parsed record for an existing
  `{storage_dir}/{event_id}.json`; returns `None` (no exception) for a nonexistent `event_id`
- [ ] T004b [P] Implement `get_event(event_id) -> Optional[Dict]` in
  `src/managers/ledger_event_manager.py`, reading `self.storage_dir / f"{event_id}.json"`
  (BLOCKED until T004a approved) — needed because `resolve_reply` (below) must hydrate full
  `LedgerEvent` records, not just pass through bare ids (data-model.md revision)

- [ ] T005a Write tests for `SessionManager.resolve_reply` in
  `tests/unit/test_session_manager.py`: exact-match hit with NO `ledger_event_ids` on the
  target returns `resolved_reference` with `content` populated and `ledger_events` absent/empty;
  exact-match hit WITH `ledger_event_ids` returns `resolved_reference` with `ledger_events`
  fully hydrated (via a fake/fixture `LedgerEventManager.get_event`) and `content` absent (the
  new mutual-exclusivity rule, data-model.md); miss (no matching `stanzaId` in active session)
  returns `None`; miss (no active session for `whatsapp_chat`) returns `None`; a `stanzaId`
  matching a message in a DIFFERENT chat's session does NOT resolve (Scenario 8); a `stanzaId`
  matching a message in an EXPIRED/archived session does NOT resolve (Scenario 7); `content`
  for a media-message target equals its `extracted_text`/`document_analysis` IN FULL
  (Scenario 5's data-shape, exercised here at unit level with a fixture — the real end-to-end
  proof is the `expensive` tests below); `content` absent AND `ledger_events` absent (both
  falsy) for a media-message target with no extraction available, no exception (Scenario 6)
- [ ] T005b Implement `id_message_index` (per-session, alongside `chat_to_session`) and
  `resolve_reply(whatsapp_chat, stanza_id, ledger_event_manager)` in
  `src/managers/session_manager.py`: populate the index in `add_message`; rebuild on session
  load from disk (mirrors `chat_to_session` rebuild, `session_manager.py:333`); hydrate
  `ledger_events` via `ledger_event_manager.get_event` for each id in the matched message's
  `ledger_event_ids`, else populate `content` (BLOCKED until T005a approved, depends on
  T003b, T004b)

**Checkpoint**: Data model + resolution primitive ready — user story work can now begin.

---

## Phase 3: User Story 1 — Resolve a WhatsApp reply to the internal message it quotes (Priority: P1) 🎯 MVP

**Goal**: A reply's `stanzaId` resolves to the quoted message's content or structured
`LedgerEvent` data, surfaced as extra AI prompt context — scoped to the active session, per
chat/group.

**Independent Test**: Send message A, reply to it, verify the reply's stored
`Message.resolved_reference` correctly points at message A.

### Tests for User Story 1 — non-billed (internal-state / integration, no real OpenAI call)

- [ ] T006a [P] [US1] Write integration test in `tests/integration/test_reply_resolution.py`:
  dispatch a real Green API webhook payload (per
  `specs/done/v0.0.1/001-whatsapp-chatbot-passthrough/contracts/green-api.md`'s documented shape,
  with `quotedMessage.stanzaId` set) through `bot.router` for a reply to a previously-sent
  ordinary message with no ledger event; verify the reply's persisted `Message` JSON has
  `resolved_reference.content` populated with message A's content/sender/timestamp, no
  `ledger_events` (Scenario 1 + 3 combined — they're the same shape now that content/
  ledger_events are mutually exclusive)
- [ ] T007a [P] [US1] Extend the same file: send "לבטל"-lookalike or any text with NO quote at
  all (`quotedMessage` absent) — verify behavior completely unchanged from pre-feature, no
  `resolved_reference` attempted (Scenario 4)
- [ ] T008a [P] [US1] Extend the same file, using a fixture `Message` with `ledger_event_ids`
  set and a fixture `LedgerEvent` record on disk: reply to it — verify
  `resolved_reference.ledger_events` contains the full structured record (client_name,
  source_type, amounts, etc.), no new `LedgerEvent` is created by this feature itself
  (Scenario 2)
- [ ] T009a [P] [US1] Extend the same file, using a fixture media `Message` (pre-populated
  `extracted_text`, no real vision call): reply to it — verify `resolved_reference.content`
  is the FULL, untruncated extracted text, not raw bytes, no vision-model call logged
  (Scenario 5, integration-level complement to T005a's unit coverage)
- [ ] T010a [P] [US1] Extend the same file, fixture media `Message` with NO `extracted_text`
  set: reply to it — verify resolution succeeds with no `content`/`ledger_events`, no error
  (Scenario 6)
- [ ] T011a [P] [US1] Extend the same file: reply to a message whose session has been
  force-expired in the fixture — verify graceful no-resolution, no crash (Scenario 7,
  integration-level complement to T005a)
- [ ] T012a [P] [US1] Extend the same file: reply with a `stanzaId` matching a message that
  exists in a DIFFERENT chat's active session — verify no cross-chat match (Scenario 8,
  integration-level complement to T005a)

### Tests for User Story 1 — `billed` (real OpenAI, text-only, free to run)

- [ ] T013a [US1] Add `tests/billed/test_reply_resolution_billed.py::test_text_agreement_reply_uses_structured_fields`:
  capture a real fee-agreement `LedgerEvent` from a plain text message via a real (billed,
  text-only) OpenAI call, then reply to that message asking a question only answerable from
  the captured amount/client — verify the real follow-up response is correct, proving
  `resolved_reference.ledger_events` actually reaches and is usable by the model
- [ ] T014a [US1] Add
  `tests/billed/test_reply_resolution_billed.py::test_ordinary_reply_no_ledger_event_baseline`:
  reply to a message with no captured `LedgerEvent`, with an ordinary (non-contrived) message
  — verify the real response is a normal reply with no hallucinated agreement/amount data and
  no spurious `capture_ledger_event` call

### Tests for User Story 1 — `expensive` (real vision call — requires separate per-run approval, not granted by this task-plan approval)

- [ ] T015a [US1] Add
  `tests/expensive/test_reply_resolution_expensive.py::test_agreement_image_reply_uses_structured_fields`:
  send a real fee-agreement image (real vision call, `source_type=הסכם`), reply to it asking
  about the captured amount/client, verify the real follow-up response is correct — proves the
  full real pipeline (image → extraction → capture → resolution → reply) end-to-end
- [ ] T016a [US1] Add
  `tests/expensive/test_reply_resolution_expensive.py::test_bank_image_reply_uses_structured_fields`:
  same shape, a real bank-deposit screenshot (`source_type=בנק`), reply asking about the
  deposited amount/date, verify correctness

**👤 HUMAN APPROVAL GATE — review T006a–T016a before any implementation (T017b+) begins. Note:
approving these test task DESCRIPTIONS is not the same as approving a run of T015a/T016a
themselves once written — each `expensive` run still needs its own separate go-ahead per
CLAUDE.md.**

### Implementation for User Story 1

- [ ] T017b [US1] Wire resolved-reference context into `AIHandler.create_ai_request` in
  `src/handlers/ai_handler.py`: when `message.quoted_stanza_id` is set, call
  `session_manager.resolve_reply(message.chat_id, message.quoted_stanza_id,
  self.ledger_event_manager)`; if it returns a result, append a formatted resolved-reference
  block to `constitution` in the SAME position as `memory_context` (before
  `_build_instructions`'s `---` + date suffix, research.md Decision 4) — format
  `ledger_events` as structured key/value text (not raw JSON dumped into the prompt) (BLOCKED
  until T006a–T016a approved, depends on T002b, T005b)
- [ ] T018b [US1] Wire `whatsapp_id_message` through to `SessionManager.add_message` calls in
  `src/handlers/ai_handler.py` so every message's own `idMessage` gets indexed for FUTURE
  replies to resolve against (BLOCKED until approved, depends on T002b, T003b, T005b)
- [ ] T019 [US1] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md` steps manually against `dev`
  (requires separate explicit approval to start `dev`, per CLAUDE.md — not part of this task)

**Checkpoint**: User Story 1 fully functional and independently testable — this is the MVP.

---

## Phase 4: User Story 2 — Non-reply messages are unaffected (regression guard) (Priority: P2)

### Tests for User Story 2

- [ ] T020a [US2] Write integration test in `tests/integration/test_reply_resolution.py`:
  dispatch an ordinary `textMessage` webhook with no `quotedMessage` — verify
  `resolved_reference` never populated, response identical to pre-feature snapshot

**👤 HUMAN APPROVAL GATE — review T020a before T021b.**

### Implementation for User Story 2

- [ ] T021b [US2] No new implementation expected — T017b's `if message.quoted_stanza_id:`
  guard already covers this by construction. Run T020a against the Phase 3 implementation and
  confirm it passes with no additional code changes (BLOCKED until T020a approved, depends on
  T017b)

**Checkpoint**: User Stories 1 AND 2 both verified.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T022 [P] Run full existing `tests/unit/` + `tests/integration/` suites to confirm no regressions
- [ ] T023 [P] `python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc` and
  `python3 -m mypy src/ --config-file=mypy.ini`
- [ ] T024 Update `.github/ARCHITECTURE.md`/CLAUDE.md's Key Components section with a one-line
  mention of the resolved-reference injection point (matches how `memory_context` is
  documented there)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: T002/T003/T004 pairs are `[P]`; T005
  depends on T003b + T004b.
- **Foundational MUST complete** before Phase 3 starts.
- **US1 (Phase 3)** is the MVP — T006a–T012a are `[P]` (independent test functions, same
  file); T013a/T014a (billed) and T015a/T016a (expensive) can be authored in parallel with
  them. T017b depends on T002b + T005b; T018b depends on T002b + T003b + T005b.
- **US2 (Phase 4)** depends on Phase 3's T017b existing (regression test against that
  implementation).
- **Polish (Phase 5)** depends on Phases 3–4 complete.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (trivial) + Phase 2 (Foundational)
2. Complete Phase 3 (US1) — delivers the entire feature's value
3. **STOP and VALIDATE**: run `quickstart.md` manually against `dev` (separate approval
   required to start it)
4. Phase 4 (US2) and Phase 5 (Polish) follow immediately after

### Notes

- Every `Xa` task requires explicit human approval before its paired `Xb` begins.
- `expensive` tests (T015a/T016a) additionally require their own separate per-run approval
  when actually executed, even after this task list is approved (CLAUDE.md).
