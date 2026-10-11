# Integration Contracts: Sender-Name Attribution (formerly "Sender-Role Tagging")

**Feature**: 039-group-conversation-support · Per METHODOLOGY.md §VII format.

**REVISED 2026-08-04**: This contract originally covered a new `Message.sender_role` (RBAC
role) field — retracted, see research.md §4 and data-model.md's `Message` section. It now
covers what the requirement actually turned out to need: resolving a human-readable sender
name (not RBAC role, not a raw phone number) and making it visible to the model, not just to
storage.

---

### `WhatsAppMessage.from_notification` ↔ Green API notification Contract (extension)

**`from_notification` MUST**:
- Read `senderData.senderContactName` off the raw notification, in addition to the existing
  `senderData.senderName`/`sender` reads.
- Populate a new `sender_display_name` attribute: `senderContactName` if present and non-empty,
  else `senderName`, else the raw `sender_id`. Never raise/error if `senderContactName` is
  absent (it's Green API's contact-book resolution — legitimately absent for a number that
  isn't saved as a contact on the DeniDin WhatsApp account).

**Green API notification PROVIDES** (unchanged, documented behavior — not something this repo
controls): `senderData.senderContactName` when the sender's number is saved as a contact on
the receiving WhatsApp account; `senderData.senderName` (the sender's own profile name)
otherwise/always as a secondary source.

---

### `denidin.py`/`AIHandler` ↔ `SessionManager` Contract (extension of existing contract)

**Callers (`_finalize_response`, `_store_media_turn`, and any other caller of `add_message`/
`add_message_with_tokens`/`add_message_with_token_limit`/`_store_media_turn`) MUST**:
- Pass `message.sender_display_name` (the resolved name, not `message.sender_id`) as the
  `sender=` argument when persisting a `role="user"` message.
- Pass `None` (not the literal string `"AI"`) as `recipient=` when persisting a `role="user"`
  message.
- Pass `None` (not `"AI"`) as `sender=` when persisting the paired `role="assistant"` message,
  and the same resolved display name (not the raw id) as that message's `recipient=`.
- Continue using `message.sender_id` (the raw JID), unchanged, wherever RBAC/programmatic
  identity is actually needed (`UserManager.get_user`, the `user_phone`/`sender` parameters on
  `AIHandler.create_request`/`get_response`) — this contract only changes what gets written
  into `Message.sender`/`Message.recipient`, nothing about RBAC resolution.

**`SessionManager` PROVIDES**:
- `add_message`/`add_message_with_tokens`/`add_message_with_token_limit`/
  `_store_media_turn`-equivalent persistence: unchanged signatures — this is purely "callers
  now pass different argument values," not a new parameter or new field.
- `get_conversation_history_for_session` (`session_manager.py:222-255`) gains group-aware
  formatting: for a session whose `whatsapp_chat` contains `"@g.us"`, each returned
  `role="user"` history entry's `content` is `f"[{sender}] {content}"` (using the message's
  stored `sender`, i.e. the resolved display name); `role="assistant"` entries and all 1:1
  sessions are returned exactly as today (no prefix).

**`SessionManager` EXPECTS**:
- `sender`/`recipient`, when provided, are plain display strings — no format validation
  performed (same "upstream owns correctness" convention as the rest of this codebase, e.g.
  `LedgerEventManager` trusting `AIHandler`'s tool-schema enforcement).
