# Tasks: WhatsApp Export → Ledger Event Player

**Input**: Design documents from
`specs/in-progress/043-production-data-setup-tooling/`
**Prerequisites**: `plan.md`, `spec.md`, `user-stories.md`, `research.md`,
`data-model.md`, `contracts/message-source.md`, `contracts/player-cli.md`,
`quickstart.md` — all present.

---

**IMPORTANT**: Complies with CONSTITUTION.md §I-III, §V, §XVII and
METHODOLOGY.md §I-II/§VI (TDD, human approval gates, tests IMMUTABLE once
approved, no monkey-patching).

**Tests**: TDD — every "a" task (tests) requires explicit human approval
before its matching "b" task (implementation) begins. Once approved, a test
is immutable without a fresh, explicit re-approval.

**Path Conventions**: `apps/denidin-app/src/`, `apps/denidin-app/tests/`,
`apps/denidin-app/player/` (per `plan.md`'s architecture).

**Two phases below (2 and 3) touch shared/live code** (`denidin.py`,
`ai_handler.py`, `media_handler.py`, `ledger_event_manager.py`) — these are
sequenced first because every later phase depends on them, and because
live-behavior-preservation needs its own explicit verification pass before
anything player-specific is built on top.

## Version Control steps (applied at the end of every phase below)

- **VC0**: Confirm `git branch --show-current` is
  `feature/043-production-data-setup-tooling`.
- **VC1**: `git add` only the files touched by that phase (never a broad
  `git add -A`).
- **VC2**: `git commit` with a conventional-commit message referencing the
  phase's REQ/US ids.
- **VC3**: Push only when the user explicitly asks — no push without its
  own fresh approval.
- **VC4**/**VC5** (end of feature only): PR and merge, each with their own
  explicit approval, never inferred from an earlier "yes."

---

## Phase 1: Setup

- [x] T001 Confirm `git branch --show-current` is
  `feature/043-production-data-setup-tooling` (already created).
- [x] T002 Re-check the full real sample export file (not just the excerpt
  already read this session) for: (a) any WhatsApp system-message lines
  needing filtering, (b) whether an attachment line ever carries a caption
  on the same line — finalize `export_parser.py`'s handling of both before
  T009a is written (research.md's two open items). Document findings as an
  addendum to research.md. **Done**: zero matches for either in the sample;
  documented in research.md that this is not sufficient proof for the real
  full export, and the parser must still filter known system-message
  templates defensively.

---

## Phase 2: Foundational — `MessageSource` abstraction (Blocking, US1 dependency)

**Purpose**: decouple `denidin.py`'s handler functions from live Green API
bot construction, so the player can drive them without ever touching Green
API. **Nothing player-specific starts until this phase's tests are
approved and live-behavior-preservation is verified.**

- [x] T003a [P] Write tests in `tests/unit/test_message_source.py`:
  `MessageSource` is an ABC with a `start(dispatch)` method;
  `GreenAPIMessageSource` is NOT constructed by a bare `import denidin`
  (regression test for research.md R3 — assert no `DeniDinGreenAPIBot`
  instantiation happens at import time, e.g. via a constructor-call-count
  spy passed through dependency injection, never monkey-patching per
  CONSTITUTION §XVII); `GreenAPIMessageSource.start()` constructs the bot
  and registers the full handler dispatch table. **Extended during
  implementation** with `connect()` idempotency tests and catch-all
  registration tests (a real semantic gap found by reading
  whatsapp_chatbot_python's Handler.check_event directly: an explicit
  `type_message=None` filter is NOT equivalent to no filter at all).
- [x] T003b [P] Implement `src/sources/message_source.py`
  (`MessageSource` ABC) and `src/sources/green_api_source.py`
  (`GreenAPIMessageSource`) (BLOCKED until T003a approved). **Done**: 14
  tests passing, pylint 10.00/10, mypy clean.

- [x] T004a Write tests in `tests/unit/test_denidin_dispatch.py`: the
  handler-dispatch table (`type_message → handler`) contains exactly the
  same mappings as today's `@bot.router.message(...)` decorators (one
  assertion per message type: `textMessage`/`extendedTextMessage` →
  `handle_text_message`, `contactMessage` → `handle_contact_message`,
  `contactsArrayMessage` → `handle_contacts_array_message`,
  `imageMessage`/`documentMessage`/`videoMessage`/`audioMessage` → their
  respective handlers, plus the catch-all) — a completeness check against
  the pre-refactor decorator list, not a guess.
- [x] T004b Refactor `denidin.py`: handler functions become plain/
  undecorated; build the dispatch table; move `GreenAPIMessageSource`
  construction + registration to the live entry point
  (`if __name__ == '__main__':`) (BLOCKED until T004a approved). **Done**:
  also required (a) changing `_fetch_own_whatsapp_number`/`initialize_app`
  to take an injected `green_api` parameter instead of reaching for a
  module-level `bot` (both already degrade gracefully when `None`), and
  (b) updating 2 pre-existing test files that assumed a module-level `bot`
  (`test_denidin_own_whatsapp_number.py`, and
  `test_media_webhook_routing.py::test_extended_text_message_routes_...`)
  — user explicitly delegated unit/integration test judgment calls for
  this feature. Verified: 771/771 unit+integration tests pass, pylint
  8.38/10 (baseline 8.27/10, no regression), mypy 18 pre-existing errors
  unchanged (0 new).

- [ ] T005 **Manual live-behavior-preservation verification** (not an
  automated test — requires actually starting the app, so subject to
  CLAUDE.md's "never start an environment without explicit approval" gate
  same as any other environment start): confirm `dev` container still
  routes every message type identically post-refactor. **Human approval
  required before this step runs**, separate from approval of the code
  change itself.

**Checkpoint**: `import denidin` no longer touches Green API; live routing
verified unchanged.

---

## Phase 3: Foundational — timestamp fix + schema additions (Blocking)

- [x] T006a [P] Write tests in `tests/unit/test_ai_handler_instructions.py`:
  `_build_instructions(constitution, today_timestamp=None)` uses
  wall-clock "today" when `today_timestamp` is omitted (current
  behavior, byte-for-byte); a supplied `today_timestamp` (epoch int)
  produces a "today" string matching that timestamp's UTC date instead.
- [x] T006b [P] Implement the `today_timestamp` parameter on
  `_build_instructions`, threaded through call sites at `ai_handler.py`
  lines 886, 1531, 1665 (`request.timestamp`, already present on
  `AIRequest`) (BLOCKED until T006a approved). **Done**: 4/4 tests passing.

- [x] T007a [P] Write tests in `tests/unit/test_today_timestamp_threading.py`
  asserting `today_timestamp` threads from `MediaHandler.process_media_message`'s
  existing `timestamp` argument through `_extract_text` →
  `ImageExtractor.analyze_media`/`PDFExtractor.analyze_media` → `AIHandler.
  capture_ledger_events_from_text`, and that `capture_ledger_events_from_text`
  passes it into `_build_instructions` unchanged; omitted `timestamp`
  preserves current wall-clock fallback behavior.
- [x] T007b [P] Thread `today_timestamp` through
  `capture_ledger_events_from_text`, `ImageExtractor.analyze_media`,
  `PDFExtractor.analyze_media` (delegates to ImageExtractor per page),
  `DOCXExtractor.analyze_media` (accepted for interface parity, unused -
  no ledger capture on that path), `MediaExtractor` ABC,
  `MediaHandler._extract_text`/`process_media_message` (BLOCKED until
  T007a approved). **Done**: 7/7 new tests passing; fixed one pre-existing
  integration test stub (`test_group_conversation_routing.py`) with a
  fixed-signature lambda that needed the new kwarg added. 782/782
  unit+integration tests pass; whole-project pylint 9.12/10 (was 9.10);
  no new mypy errors.

- [x] T008a [P] Write tests in `tests/unit/test_ledger_event_manager.py`
  (extending the existing suite): every `add_ledger_event` call writes
  `schema_version == CURRENT_SCHEMA_VERSION`; pre-existing fixture event
  files without the field are unaffected/untouched by unrelated operations
  (never retro-applied); `resolve_replaced_event_id` replaces the
  placeholder only when it's currently the placeholder, returns `False`
  + logs otherwise; `apply_review_answer` patches only the targeted
  event/fields.
- [x] T008b [P] Implement `CURRENT_SCHEMA_VERSION`, the `schema_version`
  field, `resolve_replaced_event_id`, `apply_review_answer` in
  `src/managers/ledger_event_manager.py` (BLOCKED until T008a approved).
  **Done**: 12/12 new tests passing (86/86 in the full file); updated one
  pre-existing exact-field-set completeness assertion to account for the
  new field (expected/intentional, per the schema addition itself).

**Phase 3 verification**: 793/793 unit+integration tests pass; whole-project
pylint 9.13/10 (up from 9.10 baseline); mypy clean on all touched files
(only pre-existing, unrelated missing-stub warnings remain).

**Checkpoint**: all shared/live code changes complete and tested. T005
(manual live-behavior-preservation verification, requiring an actual `dev`
environment start) remains outstanding, gated on explicit human approval
per CLAUDE.md - not yet run.

---

## Phase 4: User Story 1 — Replay a date range (US1)

- [x] T009a Write tests in `tests/unit/test_player_export_parser.py` against
  synthetic WhatsApp-export-format fixtures (never the real sample, per
  user's explicit instruction): message-start-line regex, multi-line
  continuation joining, sender-name emoji/RTL-mark stripping, attachment-
  line detection + filename resolution, system-message filtering (per
  T002's findings), date-range filtering/clamping (`start` never earlier
  than 2025-09-01, `end` never later than "today" as injected via a fixed
  test clock, not real wall-clock).
- [x] T009b Implement `player/export_parser.py` (BLOCKED until
  T009a approved). **Done**: 19/19 tests passing, pylint 9.89/10, mypy
  clean. Caught and fixed a real bug during implementation: a system notice
  mid-conversation (no "Name:" colon structure) could get glued onto the
  PRIOR real message as a bogus continuation line, corrupting its text -
  added a two-stage date-prefix/system-check before attempting the
  sender:text split, plus a regression test locking this down.

- [x] T010a [P] Write tests in `tests/unit/test_player_notification_synth.py`:
  a `ParsedMessage` (text) produces a notification dict that round-trips
  correctly through the real `WhatsAppMessage.from_notification`; same for
  an image `ParsedMessage` (correct `fileMessageData.downloadUrl`/
  `fileName`/`mimeType`); `mimeType` inference matches
  `MediaFileManager`'s own extension routing (imported/reused, not
  re-derived); unsupported attachment types produce no notification (per
  contracts/message-source.md).
- [x] T010b [P] Implement `player/notification_synth.py` (BLOCKED
  until T010a approved). **Done**: 14/14 tests passing, pylint 10.00/10,
  mypy clean. `synthesize_notification` returns `(event, type_message)` or
  `None` (unsupported extension).

- [x] T011a [P] Write an integration test in
  `tests/integration/test_player_media_server.py`: `LocalMediaServer`
  serves a fixture file over HTTP on an OS-assigned port, content matches
  byte-for-byte.
- [x] T011b [P] Implement `player/media_server.py` (BLOCKED until
  T011a approved). **Done**: 5/5 tests passing, pylint 10.00/10, mypy
  clean.

- [ ] T012a Write tests in `tests/unit/test_player_export_source.py`:
  `PlayerExportSource.start(dispatch)` calls `dispatch` once per
  `ParsedMessage` in chronological order, never blocks, exhausts cleanly.
- [ ] T012b Implement `player/export_source.py`
  (`PlayerExportSource`) (BLOCKED until T012a approved).

- [ ] T013a Write tests in `tests/unit/test_player_config_safety.py`:
  `--data-root` omitted → refusal, no default; `--data-root` resolving to
  the literal `data` path without `--confirm-production-data-root` →
  refusal; `config.player.json`'s shape validated (no Green API fields
  required).
- [ ] T013b Implement the CLI arg parsing + safety checks in
  `player/run_player.py`, plus `config/config.player.json`
  (BLOCKED until T013a approved).

- [ ] T014a `billed`-tier: write a small end-to-end test replaying 2-3
  synthetic text-only messages (a fee-agreement statement, a message
  spanning the date-range boundary) through the real pipeline via
  `run_player.py`'s main loop, asserting: correct `event_date`/`txn_date`
  reflect the replayed message's own historical date (regression test for
  Phase 3's fix — the actual point of this feature), and the run summary
  accounts for every message.
- [ ] T014b Implement `run_player.py`'s main loop (date-range scoping,
  driving `PlayerExportSource`, building the run summary) — no relevancy/
  reconciliation/review-queue wiring yet (BLOCKED until T014a approved).

**Checkpoint**: pure replay (no reconciliation/relevancy/review-queue)
works end-to-end for text messages.

---

## Phase 5: User Story 4 — No orphaned/unaccounted events (US4, feeds US1)

- [ ] T015a Write tests in `tests/unit/test_reconciliation.py`: pre-run
  snapshot correctly scoped to `[start,end]` by `event_date`; unmatched
  pre-existing files moved (never deleted) to `_to_delete/<run_id>/` with
  a correct manifest entry per file; files outside the range never read
  or touched; matched files (reproduced this run) left in place untouched.
- [ ] T015b Implement `player/reconciliation.py`, wire into
  `run_player.py`'s driver (BLOCKED until T015a approved).

---

## Phase 6: User Story 2 — Relevancy/reference resolution (US2)

- [ ] T016a Write tests in `tests/unit/test_relevancy.py`: the 4-step
  deterministic matching heuristic (client_name exact match →
  source_type=הסכם only → most-recent-first → agreement_label tiebreak);
  no match found → `replaces_hint` left as-is, no invented link; only
  triggered when `replaces_hint`/`reference_hint` is non-null.
- [ ] T016b Implement `player/relevancy.py`, wire into
  `run_player.py` (calls `LedgerEventManager.resolve_replaced_event_id`
  after each message) (BLOCKED until T016a approved).

- [ ] T017a `billed`-tier: write an end-to-end test replaying a fee
  agreement followed by a correction message for the same client,
  asserting the correction's `replaced_event_id` resolves to the real
  prior event's id (not the placeholder).
- [ ] T017b No new implementation expected (should already pass from
  T016b) — this task is verification-only; if it fails, fix surfaces here
  (BLOCKED until T017a approved).

---

## Phase 7: User Story 3 — Review queue (US3)

- [ ] T018a Write tests in `tests/unit/test_review_queue.py`: the notes-
  heuristic correctly flags known ambiguity-marker phrases (finalized list
  per plan.md) and does NOT flag ordinary notes text; queue `.jsonl`
  written with the documented shape (data-model.md §5); second-pass
  `--reapply-review` reads answered entries and calls
  `LedgerEventManager.apply_review_answer` correctly, skipping any entry
  still `status: "open"`.
- [ ] T019b Implement `player/review_queue.py` +
  `run_player.py`'s `--reapply-review` mode (BLOCKED until T018a
  approved).

---

## Phase 8: User Story 5 — Image-path replay regression (`expensive` tier)

- [ ] T020a **Requires explicit user approval before running** (expensive
  tier, real vision calls — per project rules, one at a time, never a bare
  sweep): write a full image-path replay test in
  `tests/expensive/test_player_image_replay.py` using `LocalMediaServer` +
  a fixture image with text mentioning a relative date ("אתמול"),
  asserting the resulting `txn_date` reflects the replayed message's
  historical date, not real wall-clock — the end-to-end regression test
  for Phase 3's 4-hop timestamp threading.
- [ ] T020b No new implementation expected — verification only (BLOCKED
  until T020a approved, and until the test has actually been run once
  with fresh approval per the expensive-test rules).

---

## Phase 9: User Story 6 — Documentation (US6)

- [ ] T021 Write `player/README.md`: invocation, `--data-root`/
  safety flags, second-pass workflow, and a link back to this spec
  directory — required by US6's "documented" criterion.

---

## Dependencies

- Phase 2 and Phase 3 block everything else (Phases 4-8 depend on both).
- Phase 4 (T009-T014) blocks Phase 5/6/7's wiring-into-driver steps (needs
  a working main loop to wire into), though the pure-logic test/implement
  pairs within Phase 5/6/7 could be written in parallel with late Phase 4.
- Phase 8 depends on Phase 3's T007b (image-path threading) and Phase 4's
  media-server (T011b).
- Phase 9 can happen any time after Phase 4 (needs a working CLI to
  document accurately).

## Next step

Human approval of this tasks.md breakdown, then begin Phase 1/2 test tasks
(T002, T003a) — per METHODOLOGY.md, implementation (any "b" task) never
starts before its paired "a" task is written AND explicitly approved.
