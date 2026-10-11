# Data Model: WhatsApp Reply/Quote Reference Resolution

**Feature**: 032-whatsapp-reply-reference-resolution
**Phase**: 1 (Design)

## Entities Touched

### `WhatsAppMessage` (`src/models/message.py`)

New fields on `WhatsAppMessage.from_notification`'s output — both optional, `None` when the
incoming notification has no `quotedMessage` (the common case):

| Field | Type | Source | Notes |
|---|---|---|---|
| `whatsapp_id_message` | `Optional[str]` | `event['idMessage']` (top-level, sibling of `senderData`/`messageData` — `green-api.md:51`) | Green API's own id for *this* message. Currently discarded entirely. |
| `quoted_stanza_id` | `Optional[str]` | `event['messageData']['extendedTextMessageData']['quotedMessage']['stanzaId']` — only present when `message_type == 'extendedTextMessage'` and a `quotedMessage` sub-object exists | The id of the message this one is replying to. `None` for a non-reply message. |

Both are plain pass-through captures — no validation/normalization beyond what Green API
already guarantees (both are opaque strings from DeniDin's perspective).

### `Message` (`src/managers/session_manager.py`)

New fields on the persisted per-session `Message` dataclass (JSON, one file per message under
`data/sessions/{session_id}/messages/`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `whatsapp_id_message` | `Optional[str]` | `None` | Mirrors `WhatsAppMessage.whatsapp_id_message` — persisted so a *later* message's `stanzaId` can be matched against it. |
| `resolved_reference` | `Optional[Dict]` | `None` | Populated only on a message that IS a reply AND whose `stanzaId` resolved successfully. Shape below. |

`resolved_reference` shape (plain dict, not a new dataclass — mirrors how `recalled_memories`
is already a `List[Dict]` in `ai_handler.py`, not a typed model, since it's transient prompt
context, not itself persisted state requiring its own lifecycle):

```json
{
  "message_id": "<the referenced Message's message_id>",
  "sender": "<the referenced Message's sender>",
  "timestamp": "<the referenced Message's timestamp>",
  "content": "<the referenced Message's content, or extracted_text/document_analysis if media - ONLY when ledger_events below is empty>",
  "ledger_events": ["<full structured LedgerEvent record(s), fetched via LedgerEventManager for each id in the referenced Message's ledger_event_ids - ONLY when non-empty>"]
}
```

**`content` vs `ledger_events` are mutually exclusive, not both populated (2026-08-04
revision).** A `LedgerEvent` record (`LEDGER_EVENT_TOOL`'s schema: `source_type`,
`event_subtype`, `client_name`, `payer_name`, `agreement_label`, and per-component
`amount`/`percent`/`hours`/`hourly_rate`/`txn_date`/etc.) already carries
`raw_message_excerpt` — "verbatim source text (or a precise description of the image) this
capture is based on" — so re-including the message's own `content`/`extracted_text`
alongside it would be a pure duplicate of data already inside the ledger record. When
`ledger_event_ids` is non-empty, `resolved_reference` carries the full structured
`LedgerEvent` record(s) (fetched via `LedgerEventManager`, not just the bare ids) — giving the
model authoritative, already-parsed values (exact `amount`, not something to re-derive from
free text) instead of bare ids with nothing to reason from. When `ledger_event_ids` is empty
(ordinary conversational message), `resolved_reference` carries plain `content` instead, since
there's no structured record to defer to.

**Note on `ledger_event_ids`/`ledger_events`**: `Message.ledger_event_ids`
(`session_manager.py:40`) already exists (Feature 033) — this feature only reads it (and the
`LedgerEvent` records it points to) as pass-through, never writes to it, never interprets it
(spec.md Scope: "not something this feature interprets or acts on"). Fetching the full record
via `LedgerEventManager` (rather than just passing the bare id) is a data-shaping decision,
not an interpretation of what the record means.

### `SessionManager` (`src/managers/session_manager.py`) — new in-memory state

| Field | Type | Notes |
|---|---|---|
| `id_message_index` (per `Session`, alongside existing `chat_to_session`) | `Dict[str, str]` (`whatsapp_id_message` → `message_id`) | Built/updated in `add_message`; rebuilt from a session's `message_ids` when a session is loaded from disk (same rebuild pattern as `chat_to_session`, `session_manager.py:333`). Scoped per-session ⇒ automatically per-chat (Decision 3, research.md). |

New method — takes a `LedgerEventManager` (already an existing collaborator elsewhere, e.g.
`AIHandler`) so it can fetch full records for any `ledger_event_ids` on the matched message:

```python
def resolve_reply(
    self, whatsapp_chat: str, stanza_id: str, ledger_event_manager: LedgerEventManager
) -> Optional[Dict]:
    """
    Resolve a reply's stanzaId to the Message it quotes, scoped to the active
    session for whatsapp_chat only (Q10/Q11 — no archived-session or cross-chat
    lookup). Returns the resolved_reference dict shape (see data-model.md) — with
    ledger_events fully hydrated via ledger_event_manager when the matched
    Message has any ledger_event_ids, else content populated instead — or None
    if no match in the active session.
    """
```

## State / Lifecycle Notes

- **No new persistence format.** `resolved_reference` and `whatsapp_id_message` are just new
  fields on the existing per-message JSON file — no migration needed for old messages (they
  simply have `whatsapp_id_message: None`, meaning they're never a match target, which is the
  correct/expected behavior for pre-feature messages per US1 Scenario 4).
- **Index lifetime matches session lifetime.** When a session expires/archives (existing
  `SessionCleanupThread` flow, `services/cleanup_service.py`), its `id_message_index` entry is
  dropped along with everything else `chat_to_session`-scoped — consistent with Q10 (active
  session only, no archived-session lookup).
- **No change to `LedgerEvent`** (Feature 033) at all — this feature only reads it (whole
  records, via `LedgerEventManager`, for any ids in `Message.ledger_event_ids`) as pass-through
  data; never writes, never interprets.

## Validation Rules

- `resolve_reply` MUST NOT raise on a miss (unmatched `stanza_id`, or no active session for
  `whatsapp_chat`) — returns `None`, caller treats the message as an ordinary new message
  (US1 Scenario 4, US1 Scenario 7).
- `resolved_reference`'s `content` and `ledger_events` are MUTUALLY EXCLUSIVE — exactly one is
  populated, never both, never neither (when `resolved_reference` itself is non-`None`):
  `ledger_events` (full structured records) when the matched message has any
  `ledger_event_ids`; `content` otherwise.
- `content`, when populated, MUST be derived from the referenced message's
  `extracted_text`/`document_analysis` (full, untruncated) if it was a media message, never
  raw media bytes (Q9).
