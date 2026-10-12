# Data Model: Realistic Message Handling (in-memory only; no new persisted data)

## ChatIntake (per `chat_id`, in `IntakeCoordinator`)
| Field | Type | Owner | Notes |
|---|---|---|---|
| `items` | `BoundedQueue[(Notification, WhatsAppMessage)]` | producer puts, worker gets | ready notification (bound to the send client) + the already-stored message |
| `deferred` | `list[dict]` | worker only | non-attachable bodies (taps, edited/deleted, contactsArray, blocked sender…) kept in order; dispatched before newer bodies |
| `media_backlog` | `list[(Notification, WhatsAppMessage)]` | worker only | media items seen at a drain, waiting to be handled on their own |

## IntakeCoordinator
`chats: dict[str, ChatIntake]` (created with `setdefault`), `arrival: BoundedQueue[str]` (chat ids in
arrival order; the worker blocks on it; stale ids with empty chat queues are skipped).

## PendingUserItem (built at a drain; never persisted — the stored `Message` already is)
| Field | Meaning |
|---|---|
| `message_id` | id of the stored message |
| `text` | message text (group: `[sender name]` prefix as in history) |
| `sent_at` | the message's stored Israel-local timestamp |
| `relation` | `"before"` if `sent_at` < `last_output_at`, else `"after"` |
| `kind` | `"text"` or `"media_note"` |

## HandBack (the backbone's `last_output_at`)
`last_output_at: datetime` — `now_local()` when the most recent `responses.create` returned.
Kept in the current handling's local state; replaced each round.

## Unchanged
`Session`, `Message`, `Session.active_capabilities`, `Session.approval_message_id` (only *when it
is cleared* changes, D14).

## SessionManager actor (D15)
`SessionManager` (facade) → one `queue.Queue` of `(operation, args, kwargs, Future)` → one thread →
`SessionStore` (today's implementation, single-thread-only). No other component touches session
files.

## BoundedQueue (D16)
`queue.Queue(maxsize)` + `put_or_raise` → `QueueLimitExceeded`, `last_get_at`, `size()`, high-water mark, dropped counter. Used for: each chat's intake queue, `arrival`, SessionManager's actor queue.
