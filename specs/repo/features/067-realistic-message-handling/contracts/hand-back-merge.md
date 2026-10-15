# Contract: hand-back merge (backbone → model)

## When
In `Backbone._run_resolution_loop`, after a round's tool calls have run and the loop would send a
follow-up `responses.create`. **Not** on a round that produced `send_to_user` /
`approval_with_yes_no_buttons` (its reply is sent as is), and **not** while handling a message where
`_turn_is_approved_write` is true (REQ-RMH-014).

## Steps
1. `pending = denidin.receive_pending(chat_id)` (None-guarded → `[]` when no coordinator, e.g. the
   player) — the attachable messages the poller already stored individually (REQ-RMH-005).
2. `last_output_at` = when the previous model response returned.
3. Build one user input item per pending message, appended **after** the `function_call_output`
   items: `input = outputs + pending_items`.
4. Re-fire the typing indicator if any item was attached.
5. Call `responses.create` with `previous_response_id` as today. *(V1: confirm the API accepts
   user items beside function_call_output; fallback in plan Phase 0.)*

## Item text
```
[USER MESSAGE · 14:32:05 02/10 · sent before your last output]     # or: ... · sent after your last output
<message text>
```
Group chats keep the existing `[sender name]` prefix inside the text. Media:
```
[FILE RECEIVED · 14:32:07 02/10 · sent after your last output · <filename>] <caption>
(the file will be analyzed separately after you finish the current request)
```
Timestamps are the stored Israel-local message timestamps. "before" = `sent_at < last_output_at`.
The first round of handling a message uses the same timestamp prefix on history items (D13).

## Model rules (`backbone.md`, D10)
Messages marked "before" were typed while you were still working on your last output — treat them
as context for it; "after" ones arrived later. Combine them as one conversation. If the order or
intent is confusing, ask. Finish a pending approval before starting the next request. A short
reply answers the most recent pending question in the same context.
