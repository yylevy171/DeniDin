# Contract: Producer / Consumer Split (live source only)

**Feature**: `feature/067-realistic-message-handling`
**Components**: `src/utils/green_api_bot.py` (`DeniDinGreenAPIBot`), `src/sources/green_api_source.py`
(`GreenAPIMessageSource`), `src/sources/intake_coordinator.py` (NEW), `denidin.py` (`__main__`)

---

## Scope

This machinery exists **only** behind the live Green API source. `PlayerExportSource` and the
`MessageSource.start(dispatch)` contract are untouched and remain synchronous (REQ-RMH-022,
IT-5). `dispatch_notification` and every handler keep their current signatures and synchronous
behaviour — the coordinator sits strictly upstream of `dispatch_notification`.

---

## Flag OFF (default) — byte-for-byte current behaviour

- `denidin.py __main__` reads `config.feature_flags.realistic_message_handling` → `False`.
- `GreenAPIMessageSource(...)` is constructed with `realistic_message_handling=False`,
  `intake_coordinator=None`.
- `GreenAPIMessageSource.start(dispatch)` sets `bot.realistic_message_handling = False` and does
  NOT set `bot.intake_coordinator`, then calls `bot.run_forever()` exactly as today.
- `DeniDinGreenAPIBot.run_forever()` executes its **current body verbatim**
  (`green_api_bot.py:169-200`): poll → `_notification_data_or_none` → read-receipt hook →
  `router.route_event(body)` → `deleteNotification(receiptId)`, one at a time, `KeyboardInterrupt`
  breaks, `except Exception` logs + sleeps 5s + continues.
- No `IntakeCoordinator` is constructed anywhere. No thread is spawned. (REQ-RMH-021)

## Flag ON

- `denidin.py __main__` reads the flag → `True`, constructs `IntakeCoordinator()`, passes it and
  the flag into `GreenAPIMessageSource(..., realistic_message_handling=True,
  intake_coordinator=coordinator)`.
- `GreenAPIMessageSource.start(dispatch)` — after `connect()` and the existing per-type
  `_register` / `_register_catch_all` / read-receipt-hook wiring — additionally sets
  `bot.realistic_message_handling = True` and `bot.intake_coordinator = self._intake_coordinator`,
  then calls `bot.run_forever()`.
- `DeniDinGreenAPIBot.run_forever()` branches at the top:
  `if not getattr(self, "realistic_message_handling", False): <current body>; return` — otherwise
  it runs the producer/consumer body below.

### `run_forever()` ON body

```
producer = threading.Thread(target=self._produce_forever, name="denidin-producer", daemon=True)
producer.start()
try:
    self._consume_forever()          # blocks on the main thread → KeyboardInterrupt still works
finally:
    self._shutdown.set()             # threading.Event; producer checks it each loop
```

### `_produce_forever()` (daemon thread)

Mirrors the current poll loop, minus `route_event`:

```
self.api.session.headers["Connection"] = "keep-alive"
while not self._shutdown.is_set():
    try:
        response = self.api.receiving.receiveNotification()
        data = _notification_data_or_none(response.data)
        if data is None:
            continue
        body = data["body"]
        hook = getattr(self, "on_notification_received", None)
        if hook is not None:
            try: hook(body)
            except Exception as e: self.logger.log(logging.ERROR, e)     # unchanged posture
        self.api.receiving.deleteNotification(data["receiptId"])          # ACK IMMEDIATELY (D3)
        self.intake_coordinator.submit(body)
    except Exception as error:
        self.logger.log(logging.ERROR, error)
        time.sleep(5.0)
        continue
```

- **Ack ordering (REQ-RMH-021a)**: `deleteNotification` is called **before** `submit`, and
  `submit` never blocks on a turn. The read-receipt hook still fires first (unchanged).
- The producer NEVER calls `route_event` / `dispatch` / any handler.

### `_consume_forever()` (blocking, main thread)

```
while not self._shutdown.is_set():
    try:
        item = self.intake_coordinator.next_work_item(timeout=1.0)
        if item is None:
            continue
        chat_id = _chat_id_of(item.reply_to)
        if item.kind == "text":
            turn = ActiveTurn(chat_id=chat_id, cancelled=threading.Event(),
                              trigger_notifications=item.notifications, started_at=now_local())
            self.intake_coordinator.mark_turn_active(chat_id, turn)
        self._dispatch(item)                         # → today's dispatch_notification path
    except KeyboardInterrupt:
        break
    except Exception as error:
        self.logger.log(logging.ERROR, error)        # REQ-RMH-024 — mirror the live loop
        time.sleep(5.0)
        continue
```

- `self._dispatch(item)` routes by `item.kind`:
  - `"text"` → the merged conversational path (`contracts/turn-cancellation.md` +
    `contracts/journal-delivery.md`): build one `AIRequest` with `user_prompt=item.combined_text`
    and `system_note` assembled from `item.carryover`, hand `cancel_check =
    coordinator.cancel_check_for(chat_id)` into `get_response`, persist each of
    `item.notifications` as its own user entry, send at most one reply to `item.reply_to`.
  - `"media"` → today's `_process_media_message` on `item.reply_to`, unchanged. Never merged,
    never interrupts an active text turn.
  - `"button"` → today's `handle_button_tap` on `item.reply_to`, unchanged.
  - `"other"` → today's `HANDLER_REGISTRY.get(type, CATCH_ALL_HANDLER)` path, unchanged.
- After the dispatch returns (reply sent, silent turn, or error fallback sent), the consumer
  calls `coordinator.on_turn_finished(chat_id)` — the **reset** (REQ-RMH-016). On a `cancelled`
  `AIResponse` it first calls `coordinator.record_side_effects(chat_id, response.side_effects_journal)`
  and does NOT send or persist an assistant reply, then loops (the merged item is already queued
  via `pending_text`).

---

## `IntakeCoordinator` API (authoritative signatures)

```python
class IntakeCoordinator:
    def submit(self, raw_body: dict) -> None: ...
    def next_work_item(self, timeout: float) -> Optional[WorkItem]: ...
    def mark_turn_active(self, chat_id: str, turn: ActiveTurn) -> None: ...
    def record_side_effects(self, chat_id: str, records: list) -> None: ...
    def on_turn_finished(self, chat_id: str) -> None: ...
    def cancel_check_for(self, chat_id: str) -> Callable[[], bool]: ...
```

State transitions and the classify/merge rules: see `data-model.md`.

---

## Concurrency guarantees

- **Single producer, single consumer.** No third thread touches coordinator state.
- **No `Lock` / `queue.Queue`** (REQ-RMH-025). `collections.deque` + `threading.Event` +
  per-key dict/list ops only. Every shared access and its accepted outcome: `research.md` D2.
- **At most one turn per chat** (REQ-RMH-023) — the consumer is serial; `active_turn[chat_id]`
  gates re-entry.
- **Shutdown**: `KeyboardInterrupt` on the main thread breaks `_consume_forever`; the `finally`
  sets `self._shutdown`; the daemon producer sees it next loop (and is daemon anyway, so process
  exit does not hang).

---

## Immutability constraints (tests that must stay green untouched)

- `tests/integration/test_denidin_dispatch.py::TestHandlerRegistryCompleteness` — `HANDLER_REGISTRY`
  stays exactly 8 message types (IT-6).
- `tests/integration/test_message_source.py` — `PlayerExportSource.start(dispatch)` still invokes
  `dispatch` once per notification, synchronously, in order (IT-5). Existing assertions unchanged;
  one new assertion added for explicitness is allowed (it does not rewrite an existing test).
