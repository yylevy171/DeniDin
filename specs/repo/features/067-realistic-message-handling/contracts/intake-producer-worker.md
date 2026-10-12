# Contract: producer / coordinator / worker

Replaces the 2026-08-30 producer-consumer contract.

## Producer — `DeniDinGreenAPIBot.run_forever` (only when `self.intake is not None`)
1. `receiveNotification()`; unusable/empty → `continue` (as today).
2. `on_notification_received(body)` read-receipt hook — errors logged, never fatal (as today).
3. Build `notification = Notification(body, send_api, state_manager)` (the source's separate send
   client — the worker's replies never use the poller's session). Only `incomingMessageReceived`
   webhooks are queued; other webhook types are ignored as today (no handlers are registered for
   them). `message = denidin.prestore(notification)` — for the message types whose handlers store at
   receipt, store exactly as the handler would (same content rules); other types: `None`.
   A store failure → log, **do not acknowledge**, `continue` (REQ-RMH-021).
4. `deleteNotification(receiptId)`.
5. `intake.submit(notification, message)`.
6. Any exception: log, `sleep(5.0)`, `continue` (as today).
With `intake is None` the loop is today's code, unchanged (player/tests).

## Coordinator
- `submit(notification, message)`: `chats.setdefault(chat_id, ChatIntake()).items.append((notification, message))`;
  `arrival.append(chat_id)`; `wake.set()`.
- `next_work_item()` (worker): `deferred` first; then the oldest chat id in `arrival` whose
  `bodies` is non-empty; media backlog item when that chat has nothing else queued; `None` if none.
  Waits on `wake` with a short timeout when empty and clears it only **before** a final re-check
  (R3: a body appended during the check is still seen).
- `drain_attachable(chat_id)` (worker, at a hand-back): pops all of that chat's `bodies`;
  text types from non-blocked senders → returned (already stored); media → noted, parked in
  `media_backlog`; everything else → `deferred`. Order preserved.

## Worker — `IntakeWorker` (knows nothing about Green API)
Constructed with the injected `dispatch(type_message, notification)` — the same callable the
message source's `start(dispatch)` already receives, and the player uses. Loop:
`item = coordinator.next_work_item()`; `denidin.preceived[idMessage] = item.message`; then
`dispatch(item.type_message, item.notification)` — the handler's `DeniDin.receive()` returns the
pre-stored message instead of storing again. Exception → log, `sleep(5)`, continue
(REQ-RMH-024). Never exits except on shutdown. It holds no HTTP client, router or session.

## Invariants
- At most one message is handled at a time (single worker) — REQ-RMH-023.
- Producer and worker share only the deques and the Event; sessions are touched only through
  the SessionManager actor (REQ-RMH-025/029). No locks.
- No body is dropped: bodies are removed from a deque only by the worker, and only into
  `receive()`, `deferred`, `media_backlog`, or `dispatch`.
