# Feature Specification: Realistic Message Handling — Multiple Interfering Messages

**Feature Branch**: `feature/067-realistic-message-handling`
**Created**: 2026-08-30
**Status**: Placeholder — not yet clarified/specced. Captured from the 2026-08-29 dev-conversation
"DeniDin improvements" list (item 3). Run `speckit.specify` + `speckit.clarify` before
implementation.

## Input

User description: handle **more than one message at a time** realistically — a user often sends
several WhatsApp messages in quick succession (a name, then the matter, then an amount, then a
screenshot) that belong to one logical request, and DeniDin should handle the burst coherently
instead of replying to each message in isolation. "Interfering messages" = a later message
arrives while an earlier one is still being processed / awaiting a reply.

## Notes captured so far

- Needs `speckit.clarify` to separate the problems this covers:
  1. **Message coalescing** — buffer messages arriving within a short window and process them as
     one turn. Related: `bugfix-030-message-sequencing-ambiguity`.
  2. **Concurrency / interference** — a second webhook for the same chat arriving mid-processing,
     racing on `SessionManager` / `PendingApprovalManager` state, or a new message landing while
     an approval is pending. Note the standing rule: no `threading.Lock` without explicit human
     approval.
  3. **Multiple attachments in one send** — e.g. several deposit screenshots at once
     (`contactsArrayMessage` is currently declined outright; image bursts have no batching).
- Current flow (`denidin.py` `dispatch_notification` → per-message handler → immediate AI call +
  reply) has no notion of "wait for more" or "a turn is already in flight."

## Open questions for `speckit.clarify`

- Which of the three problems are in scope (possibly all).
- If coalescing: debounce window length, what resets it, how it interacts with a pending "כן".
- Group chats: coalesce per-sender or per-chat.
- Desired behaviour when a message interferes with an in-flight turn (queue, merge, ignore, ask).
