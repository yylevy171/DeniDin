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
  `notification.answer_with_interactive_buttons(response.response_text, buttons=[{"type":
  "reply", "buttonId": BUTTON_ID_APPROVE, "buttonText": "כן"}, {"type": "reply", "buttonId":
  BUTTON_ID_DECLINE, "buttonText": "לא"}])` — a convenience method the `whatsapp_chatbot_python`
  `Notification` class already provides (`manager/handler.py`, confirmed while building T005;
  resolves `chat_id` internally the same way `notification.answer` does, and delegates to the
  identical `sendInteractiveButtons` Green API call) — instead of `notification.answer(...)`.
  Its body carries the full existing `📋 לאישור:` text unchanged (well under the confirmed
  20000-char cap) — buttons change how the answer arrives, never what the question contains
  (spec.md Scope).
- On failure: **implementation correction (discovered while building T005, 2026-08-14)** — the
  original assumption here ("any exception from the `sendInteractiveButtons` call") was wrong.
  Reading `API.py` confirms `whatsapp_api_client_python`'s `GreenAPI` client is constructed with
  `raise_errors=False` throughout this codebase (never overridden) — both HTTP-status failures
  and network-level errors are caught internally and returned as a `Response` object
  (`code != 200`, `data` not a dict) rather than raised. This matches something already directly
  observed live, earlier the same day: Gate Zero's first `sendInteractiveButtons` attempt (missing
  `"type": "reply"`) came back as `code=400, data=None` with **no exception raised at all**. The
  correct (and only reliable) failure check is therefore **the returned `Response`'s own
  `code`/`data`**, not a `try`/`except` around the call (a defensive `except Exception` is kept
  around the call site regardless, purely for genuinely unexpected library bugs — never the
  primary detection mechanism). On a detected failure: logs the failure (`code`/`error`), then
  sends a **separate, plain-text error notice** via the existing `notification.answer(...)` path
  (`constants/error_messages.APPROVAL_BUTTONS_SEND_FAILED`) — per spec.md Clarifications
  ("surface an error", not a silent fallback). This notice is **not** the `📋 לאישור:` block
  itself — the user is told the prompt failed, not shown a degraded copy of it, since the
  model's approval details were never actually delivered in this failure case.
- When `response.offer_approval_buttons` is `False` (the overwhelming majority of turns):
  behavior is 100% unchanged — same `notification.answer(...)` call as today.

**`WhatsAppHandler` EXPECTS** (extended):
- `response.offer_approval_buttons` is only ever `True` when `response.should_reply` is also
  `True` and `response.response_text` is non-empty (already guaranteed by `AIResponse`'s own
  `__post_init__` invariant — no new validation needed here).
- `notification` exposes `answer_with_interactive_buttons` — already true (library-provided),
  confirmed by source read, delegating to the same `sending.sendInteractiveButtons` Green API
  call Gate Zero verified live.

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
