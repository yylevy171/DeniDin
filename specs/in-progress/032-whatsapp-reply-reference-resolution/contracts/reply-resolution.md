# Integration Contract: Reply Resolution (internal, not REST/OpenAPI)

**Feature**: 032-whatsapp-reply-reference-resolution
**Per METHODOLOGY.md §VII**: this feature has no external API surface (no new endpoint, no
new external service) — the "contract" here is between existing internal components, so this
documents function signatures/call sequencing instead of an OpenAPI schema.

## Component Interaction

```
Green API webhook
  → WhatsAppMessage.from_notification(notification)
      captures: whatsapp_id_message, quoted_stanza_id  (new, data-model.md)
  → AIHandler.create_ai_request(message, ...)
      if message.quoted_stanza_id:
          resolved = session_manager.resolve_reply(message.chat_id, message.quoted_stanza_id)
          if resolved:
              constitution += format_resolved_reference(resolved)   # same position/pattern
                                                                      # as memory_context
                                                                      # (research.md Decision 4)
      → AIRequest(constitution=..., ...)
  → SessionManager.add_message(..., whatsapp_id_message=message.whatsapp_id_message)
      updates id_message_index for this session (data-model.md)
```

## Contract: `SessionManager.resolve_reply`

```python
def resolve_reply(
    self, whatsapp_chat: str, stanza_id: str, ledger_event_manager: LedgerEventManager
) -> Optional[Dict]:
```

**Preconditions**: None — safe to call with any `whatsapp_chat`/`stanza_id`, including ones
with no active session or no match.

**Postconditions**:
- Returns `None` if: no active (unexpired) session exists for `whatsapp_chat`, OR
  `stanza_id` doesn't match any `whatsapp_id_message` in that session's `id_message_index`.
- Returns the `resolved_reference` dict (data-model.md shape) on a match — scoped strictly to
  the given `whatsapp_chat`'s active session (Q10/Q11), never searches other chats or
  archived/expired sessions. `content`/`ledger_events` are mutually exclusive (data-model.md
  Validation Rules) — `ledger_events` fully hydrated via `ledger_event_manager`, never bare ids.
- Does NOT mutate any state — pure lookup.
- Does NOT raise for any input; all failure modes resolve to `None`.

**Consumers**: `AIHandler.create_ai_request` (primary, for prompt context injection). No other
consumer exists yet — Feature 040 will be a second consumer, reading `resolved_reference`'s
`ledger_events` (the hydrated `LedgerEvent` record(s), when present) to decide
cancellation/modification eligibility.

## Contract: `WhatsAppMessage.from_notification` (extended)

**New behavior**: additionally reads `event['idMessage']` and, when
`message_type == 'extendedTextMessage'` and a `quotedMessage` sub-object is present,
`messageData.extendedTextMessageData.quotedMessage.stanzaId`.

**Backward compatibility**: Existing callers unaffected — both new fields are optional with
`None` default; no existing field's meaning changes; `text_content` extraction (bugfix-008's
flattening) is untouched.

## Contract: `SessionManager.add_message` (extended)

**New parameter**: `whatsapp_id_message: Optional[str] = None` — when provided, indexed into
that session's `id_message_index` alongside the existing message-file write. Optional and
defaulted, so all existing call sites remain valid without changes (though `AIHandler`'s
call sites should be updated to pass it through, per plan.md's Project Structure).
