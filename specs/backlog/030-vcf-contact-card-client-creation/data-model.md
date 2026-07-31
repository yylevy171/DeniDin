# data-model.md — Feature 030 (vCard Contact Card → Client Creation)

No new persisted entity. Morning remains the sole source of truth for client records via the
existing `Client` model (`apps/morning-mcp-app/src/denidin_mcp_morning/models.py:58`, unchanged by
this feature — see `specs/done/026-client-management/data-model.md`). This feature adds a new
*source* of conversational input (a shared contact card instead of typed text), not a new stored
shape.

## Incoming webhook shapes (Green API, external — see `contracts/`)

Two distinct `typeMessage` values, per `research.md` Decision 1 (confirmed against Green API's
official docs, 2026-07-30):

### `contactMessage` (single contact)
- `messageData.contactMessageData.displayName`: string
- `messageData.contactMessageData.vcard`: string (raw vCard 3.0 text)
- `messageData.contactMessageData.forwardingScore`: integer (unused by this feature)
- `messageData.contactMessageData.isForwarded`: boolean (unused by this feature)

### `contactsArrayMessage` (multiple contacts)
- `messageData.messageData.contacts`: array of `{displayName: string, vcard: string}`
- `messageData.messageData.forwardingScore` / `.isForwarded`: unused

Only `typeMessage` itself is inspected for `contactsArrayMessage` (US3) — its `.contacts` payload
is never parsed, since the feature declines the whole message unconditionally.

## `WhatsAppMessage.text_content` framing (new branch, `contactMessage` only)

Not a new dataclass field — `WhatsAppMessage.text_content` (existing field, `message.py:19`) gets
a new value-construction branch for `typeMessage == 'contactMessage'`, alongside the existing
`extendedTextMessage` vs. default branch (`message.py:49-52`). Per `research.md` Decision 2, no
dedicated vCard parser exists — the branch builds a short natural-language framing string
containing the raw `displayName` and `vcard` text verbatim, e.g.:

```text
[שותף כרטיס איש קשר בוואטסאפ]
שם תצוגה: {displayName}
תוכן vCard:
{vcard}
```

This flows into `AIHandler` exactly as any other `text_content` would — the model reads the raw
vCard lines (`N`/`FN`/`TEL`/`EMAIL`) itself. `message_type` is set to `'contactMessage'` (existing
field, `message.py:21`) so downstream code/tests can distinguish a contact-card-sourced turn from
a typed one if ever needed, without it affecting how `AIHandler` processes the turn.

## Vcard-derived fields (conceptual only — not a code-level type)

`name`/`phone`/`email` as understood by the model reading the framed `text_content` above map
1:1 onto `add_client`'s existing three required parameters
(`apps/morning-mcp-app/src/denidin_mcp_morning/server.py:278-286`) — no new schema, no new
validation. Per `research.md` Decision 4, whatever phone representation the model extracts from
the vCard (`TEL` value or `waid` param) is normalized by the existing
`_normalize_israeli_phone` unchanged.

## No new local storage, no new config field

- No new file, no new `data_root` subpath, no new `config.feature_flags` entry (per spec.md
  Clarifications, this is additive conversational-input handling, not a new persisted capability
  needing a toggle — mirrors Feature 021/026's precedent of shipping additive tool-input paths
  without a flag).
