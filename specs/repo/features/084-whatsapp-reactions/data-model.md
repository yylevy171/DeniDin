# Data Model: WhatsApp Reactions

No new persistent entity, no new SQLite table or JSON file, no new manager class. This is
deliberately minimal compared to Feature 054 (reminders): reactions are stateless, fire-and-forget
side effects, and (pending `research.md` R1/R3 confirmation) Green API's own same-`messageId` flip
semantics remove the need for any reaction-history bookkeeping on this side.

## Additive fields on existing entities

### `Message` (`src/managers/session_manager.py`)

| Field | Type | Default | Purpose |
|---|---|---|---|
| `whatsapp_id_message` | `Optional[str]` | `None` | The real Green API `idMessage` for this message, as delivered on the inbound webhook. Today `Message.message_id` (line ~32) is DeniDin's own internally-generated UUID (`str(uuid.uuid4())`), never the wire id — reacting to a message requires the real `idMessage`, which is currently only captured ad hoc, at *send* time, via `whatsapp_handler.py`'s `result.data.get("idMessage")` for outbound messages. This field captures it for *inbound* messages too, reusing the extraction `green_api_bot.py`'s `_extract_read_receipt_target` (line ~38) already performs inline for a different purpose (`body.get("idMessage")`), rather than re-deriving it. |

Persisted the same way every other `Message` field is — as part of the per-message JSON file under
`{session_dir}/messages/*.json` — tolerant load applies (an old message missing this field loads
with `whatsapp_id_message=None`, not a crash, per the existing tolerant-load convention).

### `Session` (`src/managers/session_manager.py`)

| Field | Type | Default | Purpose |
|---|---|---|---|
| `active_document_message_id` | `Optional[str]` | `None` | The `whatsapp_id_message` of the most recent document/image ingestion that started a still-open, multi-turn workflow (e.g. document → client clarification → ledger capture). Satisfies REQ-084-004: lets a later turn's `react_to_message` call (or the ledger-finalization code path) flip the *original* triggering message's reaction to a terminal ✅/⚠️/❌, even though several conversational turns may have passed in between. Set when a document/image message that starts such a workflow is ingested; cleared once that workflow resolves (success or reject) — the same call site that performs the final flip also clears this field, so it never points at a stale, already-resolved message. |

Persisted as part of `session.json`, tolerant load applies (an old session missing this field loads
with `active_document_message_id=None`).

## `message_id` resolution fallback chain (used by the `react_to_message` tool and by the deferred-
flip call sites)

1. An explicit `message_id` argument, if the model (or calling code) supplies one.
2. `Session.active_document_message_id`, if set and non-stale (see Cross-Session-Resumption edge
   case in `spec.md` — if this workflow pointer is unreachable, e.g. after a session boundary the
   spec anticipates, fall through).
3. The current turn's own `Message.whatsapp_id_message` (the incoming message that triggered this
   AI turn) — the spec's own SHOULD-fallback for cross-session resumption.

This chain is documented once here and referenced by `contracts/react-to-message-tool-schema.md`
and `contracts/fast-path-reaction-heuristic.md` rather than restated in each.

## Explicitly out of scope for this data model

- **No reaction-history table.** See `research.md` R3 — same-`messageId` flip semantics (pending
  R1 confirmation) make this unnecessary; revisit only if Gate Zero disproves the flip assumption.
- **No config changes.** Nothing here is per-environment configurable.
- **No new manager class.** The two fields above live directly on the existing `Message`/`Session`
  dataclasses; no `ReactionManager`-style object is introduced, unlike `ReminderManager` in
  Feature 054, because there is no independent storage or resolution logic complex enough to
  warrant one — everything reduces to "send this exact emoji to this exact known message id,"
  which is what `send_reaction()` (see `contracts/green-api-reaction-client.md`) already fully
  captures.
