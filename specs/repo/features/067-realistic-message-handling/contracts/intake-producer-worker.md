# Contract: producer / coordinator / worker

Replaces the 2026-08-30 producer-consumer contract.

## Producer — `DeniDinGreenAPIBot.run_forever` (only when `self.intake is not None`)
1. `receiveNotification()`; unusable/empty → `continue` (as today).
2. `on_notification_received(body)` read-receipt hook — errors logged, never fatal (as today).
3. `intake.submit(body)`; then `deleteNotification(receiptId)` **immediately** (REQ-RMH-021).
4. Never parses beyond `senderData.chatId`/`messageData.typeMessage`; never touches sessions.
5. Any exception: log, `sleep(5.0)`, `continue` (as today).
With `intake is None` the loop is today's code, unchanged (player/tests).

## Coordinator
- `submit(body)`: `chats.setdefault(chat_id, ChatIntake()).bodies.append(body)`;
  `arrival.append(chat_id)`; `wake.set()`.
- `next_work_item()` (worker): `deferred` first; then the oldest chat id in `arrival` whose
  `bodies` is non-empty; media backlog item when that chat has nothing else queued; `None` if none.
  Waits on `wake` with a short timeout when empty and clears it only **before** a final re-check
  (R3: a body appended during the check is still seen).
- `drain_attachable(chat_id)` (worker, at a hand-back): pops all of that chat's `bodies`;
  text types from non-blocked senders → returned for `receive()`; media → received, noted,
  parked in `media_backlog`; everything else → `deferred`. Order preserved.

## Worker — `IntakeWorker`
Loop: `item = coordinator.next_work_item()`; `bot.router.route_event(item.body)` (pre-received
media: set `denidin.preceived[message_id]` first so the media path skips `receive`);
exception → log, `sleep(5)`, continue (REQ-RMH-024). Never exits except on shutdown.

## Invariants
- At most one exchange runs at a time (single worker) — REQ-RMH-023.
- Producer and worker share only the deques and the Event; no locks (REQ-RMH-025).
- No body is dropped: bodies are removed from a deque only by the worker, and only into
  `receive()`, `deferred`, `media_backlog`, or `route_event`.
