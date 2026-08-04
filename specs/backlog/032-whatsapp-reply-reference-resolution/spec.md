# Feature Specification: WhatsApp Reply/Quote Reference Resolution

**Feature Branch**: `feature/032-whatsapp-reply-reference-resolution`
**Created**: 2026-07-30
**Rescoped**: 2026-08-04 — split into general reply-resolution infrastructure (this feature)
and agreement-specific cancellation/modification behavior (moved to Feature 040, see "Split
History" below).
**Status**: DRAFT — pre-`speckit.clarify` on the rescoped Q1/Q2 below. Do NOT proceed to
`plan.md`/`tasks.md` until these are confirmed with the user (Q1/Q2 have working answers from
2026-08-04 discussion; formal `speckit.clarify` pass still recommended before `plan.md`).
**Input**: User description: "create a new feature to support ref msgs (stanzaID, etc)" —
originally motivated by a cancellation use case ("לבטל"/"למחוק" sent as a reply to a message
that stated a fee agreement), but the underlying capability — resolving *any* WhatsApp
reply/quote back to the internal message it refers to — is general-purpose and useful beyond
that one case. This feature covers only the general capability; agreement cancellation/
modification built on top of it is Feature 040.

---

## Split History (2026-08-04)

The original draft of this spec bundled two distinct concerns:

1. **General reply/reference resolution** — capturing Green API's `idMessage`/`stanzaId`/
   `quotedMessage` data and resolving a reply back to DeniDin's own stored `Message` record.
   **This feature.**
2. **Agreement updates (cancellation/modification)** — using a resolved reference to cancel
   ("לבטל"/"למחוק") or modify ("לעדכן") a previously captured `LedgerEvent`. **Moved to
   Feature 040** (`specs/backlog/040-agreement-cancellation-modification/`), which depends on
   this feature's resolution capability but owns all ledger-event-specific behavior,
   `replaced_event_id` semantics, and RBAC-for-cancellation questions.

This spec (032) no longer mentions cancellation/modification as in-scope behavior — only as
the motivating example for why reference resolution is needed at all.

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I-III, §V, §XV, §XVII): No env vars, UTC timestamps internally,
  feature branch workflow, integration tests as E2E, alphabetized/UTF-8 JSON, no
  monkey-patching.
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs.

**Required Files**: `user-stories.md` (present, DRAFT) ✅ · `spec.md` (this file, DRAFT) ·
`plan.md` (NOT STARTED) · `research.md` (NOT STARTED) · `data-model.md` (NOT STARTED) ·
`contracts/` (NOT STARTED) · `quickstart.md` (NOT STARTED) · `tasks.md` (NOT STARTED).

---

## User Stories Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. Summary:

| # | Title | Priority |
|---|---|---|
| US1 | Resolve a WhatsApp reply to the internal message it quotes | P1 |
| US2 | Non-reply messages are unaffected (regression guard) | P2 |

## Terminology Glossary

- **`stanzaId`**: Green API's field identifying which prior message a reply/quote refers to
  — found under `messageData.extendedTextMessageData.quotedMessage` on an incoming reply.
  References Green API's own `idMessage` scheme, NOT DeniDin's internal `message_id` (a
  separate, freshly-generated UUID with no relationship to Green API's IDs).
  **This feature's entire premise is resolving a `stanzaId` back to something DeniDin already
  has internally.**
- **`idMessage`**: Green API's own message identifier (format like
  `"true_1234567890@c.us_ABCD1234567890"`, per `specs/done/001-whatsapp-chatbot-passthrough/contracts/green-api.md`).
  Not currently captured/stored anywhere in this codebase for any message DeniDin
  sends/receives.
- **`quotedMessage`**: The Green API webhook substructure carrying the replied-to message's
  metadata (`stanzaId`, `participant`, `typeMessage`) — already typed in
  `src/models/green_api.py` (`QuotedMessage` dataclass) but never populated/read anywhere.

## Problem Statement

Investigated via code reading (not assumed), 2026-07-30:

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
3. **This capability is generally useful, not just for cancellation.** Any future feature
   that wants to know "what is this message replying to?" needs the same plumbing. Feature
   033's `LedgerEvent`/`ledger_event_ids` linkage is one consumer of a resolved reference (see
   Feature 040), but the resolution mechanism itself should not assume a ledger event exists
   — a reply may quote an ordinary conversational message with no associated ledger data at
   all, and resolution should still succeed (just with no ledger data to attach).

## Scope

**In scope**: capturing `idMessage`/`stanzaId`/`quotedMessage`, and resolving a `stanzaId` on
an incoming reply back to DeniDin's own stored `Message` record — making the original
message's content and metadata (and, if that message happens to have any
`ledger_event_ids`, that linkage too — as optional, pass-through data, not something this
feature interprets or acts on) available as extra context for whatever consumes it next.

**Out of scope** (moved to Feature 040): interpreting a resolved reference as a cancellation
or modification request, `capture_ledger_event`'s `replaces_hint`/`replaced_event_id`
semantics, and any RBAC question about who may act on a resolved reference. This feature
resolves references; it does not decide what any caller does with them.

## Open Questions

- **Q1 (RESOLVED 2026-08-04)**: Capture `idMessage` on **every** message DeniDin handles, not
  only ones associated with a ledger event — simpler, more robust, and this feature is
  explicitly general-purpose now.
- **Q2 (RESOLVED 2026-08-04)**: Resolution is injected as extra context (consistent with the
  existing pattern where the AI classifies/extracts and code never guesses semantics) — code
  resolves `stanzaId` → stored `Message`, and surfaces that message's content/metadata to
  whatever needs it (e.g. the AI's prompt, or a future non-AI consumer). **Scope is all
  messages, not just ledger-event ones** — if the resolved message happens to have
  `ledger_event_ids`, that data is included as optional pass-through; if not, resolution still
  succeeds with just the message content/metadata. This feature does not itself decide what a
  cancellation/modification request means — see Feature 040 for that.

## Technology Choices

Not yet drafted — depends on final `speckit.plan` (e.g. whether `idMessage` storage requires a
`Message` schema change, per-session or global lookup index for `stanzaId` → `Message`).

## Next Steps

1. Formal `speckit.clarify` pass (Q1/Q2 have working answers above; confirm before `plan.md`).
2. `speckit.plan` — `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`.
3. `speckit.tasks` — TDD task breakdown, human approval gate before implementation.
4. `speckit.analyze` — cross-artifact consistency check.
5. `speckit.implement`.
