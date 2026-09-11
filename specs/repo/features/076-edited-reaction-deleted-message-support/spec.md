# Feature Specification: Handle `editedMessage`, `deletedMessage`, and re-triage the remaining unhandled WhatsApp webhook types

**Feature Branch**: `feature/076-edited-reaction-deleted-message-support`
**Created**: 2026-09-04
**Clarified**: 2026-09-07 (interactive, with the user — see "Clarifications" below)
**Status**: IMPLEMENTED — all unit/integration tests green (1415 passed). Awaiting
manual verification in dev, then haleluya (spec move to done, PR, merge).
**Priority**: P1 (real client-visible symptom already observed in prod — see Evidence).

**Complies with**:
- **CONSTITUTION.md** §I (no env vars, config by DI), §V (integration tests simulate a real
  external entry point — a Green API webhook dispatched through `dispatch_notification`), §XV
  (Israel local time — `local_from_timestamp` / `now_local`), §XVII (no monkey-patching).
- **METHODOLOGY.md** §VI.b (unit/integration RED→GREEN with human approval, tests immutable
  once approved), §"Finish-Feature Trigger Phrase".

---

## Problem

DeniDin recognizes a fixed set of WhatsApp `typeMessage` values and routes every other value
through `denidin.py`'s `CATCH_ALL_HANDLER` → `WhatsAppHandler.handle_unsupported_message` →
a canned Hebrew "this message type isn't supported yet" auto-reply. Three concrete costs:

1. **`editedMessage` / `deletedMessage` are answered with "unsupported".** When a user edits or
   retracts a message — a normal, good-faith action — DeniDin replies with a canned "not
   supported" message and never registers that the earlier message changed.
2. **The canned reply fires for genuinely trivial events** — a 👍 reaction, a sticker, a shared
   location, a poll vote — cluttering the conversation with "not supported" noise.
3. **`audioMessage` is nominally "supported" but does nothing** — it routes to the media
   pipeline, which only accepts `jpg/png/pdf/docx`, so a real voice note already fails with
   `לא הצלחתי לעבד את הקובץ הזה.` There is no transcription. It behaves worse than an honest
   "unsupported" reply because the error text implies DeniDin tried and the *file* was bad.

## Evidence (real prod incident, 2026-09-04 — the trigger for this feature)

During the v0.5.4 deploy, chat `120363210094632983@g.us` ("$$ גבייה אילה $$"), sender
"אילה 🦋". All times Israel local, from real prod audit log (`[AUDIT-IN]` / `[AUDIT-OUT]`):

| Time | Event |
|---|---|
| 10:35:20 | `textMessage` `3A2F324F5A148E7F7D58`: `"כמיר כף\nזמנכל ביטוח לאומי\nמכתב\n 3,000₪"` (garbled name + typo) |
| 10:35:45–10:35:59 | DeniDin recognized a fee agreement, **captured a `LedgerEvent` with client name `"כמיר כף"`**, replied *"נרשם הסכם שכר טרחה: לקוח: כמיר כף…"* |
| 10:36:01 | `editedMessage` `3A3F9992DBC6B052C485` (stanzaId → `3A2F324F5A148E7F7D58`): name corrected `"כמיר כף"` → `"עמיר כץ"`. → **"unsupported message type" auto-reply** |
| 10:36:02 | `editedMessage` `3A8B47BFBD044BB12351` (stanzaId → same original): typo corrected `"זמנכל"` → `"סמנכל"`. → **"unsupported message type" auto-reply** |

Net effect: the user visibly corrected a client's name from a garbled `"כמיר כף"` to the
correct `"עמיר כץ"`, and DeniDin (a) never registered the correction and (b) answered a
good-faith fix with two "not supported" messages.

## Research (payload shapes — official Green API docs, 2026-09-07)

Per `green-api.com/en/docs/api/receiving/notifications-format/incoming-message/…` (the user
explicitly accepted docs-based research here in place of a live capture; reaction-removal
shape is not documented, and is not needed because reactions are ignored outright):

**`editedMessage`** — delivers the *full* corrected text plus the original message id:
```json
"messageData": {
  "typeMessage": "editedMessage",
  "editedMessageData": { "textMessage": "<full new text>", "stanzaId": "<original idMessage>" }
}
```

**`deletedMessage`** — only the pointer, no text, no flag:
```json
"messageData": {
  "typeMessage": "deletedMessage",
  "deletedMessageData": { "stanzaId": "<deleted idMessage>" }
}
```

**`reactionMessage`** (ignored — shape recorded for completeness):
```json
"messageData": {
  "typeMessage": "reactionMessage",
  "extendedTextMessageData": { "text": "👍" },
  "quotedMessage": { "stanzaId": "<reacted msg id>", "participant": "<who>" }
}
```

Both `editedMessage` and `deletedMessage` carry a normal top-level `senderData` block (chatId,
sender, senderName, senderContactName) and a top-level unix `timestamp`.

## Clarifications (2026-09-07)

| # | Question | Answer |
|---|---|---|
| Q1 | Scope | **Minimal, self-contained.** No dependency on Feature 032 (reference resolution) or Feature 040 (ledger cancel/modify). 076 only routes and logs; ledger-event mutation stays Feature 040. |
| Q2 | `editedMessage` behavior | **Note the correction, no reply.** Persist the corrected text into the chat's session as a dated note; do **not** run an AI turn or send any WhatsApp reply. The model picks up the correction on the next real turn via the 14-day rolling window. |
| Q3 | `deletedMessage` behavior | Same shape: persist a dated "user deleted an earlier message" note into the session, no reply. |
| Q4 | Where the note is stored | A new `role="user"` `Message` appended via `SessionManager.add_message`, dated from the webhook's own `timestamp` (Israel local). **No mutation** of the referenced original `Message` — the original and the note both sit in the verbatim window, so the model reconciles them naturally. Stored-history annotation / `stanzaId` resolution is Feature 032 territory, out of scope. |
| Q5 | `audioMessage` | **Move to the canned "unsupported" reply.** Voice notes are not transcribed today (media pipeline rejects the format), so nothing is lost. Removed from `HANDLER_REGISTRY` and from `WhatsAppHandler.is_media_message`. `videoMessage` is left exactly as-is (unchanged). |
| Q6 | Canned reply text | Changed to exactly **`סוג הודעה לא נתמך`** (was: `"סוג הודעה זה אינו נתמך עדיין. אני תומך בטקסט, תמונות וקבצים."`). |
| Q7 | "Ignore completely" bucket | **Silent** — `log_inbound` (the existing verbatim inbound audit log) only, **no WhatsApp reply**. Applies to `reactionMessage`, `stickerMessage`, `locationMessage`, `liveLocationMessage`, `pollUpdateMessage`, `groupInviteMessage`, `pinInChatMessage`/`pinMessageResponse`, `keepInChat`, legacy `buttonsMessage`/`buttonsResponseMessage`, `quotedMessage`-only payloads, **and any `typeMessage` value never seen before** (the new default). |
| Q8 | Feature flag | **No feature flag.** The user explicitly declined one; the behavior change is direct. |
| Q9 | Acceptance tests | **No `billed`/`expensive` tests** — nothing in this feature calls OpenAI. Unit + integration only. Integration tests are **required for at least `editedMessage` and `deletedMessage`**. |
| Q10 | Immutable registry test | `test_denidin_dispatch.py::test_registry_contains_exactly_these_eight_types_no_more_no_less` (and the per-type asserts) are updated as part of this feature — the user has signed off on this change here. |

## Functional Requirements

- **FR-001** — A `editedMessage` webhook appends one `role="user"` `Message` to the chat's
  long-lived session, content `[הודעה קודמת נערכה] <editedMessageData.textMessage>`, timestamped
  `local_from_timestamp(event["timestamp"])`. No AI call. No WhatsApp reply. `message_id` is a
  fresh UUID (the note is a new record, not the original).
- **FR-002** — A `deletedMessage` webhook appends one `role="user"` `Message`, content
  `[המשתמש מחק הודעה קודמת]`. Same rules as FR-001 (dated, no AI call, no reply). The deleted
  `stanzaId` is written to the app log for traceability; it is not persisted on the `Message`.
- **FR-003** — Neither FR-001 nor FR-002 resolves, reads, or mutates the message referenced by
  `stanzaId`, and neither touches any `LedgerEvent`, pending approval, or Morning document.
- **FR-004** — `editedMessage` / `deletedMessage` from a chat with **no existing session** create
  the session (via `SessionManager.get_session`, same as any first message) and append the note.
- **FR-005** — `audioMessage`, `pollMessage`, `templateMessage`, `templateButtonsReplyMessage`,
  `listMessage`, `listResponseMessage` each produce exactly one WhatsApp reply with the text
  `סוג הודעה לא נתמך` and nothing else (no AI call, no session write).
- **FR-006** — Every other `typeMessage` not named above and not already handled (the pre-existing
  8 conversational/media types + `interactiveButtonsResponse` + the two new ones) produces **no
  WhatsApp reply at all**. `log_inbound` still records the raw webhook verbatim.
- **FR-007** — The canned-reply constant's value is exactly `סוג הודעה לא נתמך`. No caller
  constructs this string inline.
- **FR-008** — `WhatsAppHandler.is_media_message` no longer returns `True` for `audioMessage`.
  `videoMessage`, `imageMessage`, `documentMessage` are unchanged.
- **FR-009** — The `idMessage` de-duplication (`RecentNotificationDeduper`) applies to the new
  types exactly as it does to every other type — a redelivered `editedMessage` is not logged
  to the session twice.
- **FR-010** — `GreenAPIMessageSource` is constructed with a `message_types` list that includes
  every type this feature gives explicit behavior to (`editedMessage`, `deletedMessage`, and the
  six error-reply types), so they actually reach `dispatch_notification` rather than being
  filtered out by the library before dispatch.
- **FR-011** — `config/runtime_constitution.md` gains a short subsection telling the model how to
  read the two markers (`[הודעה קודמת נערכה] …` = prefer the corrected text; `[המשתמש מחק הודעה
  קודמת]` = an earlier message was retracted, don't act on its content) and that these markers
  are never themselves something to reply to.

## Non-Functional / Constraints

- No new config keys, no feature flag (Q8).
- Israel-local timestamps only (`src/utils/time_utils.py`).
- No monkey-patching; new handlers are plain functions in `denidin.py` registered in the
  dispatch table, mirroring every existing handler.
- The "no message type is silently *dropped*" invariant is deliberately **relaxed** to "no
  message type is silently *lost*" — `log_inbound` still captures everything; the change is that
  low-value types no longer trigger a user-facing reply. Recorded here and in
  `.github/ARCHITECTURE.md`.

## Touch points

- `apps/denidin-app/denidin.py` — `handle_edited_message`, `handle_deleted_message`,
  `handle_error_reply_message`, a silent `handle_ignored_message_default`; `HANDLER_REGISTRY`
  gains `editedMessage` / `deletedMessage`, loses `audioMessage`; new `ERROR_REPLY_TYPES` set;
  `dispatch_notification` checks `ERROR_REPLY_TYPES` before the catch-all; `CATCH_ALL_HANDLER`
  → silent; `__main__` `message_types` list extended (FR-010).
- `apps/denidin-app/src/constants/error_messages.py` — `UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES`
  value → `סוג הודעה לא נתמך` (name kept to avoid a churny rename across imports; a follow-up
  rename is out of scope).
- `apps/denidin-app/src/handlers/whatsapp_handler.py` — `is_media_message` drops `audioMessage`;
  `handle_unsupported_message` unchanged in shape (still sends the same constant).
- `apps/denidin-app/config/runtime_constitution.md` — FR-011 subsection.
- `apps/denidin-app/.github/ARCHITECTURE.md` — note the relaxed invariant + new handlers.
- `apps/denidin-app/tests/unit/test_denidin_dispatch.py` — registry asserts updated (Q10).
- New: `tests/unit/test_edited_deleted_handlers.py`,
  `tests/integration/test_edited_deleted_webhook_routing.py`,
  and additions to `tests/integration/test_media_webhook_routing.py` for the new error-reply /
  silent behavior.

## Out of scope

- `stanzaId` → stored-`Message` resolution (Feature 032).
- Cancelling/modifying a `LedgerEvent` from an edit/delete (Feature 040).
- Any *reaction* that carries meaning (e.g. 👍 as approval) — explicitly not wired; reactions
  are ignored.
- Coalescing bursts of new messages (Feature 067).
- Outbound edited/reaction/deletion sends (this is inbound handling only).
- Transcribing voice notes (would be its own feature; `audioMessage` just gets an honest
  "unsupported" reply here).
- Renaming `UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES`.
