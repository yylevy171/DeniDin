# Research: WhatsApp Reactions

## R1 — Green API reaction endpoint shape (Gate Zero, BLOCKING, live, human-approved)

**Status**: 🔴 OPEN — not run during planning. Per CLAUDE.md's "never start an environment or make
real external calls without approval" rule and CONSTITUTION's "NO UNVERIFIED THIRD-PARTY
ASSUMPTIONS" rule, this must be a real, human-approved, live-verified call against a real dev
WhatsApp number before the implementation below is trusted as correct — not merely inferred from
Green API's public documentation.

**Decision (pending live confirmation)**: call
`POST {host}/waInstance{idInstance}/sendMessageReaction/{apiTokenInstance}` with body
`{"chatId": "<chat>", "messageId": "<idMessage>", "reaction": "<emoji or empty string>"}`, via the
SDK's already-vendored `GreenApi.raw_request(method="POST", url=..., json=...)` escape hatch
(`API.py` lines ~165/181) — this method exists in the installed SDK today but has **zero call
sites anywhere in this codebase**, so both the endpoint shape and the mechanism for reaching it are
unverified in this specific integration, even though `raw_request` itself is a real, existing SDK
method (not something being invented).

**Rationale**: no wrapped `sendReaction`-style method exists anywhere in the installed
`whatsapp-api-client-python` package (`tools/sending.py` was inspected in full: `sendMessage`,
`sendButtons`, `sendTemplateButtons`, `sendListMessage`, `sendFileByUpload(Url)`, `uploadFile`,
`sendLocation`, `sendContact`, `sendLink`, `forwardMessages`, `sendPoll`,
`sendInteractiveButtons(Reply)` — no reaction support). `raw_request` is the SDK's documented
generic mechanism for calling any Green API REST endpoint the Python wrapper hasn't caught up to
yet, and is strongly preferred over hand-rolled `requests` calls (which would bypass the SDK's own
session/host/timeout configuration) or patching a new method onto the vendored `GreenApi`/`Sending`
classes (forbidden by CONSTITUTION §XVII).

**Alternatives considered**:
- Hand-rolled `requests.post(...)` directly against the endpoint, bypassing the SDK entirely.
  Rejected: duplicates host/token/timeout configuration already centralized in `bot.api`, and
  every other Green API call site in this codebase goes through the SDK.
- A subclass or monkey-patch adding a `sendReaction` method onto `Sending`. Rejected outright by
  CONSTITUTION §XVII (no monkey-patching, no runtime method injection).
- Upgrading the vendored SDK version in case a newer release wraps reactions natively. Not pursued
  for this plan — would be a separate, larger dependency-upgrade decision requiring its own review,
  and `raw_request` unblocks the feature without it.

**What Gate Zero must actually confirm, live, before implementation is trusted**:
1. The exact endpoint path and payload key names (`sendMessageReaction` vs. some other exact
   spelling; `reaction` vs. a different field name) — capture the real request Green API accepts
   and the real response it returns (status code + body shape), mirroring Feature 076's
   `capture_green_api_webhooks.py` precedent for evidence capture.
2. That an empty-string `reaction` clears an existing reaction (per the spec's own glossary, not
   yet independently confirmed).
3. That sending a second, different emoji to the same `(chatId, messageId)` pair **replaces** the
   existing reaction rather than stacking a second one — this "flip, not stack" assumption is load-
   bearing for the whole feature design (see `data-model.md`: no reaction-history table is planned
   specifically because of this assumption) and must not be treated as confirmed until verified.
4. Behavior when reacting to a message that has since been deleted by the sender — expected to
   surface as a 4xx-shaped failure (must NOT be retried, per the §XI policy) rather than a 5xx/
   timeout; confirm this classification is actually what Green API returns, not assumed.
5. That the same call works identically for both `@c.us` (1:1) and `@g.us` (group) chat ids.

**Note for whoever runs Gate Zero**: this is explicitly *not* something to execute as part of
planning or task-writing — it requires its own fresh, explicit human go-ahead when the time comes,
same as any other real external call against a live environment per CLAUDE.md.

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

**Decision**: no reaction-history bookkeeping of any kind. Because the fast-path's initial
in-flight emoji and any later `react_to_message("✅", message_id=<same id>)` call target the
identical `(chatId, messageId)` pair, Green API's own flip semantics (pending R1 confirmation)
naturally replace rather than stack — so correctness here reduces entirely to always resolving and
reusing the *same* real `messageId` for a given workflow, which is exactly why
`Message.whatsapp_id_message`/`Session.active_document_message_id` (see `data-model.md`) exist as
the single source of truth for that id, rather than re-deriving it at each call site.

**Rationale**: avoids inventing new persistent state (a reaction table) purely to solve a problem
Green API's own API already solves, if R1 confirms the assumption — consistent with this codebase's
general preference for the simplest storage that satisfies the requirement (compare Feature 054's
explicit SQLite-vs-JSON-file storage-rationale discussion).

**Alternatives considered**: tracking a local "last reaction sent per message" cache to explicitly
suppress a second, redundant identical send. Rejected as unnecessary complexity unless R1 reveals
Green API does *not* reliably replace (in which case this would need revisiting before
`speckit.tasks`, not silently designed around now).
