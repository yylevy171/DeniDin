# Phase 0 Research: Feature 030 (vCard Contact Card → Client Creation)

## Decision 1: Green API webhook shapes (fully confirmed, no live/sandbox test needed)

**Source**: Green API's official docs, fetched 2026-07-30 —
`https://green-api.com/en/docs/api/receiving/notifications-format/incoming-message/ContactMessage/`
and `.../ContactsArrayMessage/`.

**Single contact** — `typeMessage: "contactMessage"`:
```json
{
  "messageData": {
    "typeMessage": "contactMessage",
    "contactMessageData": {
      "displayName": "Victor Andreevich",
      "vcard": "BEGIN:VCARD\nVERSION:3.0\nN:Andreevich;Victor;;;\nFN:Victor Andreevich\n...\nEND:VCARD",
      "forwardingScore": 4,
      "isForwarded": true
    }
  }
}
```

**Multiple contacts shared at once** — a **distinct** `typeMessage`, NOT the same type with
multiple vCards inside it:
```json
{
  "messageData": {
    "typeMessage": "contactsArrayMessage",
    "messageData": {
      "contacts": [
        {"displayName": "Viktor Andreevich", "vcard": "BEGIN:VCARD\n...\nEND:VCARD"}
      ],
      "forwardingScore": 0,
      "isForwarded": false
    }
  }
}
```
Note the doubled `messageData` nesting under `contactsArrayMessage` — confirmed from the docs'
own example, not a transcription error. Every field the multi-contact case would need
(`.contacts`) lives one level deeper than the single-contact case's `.contactMessageData`.

**Rationale**: This resolves what was previously flagged in spec.md as needing live/sandbox
confirmation. Because the two cases are genuinely different `typeMessage` values, US3
(multi-contact decline) needs **zero vCard parsing** — it's a pure type check, exactly like every
existing router in `denidin.py` (`imageMessage` vs `documentMessage` vs ...) already dispatches on
`typeMessage` alone.

**Alternatives considered**: Originally assumed (spec.md v1) that multi-contact shares might
arrive as a single `contactMessage` with multiple `BEGIN:VCARD` blocks concatenated in one
`vcard` string, which would have required parsing vCard content just to detect the multi-contact
case. Rejected once the real docs confirmed a distinct `typeMessage` exists.

## Decision 2: vCard field extraction — no dedicated parser needed

**Decision**: Do not write a vCard-field-extraction parser (no `name`/`phone`/`email` regex/library
parsing in Python). Instead, forward the raw `vcard` string (+ `displayName`) into the exact same
`AIHandler` conversational pipeline used for `textMessage`, framed with a short instruction so the
model knows it's looking at a shared contact card. The model already reliably extracts
structured fields from free text for `add_client` (Feature 026, REQ-CLIENT-012's "ask for
whatever's missing" behavior) — a vCard's `N`/`FN`/`TEL`/`EMAIL` lines are at least as
structured as typed prose, and the model has no trouble reading them directly.

**Rationale**: Confirmed via the real fixture
(`apps/denidin-app/tests/fixtures/contacts/00005372-גיל ברטל .vcf`) that the fields we care about
(name, phone) are trivially legible vCard lines (`FN:גיל ברטל`, `TEL;...:+972 50-795-1824`) — no
ambiguity a hand-rolled parser would meaningfully resolve better than the model already does for
typed text. This also means zero new dependency (no `vobject`/`vcard` parsing library) and zero
new validation code — 100% of `add_client`'s existing validation/normalization/approval pipeline
is reused unchanged (see [[Decision 3]]).

**Alternatives considered**: A dedicated Python vCard parser (e.g. the `vobject` library) that
extracts structured `name`/`phone`/`email` and injects them as pre-parsed fields into the AI
request (similar to how `ImageExtractor`/`PDFExtractor` produce structured `document_analysis`).
Rejected: adds a new dependency and a new parsing/validation surface for a format (vCard) that's
simple enough for the model to read directly, when the project already leans on the model for
exactly this kind of extraction elsewhere (typed `add_client` requests).

## Decision 3: No new add_client/approval-gate logic

**Decision**: `add_client` is already in `AIHandler.APPROVAL_REQUIRED_MCP_TOOLS`
(`apps/denidin-app/src/handlers/ai_handler.py:47-56`, Feature 026), with an existing
"ask for missing name/email/phone before proceeding" prompt-level behavior and an existing
`PendingApprovalManager`/`mcp_approval_request` two-turn confirm flow. Feature 030 introduces
**zero new code** in this area — it only needs to get vCard content in front of the model in a
turn that's otherwise indistinguishable from a typed `add_client` request.

**Rationale**: Directly satisfies the "confirm first, ask for missing mandatory fields" decision
(spec.md Clarifications, 2026-07-30) without building any new confirmation mechanism.

## Decision 4: Phone normalization — already handled

**Decision**: No new phone-normalization code. `_normalize_israeli_phone`
(`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py:886`) already runs inside `add_client`,
and was verified directly against the real fixture's phone value:
- `TEL` value `"+972 50-795-1824"` → normalizes to `"050-7951824"`
- `waid` param value `"972507951824"` → normalizes to the same `"050-7951824"`

Either representation, extracted by the model from the raw vCard text, produces the correct
result once it reaches `add_client` — no new code path needed.

## Decision 5: Router design — new routes, minimal duplication

**Decision**:
- Add `@bot.router.message(type_message='contactMessage')` → a new handler that reuses
  `handle_text_message`'s existing turn-processing logic (group-mention check → `AIHandler` →
  send response), sourcing its "text" from the vCard's `displayName`/`vcard` content instead of
  `textMessageData`. Concretely: extract the shared turn-processing body of `handle_text_message`
  (`denidin.py:292-384`) into a private helper (e.g. `_process_conversational_message`) called by
  both handlers, rather than duplicating ~90 lines of try/except/tracking boilerplate.
- Add `@bot.router.message(type_message='contactsArrayMessage')` → a new, much simpler handler
  that replies directly with the "one at a time" friendly message — no `AIHandler` call, no
  `WhatsAppMessage`/`AIRequest` construction at all (mirrors how `handle_unsupported_message_default`
  replies directly without invoking the AI pipeline).
- `WhatsAppMessage.from_notification` (`apps/denidin-app/src/models/message.py:26`) gets a new
  branch for `typeMessage == 'contactMessage'`, alongside the existing `extendedTextMessage` vs.
  default branch, building `text_content` as a short framing + the raw vCard text (see Decision 2).
- `WhatsAppHandler.validate_message_type` (`whatsapp_handler.py:61`) gets `'contactMessage'` added
  to its accepted types (alongside `textMessage`/`extendedTextMessage`).

**Rationale**: Mirrors the existing dispatcher pattern exactly (each Green API `typeMessage` gets
its own router registration — same shape as `imageMessage`/`documentMessage`/etc.), while
avoiding new duplication of the conversational-turn boilerplate that already exists once for text
messages.

**Alternatives considered**: Routing `contactMessage` by adding it to `handle_text_message`'s own
`type_message=[...]` list directly (no new handler function at all). Rejected: `contactMessage`
notifications don't carry a `textMessageData`/`extendedTextMessageData` at all, so
`from_notification` would need type-specific branching regardless, and a same-named router with
mixed semantics (text vs. contact card) is less legible than a small, clearly-named second
handler that happens to share underlying logic via a helper.

## Decision 6: runtime_constitution.md guidance

**Decision**: Add prompt-level guidance (mirrors the existing `add_client` field-requirement
guidance from Feature 026) teaching the model: "A shared WhatsApp contact card (for a
godfather/admin) is a likely request to add that person as a Morning client — extract
name/phone/email from the vCard content and follow the existing `add_client` flow (ask for
whatever's missing, confirm before creating)."

**Rationale**: Without this, the model might treat a shared contact card as inert/decorative
content rather than actionable — the constitution is the mechanism this codebase already uses to
teach the model what a given input *means* (e.g. existing invoice_id-resolution and add_client
field-requirement guidance).

## Outstanding (not blocking implementation, verify during quickstart/manual testing)

- The exact WhatsApp client behavior for what counts as a "no email" vs. "has email" real device
  contact wasn't independently re-verified beyond the one real fixture — the fixture is treated as
  representative (per its own README), not exhaustively proven across every phone/OS contact app.
  No code depends on email being present or absent structurally; this is a documentation
  confidence note only.
