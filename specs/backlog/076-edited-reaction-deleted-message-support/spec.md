# Feature Specification: Support `editedMessage`, `reactionMessage`, `deletedMessage` (and other unhandled WhatsApp webhook types)

**Feature Branch**: `feature/076-edited-reaction-deleted-message-support`
**Created**: 2026-09-04
**Status**: Placeholder — not yet clarified/specced. Run `speckit.specify` + `speckit.clarify`
before implementation.
**Priority**: TBD (real client-visible symptom already observed in prod — see Evidence).

## Input

User description: DeniDin currently supports only 8 WhatsApp message types
(`textMessage`, `extendedTextMessage`, `contactMessage`, `contactsArrayMessage`,
`imageMessage`, `documentMessage`, `videoMessage`, `audioMessage`) plus
`interactiveButtonsResponse`. Every other `typeMessage` Green API can deliver falls
through `denidin.py`'s `CATCH_ALL_HANDLER` → `handle_unsupported_message` →
a canned Hebrew "this message type isn't supported yet" auto-reply
(`UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES`, `src/constants/error_messages.py`).

Add real handling for at least:

- **`editedMessage`** — a user edits a previously-sent WhatsApp message. Green API
  delivers a new webhook carrying `editedMessageData.textMessage` (the new text) and
  `editedMessageData.stanzaId` (the `idMessage` of the original message being edited).
- **`reactionMessage`** — a user reacts to a message with an emoji (or removes a
  reaction). Carries the target message's id and the emoji (empty string = reaction
  removed).
- **`deletedMessage`** — a user deletes ("delete for everyone") a previously-sent
  message. Carries the deleted message's id.

"…and perhaps other types" — `speckit.clarify` should decide which of the remaining
Green API types are in scope now vs. deferred (candidates: `pollMessage` /
`pollUpdateMessage`, `locationMessage` / `liveLocationMessage`, `stickerMessage`,
`groupInviteMessage`, `templateMessage` / `listMessage` / legacy `buttonsMessage`,
`quotedMessage`-only payloads).

## Evidence (real prod incident, 2026-09-04 — the trigger for this feature)

During the v0.5.4 deploy, chat `120363210094632983@g.us` ("$$ גבייה אילה $$"),
sender "אילה 🦋". All times Israel local, from real prod audit log (`[AUDIT-IN]` /
`[AUDIT-OUT]`, `whatsapp_audit_log.py`):

| Time | Event |
|---|---|
| 10:35:20 | `textMessage` `3A2F324F5A148E7F7D58`: `"כמיר כף\nזמנכל ביטוח לאומי\nמכתב\n 3,000₪"` (garbled name + typo) |
| 10:35:45–10:35:59 | DeniDin processed it: recognized a fee agreement, **captured a `LedgerEvent` with client name `"כמיר כף"`**, replied *"נרשם הסכם שכר טרחה: לקוח: כמיר כף…"* |
| 10:36:01 | `editedMessage` `3A3F9992DBC6B052C485` (stanzaId → `3A2F324F5A148E7F7D58`): name corrected `"כמיר כף"` → `"עמיר כץ"`. → **"unsupported message type" auto-reply** |
| 10:36:02 | `editedMessage` `3A8B47BFBD044BB12351` (stanzaId → same original): typo corrected `"זמנכל"` → `"סמנכל"`. → **"unsupported message type" auto-reply** |

**Exactly 2 `editedMessage` notifications were received** — two genuine, separate edits
the user made to fix the same original message, 1 second apart. Each produced its own
canned "unsupported" reply (there was no duplication bug; `RecentNotificationDeduper`
correctly did not suppress them — distinct `idMessage`s).

Net effect: the user visibly corrected the client's name from a garbled `"כמיר כף"` to
the correct `"עמיר כץ"`, and DeniDin (a) never applied the correction — the captured
ledger event still carries the wrong name — and (b) answered the good-faith correction
with two "not supported" messages. This is the concrete cost of leaving `editedMessage`
unhandled.

## Notes captured so far

- **All three types are currently 100% unhandled** — no reference to `editedMessage` /
  `reactionMessage` / `deletedMessage` anywhere in `apps/denidin-app/src` or `denidin.py`
  (grep, 2026-09-04). They only reach `handle_unsupported_message`.
- `editedMessage` and `deletedMessage` both reference a prior message by `stanzaId` /
  id — this is exactly **Feature 032** (`specs/in-progress/032-whatsapp-reply-reference-resolution/`,
  planned, no implementation yet): resolving a WhatsApp reference back to DeniDin's own
  stored `Message` record. Feature 076 should build on 032's resolution capability rather
  than re-deriving it. Sequencing (076 after 032, or 076 forces 032's resolution layer to
  land first) is a `speckit.clarify` question.
- Acting on an edit/delete that targets a message which **already produced a
  `LedgerEvent`** (the prod evidence above) overlaps **Feature 040**
  (`specs/backlog/040-agreement-cancellation-modification/`): modify/cancel a captured
  ledger event via a resolved reference. Decide the boundary — does 076 only *route* the
  edit/delete to the right place, with 040 owning the ledger-event mutation? Or does 076
  cover the simple "re-run the turn on the edited text" case directly?
- Not to be confused with **Feature 067** (`realistic-message-handling` — coalescing
  bursts of *new* messages). 076 is about *retroactive* changes to an already-delivered
  message, a different concern.
- The catch-all itself must stay — "no message type is silently dropped" is a deliberate
  invariant (`denidin.py` / `.github/ARCHITECTURE.md`). 076 moves specific types *out* of
  the catch-all into real handlers; anything still unrecognized keeps getting a friendly
  reply.

## Open questions for `speckit.clarify`

**`editedMessage`:**
- Re-run the whole turn on the edited text as if it were a fresh message? Or a lighter
  "note the correction" path?
- If the original already produced a side effect (a `LedgerEvent`, a pending approval, an
  invoice), what happens? (→ likely defers to Feature 040 for ledger events.)
- Time bound — only honor an edit within N minutes / while the session is still active?
  Ignore edits to messages older than the current session?
- Group chats: does the edit have to come from the same sender as the original? (Prod
  evidence: yes, same sender.)
- Does the edited message get stored as a new `Message`, replace the original's stored
  content, or append a "(edited: …)" annotation?

**`reactionMessage`:**
- Is any action wanted at all, or is "silently ignore, no reply" the whole feature? (A 👍
  on DeniDin's own reply almost certainly wants *no* response.)
- Any reaction that *should* mean something — e.g. 👍 on an approval prompt as an
  alternative to typing "כן" / tapping the button? (Cross-check Feature 047's approval
  UX; probably out of scope, but name it explicitly per the "EVERY NEW TOOL-BEARING
  FEATURE NEEDS EXPLICIT CONSTITUTION BOUNDARIES" rule.)

**`deletedMessage`:**
- Silently ignore, or acknowledge? ("delete for everyone" on a message that stated an
  agreement → cancel the agreement? → Feature 040 territory.)
- Remove / tombstone the corresponding stored `Message`? Affect session history sent to
  OpenAI?

**Scope:**
- Which of the "perhaps other types" are in this feature vs. a follow-up.
- Feature-flag the new behavior (per CONSTITUTION §? — new behavior defaults off, catch-all
  path byte-identical when the flag is off).

## Impact / touch points (preliminary — confirm during `speckit.plan`)

- `denidin.py` — `HANDLER_REGISTRY` gains entries; new `handle_edited_message` /
  `handle_reaction_message` / `handle_deleted_message` functions. `GreenAPIMessageSource`
  is constructed with `message_types=list(HANDLER_REGISTRY.keys()) + [...]` so new keys
  auto-register.
- `tests/unit/test_denidin_dispatch.py::test_registry_contains_exactly_these_eight_types_no_more_no_less`
  — an **immutable approved test** that hard-asserts the registry is exactly those 8
  types. Updating it needs explicit human sign-off (METHODOLOGY.md — tests immutable once
  approved).
- `src/models/message.py` — `WhatsAppMessage.from_notification` currently has no branch for
  `editedMessageData` / reaction / deletion payload shapes.
- `src/handlers/whatsapp_handler.py` — `validate_message_type` allow-list; possibly new
  send paths.
- `config/runtime_constitution.md` — if any new type carries conversational meaning (an
  edit re-running a turn), it needs its own scope section + cross-references, per the
  "EVERY NEW TOOL-BEARING FEATURE NEEDS EXPLICIT CONSTITUTION BOUNDARIES" rule.
- Depends on / coordinates with **Feature 032** (reference resolution) and **Feature 040**
  (ledger-event cancel/modify).

## Out of scope (tentative — confirm in `speckit.clarify`)

- Coalescing bursts of new messages (Feature 067).
- The full ledger-event modification/cancellation behavior (Feature 040) — 076 routes the
  edit/delete to it, 040 owns what happens to the event.
- Sending our own edited/reaction messages outbound (this is inbound handling only).
