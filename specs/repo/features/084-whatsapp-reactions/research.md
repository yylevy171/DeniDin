# Research: WhatsApp Reactions

## R1 — Green API reaction endpoint shape (Gate Zero, BLOCKING, live, human-approved)

**Status**: ✅ CLOSED (2026-09-12) — live-verified against the real dev Green API instance and a
real dev WhatsApp account, with explicit human approval, human present to visually confirm each
result. Two of the pre-Gate-Zero assumptions below turned out to be **wrong** and are corrected
here; nothing about the endpoint's real behavior was accepted without this live confirmation.

**Confirmed mechanism**: `bot.api.request("POST", url, payload)` — the SDK's existing higher-level
`request()` wrapper (used by every other `Sending` method, e.g. `sendMessage`), which handles
`{{host}}`/`{{idInstance}}`/`{{apiTokenInstance}}` templating itself — **not** `raw_request`
(`raw_request` takes literal `requests.Session.request` kwargs with no templating, and is a worse
fit than `request()` for this SDK's own idiom; the pre-live-verification plan's preference for
`raw_request` is superseded by this finding).

**Confirmed endpoint** (differs from the pre-verification assumption):
```
POST {{host}}/waInstance{{idInstance}}/sendReaction/{{apiTokenInstance}}
Body: {"chatId": "<chat>", "idMessage": "<the target message's real Green API id>", "reaction": "<emoji or empty string>"}
```
`sendMessageReaction` (the originally assumed path) returns `404`; `messageId` (the originally
assumed payload key) is wrong — the correct key is **`idMessage`**, confirmed by the exact error
Green API returns when it's omitted: `400 {"message": "Validation failed. Details: 'idMessage' is
required"}`.

**Confirmed, live, with a human visually checking WhatsApp after each call**:
1. ✅ Reacting to a real **inbound** (user-sent) message with 👀 — reaction appeared.
2. ✅ Flipping the same message's reaction to ✅ (second call, same `idMessage`, different
   `reaction`) — **replaced** the 👀, did not stack. Confirms R3's flip-not-stack assumption.
3. ✅ Clearing with `reaction: ""` — reaction disappeared.
4. ⚠️ Reacting to a message the **bot itself sent** (self-reaction: same account as both sender
   and reactor) — the API call returned `200` exactly as for an inbound message, but **no
   reaction ever rendered in WhatsApp**, confirmed by direct visual check across three separate
   attempts. This is a real, load-bearing limitation. **However, it does not block this feature**:
   every use case in `spec.md`/`user-stories.md` only ever reacts to messages the *user* sent
   (documents, action-request text, the "current turn's incoming message" default for
   `react_to_message`) — DeniDin never needs to react to its own replies. Recorded here so this
   constraint is never silently forgotten if a future design change (e.g. reacting to the bot's
   own confirmation message) is proposed.
5. ⚠️ Reacting with a **bogus/nonexistent `idMessage`** also returned `200` — Green API does
   **not** synchronously validate that the target message exists. This **invalidates** the
   pre-verification assumption that a deleted-message reaction attempt would surface as a
   detectable 4xx. **Design consequence** (updates `spec.md`'s Edge Cases /
   `contracts/green-api-reaction-client.md`): `send_reaction()` cannot distinguish "the message
   existed and was reacted to" from "the message doesn't exist and nothing happened" via the HTTP
   response alone — both return `200`. This is fine given REQ-084-007's own framing (reaction
   failures must never block the core turn) — a silent no-op on a deleted message is
   indistinguishable from success and requires no special handling, error suppression, or retry
   logic differentiation; the deleted-message edge case in `spec.md` is satisfied "for free" by
   this behavior rather than by any explicit error-catching code.
6. 🔲 **Not tested**: group chat (`@g.us`) behavior — explicit human decision (2026-09-12) to skip
   for now, since the 1:1 mechanism is now fully confirmed and group chats use the identical
   endpoint/payload shape with a different `chatId` suffix. Documented as an assumption-by-analogy,
   not an independent confirmation — flag for a follow-up live check before/during
   `speckit.tasks`'s billed acceptance tests if group-chat reaction behavior becomes load-bearing
   for a specific test assertion.

**Rationale for the corrected mechanism/endpoint**: no wrapped `sendReaction`-style method exists
anywhere in the installed `whatsapp-api-client-python` package (`tools/sending.py` was inspected in
full: `sendMessage`, `sendButtons`, `sendTemplateButtons`, `sendListMessage`,
`sendFileByUpload(Url)`, `uploadFile`, `sendLocation`, `sendContact`, `sendLink`,
`forwardMessages`, `sendPoll`, `sendInteractiveButtons(Reply)` — no reaction support), so a generic
mechanism was required; `bot.api.request()` is what every other wrapped method already uses
internally, making it the correct fit once `raw_request`'s awkward literal-kwargs shape was found
unnecessary during live testing (a plain string URL with `{{host}}`/`{{idInstance}}`/
`{{apiTokenInstance}}` placeholders, exactly like `sendMessage`'s own implementation, worked
directly).

**Alternatives considered**:
- `GreenApi.raw_request(...)` (the original plan). Superseded once live testing showed
  `bot.api.request()` — the SDK's own standard wrapper, doing its own URL templating — was simpler
  and consistent with every existing call site in this codebase.
- Hand-rolled `requests.post(...)` directly against the endpoint, bypassing the SDK entirely.
  Rejected: duplicates host/token/timeout configuration already centralized in `bot.api`, and
  every other Green API call site in this codebase goes through the SDK.
- A subclass or monkey-patch adding a `sendReaction` method onto `Sending`. Rejected outright by
  CONSTITUTION §XVII (no monkey-patching, no runtime method injection).
- Upgrading the vendored SDK version in case a newer release wraps reactions natively. Not pursued
  — `bot.api.request()` unblocks the feature without it.

## R2 — Fast-path classification tables (non-live, resolved now)

**Decision**: two small, plain code-constant lookup tables in the fast-path hook module (no
external unknown, no LLM call):
- **Media reaction pool**: `["👀", "🔍", "⏳"]` (per spec REQ-084-002's own example), applied
  whenever `typeMessage` is `imageMessage` or `documentMessage` and the message is addressed to
  DeniDin (see `contracts/group-discretion-gating.md`).
- **Action-request reaction pool**: `["👍", "🫡", "👌"]` (per spec REQ-084-002's own example),
  applied when a short, curated action-verb keyword list matches the incoming text
  (`textMessage`/`extendedTextMessage`) — e.g. Hebrew/English verbs already used elsewhere in the
  runtime constitution's own examples for invoice/ledger actions ("צור", "הוצא", "מחק", "create",
  "issue", "delete", "cancel"). This is a cheap local regex/keyword match, never an LLM call, to
  stay inside the <1000ms budget.

**Rationale**: the spec gives these exact emoji sets as examples (REQ-084-002); using them
verbatim avoids inventing new UX choices this stage isn't positioned to make, and keeps the
fast-path fully synchronous/local per the performance constraint.

**Alternatives considered**: a cheap classifier call to a small/fast model instead of keyword
matching. Rejected for the fast-path specifically — any network round-trip to an LLM provider risks
blowing the <1000ms budget and reintroduces exactly the kind of external-call latency/failure-mode
risk the fast-path exists to avoid; the *slower*, LLM-driven path already exists as the
`react_to_message` tool call the model can make on its own turn.

## R3 — Flip-not-stack de-duplication (depends on R1)

**Status**: ✅ CLOSED — confirmed live as part of R1 above (item 2: flipping 👀→✅ on the same
`idMessage` replaced rather than stacked).

**Decision**: no reaction-history bookkeeping of any kind. Because the fast-path's initial
in-flight emoji and any later `react_to_message("✅", message_id=<same id>)` call target the
identical `(chatId, idMessage)` pair, Green API's own flip semantics (now confirmed) naturally
replace rather than stack — so correctness here reduces entirely to always resolving and reusing
the *same* real message id for a given workflow, which is exactly why
`Message.whatsapp_id_message`/`Session.active_document_message_id` (see `data-model.md`) exist as
the single source of truth for that id, rather than re-deriving it at each call site.

**Rationale**: avoids inventing new persistent state (a reaction table) purely to solve a problem
Green API's own API already solves — consistent with this codebase's general preference for the
simplest storage that satisfies the requirement (compare Feature 054's explicit
SQLite-vs-JSON-file storage-rationale discussion).

**Alternatives considered**: tracking a local "last reaction sent per message" cache to explicitly
suppress a second, redundant identical send. Rejected as unnecessary complexity — now confirmed
unnecessary, since Green API reliably replaces.

## R4 — Self-reaction limitation (new finding from Gate Zero, non-blocking)

**Status**: ✅ CLOSED — documented constraint, not a blocker.

**Finding**: reacting to a message the bot's own account sent (as opposed to a message the user
sent) returns `200` but never renders in WhatsApp (see R1 item 4).

**Decision**: no code-level guard against this is needed. Every reaction use case in this feature
targets a message the *user* sent (a document, an action-request command, or whatever message
`Session.active_document_message_id`/the current turn's `whatsapp_id_message` resolves to — all
inbound). If a future feature ever wants to react to DeniDin's own sent message, that would need
its own investigation at that time; out of scope here.
