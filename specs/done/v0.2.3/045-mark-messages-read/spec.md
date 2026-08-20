# Feature Specification: Mark Incoming Messages as Read (Blue Checkmarks)

**Feature Branch**: `feature/045-mark-messages-read`
**Created**: 2026-08-07
**Status**: DONE — merged to master (PR #198, 2026-08-07).
**Input**: User-submitted feature request #45 (2026-08-07): "mark incoming messages as read
so that sender sees blue checkmarks (send something back?)" — logged to
`specs/ROADMAP.md`'s Ideas Backlog same day, promoted to a spec on explicit request.

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** ("NO UNVERIFIED THIRD-PARTY ASSUMPTIONS"): no assumption about how
  Green API behaves may be treated as confirmed without an actual call and review of the real
  result — this is the primary open question below, not a detail to fill in later.
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
| US1 | Sender sees a read receipt (blue checkmarks) after DeniDin processes their message | P1 |
| US2 | Read receipt is sent even when DeniDin does not otherwise reply (e.g. `[[NO_REPLY]]`, group etiquette) | P2 |

## Terminology Glossary

- **Read receipt / blue checkmarks**: WhatsApp's standard UI indicator that a message has
  been read by its recipient — a client-rendered effect of the recipient's app or platform
  having marked the message read, not something a bot can paint directly.
- **`readChat`** (working name only — NOT confirmed): the Green API endpoint referenced in
  their public docs for marking a chat/message as read. Naming, exact request shape, and
  actual on-device effect are all unconfirmed as of this draft — see Open Questions.

## Problem Statement

Right now, whatever WhatsApp Business number DeniDin runs on does not appear to mark incoming
messages as read from the sender's point of view — the sender never sees the blue double-
checkmark WhatsApp normally shows once a message has been read on the recipient's device.
The request is for DeniDin to actively trigger that read state (described informally in the
original ask as "send something back?" — the requester was unsure of the mechanism), so a
human sender gets normal WhatsApp read-receipt feedback rather than only ever seeing single
grey checks (or single/double grey, if delivered) even after DeniDin has processed and
responded to their message.

## Resolved Questions (2026-08-07, via `speckit.clarify`)

- **Q1 (RESOLVED, live-verified)**: Green API's Python client (`whatsapp_api_client_python`,
  wrapped by `whatsapp-chatbot-python` which this app already depends on) exposes
  `bot.api.marking.readChat(chatId, idMessage=None)` — confirmed both in the installed
  library's source (`marking.py`, wrapping Green API's real `.../readChat/...` endpoint) AND
  by an actual live call against DeniDin dev's real Green API instance: `api.marking.readChat(
  '972522968679@c.us', idMessage='ACF7211F8892B1E31FD1B8EE7C7CE826')` returned `200 {'setRead':
  True}`, and the sender visually confirmed the targeted message (sent 2026-08-07 11:07:25
  Israel time) turned blue on their real device. No further capability confirmation needed.
- **Q2 (RESOLVED)**: Fires immediately on receiving the webhook, before AI processing —
  mirrors how a human reading a message shows blue checks right away, before typing a reply.
- **Q3 (RESOLVED)**: Scoped to the specific message, not the whole chat — always pass the
  real `idMessage` from the inbound webhook notification (`api.marking.readChat(chatId,
  idMessage=<the message's own id>)`), never omit `idMessage`. Avoids the broader "marks whole
  chat read" side effect entirely.
- **Q4 (RESOLVED)**: Skip for blocked users — consistent with DeniDin already ignoring their
  messages outright; no reason to give them read-receipt feedback.

## Open Questions (non-blocking, may still need attention during `plan.md`)

- **Q5**: Retry/error handling if the read-receipt call fails — best-effort, log-only (per
  CONSTITUTION's friendly-user-error / technical-detail-to-logs-only split), non-blocking to
  the rest of the message flow. This is a reasonable default and not expected to need further
  clarification, but confirm during `plan.md` that this doesn't conflict with the existing
  "retry once on 5xx/timeout after 1s; never retry 4xx" policy — likely: no retry at all here,
  since a missed read receipt is purely cosmetic and not worth a retry round-trip.

## Technology Choices

- **Call**: `bot.api.marking.readChat(chatId, idMessage=<inbound message's real id>)` (sync;
  the codebase does not currently use `whatsapp_api_client_python`'s async variants elsewhere,
  so no reason to introduce `readChatAsync` here).
- **Call site**: fires as early as possible in the message-handling flow, right after a webhook
  notification is validated/parsed into a `WhatsAppMessage` — before RBAC resolution, session
  load, or the OpenAI call — for every non-blocked sender, every message type (text, media,
  contact cards). Exact insertion point (`denidin.py`'s `@bot.router.message` handlers vs.
  inside `WhatsAppHandler`) to be finalized in `plan.md`.
- **Error handling**: best-effort, log-only, no retry (see Q5 above) — a failed read-receipt
  call must never block or fail the rest of message processing.

## Out of Scope

- Any read-receipt behavior for messages DeniDin sends (outbound) — this feature is about
  marking *incoming* messages as read, not about DeniDin knowing whether ITS replies were read.
- Typing indicators ("DeniDin is typing…") — a related but distinct WhatsApp UI affordance, not
  requested here.

## Next Steps

1. ~~`speckit.clarify`~~ — DONE 2026-08-07, all Q1-Q4 resolved (Q5 is a non-blocking default,
   confirm during plan).
2. `speckit.plan` — `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`.
3. `speckit.tasks` — TDD task breakdown, human approval gate before implementation.
4. `speckit.analyze` — cross-artifact consistency check.
5. `speckit.implement`.
