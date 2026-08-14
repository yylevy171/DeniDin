# Integration Contracts: Sending the Approval Buttons Message

**Feature**: 047-whatsapp-interactive-approval-buttons · Per METHODOLOGY.md §VII format.

---

### `denidin.py` ↔ `WhatsAppHandler` Contract (extension of existing `send_response` contract)

**`denidin.py` MUST**:
- Continue calling `whatsapp_handler.send_response(notification, ai_response)` exactly where it
  does today for every conversational turn — no new call site, no branching in `denidin.py`
  itself on `offer_approval_buttons` (that branching belongs inside `WhatsAppHandler`, which
  already owns every Green API send decision).
- After `send_response` returns, if `ai_response.offer_approval_buttons` was `True` **and** the
  send succeeded, call
  `ai_handler.pending_approval_manager.attach_sent_message_id(chat_id, returned_id_message)`
  with whatever `send_response` reports back (see return-value change below). If the send
  failed, do **not** call `attach_sent_message_id` — there is no `id_message` to attach, and the
  pending approval stays exactly as `set()` left it (`sent_message_id=None`), which already
  reads as "not yet resolvable by tap" per `pending-approval-message-binding.md`.

**`WhatsAppHandler` PROVIDES** (extended):
- `send_response(notification, response) -> Optional[str]` — **return type changes** from `None`
  to `Optional[str]`: the sent `idMessage` when `response.offer_approval_buttons` was `True` and
  the buttons send succeeded; `None` in every other case (plain-text sends, `should_reply=False`
  no-ops, or a failed buttons send — callers distinguish "no id because plain text" from "no id
  because it failed" the same way they always could, via whatever `send_response` already does
  on failure — see below). This is a superset of the existing contract; every existing caller
  that ignores the return value keeps working unchanged.
- When `response.offer_approval_buttons` is `True`: calls
  `notification.api.sending.sendInteractiveButtons(chatId=chat_id, body=response.response_text,
  buttons=[{"type": "reply", "buttonId": BUTTON_ID_APPROVE, "buttonText": "כן"},
  {"type": "reply", "buttonId": BUTTON_ID_DECLINE, "buttonText": "לא"}])` instead of
  `notification.answer(response.response_text)`. `body` carries the full existing
  `📋 לאישור:` text unchanged (well under the confirmed 20000-char cap) — buttons change how the
  answer arrives, never what the question contains (spec.md Scope).
- On failure (any exception from the `sendInteractiveButtons` call): logs the failure using the
  same categorized-by-status-code pattern `send_response` already applies to
  `requests.HTTPError`/`Timeout`/`ConnectionError`, then sends a **separate, plain-text error
  notice** via the existing `notification.answer(...)` path (e.g. "⚠️ לא הצלחתי לשלוח את בקשת
  האישור עם כפתורים. נסי לשלוח את הבקשה שוב.") — per spec.md Clarifications ("surface an error",
  not a silent fallback). This notice is **not** the `📋 לאישור:` block itself — the user is told
  the prompt failed, not shown a degraded copy of it, since the model's approval details were
  never actually delivered in this failure case.
- When `response.offer_approval_buttons` is `False` (the overwhelming majority of turns):
  behavior is 100% unchanged — same `notification.answer(...)` call as today.

**`WhatsAppHandler` EXPECTS** (extended):
- `response.offer_approval_buttons` is only ever `True` when `response.should_reply` is also
  `True` and `response.response_text` is non-empty (already guaranteed by `AIResponse`'s own
  `__post_init__` invariant — no new validation needed here).
- `notification.api` exposes `sending.sendInteractiveButtons` — already true, confirmed live via
  Gate Zero, same client object `notification.answer` itself delegates through.

---

### Why the error notice, not a silent fallback to text

Rejected: catching the `sendInteractiveButtons` failure and silently retrying with
`notification.answer(response.response_text)` (the plain `📋 לאישור:` block, no buttons) — this
was the "Recommended" option during `speckit.clarify` and was explicitly turned down in favor of
surfacing an error. The distinction that matters: a silent fallback would leave the user with a
seemingly-normal approval prompt and no signal that a real, but different, request (button
delivery) had failed — the human's stated concern was exactly that a failure here must be
visible, not masked by "well, the underlying approval question got through, just without
buttons."
