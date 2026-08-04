# Feature Specification: Agreement Cancellation & Modification via Reply Reference

**Feature Branch**: `feature/040-agreement-cancellation-modification`
**Created**: 2026-08-04 (split out of Feature 032, see "Split History" below)
**Status**: DRAFT — pre-`speckit.clarify`. Do NOT proceed to `plan.md`/`tasks.md` until the
Open Questions below are resolved with the user.
**Input**: Split from Feature 032 (`specs/backlog/032-whatsapp-reply-reference-resolution/`)
on 2026-08-04, per explicit user instruction: 032's original draft bundled (1) general
WhatsApp reply/reference resolution infrastructure and (2) agreement-specific
cancellation/modification behavior built on top of it. (1) stays in 032; (2) — this feature —
depends on 032's resolution capability but is scoped and delivered separately.

---

## Split History (2026-08-04)

Originally drafted as part of Feature 032's Problem Statement/User Story 1, motivated by a
real example: a lawyer replying "לבטל"/"למחוק" to an earlier WhatsApp message that stated a
fee agreement, meaning "cancel that agreement." Feature 032 now owns only the generic
"resolve a reply to the message it quotes" capability; this feature owns the ledger-event-
specific behavior — recognizing a cancellation/modification request against a resolved
reference and acting on it via `capture_ledger_event`.

**Dependency**: This feature requires Feature 032 to be implemented first — it consumes
032's resolved reference (original message content/metadata + optional `ledger_event_ids`) as
input; it does not itself capture `idMessage`/`stanzaId` or perform `stanzaId` → `Message`
resolution.

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I-III, §V, §XV, §XVII): No env vars, UTC timestamps internally,
  feature branch workflow, integration tests as E2E, alphabetized/UTF-8 JSON, no
  monkey-patching.
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
| US1 | Cancel an agreement by replying "לבטל"/"למחוק" to its original message | P1 |
| US2 | Modify ("לעדכן") a previously captured agreement | P2 |
| US3 | Reply-cancellation to a non-ledger message is a no-op (regression guard) | P2 |

## Terminology Glossary

- **Resolved reference**: The output of Feature 032's `stanzaId` → `Message` resolution — the
  original message's content/metadata plus, if present, its `ledger_event_ids`. This feature
  treats the presence/absence of `ledger_event_ids` on a resolved reference as the signal for
  "is there anything here to cancel/modify."
- **`replaced_event_id`**: `capture_ledger_event`'s existing field (Feature 033,
  REQ-DATA-002) that today always writes the literal placeholder `"צריך למצוא"` for any
  `replaces_hint`. This feature is what lets it resolve to a real `event_id` instead, in the
  one case resolution is tractable: a direct reply.

## Problem Statement

1. **`capture_ledger_event`'s cancellation path already exists but is permanently
   unresolvable today.** `replaces_hint` (free text) → `replaced_event_id` always writes
   `"צריך למצוא"` — DeniDin has never had a way to resolve a hint to a real id. Feature 032
   gives this feature a resolved reference to work with when the request is a direct reply.
2. **Modification (`לעדכן`) was explicitly deferred** in the original 032 draft ("modify can
   be relaxed for now") but is included here as US2, to be prioritized/scoped properly rather
   than dropped.

## Open Questions (BLOCKING — must be resolved via `speckit.clarify` before `plan.md`)

- **Q3**: What happens on a reply to a message that captured MULTIPLE components (e.g. a
  multi-stage agreement, Feature 033 US3)? Cancel all of them? Ask which one?
- **Q5**: User Story 1, Scenario — replying "לבטל" to a message that resolves (per Feature
  032) but has no `ledger_event_ids` (nothing to cancel): does DeniDin need to say anything
  back (e.g. "nothing to cancel here"), or is silence/normal conversational handling
  acceptable? Affects whether this needs its own user-facing error message
  (`constants/error_messages.py`).
- **Q7 (new, modification scope)**: What exactly can be modified via `לעדכן`? Same fields as
  original capture (amount, client, description)? Full replace, or partial/field-level patch?
  Needs its own data-model thought, separate from cancellation's simpler "reference the old
  event" shape.
- **Q8 (new, modification vs cancellation event shape)**: Does a modification produce a new
  `LedgerEvent` with `event_subtype` other than `ביטול` (e.g. `עדכון`), referencing
  `replaced_event_id` the same way cancellation does? Confirm against real `Events.csv`
  convention, same verification `REQ-DATA-004` did for `agreement_id`/`component_id`.

## Resolved from original 032 draft (2026-08-04)

- **Q4 (RESOLVED)**: `replaced_event_id` stores the specific `event_id`, not the broader
  `agreement_id`.
- **Q6 (RESOLVED)**: No new RBAC — unrestricted for any godfather/admin, same as
  `capture_ledger_event` itself today. No original-creator restriction.

## Technology Choices

Not yet drafted — depends on Q3/Q7/Q8 above. Will follow `speckit.clarify` → `speckit.plan`.

## Out of Scope

- Cancellation/modification for requests that are NOT a direct WhatsApp reply (name/context-
  based matching against history) — a separate, harder problem, not addressed by this feature
  or by Feature 032.

## Next Steps

1. `speckit.clarify` — resolve Q3/Q5/Q7/Q8 above with the user.
2. `speckit.plan` — `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`.
3. `speckit.tasks` — TDD task breakdown, human approval gate before implementation.
4. `speckit.analyze` — cross-artifact consistency check.
5. `speckit.implement` — blocked on Feature 032 being implemented first.
