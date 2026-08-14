# Integration Contracts: Button Tap Routing & Resolution

**Feature**: 047-whatsapp-interactive-approval-buttons · Per METHODOLOGY.md §VII format.

---

### `denidin.py` (router) ↔ `AIHandler` Contract (new)

**`denidin.py` MUST**:
- Register the new handler as
  `@bot.router.message(type_message="interactiveButtonsResponse")` — **not**
  `@bot.router.buttons(...)`. Confirmed via source read (research.md): the library's own
  `router.buttons`/`ButtonObserver` only matches the older, deprecated
  `buttonsResponseMessage`/`templateButtonsReplyMessage`/`listResponseMessage` types, never the
  type Gate Zero actually observed live from `sendInteractiveButtons`. A handler registered the
  wrong way would silently never fire — this is not a stylistic choice, it's the only mechanism
  that reaches this feature's real traffic at all.
- In the new handler, extract from `notification.event` (the raw dict, same access pattern
  `handle_unsupported_message_default` already uses):
  - `chat_id = notification.event["senderData"]["chatId"]`
  - `selected_id = notification.event["messageData"]["interactiveButtonsResponse"]["selectedId"]`
  - `stanza_id = notification.event["messageData"]["interactiveButtonsResponse"]["stanzaId"]`
  - `chat_id`/`message_id`/`user_phone`/`sender` all resolved via
    `WhatsAppMessage.from_notification(notification)` (same machinery `handle_media_message`
    already uses for a non-text message type — its shared `senderData`-based extraction works
    unchanged for `interactiveButtonsResponse` too, confirmed against the real captured
    payload): `message.chat_id`, `message.message_id` (**this app's own synthetic UUID**, not
    the raw Green API `idMessage` — matches exactly what a typed reply's `AIRequest.message_id`
    already carries, for consistency), `message.sender_id` (real phone/JID, for RBAC), and
    `message.sender_display_name` (Feature 039's resolution chain, for persistence/logging
    only). The tap's *effect* is otherwise determined solely by
    `chat_id`/`selected_id`/`stanza_id` (RBAC for who's *allowed* to approve is out of scope for
    this feature — Gate Zero item 4 established correct per-tapper attribution is available, but
    this feature doesn't add a new permission check beyond what already gates the underlying MCP
    tool).
- Call
  `ai_handler.resolve_button_tap(chat_id, selected_id, stanza_id, message_id, user_phone, sender)`.
- If the result is `None` (stale tap, or a genuinely absent pending approval): send nothing —
  no call to `send_response`, no call to `notification.answer`. This is the literal
  implementation of spec.md's "silently ignore."
- If the result is a real `AIResponse`: pass it to `whatsapp_handler.send_response(...)` exactly
  like any other turn's response.
- If `denidin_app is None` (not yet initialized): same `_handle_not_initialized_error` pattern
  every other handler already uses.

**`AIHandler` PROVIDES** (new):
- `resolve_button_tap(chat_id, selected_id, stanza_id, message_id, user_phone, sender) ->
  Optional[AIResponse]` — per data-model.md. Internally: looks up
  `pending = pending_approval_manager.get(chat_id)` (only if RBAC resolved a non-blocked
  `user_obj` from `user_phone` — same precondition `get_response` already applies to the typed
  path); returns `None` immediately if `pending is None` or `pending.sent_message_id !=
  stanza_id` (stale — see `pending-approval-message-binding.md`).
- **Implementation simplification, found while building this (2026-08-14)**: rather than
  reimplementing `_call_openai_approval_api`'s duplicate-execution guards a second time,
  `resolve_button_tap` synthesizes a plain `AIRequest` with `user_prompt="כן"` (if
  `selected_id == BUTTON_ID_APPROVE`) or `"לא"` (otherwise) and **delegates to the existing
  `get_response`/`_resolve_pending_approval` pipeline verbatim** — genuinely zero duplicated
  approve/decline logic, not just guard-reuse. This also means a button decline inherits
  `_resolve_pending_approval`'s exact existing behavior: it declines, then **falls through to a
  fresh conversational turn** processing `"לא"` as a new message — identical, byte-for-byte, to
  what a genuine typed `לא` already produces today. This was a deliberate choice over hand-writing
  a bespoke "cancelled" confirmation: it guarantees button-decline and text-decline can never
  drift apart in behavior, satisfying US2's non-interference requirement by construction rather
  than by parallel-but-separate implementation. `resolve_button_tap` itself never calls
  `_is_affirmative_reply` on anything (that function parses free text; the synthesized `"כן"`/`"לא"`
  strings are fixed constants chosen because they're unambiguously in/out of its whitelist, not
  parsed values) — the staleness decision is made entirely beforehand, by `stanza_id`, before any
  free-text-shaped value is ever constructed.
- Logs the approval mechanism distinguishably from a typed reply *before* delegating — e.g.
  `logger.info(f"[047] Resolving pending approval via BUTTON TAP for chat={chat_id!r}, "
  f"tool={pending.tool_name!r}, selected_id={selected_id!r}, approve={approve}")`, alongside the
  existing `[022]`-prefixed resolution logging `_call_openai_approval_api`/
  `_resolve_pending_approval` already emit — satisfies spec.md Clarifications' audit requirement
  via `denidin-app`-side logging (see plan.md's Constitution Check note on why this doesn't
  extend into `apps/morning-mcp-app`'s own audit trail).

**`AIHandler` EXPECTS**:
- `selected_id` is one of the two known constants (`BUTTON_ID_APPROVE`/`BUTTON_ID_DECLINE`) —
  any other value is treated the same as `BUTTON_ID_DECLINE` (`approve = selected_id ==
  BUTTON_ID_APPROVE`, so anything else takes the decline/fresh-turn path — never silently
  ignored *once a live match on `stanza_id` has already established this is a real, current
  tap*; staleness is decided first, by `stanza_id`, and only then does `selected_id` decide
  approve vs. decline).
- `chat_id`/`stanza_id`/`message_id` are non-empty strings, per the always-present shape
  confirmed in every captured Gate Zero payload.

---

### Ordering with the existing free-text resolution path

No conflict: `resolve_button_tap` and `_resolve_pending_approval` are two independent entry
points into the same `PendingApprovalManager` state, reached via different router dispatches
(`interactiveButtonsResponse` vs. `textMessage`/`extendedTextMessage`). Whichever one runs first
calls `pending_approval_manager.clear(chat_id)`, so a race between "user taps" and "user also
types כן in the same moment" resolves on a first-write-wins basis — identical in spirit to the
existing risk of two rapid typed replies, not a new category of race this feature introduces.
