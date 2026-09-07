# Data Model: Group Conversation Support

**Feature**: 039-group-conversation-support · Phase 1 output of `speckit.plan`.

## Entities

### `Message` (modified — `src/managers/session_manager.py`)

**No new fields.** (REVISED 2026-08-04 — an earlier pass of this doc proposed a new
`sender_role` field; retracted, see research.md §4 for why it was solving a non-problem.)
Instead, two existing fields change what value they're populated with:

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `message_id` | `str` | unchanged | |
| `session_id` | `str` | unchanged | |
| `role` | `str` | unchanged | `"user"`/`"assistant"` — OpenAI conversation-turn role. Already sufficient to answer "is this DeniDin's own message" (`role == "assistant"`) — no field is needed for that (per direct user confirmation this is trivial). |
| `content` | `str` | unchanged | Stored raw/unprefixed — the group-aware sender-name prefix (see "Relationships" below) is applied only when history is formatted for OpenAI, never persisted. |
| `sender` | `Optional[str]` | **VALUE CHANGES** | Previously the sender's raw WhatsApp id (e.g. `"972501234567@c.us"`) for user messages, or the literal string `"AI"` for assistant messages. Now: for a `role="user"` message, the sender's **resolved display name** (Green API's `senderContactName` → `senderName` → raw id fallback chain, research.md §4a) — e.g. `"Godfather"` instead of the raw number. For a `role="assistant"` message, `None` (redundant with `role` — dropped, not replaced). |
| `recipient` | `Optional[str]` | **VALUE CHANGES** | Previously `"AI"` for user messages, or the sender's raw id for assistant messages. Now: for a `role="user"` message, `None` (redundant with `role`). For a `role="assistant"` message, the same resolved display name as that turn's paired user message's `sender` (still real information — who this specific reply was for — not a sentinel). |
| `timestamp` / `received_at` / `was_received` / `order_num` / `image_path` / `ledger_event_ids` | — | unchanged | |

**Validation rules**: `sender`/`recipient`, when present, are plain display-name strings (no
enum, no fixed vocabulary) — whatever Green API's contact resolution or the raw id fallback
produces. `message.sender_id` (the raw JID, on `WhatsAppMessage`, not `Message`) remains the
only value used for RBAC/programmatic identity (`UserManager.get_user`) — never derived back
out of a stored `Message.sender` display name.

**State transitions**: None — both fields are set once at message-creation time, never
mutated afterward (unchanged from today).

**No change to `Session`** — group/1:1 session separation already holds by construction
(`chat_id`-keyed, US2's baseline confirms this needs no new field).

---

### `WhatsAppMessage` (modified — `src/models/message.py`)

One new attribute, populated at parse time in `from_notification`:

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `sender_display_name` | `str` | **NEW** | `senderData.senderContactName` if present and non-empty, else `senderData.senderName` (already parsed today as `sender_name`, unchanged), else the raw `sender_id`. Computed once at parse time, alongside the existing `sender_name`/`sender_id` fields — not a new Green API call, just reading one more key off the same `senderData` object already being read. |

`sender_id` (raw JID) and `sender_name` (existing, WhatsApp-profile-name) are both unchanged —
`sender_display_name` is additive, the new preferred value for anything human-facing
(storage's `Message.sender`, and the group conversation-history prefix below).

---

### Conversation History Group-Aware Formatting (new behavior — not a persisted entity)

A formatting step inside `SessionManager.get_conversation_history_for_session`
(`session_manager.py:222-255`), not a new stored field: when the session being read is a group
session (`"@g.us" in session.whatsapp_chat`), each `role="user"` entry's `content` is returned
as `f"[{message_data['sender']}] {message_data['content']}"` instead of the raw `content` —
using the already-resolved-to-a-name `sender` field above. `role="assistant"` entries are
returned unprefixed (unambiguous — it's always DeniDin). 1:1 sessions: no prefix, unchanged
from today's output shape.

---

### `AIResponse` (modified — `src/models/message.py:146`) (NEW 2026-08-04)

One new field:

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `should_reply` | `bool` | **NEW**, default `True` | `False` when `_finalize_response` detects the no-reply sentinel (research.md §8, contracts/no-reply-mechanism.md) as the model's entire `response_text` for this turn. Callers (`denidin.py`) check this before calling `WhatsAppHandler.send_response`. |

**Validation rules**: None beyond the type itself — a plain boolean, always set (never `None`).

**State transitions**: Set once per response, at construction — not mutated afterward.

---

### Group Membership Resolution (new concept — not a persisted entity)

Not a stored data model — a **computed, cached runtime value**, resolved per group `chat_id`
on demand from a live Green API call, not from any new config or database table (see
research.md §1 for why: avoids config/reality drift).

**Conceptual shape** (in-process cache entry, exact implementation is a `speckit.tasks`
decision):

| Field | Type | Notes |
|-------|------|-------|
| `chat_id` | `str` | The group's `...@g.us` chat ID — cache key. |
| `member_phones` | `list[str]` | Raw phone/JID list from `getGroupData`'s participant data. |
| `resolved_role` | `Role` | The most-permissive `Role` among `member_phones`, per `UserManager`'s existing ADMIN > GODFATHER > CLIENT > BLOCKED precedence (`user_manager.py:68-78`), reused unchanged — not a new precedence rule. |
| `resolved_phone` | `str` | The specific phone number (among `member_phones`) that produced `resolved_role` — this is what gets passed as `AIHandler`'s `user_phone=` override (research.md §3), since `AIHandler` resolves a `User` from a phone, not a bare `Role`. |

**Lifecycle**: Populated lazily on first group turn for a given `chat_id` (or refreshed per a
caching strategy decided at `speckit.tasks` time); never persisted to disk — a restart simply
re-fetches on next use, same failure-recovery profile as any other in-memory cache in this
codebase (e.g. `SessionManager.chat_to_session`).

**Failure mode**: If `getGroupData` fails (Green API error, group not found, etc.), fall back
to resolving RBAC from the sender alone (today's existing per-sender behavior) rather than
blocking the turn — a temporary degradation to "correct behavior, wrong precedence" is
preferable to no reply at all. (Exact retry/backoff policy: standard project retry rule —
retry once on 5xx/timeout after 1s, never retry 4xx, per CONSTITUTION.)

---

## Relationships

```
WhatsAppMessage (parsed notification)
  │  is_group=True; sender_display_name resolved (NEW, §senderContactName fallback chain)
  ▼
_process_conversational_message (denidin.py)
  │  resolves via Group Membership Resolution (new) → resolved_phone
  ▼
AIHandler.create_request(message, user_phone=resolved_phone)
AIHandler.get_response(request, sender=message.sender_id, user_phone=resolved_phone)
  │  (sender= stays the raw id — RBAC/tracking parameter, unrelated to display)
  ▼
SessionManager.add_message(..., sender=message.sender_display_name, recipient=None)
  │  Message.sender now holds a resolved NAME, not a raw id or "AI" sentinel
  ▼
SessionManager.get_conversation_history_for_session(group session)
  │  prefixes each user turn's content with "[<sender>] " before returning to AIHandler
  ▼
OpenAI Responses API call — model now sees who said each turn within the shared session
```

Note the deliberate separation of two different questions that must not be conflated: (1)
`user_phone=resolved_phone` (most-permissive across the group) governs `max_tokens`/tool
attachment for the turn (US4) — an RBAC concern, entirely internal to the `AIHandler` call,
never touches `Message` storage; (2) `Message.sender`/the conversation-history prefix (this
page) is purely about display attribution — who a human reader (or the model itself) sees as
having said a given line — and always reflects the actual individual sender, regardless of
which role's limits governed the turn.

A third, independent branch (US4a/US5/US7's no-reply path):

```
OpenAI Responses API call
  │  response_text == no-reply sentinel?
  ├─ No  → normal flow: AIResponse.should_reply=True, assistant message persisted, sent
  └─ Yes → AIResponse.should_reply=False; user message still persisted (context preserved);
           NO assistant message persisted; denidin.py skips WhatsAppHandler.send_response
```
