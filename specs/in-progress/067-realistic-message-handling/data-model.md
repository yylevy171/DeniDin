# Phase 1 Data Model: Realistic Message Handling — Multiple Interfering Messages

**Feature**: `feature/067-realistic-message-handling` · **Date**: 2026-08-30

No persistent storage. Everything here is in-memory, per-process, per-`chat_id`, rebuilt empty on
restart — the same lifetime and justification as `GroupMembershipResolver._cache` and
`RecentNotificationDeduper`. Two existing dataclasses gain optional, defaulted fields.

---

## In-memory state: `IntakeCoordinator` (`src/sources/intake_coordinator.py`)

Constructed only when `config.feature_flags.realistic_message_handling` is `true`. Owns all
burst/merge/journal state. No AI, WhatsApp, or persistence imports — pure state + `threading.Event`
+ `collections.deque`.

### Fields

| Field | Type | Meaning |
|---|---|---|
| `_work` | `collections.deque[WorkItem]` | producer→consumer handoff; producer `.append`, consumer `.popleft` |
| `_wake` | `threading.Event` | producer `.set()`s it after every `.append`; consumer waits on it (with timeout) when `_work` is empty |
| `pending_text` | `Dict[str, List[RawNotification]]` | per chat: text notifications received but not yet folded into a turn (the **burst buffer**) |
| `active_turn` | `Dict[str, ActiveTurn]` | per chat: the currently-running turn's handle, or key absent if no turn in flight |
| `carryover` | `Dict[str, List[SideEffectRecord]]` | per chat: the "already done" journal from a discarded turn, awaiting the next merged turn |

### `ActiveTurn` (per in-flight turn)

| Field | Type | Meaning |
|---|---|---|
| `chat_id` | `str` | the chat this turn serves |
| `cancelled` | `threading.Event` | one-way flag; producer `.set()`s it when an interfering text arrives; the turn thread reads `.is_set()` at round boundaries |
| `trigger_notifications` | `List[RawNotification]` | the ordered burst messages this turn is answering (≥1) |
| `started_at` | `datetime` (`now_local()`) | diagnostic only |

**Rules**:
- `active_turn[chat_id]` is set by the consumer the instant it pulls a work item for that chat,
  and removed by `on_turn_finished(chat_id)`.
- `cancelled` is never cleared or reused — a new turn gets a fresh `ActiveTurn` with a fresh
  `Event`.
- At most one `ActiveTurn` per `chat_id` at any time (REQ-RMH-023).

### `WorkItem` (a unit of work for the consumer)

| Field | Type | Meaning |
|---|---|---|
| `kind` | `"text"` \| `"media"` \| `"button"` \| `"other"` | routing category, decided by the producer from `typeMessage` |
| `notifications` | `List[RawNotification]` | for `kind="text"`: the ordered burst (1..N). For everything else: exactly 1 |
| `reply_to` | `RawNotification` | the notification `send_response` answers / button ids attach to — the **last** of `notifications` |
| `combined_text` | `Optional[str]` | for `kind="text"`: every notification's text, newline-joined in arrival order. `None` otherwise |
| `carryover` | `List[SideEffectRecord]` | the "already done" journal to hand this turn (empty unless this is a merged turn following a discard) |

**Rules**:
- Only `kind="text"` items are ever merged / can carry >1 notification or a `carryover`.
- `kind in {"media","button","other"}` items are always single-notification, `combined_text=None`,
  `carryover=[]`, and are enqueued immediately without touching `active_turn` (they do **not**
  interrupt an in-flight text turn — REQ-RMH-018/019).

### `SideEffectRecord` (one "already done" item)

| Field | Type | Meaning |
|---|---|---|
| `source` | `"mcp"` \| `"ledger"` | where the side effect happened |
| `tool_name` | `str` | e.g. `"create_receipt"`, `"capture_ledger_event"` |
| `identifier` | `Optional[str]` | Morning document number, or ledger `event_id` |
| `summary_he` | `str` | one Hebrew line for the journal, built from structured fields — never free model text |
| `raw` | `Dict` | the underlying `mcp_call` output item or the persisted ledger event dict, for debugging/logging only |

---

## `IntakeCoordinator` public API (contract in `contracts/producer-consumer.md`)

| Method | Called by | Behaviour |
|---|---|---|
| `submit(raw_body: dict) -> None` | producer thread | classify the notification; apply the state-machine rules below; `_work.append(...)` + `_wake.set()` when a work item is ready |
| `next_work_item(timeout: float) -> Optional[WorkItem]` | consumer thread | `_work.popleft()` if present; else `_wake.wait(timeout)` then retry once; `None` on timeout. On returning a `text` item, fold in any `pending_text[chat_id]` accumulated since and set `active_turn[chat_id]` |
| `mark_turn_active(chat_id, turn: ActiveTurn) -> None` | consumer thread | record `active_turn[chat_id] = turn` (called as the turn starts) |
| `record_side_effects(chat_id, records: List[SideEffectRecord]) -> None` | consumer thread | `carryover[chat_id] = records` (called when a cancelled `AIResponse` comes back) |
| `on_turn_finished(chat_id) -> None` | consumer thread | clear `active_turn`, `pending_text`, `carryover` for `chat_id` — the **reset** (REQ-RMH-016). Called after a successful send, a deliberate silent turn, or an error-fallback send |
| `cancel_check_for(chat_id) -> Callable[[], bool]` | consumer thread | returns `lambda: active_turn[chat_id].cancelled.is_set()` bound to the current turn, to hand into `get_response` |

### Producer state-machine (inside `submit`)

| Incoming | Condition | Action |
|---|---|---|
| media / button / other | any | build single-notification `WorkItem(kind=...)`; `append`; **do not** touch `active_turn`, **do not** set any `cancelled` |
| text | no `active_turn[chat_id]` and `pending_text[chat_id]` empty | build `WorkItem(kind="text", notifications=[n])`; `append` |
| text | `active_turn[chat_id]` present | `active_turn[chat_id].cancelled.set()`; `pending_text[chat_id].append(n)` — the consumer will build the merged item when the cancelled turn unwinds |
| text | no `active_turn` but `pending_text[chat_id]` non-empty (consumer mid-assembly) | `pending_text[chat_id].append(n)` |

### Consumer merged-item assembly (inside `next_work_item`, on a `text` pull)

1. Swap the buffer out atomically: `extra, self.pending_text[cid] = self.pending_text.get(cid, []), []`.
2. `notifications = pulled.notifications + extra` (arrival order preserved).
3. `combined_text = "\n".join(n.text for n in notifications)`.
4. `carryover = self.carryover.get(cid, [])`.
5. `reply_to = notifications[-1]`.
6. Return the assembled `WorkItem`; the consumer then calls `mark_turn_active(cid, ActiveTurn(...))`.

Any text that arrives *during* step 1's swap window lands in the fresh list and is folded into the
**next** turn — never dropped (see `research.md` D2).

---

## Modified dataclass: `AIRequest` (`src/models/message.py`)

| New field | Type | Default | Meaning |
|---|---|---|---|
| `system_note` | `str` | `""` | the assembled "already done" journal text; when non-empty, appended to `instructions` **after** the per-call date line (contract in `contracts/journal-delivery.md`). Empty for every existing caller — no behaviour change |

**Rule**: `system_note` is data assembled by the consumer from `SideEffectRecord`s before the
`get_response` call — `ai_handler` treats it as opaque text to place after the date line, never
parses it.

---

## Modified dataclass: `AIResponse` (`src/models/message.py`)

| New field | Type | Default | Meaning |
|---|---|---|---|
| `cancelled` | `bool` | `False` | `True` when the turn was interrupted at a round boundary; the consumer must NOT send this response |
| `side_effects_journal` | `List[Dict]` | `field(default_factory=list)` | `SideEffectRecord`-shaped dicts for side effects the discarded turn already caused; the consumer stashes these via `record_side_effects` |

**Rule change**: `AIResponse.__post_init__` currently raises `ValueError` when
`should_reply and not has_text`. It must be relaxed so a `cancelled=True` response with no text is
valid: skip the check when `cancelled` is `True` (a cancelled response is never sent and never
needs text). All non-cancelled responses keep the existing invariant.

---

## What is explicitly NOT modelled

- **No persistence** of burst/journal/active-turn state. A restart loses it (accepted — spec Edge
  Cases; matches ack-immediately's crash-window in `research.md` D3).
- **No new `HANDLER_REGISTRY` entry** — the coordinator is upstream of `dispatch_notification`;
  the registry stays exactly 8 message types (IT-6).
- **No change to `Message` / session storage shape** — each burst message is persisted as an
  ordinary `role="user"` entry via the existing `SessionManager.add_message`; only the count per
  turn changes (N user, 1 assistant).
- **No `PendingApproval` / `PendingLocalToolApproval` schema change** — a discarded turn simply
  never creates one (contract in `contracts/turn-cancellation.md`).
