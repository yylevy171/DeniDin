---
description: "Task list for Feature 016: Per-Task AI Model Selection"
---

# Tasks: Per-Task AI Model Selection

**Input**: Design documents from `specs/P1/016-ai-model-selection/` (spec.md, plan.md)
**Prerequisites**: plan.md ✅, spec.md ✅ (no research.md/data-model.md/contracts/ — folded into spec.md + plan.md per plan's Project Structure note)

---

**IMPORTANT**: This task list complies with:
- **CONSTITUTION.md** (§I-III, §V, §VIII): Config-only (NO env vars), UTC timestamps, feature-branch git workflow, no-mocking-in-integration-tests, test immutability
- **METHODOLOGY.md** (§VI, §VII): TDD with human approval gates; Bug-Driven Development if pre-existing wiring bugs surface

**Scoping decision (human-directed, 2026-07-07)**: This feature adds **no unit tests**. Only integration/E2E tests count, framed as "user does X, expected result is Y." Where an integration/E2E test already covers a story, no new test is written — existing coverage is relied on and, where useful, re-run or lightly extended (never rewritten) to confirm this feature's changes. Confirmed against the actual `tests/` tree before finalizing this list (see per-story rationale below).

**Git Workflow**: All work on `feature/016-ai-model-selection` (already created and current branch). Conventional commits referencing REQ-IDs from spec.md.

---

**Organization**: Tasks grouped by user story (spec.md priorities: US1=P1, US2=P1, US3=P2), preceded by one small Foundational phase for the config schema change all three stories build on.

## Path Conventions

Single project: all paths relative to `apps/denidin-app/` (per plan.md Structure Decision — `morning-mcp-app` is untouched by this feature).

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: Add the config schema change (`ai_embedding_model` field, `ai_vision_model` default, validation) that all three user stories depend on.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [x] T001 Implement config schema changes in `src/models/config.py` (deviation from original plan, human-directed: the legacy `memory.longterm.embedding_model` fallback was found to be unreachable given dataclass defaults, so it was removed entirely rather than kept as a fallback — see spec.md Clarifications "implementation-time findings"):
  - Add `ai_embedding_model: str = 'text-embedding-3-large'` dataclass field
  - Change `ai_vision_model: str = 'gpt-4o'` → `'gpt-4o-mini'`
  - Add both to the `defaults` dict in `from_file()` (mirroring the existing `ai_model`/`ai_vision_model` pattern)
  - Add empty-string validation for `ai_model`, `ai_vision_model`, `ai_embedding_model` in `validate()`, following the existing `data_root` check pattern
  - No dedicated test for this task — every integration test that loads `config.test.json` via `AppConfiguration.from_file()` (e.g. `test_media_webhook_routing.py`, `test_session_transfer.py`) already exercises the defaults/validation path and would fail on a broken default. That's the existing safety net; see T005/T012.

- [x] T002 [P] Update `config/config.example.json`: set `ai_vision_model` to `"gpt-4o-mini"`, add `ai_embedding_model: "text-embedding-3-large"` (2-space indent, UTF-8, per Constitution §XV). Also updated `ai_model` to `"gpt-4o-mini"` (was `"gpt-3.5-turbo"`, human-directed) and removed the now-dead `memory.longterm.embedding_model` key.

- [x] T003 [P] Update `config/config.test.json`: same field updates as T002. Also applied the same updates to production `config/config.json` (gitignored, human-approved) and recalibrated `min_similarity` from 0.7 to 0.15 in all three files (see T006a/b finding).

**Checkpoint**: Config schema complete, validated, documented in both config files — ready for user story implementation.

---

## Phase 2: User Story 1 - Text conversations use the configured default text model (Priority: P1)

**Goal**: `AIHandler` already uses `config.ai_model` end-to-end for text completions (verified by reading `ai_handler.py:261`/`:563` during planning). Nothing changes here — `ai_model` stays `gpt-4o-mini` — this story is a no-op by design.

**Test decision**: **No new or modified test.** Every existing real-API integration test that sends a text message (`test_session_transfer.py::test_session_transfer_and_recall_after_expiration`, `test_end_to_end.py::test_send_message_and_verify_response`) already exercises `AIHandler` with `config.ai_model` on every run and would fail outright if that wiring were ever hardcoded to something else. Approved by human (2026-07-07): US1 needs no test work.

- [x] T004 No-op / documentation task only: note in the PR description that US1 required no code or test changes, since the existing wiring was already correct and is already covered by existing passing integration tests.

**Checkpoint**: User Story 1 — nothing to do, nothing broke.

---

## Phase 3: User Story 2 - Image/PDF/DOCX extraction uses the configured vision model (Priority: P1)

**Goal**: Switch the vision model default from `gpt-4o` to `gpt-4o-mini` (done in T001) and confirm real extraction quality holds, including on Hebrew content.

**Test decision**: **No new test, no test-file edit.** Investigated whether a meaningful assertion could be added (e.g. "the API call used `config.ai_vision_model`") — traced the extraction result's `model_used` field (`image_extractor.py:100`, `pdf_extractor.py:82`) and confirmed it never reaches the user-visible response text (`denidin.py:381-409` → `MediaHandler` → final WhatsApp reply is text-only). So there is no user-observable signal to assert on beyond output quality, which is exactly what the existing expensive tests in `tests/expensive/test_media_e2e.py` already check via `validate_response_full()` / Hebrew-ratio assertions:
  - `test_e2e_image_no_caption` (real image)
  - `test_e2e_docx_no_caption` (real Hebrew DOCX)
  - `test_e2e_hebrew_pdf_from_you` (real Hebrew PDF)
  - `test_e2e_pdf_with_caption_user_question`, `test_e2e_pdf_multipage_no_caption`

These already are "user sends real file via WhatsApp → expects a coherent Hebrew summary back" scenarios. Re-running them after the default switches is the correct verification, not writing new ones.

- [x] T005 👤 **MANUAL/EXPENSIVE APPROVAL GATE**: With the new `ai_vision_model: gpt-4o-mini` default in place, ran every test in `tests/expensive/test_media_e2e.py` individually, human-approved each run: `test_e2e_image_no_caption`, `test_e2e_docx_no_caption`, `test_e2e_hebrew_pdf_from_you`, `test_e2e_pdf_with_caption_user_question`, `test_e2e_unsupported_audio_file`, `test_e2e_pdf_multipage_no_caption` — all passed. Response quality manually verified against `logs/test_logs/test_media_e2e.log` (confirmed genuinely Hebrew, contextually correct extraction), not just trusting pytest's PASSED status. No regression found; `gpt-4o-mini` default kept.

**Checkpoint**: User Story 2 verified via real, already-existing E2E tests — no new test debt introduced.

---

## Phase 4: User Story 3 - Long-term memory embeddings use the configured, promoted embedding model (Priority: P2)

**Goal**: `MemoryManager` uses `config.ai_embedding_model` (new top-level field, default `text-embedding-3-large`), falling back to the legacy nested `config.memory.longterm.embedding_model` only when the top-level field is absent. Every ChromaDB write gains an `embedding_model` provenance field (REQ-DATA-001).

**Test decision**: **Extend one existing E2E test — no new test file.** `test_session_transfer.py::test_session_transfer_and_recall_after_expiration` is already a real, non-mocked E2E scenario — *"Given a user says 'my name is Mike', when their session expires, then it's transferred to long-term memory and recalled correctly when they return"* — and it already inspects `recalled` memory dicts in PHASE 6. Human-approved (2026-07-07) to extend its assertions rather than write a new test, since this modifies an existing/approved test per Constitution §VIII.

- [x] T006a Added one assertion to `tests/integration/test_session_transfer.py::test_session_transfer_and_recall_after_expiration` (PHASE 6.5): asserts `recalled[0]['metadata']['embedding_model'] == denidin_app.ai_handler.config.ai_embedding_model` (references config directly, not a hardcoded string, per human feedback). Test marked `@pytest.mark.expensive` (human-directed) since it hits the real OpenAI API.

- [x] T006b Implemented (simplified per human direction — no legacy fallback, see T001):
  - `src/handlers/ai_handler.py`: `MemoryManager` now constructed with `embedding_model=config.ai_embedding_model` directly (REQ-CONFIG-004, simplified)
  - `src/managers/memory_manager.py`: `remember()` adds `metadata.setdefault('embedding_model', self.embedding_model)` (REQ-DATA-001)
  - **Regression found and fixed during verification**: `min_similarity` (0.7 prod, 0.2 test) was tuned for `text-embedding-3-small` and caused real recall failures under `text-embedding-3-large` (measured similarity for a genuinely relevant match: 0.1858, just below the 0.2 test threshold). Root-caused via one trivial real embedding API call against actual stored data (not guessed). Recalibrated to 0.15 across `config.json`/`config.example.json`/`config.test.json`/test fixture. Documented in spec.md as REQ-CONFIG-006 and flagged as a provisional single-data-point calibration in Open Questions.
  - **Also fixed**: pre-existing bug where `denidin.py`'s `__main__` and `test_media_webhook_routing.py`'s config fixture never passed `ai_vision_model`/`ai_embedding_model` through to `initialize_app()` (REQ-BUGFIX-001).
  - Run T006a's extended test again — must now pass.

**Checkpoint**: User Story 3 verified via one real, extended E2E test — embedding-model resolution and provenance field both proven end-to-end.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T007 Update `apps/denidin-app/src/handlers/ai_handler.py`'s startup debug log (`ai_handler.py:118`) to also log the resolved vision and embedding models, not just the text model, for operator visibility (logging-only change, no test required)
- [x] T008 Run full non-expensive test suite (`cd apps/denidin-app && python3 -m pytest tests/ -v --tb=short`) to confirm no regressions across existing suites (RBAC, session, media, memory, config) — 490 passed. Also ran every expensive test individually (human-approved, one at a time): all pass, including after fixing an unrelated pre-existing typo in `test_simple_text_e2e.py` (`textMessageData.body` → `.textMessage`, verified against real fixtures/code) and removing a stale duplicate `tests/expensive/test_whatsapp_e2e.py` that risked writing to production data.
- [x] T009 Run lint/type-check (`python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc` and `python3 -m mypy src/ --config-file=mypy.ini`) on the 3 modified source files — pylint 9.18/10, mypy shows only pre-existing errors unrelated to this feature's changes.
- [x] T010 Update documentation referencing the old model config shape: `CLAUDE.md`, `.github/ARCHITECTURE.md`, `apps/denidin-app/README.md` (config example, options list, cost/FAQ sections), `apps/denidin-app/docs/MEMORY_API.md`, `apps/denidin-app/docs/MEMORY_PRODUCTION.md` (fixed a reference to the now-removed `config['memory']['longterm']['embedding_model']` path that would have raised `KeyError`, and recalibrated all documented `min_similarity` example values from the old 0.7 baseline to the new 0.15 baseline). `specs/done/*` archives intentionally left untouched (historical record, per METHODOLOGY §XI).

---

## Dependencies & Execution Order

- **Foundational (Phase 1)**: No dependencies — start immediately. Blocks all user stories.
- **US1 (Phase 2)**: No-op, can be "completed" immediately after Foundational (nothing to build or test).
- **US2 (Phase 3)**: Depends on Foundational (needs the new `ai_vision_model` default). Independent of US3 (different files/tests).
- **US3 (Phase 4)**: Depends on Foundational. Touches `ai_handler.py` (also read, not modified, by US1) and `memory_manager.py` (US3-only).
- **Polish (Phase 5)**: Depends on US2 and US3 both being complete (US1 has nothing to wait on).

### Parallel Opportunities

- T002 and T003 (config file edits) can run in parallel, both after T001.
- US2 (Phase 3) and US3 (Phase 4) can proceed in parallel — no shared files, no shared tests.

---

## Implementation Strategy

1. Foundational (T001-T003) → config schema exists, nothing behaviorally changed yet.
2. US1 (T004) → confirmed no-op.
3. US3 (T006a/T006b) → embedding model promoted + provenance field added, proven via one extended real E2E test; safe today because there's no existing ChromaDB data to strand (verified in spec.md).
4. US2 (T005) → re-run existing expensive Hebrew/media E2E tests once, with approval, to confirm the `gpt-4o-mini` vision default holds quality.
5. Polish (T007-T009) → logging visibility, full regression pass, lint/type-check.

(US2 and US3 can happen in either order or in parallel; US3's implementation is lower-risk to land first since it's the one with an automated test proving correctness, while US2's verification depends on human-approved expensive test runs.)

---

## Notes

- No unit tests are added anywhere in this feature (human-directed scoping decision, 2026-07-07) — every verification is either a no-op (US1), a re-run of pre-existing real E2E tests (US2), or one assertion added to a pre-existing real E2E test (US3).
- If T005's expensive-test re-run surfaces a pre-existing failure unrelated to the model change, treat it as a separate bug per Bug-Driven Development (METHODOLOGY §VII) — do not fold an unrelated fix into this feature.
- No feature flag is used anywhere in this task list, consistent with spec.md's Clarifications (config-value tuning on existing code paths, not new behavior).
- Expensive-test rules apply throughout T005: human approval every single run, one test at a time, read `logs/test_logs/` before re-running, never a bare `-m expensive` sweep.
