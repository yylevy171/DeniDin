# Integration Contracts: Pending-Approval Message Binding

**Feature**: 047-whatsapp-interactive-approval-buttons · Per METHODOLOGY.md §VII format.

---

### `AIHandler` ↔ `PendingApprovalManager` Contract (extension of existing contract)

**`AIHandler` MUST**:
- Continue calling `pending_approval_manager.set(chat_id, new_pending)` at the exact point it
  does today (`ai_handler.py` ~line 1591-1599, when an `mcp_approval_request` appears in the
  OpenAI response) — `new_pending.sent_message_id` is `None` at this point, since the WhatsApp
  message carrying the buttons has not been sent yet (that happens later, in
  `WhatsAppHandler`/`denidin.py` — see `whatsapp-buttons-send.md`). `AIHandler` does not send
  WhatsApp messages itself and must not start doing so for this feature.
- Set `AIResponse.offer_approval_buttons = True` on the same response, at the same point.
- When resolving a tap (`resolve_button_tap`, see `button-tap-resolution.md`), treat a pending
  approval as **live and resolvable** only if `pending.sent_message_id == stanza_id`. Any other
  case (`pending is None`, or `pending.sent_message_id` is `None` or differs from `stanza_id`)
  MUST be treated as stale and MUST NOT call `_call_openai_approval_api` or clear/mutate the
  pending approval in any way — per spec.md Clarifications, a stale tap does nothing observable
  at all, including no reply.

**`PendingApprovalManager` PROVIDES**:
- `get(chat_id) -> Optional[PendingApproval]` — unchanged.
- `set(chat_id, approval)` — unchanged; `approval.sent_message_id` may legitimately be `None`
  at the time of this call (see above).
- `attach_sent_message_id(chat_id: str, id_message: str) -> None` — **NEW**. Updates the
  currently-pending approval's `sent_message_id` in place, if one still exists for `chat_id`.
  Never raises. If the pending approval was already resolved/cleared/replaced before this call
  arrives (a real possible race — e.g. an unusually fast text reply beating the send's own
  response), this is a silent no-op (logged at `info`), not an error: whatever it would have
  attached to no longer matters.
- `clear(chat_id)` — unchanged; clearing also discards `sent_message_id` (the whole record is
  removed, nothing to preserve).

**`PendingApprovalManager` EXPECTS**:
- `id_message` passed to `attach_sent_message_id` is a real WhatsApp `idMessage` string, exactly
  as returned by `sendInteractiveButtons` (`result.data["idMessage"]`, confirmed shape via Gate
  Zero) — never a display value, never fabricated.
- Callers never write directly to `PendingApproval.sent_message_id` — always through
  `attach_sent_message_id`, so the manager's own logging stays the single source of truth for
  "when did this pending approval last change."

---

### Why this is two calls, not one

`AIHandler.get_response` (where the pending approval is created) has no reference to
`notification`/the Green API client — it only builds `response_text` and returns an
`AIResponse`; the actual send happens later, in `denidin.py`'s existing turn-processing glue,
via `WhatsAppHandler`. Collapsing this into a single call would require either giving
`AIHandler` a WhatsApp-sending capability it doesn't have today (breaks the existing
`AIHandler`/`WhatsAppHandler` layering) or moving pending-approval creation *after* the send
(would require restructuring how `_finalize_response` builds `response_text`, since the
`📋 לאישור:` details block — including the `sent_message_id`-free version of it — must exist
*before* it can be sent). Two calls at existing seams is the smaller change.
