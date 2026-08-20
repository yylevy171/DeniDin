# Feature Specification: WhatsApp Typing Indicator While Processing

**Feature Branch**: `feature/048-whatsapp-typing-indicator`
**Created**: 2026-08-13
**Status**: DONE — merged to master (PR #217, 2026-08-13). Single-call design (final). A renewal-loop
attempt was built, live-tested, found buggy (unresolved ~20s scheduling delay), and reverted
same day; see Q1. Media message support (US4) added same day after a scope correction (Q2).
**Input**: User description: "whatsapp typing dots when processing" — show WhatsApp's native
"typing…" indicator while DeniDin is processing a message, so the user sees the bot is working
instead of silence until the reply lands.

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** ("NO UNVERIFIED THIRD-PARTY ASSUMPTIONS"): no assumption about how
  Green API behaves may be treated as confirmed without an actual call and review of the real
  result. The endpoint's *existence* and request/response shape are confirmed below via the
  installed client library's source plus Green API's own public docs. Exact on-device timing
  behavior (e.g. precisely how the dots render/clear) is left to be observed during real
  implementation testing, not asserted here — the spec-level design no longer depends on it,
  since v1 deliberately ships without a resend/renewal mechanism (Q1, resolved below).
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs.

**Required Files**: `user-stories.md` (present, CLARIFIED) ✅ · `spec.md` (this file,
CLARIFIED) · `plan.md` (NOT STARTED — ready to start) · `research.md` (NOT STARTED) ·
`data-model.md` (NOT STARTED — none expected, no new persisted data) ·
`contracts/` (NOT STARTED) · `quickstart.md` (NOT STARTED) · `tasks.md` (NOT STARTED).

---

## User Stories Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. Summary:

| # | Title | Priority |
|---|---|---|
| US1 | Sender sees typing dots only while it is DeniDin's turn to respond | P1 |
| US2 | Typing indicator does not fire for blocked users | P2 |
| US3 | Single call only, no renewal — accepted permanent limitation | P2 |
| US4 | Indicator also shows while media (images/docs/video/audio) is processed | P1 |

## Terminology Glossary

- **Typing indicator ("… is typing" dots)**: WhatsApp's native UI affordance — three animated
  dots plus the sender's name/avatar shown under the chat header — signaling the other party is
  composing a message or recording audio. Client-rendered based on the peer signaling an
  activity state; not something a bot paints directly (same category of effect as feature 045's
  blue checkmarks).
- **`sendTyping`**: Green API's real `POST /waInstance{id}/sendTyping/{token}` endpoint
  ([green-api.com/en/docs/api/service/SendTyping](https://green-api.com/en/docs/api/service/SendTyping/)),
  exposed by the installed `whatsapp_api_client_python` library (already a dependency, wrapped
  by `whatsapp-chatbot-python` — the same library family feature 045 used for `readChat`) as
  `bot.api.serviceMethods.sendTyping(chatId, typingTime=None, typingType=None)`. Confirmed
  present in the installed library's source (`serviceMethods.py:263`) and cross-checked against
  Green API's own docs; **not yet exercised anywhere in this codebase**.
- **DeniDin's turn**: the window between DeniDin beginning to process an inbound message and
  DeniDin sending its *next* outbound message in that exchange — whether that outbound message
  is a final answer or an interim one (e.g. a Morning MCP approval request). The moment DeniDin
  sends anything, the turn ends and it is the user's turn — DeniDin is waiting on them for a
  reply, clarification, or approval, and must not appear to be typing during that wait.

## Problem Statement

DeniDin currently gives no visual feedback in WhatsApp while it's working on a reply — silence
from the moment a message is sent until the reply lands. That gap can be a couple of seconds for
a plain text turn, or much longer for tool-calling/vision-heavy turns (media extraction,
multi-page PDF analysis, a Morning MCP round trip). Users have no signal DeniDin even received
their message until the answer appears. This feature asks DeniDin to trigger WhatsApp's native
typing indicator while actively processing, mirroring how a human correspondent's client shows
typing dots while they're composing a reply — and, symmetrically, to *not* show it while DeniDin
itself is the one waiting on the user.

## Resolved Questions (2026-08-13)

- **Q0 (RESOLVED, doc + source confirmed)**: `sendTyping` is a real, existing Green API
  capability, already reachable through this codebase's existing dependency chain — no new
  library needed. Request: `chatId` (required), `typingTime` (optional, 1000–20000 ms per Green
  API's docs), `typingType` (optional — omit for the typing-dots indicator, `"recording"` for
  the audio-recording icon instead; DeniDin only needs the default/omitted case). Response: HTTP
  200, empty body, meaning the notification was queued for delivery — not a synchronous
  guarantee of on-device rendering.
- **Q1 (RESOLVED, reverted to single-call 2026-08-13 after a failed renewal attempt)**: v1
  shipped with a single `sendTyping(chatId, typingTime=20000)` call and no renewal —
  live-tested, worked, but the indicator visibly lapsed after 20 seconds on any turn slower
  than that. A background renewal loop (resending every 15s, capped at 180s) was built and
  live-tested as a fix, but surfaced a real, unresolved bug: the renewer thread's first call
  was observed delayed by ~20 seconds after `start()` in at least one live test — meaning the
  indicator wasn't showing for most of the turn anyway, worse than the original gap in
  practice. Root cause (thread-scheduling delay vs. HTTP call latency) was not pinned down
  before the attempt was abandoned as not worth the added complexity. **Final decision**:
  reverted to the original single-call design. Accepted, permanent v1 limitation: the
  indicator may lapse before the reply arrives on turns slower than ~20 seconds. A renewal
  mechanism may be revisited later, but only with a solid root-cause understanding first.
- **Q2 (CORRECTED 2026-08-13, after live testing)**: originally resolved as "media messages
  out of scope" — this was wrong. It was a default I (the assistant) wrote into the spec during
  the initial draft and never surfaced back as its own explicit decision point, unlike Q1/Q4.
  "Show typing while processing" plainly means any processing, media included, and the user
  caught this live once images visibly had no indicator. Corrected scope: the indicator applies
  to **every** inbound message DeniDin processes — conversational turns (text, contact card)
  AND media messages (`imageMessage`, `documentMessage`, `videoMessage`, `audioMessage`) alike.
  Since `WhatsAppHandler.handle_media_message()` never routes through `AIHandler.get_response`
  (media bypasses the conversational pipeline entirely — see CLAUDE.md's "Message flow"
  section), this needed its own call site rather than reusing `_process_conversational_message`'s
  — see Technology Choices.
- **Q3 (RESOLVED)**: skip for blocked users, mirroring feature 045's Q4 precedent for read
  receipts — consistent with DeniDin already ignoring their messages outright.
- **Q4 (RESOLVED, user decision — the core clarification)**: the indicator reflects "DeniDin's
  turn" as defined in the Terminology Glossary above, **not** just "has this exchange fully
  concluded." Concretely: DeniDin starts "typing" when it begins processing an inbound message,
  and stops the instant it sends *any* outbound message — a final reply, an interim
  clarification question, or a pending-approval request (e.g. mid-way through a Morning MCP
  flow). It does not resume typing again until the user's next inbound message starts a new
  turn. This rules out any design where DeniDin appears to be "still typing" while it is, in
  fact, the one waiting on the user.

## Technology Choices

- **Call**: `bot.api.serviceMethods.sendTyping(chatId, typingTime=20000)` — no `typingType`
  (default typing-dots behavior, not the recording icon). Resent every 15 seconds by a
  background renewal loop (`TypingIndicatorRenewer`) for as long as the turn is still
  processing, capped at 180 seconds total (Q1, revised).
- **Call sites (two, after Q2's correction)**: (1) conversational turns — a single
  `send_typing_indicator(bot, chat_id, is_blocked)` call at the start of processing in
  `_process_conversational_message`; (2) media messages — same call in a shared wrapper
  (`_process_media_message` in `denidin.py`, since `WhatsAppHandler` has no `bot`/API
  reference of its own), used by all four media-type routers (image/document/video/audio).
  Both are one-shot, best-effort, no thread/renewal machinery (Q1).
- **Error handling**: best-effort, log-only, no retry, on every renewal call — consistent with
  the constitution's retry policy and feature 045's precedent; a failed/missing typing
  indicator is purely cosmetic and must never block or fail the rest of message processing.

## Out of Scope

- Any change to feature 045's read-receipt behavior — these are two independent WhatsApp UI
  affordances that happen to use the same underlying client library. (Read-receipts already
  applied to media messages from the start, since `on_notification_received` fires pre-routing
  for every notification type — only the typing indicator needed correcting, see Q2.)
- A "recording audio" indicator (`typingType="recording"`) — DeniDin doesn't send voice notes.
- A renewal/resend mechanism for turns longer than ~20 seconds — tried and reverted 2026-08-13
  after surfacing an unresolved delay bug; the single-call gap is now a permanent, accepted v1
  limitation rather than something to fix in this pass.

## Next Steps

1. ~~`speckit.clarify`~~ — DONE 2026-08-13, all Q1–Q4 resolved via explicit user decision.
2. `speckit.plan` — `plan.md`, `research.md`, `data-model.md` (likely empty — no new persisted
   state), `contracts/`, `quickstart.md`.
3. `speckit.tasks` — TDD task breakdown, human approval gate before implementation.
4. `speckit.analyze` — cross-artifact consistency check.
5. `speckit.implement`.
