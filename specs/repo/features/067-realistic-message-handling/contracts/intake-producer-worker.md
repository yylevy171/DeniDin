# Contract: producer / coordinator / worker

Replaces the 2026-08-30 producer-consumer contract.

## Producer — `DeniDinGreenAPIBot.run_forever` (only when `self.intake is not None`)
1. `receiveNotification()`; unusable/empty → `continue` (as today).
2. `on_notification_received(body)` read-receipt hook — errors logged, never fatal (as today).
3. `message = denidin.prestore(notification)` — for the message types whose handlers store at
   receipt, store exactly as the handler would (same content rules); other types: `None`.
   A store failure → log, **do not acknowledge**, `continue` (REQ-RMH-021).
4. `deleteNotification(receiptId)`.
5. `intake.submit(body, message)`.
6. Any exception: log, `sleep(5.0)`, `continue` (as today).
With `intake is None` the loop is today's code, unchanged (player/tests).

## Coordinator
- `submit(body, message)`: `chats.setdefault(chat_id, ChatIntake()).bodies.append((body, message))`;
  `arrival.append(chat_id)`; `wake.set()`.
- `next_work_item()` (worker): `deferred` first; then the oldest chat id in `arrival` whose
  `bodies` is non-empty; media backlog item when that chat has nothing else queued; `None` if none.
  Waits on `wake` with a short timeout when empty and clears it only **before** a final re-check
  (R3: a body appended during the check is still seen).
- `drain_attachable(chat_id)` (worker, at a hand-back): pops all of that chat's `bodies`;
  text types from non-blocked senders → returned (already stored); media → noted, parked in
  `media_backlog`; everything else → `deferred`. Order preserved.

## Worker — `IntakeWorker`
Loop: `item = coordinator.next_work_item()`; sets `denidin.preceived[idMessage] = item.message`
then `worker_router.route_event(item.body)` — the handler's `DeniDin.receive()` returns the
pre-stored message instead of storing again. The worker's router/bot uses **its own** Green API
client (REQ-RMH-032);
exception → log, `sleep(5)`, continue (REQ-RMH-024). Never exits except on shutdown.

## Invariants
- At most one exchange runs at a time (single worker) — REQ-RMH-023.
- Producer and worker share only the deques and the Event; sessions are touched only through
  the SessionManager actor (REQ-RMH-025/029). No locks.
- No body is dropped: bodies are removed from a deque only by the worker, and only into
  `receive()`, `deferred`, `media_backlog`, or `route_event`.
