# Feature Specification: WhatsApp Reply/Quote Reference Resolution

**Feature Branch**: `feature/032-whatsapp-reply-reference-resolution`
**Created**: 2026-07-30
**Status**: DRAFT — pre-`speckit.clarify`. Do NOT proceed to `plan.md`/`tasks.md` until the
Open Questions below are resolved with the user.
**Input**: User description: "create a new feature to support ref msgs (stanzaID, etc) so
that cancelations can work" — real example: "למחוק"/"לבטל" sent as a WhatsApp reply to an
earlier message that stated a fee agreement, meaning "cancel that agreement." "Not sure if
this is supported" (it isn't — confirmed via code investigation, see Problem Statement).

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I-III, §V, §XV, §XVII): No env vars, UTC timestamps internally,
  feature branch workflow, integration tests as E2E, alphabetized/UTF-8 JSON, no
  monkey-patching.
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs.

**Required Files**: `user-stories.md` (present, DRAFT) ✅ · `spec.md` (this file, DRAFT) ·
`plan.md` (NOT STARTED — blocked on clarify) · `research.md` (see inline research below,
not yet a separate file) · `data-model.md` (NOT STARTED) · `contracts/` (NOT STARTED) ·
`quickstart.md` (NOT STARTED) · `tasks.md` (NOT STARTED).

---

## User Stories Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. Summary:

| # | Title | Priority |
|---|---|---|
| US1 | Cancel an agreement by replying "לבטל"/"למחוק" to its original message | P1 |
| US2 | Non-ledger replies are unaffected (regression guard) | P2 |

## Terminology Glossary

- **`stanzaId`**: Green API's field identifying which prior message a reply/quote refers to
  — found under `messageData.extendedTextMessageData.quotedMessage` on an incoming reply.
  References Green API's own `idMessage` scheme, NOT DeniDin's internal `message_id` (a
  separate, freshly-generated UUID with no relationship to Green API's IDs).
  **This feature's entire premise is resolving a `stanzaId` back to something DeniDin already
  has internally** — see Open Questions for exactly how.
- **`idMessage`**: Green API's own message identifier (format like
  `"true_1234567890@c.us_ABCD1234567890"`, per `specs/done/001-whatsapp-chatbot-passthrough/contracts/green-api.md`).
  Not currently captured/stored anywhere in this codebase for any message DeniDin
  sends/receives.
- **`quotedMessage`**: The Green API webhook substructure carrying the replied-to message's
  metadata (`stanzaId`, `participant`, `typeMessage`) — already typed in
  `src/models/green_api.py` (`QuotedMessage` dataclass) but never populated/read anywhere.

## Problem Statement

Real usage (2026-07-30): a lawyer wants to cancel a previously-captured fee agreement by
replying directly to the WhatsApp message that originally stated it, with "לבטל"/"למחוק".
Investigated via code reading (not assumed):

1. **Reply/quote data is discarded on ingestion.** `WhatsAppMessage.from_notification`
   (`src/models/message.py`) reads `extendedTextMessageData.text` to extract a forwarded/
   quoted/link-preview message's flat body text (per `bugfix-008`, a deliberate and correct
   fix for a different bug at the time) — but never reads the sibling `quotedMessage`/
   `stanzaId` fields. A reply today is indistinguishable from an unrelated new message once
   it reaches the AI.
2. **DeniDin doesn't capture its own messages' real WhatsApp IDs.** `WhatsAppMessage.message_id`
   is a freshly-generated `uuid.uuid4()` at ingestion time, not Green API's `idMessage`. No
   code anywhere reads `idMessage` from a notification. This means even if `stanzaId` were
   captured on an incoming reply, there is currently no stored value anywhere to match it
   against.
3. **The resolution target already exists, though** (Feature 033): every captured
   `LedgerEvent` has a real `event_id`/`agreement_id`, and every `Message` has
   `ledger_event_ids` linking it to what it captured. Once (1) and (2) are solved, resolving
   "this reply's `stanzaId`" → "our stored `Message`" → "its `ledger_event_ids`" → "the real
   `agreement_id`/`event_id`" is straightforward, existing plumbing.
4. **`capture_ledger_event`'s cancellation path already exists but is permanently unresolvable
   today.** `replaces_hint` (free text) → `replaced_event_id` always writes the literal
   placeholder `"צריך למצוא"` (REQ-DATA-002, Feature 033) — DeniDin has never had a way to
   resolve a hint to a real id. This feature is what would let that resolve to something real,
   in the one case resolution is actually tractable: a direct reply.

## Open Questions (BLOCKING — must be resolved via `speckit.clarify` before `plan.md`)

- **Q1**: Should `idMessage` be captured/stored on *every* message DeniDin handles, or only on
  ones associated with a captured `LedgerEvent`? (Storing on every message is simpler/more
  robust for future reply-resolution needs beyond just cancellation; storing selectively is
  less invasive but narrower.)
- **Q2**: How does the resolved reference reach the model? Two candidate designs:
  (a) Resolve entirely in code — when an incoming message has a `stanzaId` matching a stored
  `Message` with `ledger_event_ids`, inject that resolved agreement's real details (client,
  description, `agreement_id`) directly into the AI's prompt/instructions as extra context
  ("this message replies to a message that captured: ..."), letting the AI's existing
  `capture_ledger_event`/`replaces_hint` flow work mostly unchanged, just with resolvable
  context available. (b) Something more code-driven — detect "this is a reply to a
  ledger-capturing message + the new text looks like a cancellation" heuristically in code,
  bypassing the AI's classification for this specific case. (a) seems more consistent with
  this codebase's existing pattern (the AI classifies/extracts, code never guesses semantics)
  — but needs confirmation.
- **Q3**: What happens on a reply to a message that captured MULTIPLE components (e.g. a
  multi-stage agreement, Feature 033 US3)? Cancel all of them? Ask which one? Only sensible
  once Q2 is settled.
- **Q4**: `replaced_event_id` currently stores a single `event_id`-shaped placeholder — should
  a real resolution populate it with the specific `event_id`, or the broader `agreement_id`
  (covering all its components)? Real `Events.csv` convention for this column would need
  re-checking (same kind of verification Feature 033's `REQ-DATA-004` did for
  `agreement_id`/`component_id`).
- **Q5**: User Story 1, Scenario 3 — replying "לבטל" to a message that captured nothing: does
  DeniDin need to say anything back (e.g. "nothing to cancel here"), or is silence/normal
  conversational handling acceptable? Affects whether this needs its own user-facing error
  message (`constants/error_messages.py`) or not.
- **Q6**: Any interaction with RBAC? (e.g., can only the original agreement's creator/a
  godfather cancel it, or is this unrestricted for any godfather/admin same as capture
  itself today?)

## Technology Choices

Not yet drafted — depends on Q1/Q2 above (e.g. whether `idMessage` storage requires a
`Message` schema change, per-session or global lookup index, etc.). Will follow
`speckit.clarify` → `speckit.plan`.

## Out of Scope (per explicit user instruction, 2026-07-30)

- Modification (`לעדכן`) — relaxed/deferred, not part of this feature.
- Cancellation/reference resolution for requests that are NOT a direct WhatsApp reply (name/
  context-based matching against history) — a separate, harder problem.

## Next Steps

1. `speckit.clarify` — resolve Q1–Q6 above with the user.
2. `speckit.plan` — `plan.md`, `research.md` (formalized), `data-model.md`, `contracts/`,
   `quickstart.md`.
3. `speckit.tasks` — TDD task breakdown, human approval gate before implementation.
4. `speckit.analyze` — cross-artifact consistency check.
5. `speckit.implement`.
