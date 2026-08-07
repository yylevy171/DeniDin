# Implementation Plan: Accept "מאשר"/"מאשרת" as Approval Answers — Feature 046

**Feature**: 046-hebrew-approval-synonyms
**Branch**: `feature/046-hebrew-approval-synonyms`
**Spec**: `./spec.md` · **User Stories**: `./user-stories.md`
**Status**: Ready for Task Generation
**Updated**: 2026-08-07

**Compliance**: CONSTITUTION.md (§I no env vars — N/A, no config touched; §II UTC — N/A;
§III git workflow; §V zero-mocking — the new unit test exercises a pure function directly, no
external service involved to mock; §XVII no monkey-patching — N/A, plain set literal edit).
No feature flag: this extends an already-enabled, already-shipped approval-recognition gate
with more recognized words — the same class of change as adding a missing synonym to an
existing keyword list, not new capability being introduced behind a toggle.

---

## Summary

Root cause fully resolved during `speckit.clarify` (see spec.md): `_AFFIRMATIVE_REPLIES`
(`src/handlers/ai_handler.py:176-179`) is missing `"מאשר"`/`"מאשרת"` (and a couple of other
common Hebrew affirmatives). **Deliverable**: add the missing tokens to that literal set, plus
one unit test asserting `_is_affirmative_reply()` recognizes them. No other code changes.

## Technical Context

- **Language/Version**: Python 3.11 (unchanged).
- **Primary Dependencies**: none new.
- **Storage**: N/A.
- **Testing**: one unit test in `apps/denidin-app/tests/unit/` (wherever
  `_is_affirmative_reply`/`_AFFIRMATIVE_REPLIES` is already covered, or a new
  `test_ai_handler_affirmative_replies.py` if not) — pure function, no mocking needed.
- **Target Platform**: N/A — no runtime/container change, no rebuild/redeploy required until
  merged (this is source, not config).
- **Scale/Scope**: one set literal edit (4 new string tokens), one test file.

## Constitution Check

- **No env vars** — PASS.
- **UTC** — N/A.
- **Feature branch** — PASS: `feature/046-hebrew-approval-synonyms`.
- **Feature flags** — N/A, see Compliance note above.
- **Zero-mocking** — PASS: new test calls `_is_affirmative_reply()` directly, a pure function.
- **No monkey-patching** — PASS: plain literal edit.
- **Test immutability (§VIII)** — PASS: only adds new test assertions, doesn't rewrite existing
  ones covering `"כן"`/`"אישור"`/etc.

## Project Structure

```text
specs/backlog/046-hebrew-approval-synonyms/
├── spec.md          # done — CLARIFIED
├── user-stories.md  # done — CLARIFIED
├── plan.md          # this file
└── tasks.md         # next — /speckit.tasks
```
(No `research.md`, `data-model.md`, `contracts/`, `quickstart.md` — root cause and fix are
already fully confirmed in spec.md via code-path trace; no new entities, no new external
contract, no new setup steps. Producing those files here would be pure boilerplate.)

### Source Code

```text
apps/denidin-app/src/handlers/ai_handler.py
  # _AFFIRMATIVE_REPLIES (line ~176-179): add "מאשר", "מאשרת", "בטח", "סבבה"

apps/denidin-app/tests/unit/
  # new/extended test(s) asserting _is_affirmative_reply() returns True for the new tokens
  # (and for casing/leading-token/trailing-punctuation variants, consistent with how existing
  # entries are already tested, if such coverage exists — otherwise write it fresh)
```

## Phased Execution

### Phase 1 — Test (TDD)
Write the unit test asserting the new tokens are NOT yet recognized (RED — confirms the gap is
real before fixing it), per METHODOLOGY §VI.

### Phase 2 — Fix
Add the four tokens to `_AFFIRMATIVE_REPLIES`. Test goes GREEN.

### Phase 3 — Close out
Move spec to `specs/done/` once merged, per folder movement rules.

## Complexity Tracking

No Constitution Check violations requiring justification — single set-literal edit plus one
test file, no new dependencies or infrastructure.
