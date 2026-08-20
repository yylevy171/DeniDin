# Research: WhatsApp Reply/Quote Reference Resolution

**Feature**: 032-whatsapp-reply-reference-resolution
**Phase**: 0 (Outline & Research)

All decisions below were reached by reading actual code (`apps/denidin-app/src/`) and the
existing Green API contract doc (`specs/done/v0.0.1/001-whatsapp-chatbot-passthrough/contracts/green-api.md`),
not assumed.

## Decision 1: Feature flag or not?

**Decision**: No feature flag. Ship as always-on, additive behavior.

**Rationale**: `idMessage`/`stanzaId` capture and resolution are purely additive — a message
with no `quotedMessage` (the overwhelming majority) is completely unaffected (US2). There is
no existing behavior this could regress for non-reply messages, and CLAUDE.md's feature-flag
guidance exists for changes where the disabled path must stay byte-for-byte identical to
today — here "disabled" and "no reply present" are already the same code path. A flag would
add surface area with no real toggle-able behavior behind it.

**Alternatives considered**: `config.feature_flags.enable_reply_resolution` — rejected as
unnecessary ceremony per the above; revisit only if `speckit.tasks`/review surfaces a real
rollout risk (e.g. if index-building on startup for existing sessions is expensive — see
Decision 3).

## Decision 2: Capturing `idMessage` for outgoing (DeniDin-sent) messages

**Decision**: Capture incoming `idMessage` first (trivial, unblocks the actual motivating
scenario); treat outgoing `idMessage` capture as a fast-follow within the same feature, gated
on confirming `notification.answer()` (in `WhatsAppHandler._send_with_retry`,
`whatsapp_handler.py:140`) surfaces the Green API `sendMessage` response body (which contract
docs confirm includes `{"idMessage": "..."}`, `green-api.md:151-157`).

**Rationale**: The real-world motivating example (spec.md Problem Statement) is a lawyer
replying to their **own earlier message** — i.e. an incoming message DeniDin received, not
one it sent. `event['idMessage']` is already present at the top level of every incoming
notification body (`green-api.md:51`, sibling to `senderData`/`messageData`), so capturing it
requires zero new Green API interaction — just reading a field `WhatsAppMessage.from_notification`
currently ignores. Capturing outgoing `idMessage` (so a reply to *DeniDin's own* message also
resolves) requires reading `notification.answer()`'s return value, which is currently
discarded (`whatsapp_handler.py:150`, `self._send_with_retry(notification, response.response_text)`
— no return captured). Whether `notification.answer()` (from the `whatsapp-chatbot-python`
library) returns the raw HTTP response body is not yet confirmed by reading vendored library
source (not available in this environment) — **verify during `speckit.tasks`/implementation**,
not blocking for `plan.md`.

**Fallback if unconfirmed**: If `notification.answer()`'s return value turns out not to expose
`idMessage` cheaply, outgoing-message capture can be deferred to a fast-follow without
weakening US1's P1 scenario, since that scenario only needs incoming-message resolution.

**Alternatives considered**: Making a second `sendMessage`-adjacent Green API call just to
fetch the sent message's `idMessage` — rejected, unnecessary extra network round-trip when the
`sendMessage` response likely already contains it.

## Decision 3: Lookup index design

**Decision**: An in-memory `dict[str, str]` (`idMessage` → `message_id`) built per-`Session`,
alongside `SessionManager`'s existing `chat_to_session` in-memory index
(`session_manager.py:85`), populated as messages are added (`add_message`,
`session_manager.py:130`) and rebuilt from a session's existing `message_ids` on load (mirrors
how `chat_to_session` itself is rebuilt from disk, `session_manager.py:333`).

**Rationale**: `Session` is already strictly 1:1 with `whatsapp_chat`
(`session_manager.py:47`, `get_session`/`get_or_create_session` keyed by chat), so an
index scoped to a `Session` is automatically scoped per chat/group — satisfying Q11 (per-chat
scoping) with no extra participant-matching logic needed. Scoping resolution to "the active
session only" (Q10) means the index never needs to span archived sessions, keeping it small
(bounded by one session's message count, already bounded by the existing token-limit-driven
pruning in `add_message_with_token_limit`, `session_manager.py:609`) and cheap to rebuild on
load.

**Alternatives considered**: A single global `idMessage` → `(session_id, message_id)` index
across all sessions — rejected: actively works against Q11's per-chat scoping requirement
(would need extra filtering to re-derive chat scoping) and Q10's active-session-only scoping
(would need pruning logic to drop entries for expired sessions, duplicating what session
expiry/archival already does).

## Decision 4: Where resolved-reference context is injected into the AI prompt

**Decision**: Append to the `constitution` string inside `AIHandler.create_ai_request`
(`ai_handler.py:634-680`), in the same position and using the same pattern as recalled
long-term memories (`memory_context`, `ai_handler.py:668-672`: computed, then
`constitution += memory_context`) — i.e. after the constitution's stable prefix but before
`_build_instructions` appends the `---` + current-date suffix (`ai_handler.py:790`).

**Rationale**: This is literally the same pattern the codebase already uses for the only
other per-call-dynamic prompt content today (recalled memories), and CLAUDE.md is explicit
that anything per-call-dynamic must come after the constitution's stable prefix to preserve
OpenAI's automatic prompt-caching (`ai_handler.py:363-368`'s comment, CLAUDE.md's Key
Components section). Reusing the exact same insertion point means no new reasoning is needed
about cache-prefix stability — it inherits the property that's already been verified for
`memory_context`.

**Alternatives considered**: A separate system message / new Responses API content block —
rejected, more surface area for no benefit; the existing single-string-append pattern already
does the job and keeps this feature's footprint minimal.

## Decision 5: Media message resolution (full extracted text, no raw bytes)

**Decision**: Confirmed via spec Q9 — resolved reference for a media message
(`imageMessage`/`documentMessage` processed by `MediaHandler`/an extractor) carries that
message's stored `extracted_text`/`document_analysis` in full. This requires those fields to
already be persisted on the `Message` record for a media message, which needs verifying
against current `MediaHandler`/`Message` wiring at `speckit.tasks` time — if extraction output
isn't currently persisted onto the `Message` object itself (only used transiently to build the
AI response), storing it there is in scope for this feature's data-model change, not a
separate feature.

**Rationale**: See spec.md's Q9 resolution — raw media bytes are excluded for cost/latency
and prompt-size reasons; the extracted text itself must never be re-clipped or re-summarized
by this feature since that data was already validated at ingestion time.
