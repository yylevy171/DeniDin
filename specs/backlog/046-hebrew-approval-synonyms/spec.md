# Feature Specification: Accept "מאשר"/"מאשרת" as Approval Answers

**Feature Branch**: `feature/046-hebrew-approval-synonyms`
**Created**: 2026-08-07
**Status**: CLARIFIED (2026-08-07) — all blocking Open Questions resolved. Ready for
`speckit.plan`.
**Input**: User-submitted feature request #46 (2026-08-07): "allow \"מאשר\" / \"מאשרת\" as
answers to approval questions meaning \"yes\"" — logged to `specs/ROADMAP.md`'s Ideas Backlog
same day, promoted to a spec on explicit request.

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** ("NO UNVERIFIED THIRD-PARTY ASSUMPTIONS"): whether the current gap is a
  model-judgment issue or an actual hard-coded string comparison must be confirmed against the
  real code path before deciding what, if anything, needs to change — see Open Questions.
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs.

**Required Files**: `user-stories.md` (present, DRAFT) ✅ · `spec.md` (this file, DRAFT) ·
`plan.md` (NOT STARTED — blocked on clarify) · `research.md` (NOT STARTED) ·
`data-model.md` (NOT STARTED) · `contracts/` (NOT STARTED) · `quickstart.md` (NOT STARTED) ·
`tasks.md` (NOT STARTED).

---

## User Stories Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. Summary:

| # | Title | Priority |
|---|---|---|
| US1 | Replying "מאשר" (masc.) or "מאשרת" (fem.) to a pending-action prompt executes it, same as "כן" | P1 |

## Terminology Glossary

- **Pending-action prompt**: The confirmation DeniDin sends after a tool call comes back
  pending (see `config/runtime_constitution.md`'s approval-gate section, e.g. "ליצור חשבונית
  ל... — לאשר?"), which the system holds until the user's next message resolves it as an
  affirmative or not.
- **"מאשר"/"מאשרת"**: Hebrew present-tense first-person "I confirm/approve" — masculine and
  feminine grammatical forms respectively of the same verb (אישר, "to approve/confirm"). Not
  currently listed among the example affirmatives in `runtime_constitution.md` (which
  currently names "כן"/"אישור"/"בסדר"/etc.).

## Problem Statement

`config/runtime_constitution.md`'s prose (`"...a clear affirmative (\"כן\"/\"אישור\"/\"בסדר\"/
etc.) in the next turn, the pending action executes automatically"`) reads as if approval is
resolved by the AI model's own judgment. It is not: `speckit.clarify` (2026-08-07) traced the
real code path and found a hard-coded, deterministic gate that runs BEFORE the model ever sees
the reply as an approval decision — see Resolved Questions. "מאשר"/"מאשרת" fail today because
they are simply absent from that gate's literal keyword set, not because of any model-judgment
gap.

## Resolved Questions (2026-08-07, via `speckit.clarify`)

- **Q1 (RESOLVED, code-path confirmed)**: `src/handlers/ai_handler.py:176-179` defines a
  literal keyword set:
  ```python
  _AFFIRMATIVE_REPLIES = {
      "yes", "yep", "yeah", "sure", "ok", "okay", "go ahead",
      "כן", "אישור", "בסדר", "אוקיי", "אוקי",
  }
  ```
  `_is_affirmative_reply()` (lines 182-195) casefolds/strips the reply and checks whether the
  *entire trimmed message* or its *leading token* (stripped of trailing `.,!?`) is in this set.
  It's called at line 1711 inside `_resolve_pending_approval` (triggered whenever
  `pending_approval_manager.get(chat_id)` returns a stored `PendingApproval`) — if the check
  returns `False`, code takes the **decline** branch (line 1781-1789) and never forwards the
  reply to OpenAI as an approval at all. This is a genuine code bug/gap, not a prompt-wording
  issue — `config/runtime_constitution.md`'s "etc." is misleading about how this actually
  works, since the model is never consulted for this specific decision.
- **Q2 (RESOLVED)**: Fix is a code change to `_AFFIRMATIVE_REPLIES` in `ai_handler.py`, not a
  constitution wording change — add `"מאשר"`, `"מאשרת"` to the set.
- **Q3 (RESOLVED)**: While touching this set, also add a few more common Hebrew affirmatives
  in the same class of gap: `"אוקיי"`/`"אוקי"` are already present; add `"בטח"`, `"סבבה"` (exact
  final list to be confirmed during `plan.md`/implementation, but the direction is "a few more,
  not just the two literally requested").
- **Q4 (RESOLVED)**: Since the mechanism is a deterministic, pure-function keyword check
  (`_is_affirmative_reply`), this needs only a plain unit test (`tests/unit/`) asserting the
  new tokens return `True` (and casing/whitespace/leading-token variants behave consistently
  with the existing entries) — no OpenAI call, no `billed`/`expensive` tier needed at all.

## Technology Choices

- **Change**: add `"מאשר"`, `"מאשרת"`, `"בטח"`, `"סבבה"` (final list confirmed at
  implementation time) to `_AFFIRMATIVE_REPLIES` in `src/handlers/ai_handler.py:176-179`.
- **Test**: new/extended unit test(s) in `tests/unit/` directly exercising
  `_is_affirmative_reply()` with the new tokens — plain deterministic assertions, no mocking of
  internal components needed since this is a pure string-matching function.
- Optionally, revisit `config/runtime_constitution.md`'s wording (the misleading "resolved by
  the model" framing) as a documentation cleanup — not required for the fix itself, but worth
  flagging during `plan.md` so the doc doesn't keep misdescribing this code path for the next
  person who reads it.

## Out of Scope

- Any other language's approval synonyms (English "yes"/"ok"/etc. are already presumably
  handled by the same model-judgment mechanism and are not the subject of this request).

## Next Steps

1. ~~`speckit.clarify`~~ — DONE 2026-08-07, all Q1-Q4 resolved.
2. `speckit.plan` — `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
   (expected minimal, given the confirmed scope is a small `ai_handler.py` set change + unit
   test).
3. `speckit.tasks` — TDD task breakdown, human approval gate before implementation.
4. `speckit.analyze` — cross-artifact consistency check.
5. `speckit.implement`.
