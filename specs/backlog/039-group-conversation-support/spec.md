# Feature Spec: Group Conversation Support

**Feature ID**: 039-group-conversation-support
**Priority**: TBD
**Status**: Draft
**Created**: August 4, 2026

---

## Problem Statement

Today, group messages are only processed if the bot's name is
substring-matched in the text (`WhatsAppHandler.is_bot_mentioned_in_group`,
`apps/denidin-app/src/handlers/whatsapp_handler.py`, line 82); otherwise
`_process_conversational_message` (`denidin.py`, line 307) logs and returns
early with no reply. The entire group shares one session/memory keyed by the
group's own `chat_id` (`SessionManager.get_session`,
`src/managers/session_manager.py`, line 93; `AIHandler.create_request`/
`get_response`, `src/handlers/ai_handler.py`, lines 587/842), with no
distinction between which member sent a given message.

**Target scenario**: a WhatsApp group containing exactly three participants
— godfather, admin, and DeniDin itself. Godfather sends most messages;
admin occasionally joins in. Both address DeniDin **implicitly** — no
@mention — since godfather and admin are not expected to converse with each
other in this group (they have a separate channel for that). Admin also has
a pre-existing separate 1:1 chat with DeniDin, which must keep being managed
as its own distinct session, entirely separate from this group's session.

## Requirements (draft, generalized beyond the specific 2-human scenario to
any group DeniDin is added to)

- Remove the @mention gate for message routing in a group — a group message
  should be treated as addressed to DeniDin by default (not filtered out
  the way it is today), since in the target scenario there's no one else in
  the group to address.
- The group needs "etiquette" behavior: when it's genuinely ambiguous
  whether a message is directed at DeniDin (vs. two humans talking to each
  other), DeniDin should ask for clarification rather than silently
  guessing — but this should be the exception path, not the common case,
  since messages will almost always be directed at it.
- The group's own session must be tracked separately from any individual
  member's 1:1 session with DeniDin (e.g. admin's existing private chat) —
  a group conversation and a 1:1 conversation with the same person are
  distinct contexts, not merged.
- Media (images) and text should both be handled in a group exactly as they
  are in a 1:1 chat today — no reduced feature set; only the
  routing/gating and session-identity rules change.

## Open Questions (for `speckit.clarify`)

- How does RBAC/role resolution work inside a group when multiple distinct
  roles (godfather, admin) can post into the same group session — whose
  token limit/permissions apply for a given turn: the sender's, or some
  combined group-level policy?
- What signal should trigger the "ask for clarification" ambiguity path
  (e.g. more than 2 human participants present, or something else)?
- Is per-sender attribution needed *within* the shared group session (so
  DeniDin knows who said what), even though the session itself is shared?

---

*No `speckit.plan`/`user-stories.md`/`tasks.md` has been run yet — this is a
definition-only draft, not a fully specified feature.*
