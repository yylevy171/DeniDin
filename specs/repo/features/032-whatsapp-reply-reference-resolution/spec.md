# Feature Specification: WhatsApp Reply/Quote Reference Resolution

**Feature Branch**: `feature/032-whatsapp-reply-reference-resolution`
**Created**: 2026-07-30
**Rescoped**: 2026-08-04 — split into general reply-resolution infrastructure (this feature)
and agreement-specific cancellation/modification behavior (moved to Feature 040, see "Split
History" below).
**Status**: IN PROGRESS (moved to `specs/in-progress/` 2026-08-07) — planning complete
(`speckit.clarify` → `speckit.plan` → `speckit.tasks` → `speckit.analyze`, all done 2026-08-04/05,
PR #194 merged). Zero implementation code written yet. See `HANDOFF.md` for full state and
next steps. Ready for `speckit.implement`.
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

**Required Files**: `user-stories.md` ✅ · `spec.md` (this file) ✅ · `plan.md` ✅ ·
`research.md` ✅ · `data-model.md` ✅ · `contracts/` ✅ (`reply-resolution.md`) ·
`quickstart.md` ✅ · `tasks.md` (NOT STARTED — next: `speckit.tasks`).

---

## Clarifications

### Session 2026-08-04

- Q: Should stanzaId resolution search only the active (unexpired) session, or also
  archived/expired sessions and long-term ChromaDB memory? → A: Active session only — a
  reply to a message from an expired/archived session simply fails to resolve, same as any
  other unmatched `stanzaId` (falls back to ordinary new message).
- Q: Should idMessage matching be scoped per-chat/group, or a global match across all chats?
  → A: Scoped per chat/group (using `quotedMessage.participant`/the chat id) — matches how
  WhatsApp reply/quote actually works (you can only reply within the same conversation) and
  avoids theoretical cross-chat `idMessage` collisions.

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
  `"true_1234567890@c.us_ABCD1234567890"`, per `specs/done/v0.0.1/001-whatsapp-chatbot-passthrough/contracts/green-api.md`).
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
`ledger_event_ids`, the FULL structured `LedgerEvent` record(s) they point to — fetched via
`LedgerEventManager`, not just the bare ids — as pass-through data, not something this feature
interprets or acts on) available as extra context for whatever consumes it next. (Revised
2026-08-04: bare `ledger_event_ids` alone would give a consumer nothing to actually reason
from — see data-model.md's `content`/`ledger_events` mutual-exclusivity design, and the
duplicate-data rationale below.)

**Media messages are surfaced as their already-extracted text/analysis, in full, never the
raw media.** If the resolved message is an image/PDF/DOCX (i.e. it went through
`MediaHandler`/an extractor), the resolved reference carries that message's FULL, untruncated
`extracted_text` (plus `document_analysis`) — the same text already computed and stored at
ingestion time, included whole, not summarized or clipped further by this feature — but never
the original image bytes/base64, and this feature never re-runs a vision call to produce it.
Two reasons the raw media itself is excluded: (1) cost/latency — re-sending or re-analyzing
an image on every future reply to it would silently multiply vision-model spend; (2) prompt
size — raw image data doesn't belong inline in text context the way text does. The
distinction is specifically raw-media-bytes vs. extracted-text — not a distinction about how
much of the extracted text to include; extracted text goes in whole. If the resolved message
is a media message with no extracted text/analysis available for any reason, resolution still
succeeds with whatever metadata is available (sender, timestamp, media type) — no raw media,
no error.

**`content` (text or extracted text) and the structured `ledger_events` are mutually
exclusive, never both** (2026-08-04 revision, data-model.md): a `LedgerEvent` record already
contains `raw_message_excerpt` — the verbatim source text/image description the capture was
based on — so when a message has `ledger_event_ids`, the resolved reference surfaces the full
structured record(s) instead of `content`, not in addition to it. This avoids duplicating the
same raw text twice and gives the model already-parsed, authoritative values (exact amounts,
client name) rather than something it would otherwise need to re-derive from free text.

**Lookup scope: active session only, scoped per chat/group.** Resolution only searches the
current, unexpired session's stored messages (`data/sessions/`, per-role 24h expiration) —
not archived/expired sessions (`data/sessions/expired/YYYY-MM-DD/`) and not long-term
ChromaDB memory. A `stanzaId` referencing a message from an expired session simply fails to
resolve (no crash — falls back to "ordinary new message," same as any other unmatched
`stanzaId`). Additionally, matching is scoped per chat/group (using the chat/group id and/or
`quotedMessage.participant`), never a global cross-chat match — mirrors how WhatsApp
reply/quote actually works (you can only reply within the conversation you're in).

**Out of scope** (moved to Feature 040): interpreting a resolved reference as a cancellation
or modification request, `capture_ledger_event`'s `replaces_hint`/`replaced_event_id`
semantics, and any RBAC question about who may act on a resolved reference. This feature
resolves references; it does not decide what any caller does with them.

**Out of scope** (deferred, not Feature 040 either): resolving a reply to a message from an
expired/archived session. If this turns out to matter in practice (e.g. Feature 040 needs to
cancel a weeks-old agreement via reply), it would need its own follow-up spec — not silently
folded in here.

## Open Questions

- **Q1 (RESOLVED 2026-08-04)**: Capture `idMessage` on **every** message DeniDin handles, not
  only ones associated with a ledger event — simpler, more robust, and this feature is
  explicitly general-purpose now.
- **Q2 (RESOLVED 2026-08-04)**: Resolution is injected as extra context (consistent with the
  existing pattern where the AI classifies/extracts and code never guesses semantics) — code
  resolves `stanzaId` → stored `Message`, and surfaces that message's content/metadata to
  whatever needs it (e.g. the AI's prompt, or a future non-AI consumer). **Scope is all
  messages, not just ledger-event ones** — if the resolved message happens to have
  `ledger_event_ids`, the full structured `LedgerEvent` record(s) are included as pass-through
  (not bare ids — see 2026-08-04 revision above); if not, resolution still succeeds with just
  the message content/metadata. This feature does not itself decide what a
  cancellation/modification request means — see Feature 040 for that.
- **Q9 (RESOLVED 2026-08-04)**: If the resolved message is a media message (image/PDF/DOCX),
  the resolved reference surfaces its already-computed `extracted_text`/`document_analysis`
  IN FULL (from `MediaHandler`/extractors at original ingestion time) — never the raw
  image/media bytes and never a fresh vision-model call. The line is raw-media-bytes vs.
  extracted-text, not full-vs-truncated-text: the extracted text itself is never clipped by
  this feature. Keeps resolved-reference context cheap and text-only regardless of what kind
  of message is being referenced, without losing any of the already-extracted detail.
- **Q10 (RESOLVED 2026-08-04)**: `stanzaId` resolution searches only the active/unexpired
  session — not archived/expired sessions, not long-term ChromaDB memory. See Clarifications
  and Scope above.
- **Q11 (RESOLVED 2026-08-04)**: `idMessage` matching is scoped per chat/group, never a
  global cross-chat match. See Clarifications and Scope above.

## Technology Choices

Not yet drafted — depends on final `speckit.plan` (e.g. whether `idMessage` storage requires a
`Message` schema change, per-session or global lookup index for `stanzaId` → `Message`).

## Next Steps

1. ~~Formal `speckit.clarify` pass~~ — done 2026-08-04, see Clarifications above.
2. ~~`speckit.plan`~~ — done 2026-08-04: `plan.md`, `research.md`, `data-model.md`,
   `contracts/reply-resolution.md`, `quickstart.md`.
3. `speckit.tasks` — TDD task breakdown, human approval gate before implementation.
4. `speckit.analyze` — cross-artifact consistency check.
5. `speckit.implement`.
