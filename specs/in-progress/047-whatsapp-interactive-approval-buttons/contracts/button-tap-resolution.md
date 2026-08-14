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
  - `sender`/`recipient` resolved the same way every other handler resolves them today (Feature
    039's display-name resolution chain), for audit logging only — the tap's *effect* is
    determined solely by `chat_id`/`selected_id`/`stanza_id`, never by who sent it (RBAC for
    who's *allowed* to approve is out of scope for this feature — Gate Zero item 4 established
    correct per-tapper attribution is available, but this feature doesn't add a new permission
    check beyond what already gates the underlying MCP tool).
- Call `ai_handler.resolve_button_tap(chat_id, selected_id, stanza_id, sender, recipient)`.
- If the result is `None` (stale tap, or a genuinely absent pending approval): send nothing —
  no call to `send_response`, no call to `notification.answer`. This is the literal
  implementation of spec.md's "silently ignore."
- If the result is a real `AIResponse`: pass it to `whatsapp_handler.send_response(...)` exactly
  like any other turn's response (this response's `offer_approval_buttons` is always `False` —
  a resolution reply is plain text, e.g. the same confirmation text `_resolve_pending_approval`
  already produces for a typed `כן`).
- If `denidin_app is None` (not yet initialized): same `_handle_not_initialized_error` pattern
  every other handler already uses.

**`AIHandler` PROVIDES** (new):
- `resolve_button_tap(chat_id, selected_id, stanza_id, sender, recipient) -> Optional[AIResponse]`
  — per data-model.md. Internally: looks up `pending = pending_approval_manager.get(chat_id)`;
  returns `None` immediately if `pending is None` or `pending.sent_message_id != stanza_id`
  (stale — see `pending-approval-message-binding.md`). Otherwise resolves via the same
  `_call_openai_approval_api`/duplicate-execution-guard logic
  `_resolve_pending_approval` already uses, branching on `selected_id == BUTTON_ID_APPROVE`
  (approve) vs. anything else, i.e. `BUTTON_ID_DECLINE` (decline) — **never** via
  `_is_affirmative_reply` (that function parses free text; a button's `selected_id` is already
  an unambiguous, closed value by construction, so applying word-matching to it would be a
  regression, not a simplification).
- Logs the approval mechanism distinguishably from a typed reply — e.g.
  `logger.info(f"[047] Pending approval resolved via BUTTON TAP for chat={chat_id!r}, "
  f"tool={pending.tool_name!r}, selected_id={selected_id!r}")`, alongside the existing
  `[022]`-prefixed resolution logging `_call_openai_approval_api`/`_resolve_pending_approval`
  already emit — satisfies spec.md Clarifications' audit requirement via `denidin-app`-side
  logging (see plan.md's Constitution Check note on why this doesn't extend into
  `apps/morning-mcp-app`'s own audit trail).

**`AIHandler` EXPECTS**:
- `selected_id` is one of the two known constants (`BUTTON_ID_APPROVE`/`BUTTON_ID_DECLINE`) —
  any other value (a malformed/unexpected payload) is treated the same as `BUTTON_ID_DECLINE`
  (the existing `_resolve_pending_approval` precedent: anything not affirmatively recognized is
  a decline, never silently ignored *once a live match on `stanza_id` has already established
  this is a real, current tap* — staleness is decided first, by `stanza_id`, and only then does
  `selected_id` decide approve vs. decline).
- `chat_id`/`stanza_id` are non-empty strings, per the always-present shape confirmed in every
  captured Gate Zero payload.

---

### Ordering with the existing free-text resolution path

No conflict: `resolve_button_tap` and `_resolve_pending_approval` are two independent entry
points into the same `PendingApprovalManager` state, reached via different router dispatches
(`interactiveButtonsResponse` vs. `textMessage`/`extendedTextMessage`). Whichever one runs first
calls `pending_approval_manager.clear(chat_id)`, so a race between "user taps" and "user also
types כן in the same moment" resolves on a first-write-wins basis — identical in spirit to the
existing risk of two rapid typed replies, not a new category of race this feature introduces.
