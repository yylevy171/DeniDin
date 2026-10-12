# Data Model: Realistic Message Handling (in-memory only; no new persisted data)

## ChatIntake (per `chat_id`, in `IntakeCoordinator`)
| Field | Type | Owner | Notes |
|---|---|---|---|
| `bodies` | `deque[dict]` | producer appends, worker pops left | raw Green API webhook bodies not yet received |
| `deferred` | `list[dict]` | worker only | non-attachable bodies (taps, edited/deleted, contactsArray, blocked sender…) kept in order; dispatched before newer bodies |
| `media_backlog` | `deque[(dict, WhatsAppMessage)]` | worker only | media bodies already received/stored at a drain, waiting for their own exchange |

## IntakeCoordinator
`chats: dict[str, ChatIntake]` (created with `setdefault`), `arrival: deque[str]` (chat ids in
arrival order; stale ids with empty deques are skipped), `wake: threading.Event`.

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
Kept on the exchange's local state; replaced each round.

## Unchanged
`Session`, `Message`, `Session.active_capabilities`, `Session.approval_message_id` (only *when it
is cleared* changes, D14).
