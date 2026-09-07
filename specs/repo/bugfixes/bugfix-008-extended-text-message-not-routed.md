# Bugfix Spec: Forwarded/Quoted Text Messages Not Routed or Extracted

## Bug ID
bugfix-008-extended-text-message-not-routed

## Title
Forwarded text messages (`extendedTextMessage`) are rejected as "unsupported" and, even if routed, their text would not be extracted

## Status
Fixed — verified, ready for review/PR

## Date Opened
2026-07-07

## Reported By
yaron (live production observation)

## Affected Area
- `denidin.py` (Green API router registration)
- `src/models/message.py` (`WhatsAppMessage.from_notification`)
- `src/handlers/whatsapp_handler.py` (`validate_message_type`)

## Description
A simple forwarded WhatsApp text message sent to the live bot triggered the "unsupported message type" auto-reply instead of being processed as a normal text message. Observed live in `logs/denidin.log`:

```
2026-07-07 21:31:22 - src.handlers.whatsapp_handler - INFO - Sending unsupported message auto-reply to Yaron Levy for extendedTextMessage
```

Green API reports plain text as `typeMessage: "textMessage"`, but text with extra metadata — forwarded messages, quoted replies, and messages with link previews — is reported as `typeMessage: "extendedTextMessage"`, with the body nested under `messageData.extendedTextMessageData.text` instead of `messageData.textMessageData.textMessage`.

## Steps to Reproduce
1. Send (or forward) a text message to the bot via WhatsApp such that Green API classifies it as `extendedTextMessage` (forwarding, quoting/replying, or a message containing a URL preview all trigger this).
2. Observe the bot's response.

## Expected Behavior
- Forwarded/quoted text messages should be processed identically to plain text messages: routed to the AI handler, with the correct text content extracted, and a real AI-generated reply sent back.

## Actual Behavior
- The bot replies with the generic "unsupported message type" auto-reply and never processes the message content.

## Root Cause Analysis

Two independent defects, both required to fully fix the behavior:

**1. Missing router registration (`denidin.py:286`)**
Only `@bot.router.message(type_message="textMessage")` is registered, pointing at `handle_text_message`. There is no registration for `type_message="extendedTextMessage"`. The `whatsapp_chatbot_python` router falls through to the catch-all `@bot.router.message()` handler (`denidin.py:444`, `handle_unsupported_message_default`), which unconditionally calls `whatsapp_handler.handle_unsupported_message(notification)` and sends the auto-reply — the message never reaches `handle_text_message` at all.

Notably, `WhatsAppHandler.validate_message_type()` (`src/handlers/whatsapp_handler.py:73`) *already* explicitly treats `extendedTextMessage` as valid:
```python
if message_type != 'extendedTextMessage' and message_type != "textMessage":
```
This check is dead code for this scenario — it never executes because the message is intercepted by the catch-all router before `validate_message_type` is ever called. This strongly suggests the original intent was to support `extendedTextMessage`, but the router registration was never added to match.

**2. Text extraction only reads `textMessageData` (`src/models/message.py:43-44`)**
```python
text_message_data = message_data.get('textMessageData', {})
text_content = text_message_data.get('textMessage', '')
```
For `extendedTextMessage` notifications, Green API nests the body under `messageData.extendedTextMessageData.text`, not `messageData.textMessageData.textMessage`. Even if defect #1 is fixed and the message is routed to `handle_text_message`, `text_content` would resolve to `''` (empty string), producing an empty/garbage AI request instead of the forwarded message's actual content.

**Conclusion**: Fixing only the router (defect #1) without fixing extraction (defect #2) would silently swap one bug (auto-reply) for another (empty message sent to the AI). Both must be fixed together.

**Confirming evidence from the SDK itself**: `whatsapp_chatbot_python`'s own `Notification.get_message_text()` (`.venv/lib/python3.9/site-packages/whatsapp_chatbot_python/manager/handler.py`) already branches correctly:
```python
if type_message == "textMessage":
    return message_data["textMessageData"]["textMessage"]
elif type_message == "extendedTextMessage" or type_message == "quotedMessage":
    return message_data["extendedTextMessageData"]["text"]
```
The app's `WhatsAppMessage.from_notification` reimplements text extraction manually instead of delegating to this, and the reimplementation only ported the `textMessage` branch. The SDK's `TypeMessageFilter` (`whatsapp_chatbot_python/filters.py`) also natively accepts a list for `type_message`, so router registration can cover both types with a single decorator.

## Proposed Fix Approach
1. In `denidin.py`, change the existing registration to `@bot.router.message(type_message=["textMessage", "extendedTextMessage"])` on `handle_text_message` (single decorator, list form — natively supported by `TypeMessageFilter`, no need for a second handler function).
2. Update `WhatsAppMessage.from_notification` to extract text from `extendedTextMessageData.text` when `typeMessage == "extendedTextMessage"`, falling back to the existing `textMessageData.textMessage` path for plain `textMessage`.

## Impact
- Any forwarded message, quoted reply, or link-preview text message sent to the bot is currently unusable — user receives a generic unsupported-type reply instead of an AI response.

## Evidence
- `logs/denidin.log` (2026-07-07 21:31:22): live auto-reply for `extendedTextMessage` from real WhatsApp traffic.
- `denidin.py:286-303` — router registrations, only `textMessage` mapped.
- `denidin.py:444-458` — catch-all handler that intercepts `extendedTextMessage`.
- `src/handlers/whatsapp_handler.py:60-77` — `validate_message_type` already treats `extendedTextMessage` as valid (dead code today).
- `src/models/message.py:26-74` — `from_notification` only reads `textMessageData`.

## Test Gap Analysis

**Why didn't existing tests catch this?**
- `grep -rl "extendedTextMessage"` across `tests/` returns zero matches — no test, unit or integration, has ever constructed a notification with `typeMessage: "extendedTextMessage"`. Every text-message fixture in `tests/unit/test_message.py`, `tests/fixtures/sample_messages.json`, and the integration suite uses `textMessage` only.
- `tests/integration/test_media_webhook_routing.py` (the file that documents itself as testing "bot.router → handler" from the user's perspective) actually calls handler functions directly (e.g. `handle_image_message(notification)`), bypassing `bot.router` entirely. So even a hypothetical `extendedTextMessage` test written in that existing style would not have caught defect #1 (missing router registration) — it would only ever catch defect #2 (extraction), because it never exercises the SDK's real `Router`/`Observer`/`Handler` filter-matching machinery that decides *which* handler a given `typeMessage` reaches.

**Missing test scenarios**:
1. A routing-level test that dispatches through the *real* `bot.router.message.handlers` filter-matching (no mocking of internal components — using the SDK's own `Handler.check_event`) to prove an `extendedTextMessage` notification resolves to `handle_text_message`, not the catch-all `handle_unsupported_message_default`.
2. A unit test proving `WhatsAppMessage.from_notification` extracts the correct `text_content` for `extendedTextMessage` notifications (currently returns `''`).

## Failing Tests Added

1. **`tests/unit/test_message.py::TestWhatsAppMessage::test_from_notification_extracts_extended_text_message_body`** — builds an `extendedTextMessage` notification (matching Green API's real nested shape) and asserts `text_content` equals the forwarded text. **Currently fails**: `text_content` resolves to `''` because `from_notification` only reads `textMessageData`.
2. **`tests/integration/test_media_webhook_routing.py::TestMediaWebhookRoutingUserPerspective::test_extended_text_message_routes_to_text_handler_not_unsupported`** — uses the real, production `denidin.bot.router.message.handlers` list (populated by the actual `@bot.router.message(...)` decorators at module import) and the SDK's real `Handler.check_event`/`Notification` classes (no mocking) to determine which registered handler would fire first for an `extendedTextMessage` event, and asserts it is `handle_text_message`, not `handle_unsupported_message_default`. **Currently fails**: no handler is registered for `extendedTextMessage`, so the catch-all matches.

Both tests were run and confirmed **failing** against current code before any fix was applied (see command output in this session).

## Fix Implemented
1. `denidin.py:286` — registration changed to `@bot.router.message(type_message=["textMessage", "extendedTextMessage"])` on `handle_text_message` (list form, natively supported by the SDK's `TypeMessageFilter`).
2. `src/models/message.py` — `WhatsAppMessage.from_notification` now branches on `typeMessage`: reads `extendedTextMessageData.text` for `extendedTextMessage`, falls back to the existing `textMessageData.textMessage` path otherwise.

## Verification
- Both previously-failing tests now pass:
  - `tests/unit/test_message.py::test_from_notification_extracts_extended_text_message_body`
  - `tests/integration/test_media_webhook_routing.py::test_extended_text_message_routes_to_text_handler_not_unsupported`
- Full non-expensive suite: `492 passed, 11 deselected` — no regressions to plain `textMessage`, media, or unsupported-type handling.

## Acceptance Criteria
- [x] Root cause confirmed and approved (this document).
- [x] Test-gap analysis documented.
- [x] Failing test(s) added reproducing both defects (routing + extraction) before any fix.
- [x] Human approval gate (tests) — approved.
- [x] Fix implemented for both defects.
- [x] Previously-failing tests pass; full suite passes; no regression to plain `textMessage` handling.

## References
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
- `.github/CONSTITUTION.md` §V (integration test / router coverage rationale — this bug is the same class as the documented missing-`imageMessage`-router precedent)
- `specs/bugfixes/README.md`

## Next Steps
1. **Human approval gate (root cause)** — awaiting sign-off on the above analysis and proposed fix approach before any test is written.
2. Test-gap analysis: why existing tests didn't catch this (no integration test currently dispatches an `extendedTextMessage` notification through `bot.router`).
3. Write failing test(s).
4. Human approval gate (tests).
5. Implement minimal fix.
6. Verify.
