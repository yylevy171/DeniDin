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

- [x] ~~T005~~ **DROPPED** (human decision, 2026-08-07): manual `dev`-container
  live-behavior verification is not needed. T003/T004's automated dispatch-
  table-completeness tests, plus the real replay run against `test_data/events`
  (see Phase 4), together substitute for it in practice — no `dev` start
  required for this feature.

**Checkpoint**: `import denidin` no longer touches Green API; live routing
verified via automated tests (T003/T004) — no manual `dev` verification needed
(T005 dropped).

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

**Checkpoint**: all shared/live code changes complete and tested. T005 dropped
(see Phase 2) — no outstanding manual verification for this phase.

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

- [x] T012a Write tests in `tests/unit/test_player_export_source.py`:
  `PlayerExportSource.start(dispatch)` calls `dispatch` once per
  `ParsedMessage` in chronological order, never blocks, exhausts cleanly.
- [x] T012b Implement `player/export_source.py`
  (`PlayerExportSource`) (BLOCKED until T012a approved). **Done**.

- [x] T013a Write tests in `tests/unit/test_player_config_safety.py`:
  `--data-root` omitted → refusal, no default; `--data-root` resolving to
  the literal `data` path without `--confirm-production-data-root` →
  refusal. **Revised from the original wording** (human decision,
  2026-08-07): there is no separate `config/config.player.json` shape, and
  no "no Green API fields required" criterion — the player's own config
  file (`player/player_config.py`'s `PlayerConfig`:
  `export_zip`/`chat_id`/`sender_map`/`data_root`/`denidin_config`) instead
  *points at* an existing full `AppConfiguration` file (`config.test.json`/
  `config.dev.json`) via `denidin_config`, reused as-is — Green API fields
  are present and validated (unused, since the player always passes
  `green_api=None`), but that's accepted as fine: one less config format to
  maintain, and the unused fields are harmless. See
  `tests/unit/test_player_config.py` for this file's own coverage
  (`load_player_config`/`PlayerConfig`/`PlayerConfigError`).
- [x] T013b Implement the CLI arg parsing + safety checks in
  `player/run_player.py`, plus `player/player_config.py` (not
  `config/config.player.json` — see T013a's revision above) (BLOCKED until
  T013a approved). **Done**: `run_player.py` takes one positional player
  config JSON file; `--start`/`--end`/`--confirm-production-data-root` stay
  CLI-only (never baked into a reusable file — see
  `contracts/player-cli.md`).

- [ ] T014a `billed`-tier: **SKIPPED this phase** (human decision,
  2026-08-07) — a real run against `test_data/events` (prepared, not yet
  executed — see HANDOFF.md) was judged sufficient end-to-end verification
  instead of a synthetic `billed` test, for this phase specifically. **Not
  a fixed precedent** — whether T017a (Phase 6, `billed`) and T020a (Phase
  8, `expensive`) follow the same pattern or write the originally-planned
  synthetic tests is an open, separate decision for whenever those phases
  start (see each task's own note).
- [x] T014b Implement `run_player.py`'s main loop (date-range scoping,
  driving `PlayerExportSource`, building the run summary) — no relevancy/
  reconciliation/review-queue wiring yet (BLOCKED until T014a approved).
  **Done**: core replay loop working end-to-end for text + image/document
  messages (via `LocalMediaServer`). **The prepared real run against
  `test_data/events` (33 messages: 18 text + 15 vision) has still never
  been executed** — needs fresh explicit approval (real OpenAI cost); this
  is the actual end-to-end proof that Phase 3's `today_timestamp` fix works
  and is recommended to happen before Phase 5 starts, since reconciliation
  logic will reason about exactly this kind of real run's output.

**Checkpoint**: pure replay (no reconciliation/relevancy/review-queue)
works end-to-end for text and media messages against the real live
pipeline. **Not yet verified against a real run** (see T014b) — recommended
before starting Phase 5.

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
  prior event's id (not the placeholder). **Open decision when this phase
  starts** (human decision, 2026-08-07: deliberately not pre-decided): T014a
  skipped its synthetic `billed` test in favor of one real run instead —
  decide fresh whether T017a follows that same pattern or writes this test
  as originally planned; not a fixed precedent either way.
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
  for Phase 3's 4-hop timestamp threading. **Open decision when this phase
  starts** (human decision, 2026-08-07: deliberately not pre-decided) —
  same open question as T017a above: whether to follow T014a's
  skip-synthetic-test/real-run-instead pattern, or write this test as
  originally planned. The prepared real run against `test_data/events`
  (Phase 4, T014b) does include 15 vision messages, so it may already
  partially substitute — worth checking that run's actual results first.
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

## Status (updated 2026-08-07)

Phases 1–4 done (T005 dropped by human decision; T014a skipped in favor of
a real run — see Phase 4). Phases 5 (reconciliation), 6 (relevancy), 7
(review queue), 8 (expensive image-path regression), and 9 (README) are
**not started** — no `player/reconciliation.py`, `player/relevancy.py`,
`player/review_queue.py`, or `player/README.md` exist yet, and
`run_player.py` has no `--reapply-review` mode.

## Next step

**Recommended**: execute the prepared real run against `test_data/events`
(Phase 4, T014b's note — 33 messages, 18 text + 15 vision; needs fresh
explicit approval, real OpenAI cost) before starting Phase 5. It's the
actual end-to-end proof that Phase 3's `today_timestamp` fix works, and
Phase 5's reconciliation logic will reason about exactly the kind of
real-run output it would produce — better to see real output first.

Then begin Phase 5's test task (T015a), per METHODOLOGY.md — implementation
(any "b" task) never starts before its paired "a" task is written AND
explicitly approved.
