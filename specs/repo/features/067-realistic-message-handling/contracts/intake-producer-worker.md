# Contract: producer / coordinator / worker

Replaces the 2026-08-30 producer-consumer contract.

## Producer — `DeniDinGreenAPIBot.run_forever` (only when `self.intake is not None`)
1. `receiveNotification()`; unusable/empty → `continue` (as today).
2. `on_notification_received(body)` read-receipt hook — errors logged, never fatal (as today).
3. **Room check first:** if the chat's queue (or `arrival`) is full → raise `QueueLimitExceeded`
   (ERROR: queue, size, limit, message id), acknowledge, **drop without storing**, `continue`.
   Only the worker removes items, so a check by the single producer cannot be invalidated.
4. Build `notification = Notification(body, bot.api, state_manager)` (the existing bot client, as
   the router's handler does today). Only `incomingMessageReceived`
   webhooks are queued; other webhook types are ignored as today (no handlers are registered for
   them). `message = denidin.prestore(notification)` — for the message types whose handlers store at
   receipt, store exactly as the handler would (same content rules); other types: `None`.
   A store failure → log, **do not acknowledge**, `continue` (REQ-RMH-021).
5. `deleteNotification(receiptId)`.
6. `intake.submit(notification, message)`.
7. Any exception: log, `sleep(5.0)`, `continue` (as today).
With `intake is None` the loop is today's code, unchanged (player/tests).

## Coordinator
- `submit(notification, message)`: `chats.setdefault(chat_id, ChatIntake()).items.put_or_raise((notification, message))`;
  `arrival.put_or_raise(chat_id)`. A full queue raises `QueueLimitExceeded`: the producer logs ERROR, acknowledges and drops the item (REQ-RMH-033).
- `next_work_item()` (worker): `deferred` first; then `arrival.get(timeout)` → that chat's queue
  `get_nowait()` (`queue.Empty` = a stale id already drained at a hand-back: skip); media backlog
  item when that chat has nothing else queued; `None` on timeout.
- `drain_attachable(chat_id)` (worker, at a hand-back): `get_nowait()` until `queue.Empty` on that chat's queue;
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
- Producer and worker share only the bounded queues; sessions are touched only through
  the SessionManager actor (REQ-RMH-025/029). No locks.
- Nothing is dropped silently: an item leaves a queue only via the worker's `get`, and only into
  `deferred`, `media_backlog`, or `dispatch` — except a `QueueLimitExceeded` drop, which is always logged at ERROR and counted.
