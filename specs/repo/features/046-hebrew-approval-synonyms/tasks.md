# Tasks: Accept "מאשר"/"מאשרת" as Approval Answers — Feature 046

**Input**: `plan.md`, `spec.md`, `user-stories.md` (this directory)
**Prerequisites**: plan.md (done), spec.md (done, CLARIFIED)

---

**Compliance**: CONSTITUTION.md §V (zero mocking — new test calls the real pure function
directly) and METHODOLOGY.md §VI (TDD, RED before GREEN) and §VIII (test immutability — the
existing `test_ai_handler_approval_gate.py` parametrize lists are NOT edited; new coverage is
added as a new test function instead, so already-approved assertions stay untouched).

**Existing test file found**: `apps/denidin-app/tests/unit/test_ai_handler_approval_gate.py`
already covers `_is_affirmative_reply()` with the current `_AFFIRMATIVE_REPLIES` set (Feature
022). This feature adds a sibling test function for the new tokens rather than touching the
existing `test_recognized_affirmatives`/`test_non_affirmatives` parametrize lists.

---

## Phase 3: User Story 1 — Recognize "מאשר"/"מאשרת" (and other new synonyms) as affirmative (Priority: P1)

**Goal**: `_is_affirmative_reply()` returns `True` for `"מאשר"`, `"מאשרת"`, `"בטח"`, `"סבבה"`
(plus the same casing/whitespace/trailing-punctuation/leading-token variants already exercised
for existing entries), and the pending-approval code path (`ai_handler.py:1711`) treats a reply
of one of these as approval, same as `"כן"` today.

**Independent Test**: `pytest tests/unit/test_ai_handler_approval_gate.py -v` — new test
function passes on its own, independent of the existing ones in the file.

- [x] T001 [US1] **[TEST — RED]** Add a new test function
  `test_recognized_affirmatives_feature_046` to
  `apps/denidin-app/tests/unit/test_ai_handler_approval_gate.py`, parametrized over
  `"מאשר"`, `"מאשרת"`, `"בטח"`, `"סבבה"` plus a few variant forms mirroring the existing
  `test_recognized_affirmatives` style (e.g. `"  מאשר  "`, `"מאשרת."`, `"מאשר, תודה"`), each
  asserting `_is_affirmative_reply(text) is True`. Run it and confirm it FAILS against current
  code (the tokens aren't in `_AFFIRMATIVE_REPLIES` yet) — this is the RED checkpoint.
  **DONE 2026-08-07** — confirmed RED: 9 failed, 29 passed (pre-existing tests untouched).
- [x] T002 [US1] **[IMPL — GREEN]** In `apps/denidin-app/src/handlers/ai_handler.py:176-179`,
  add `"מאשר"`, `"מאשרת"`, `"בטח"`, `"סבבה"` to the `_AFFIRMATIVE_REPLIES` set. Re-run T001's
  test — confirm it now PASSES, and re-run the full
  `test_ai_handler_approval_gate.py` file to confirm the pre-existing tests are unaffected.
  **DONE 2026-08-07** — confirmed GREEN: 38 passed. Full `tests/unit/` suite also re-run:
  724 passed, no regressions.

**Checkpoint**: `pytest tests/unit/test_ai_handler_approval_gate.py -v` — all tests (existing +
new) pass. **DONE.**

---

## Dependencies

- T002 depends on T001 (RED before GREEN, per TDD).
- No dependency on any other in-flight feature.

## Parallel Execution

Not applicable — two sequential tasks, single file pair.

## Implementation Strategy

**MVP = the whole feature**: T001 + T002 is the entire scope. Once both pass, this feature is
complete — proceed directly to closing out per `plan.md`'s Phase 3 (move spec to
`specs/done/`); `/speckit.analyze` is optional given the tiny surface area.
