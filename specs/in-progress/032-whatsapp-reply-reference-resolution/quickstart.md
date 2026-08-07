# Quickstart / Verification: WhatsApp Reply/Quote Reference Resolution

**Feature**: 032-whatsapp-reply-reference-resolution

This is the manual/E2E verification procedure — mirrors what the integration test
(`tests/integration/test_reply_resolution.py`, per plan.md's Project Structure) automates
with real webhook payloads dispatched through `bot.router`, per CONSTITUTION §V (no direct
method calls into internal components for the integration tier).

## Prerequisites

- `dev` environment running (`./scripts/run_all.sh dev` — requires explicit approval per
  CLAUDE.md, not run as part of this doc).
- A WhatsApp account able to message the dev instance's number.

## Steps

1. **Send an ordinary message** (no reply): e.g. "שלום". Confirm normal response — this is
   the US2 regression guard; behavior must be identical to before this feature.

2. **Send a message, then reply to it** with unrelated text (e.g. reply "מה?" to your own
   prior "שלום"). Confirm:
   - Normal conversational response (no crash, no unexpected behavior change).
   - (Requires log/data inspection) `data/sessions/{session_id}/messages/{message_id}.json`
     for the reply shows `resolved_reference.content` populated (plain text), pointing at the
     original "שלום" message, with no `ledger_events` (US1 Scenario 1/3 — nothing to attach).

3. **Send a fee-agreement-stating message** that captures a `LedgerEvent` (per Feature 033
   behavior — e.g. "X - הצעת שכר טרחה: 9,000 ₪"). Then **reply to that message** with
   unrelated text (NOT "לבטל" — that's Feature 040's concern, not this one).
   Confirm:
   - `resolved_reference` on the reply's stored `Message` includes `ledger_events` — the FULL
     structured `LedgerEvent` record(s) (client_name, amount, etc.), not just bare ids — and
     `content` is NOT also populated (mutually exclusive, data-model.md) — but no new
     `LedgerEvent`/cancellation is triggered by this feature alone (US1 Scenario 2; Feature 040
     territory is deciding what to DO with it — this feature only proves the data reaches the
     reply's stored record).

4. **Send an image**, wait for DeniDin's extraction response, then **reply to that image
   message**. Confirm:
   - `resolved_reference`'s `content` contains the FULL `extracted_text`/`document_analysis`
     from the original image (US1 Scenario 5) — verify by inspecting the stored JSON, not
     just the conversational reply (the AI's reply text won't necessarily echo it verbatim).
   - No new OpenAI vision-model call occurs as part of resolving the reply (check
     `logs/denidin.log` / `logs/dev/` for absence of a second vision-model call tied to the
     reply's request, beyond whatever the reply's own text needs).

5. **Wait past session expiry (24h)** (or use a short-TTL test session if available), then
   reply to a message from the now-expired/archived session. Confirm:
   - Resolution fails gracefully (`resolved_reference` absent), reply treated as an ordinary
     new message (US1 Scenario 7) — no crash, no stale/incorrect resolution.

## Automated Equivalent

`tests/integration/test_reply_resolution.py` should cover steps 1–4 with real webhook JSON
fixtures containing `messageData.extendedTextMessageData.quotedMessage.stanzaId`, dispatched
through `bot.router` exactly as a real Green API notification would arrive — per
`specs/done/001-whatsapp-chatbot-passthrough/contracts/green-api.md`'s documented shape.
Step 5 (session expiry) is better covered as a `tests/unit/test_session_manager.py` case
directly against `resolve_reply` with a pre-expired session fixture, rather than a real 24h
wait in an integration test.
