# Bugfix-007: Media Message Responses Not Reaching Users

**Date**: January 29, 2026  
**Status**: In Progress  
**Branch**: `bugfix/007-media-response-missing-chatid`

---

## Bug Description

Media message responses (images, documents) are not being delivered to users. The system processes the media successfully and generates a summary, but users never receive the response.

**Observed Behavior**:
- Logs show: "Sending media processing summary to 972522968679@c.us"
- No error messages
- User never receives the response
- Text messages work correctly

**Expected Behavior**:
- Users should receive media processing summaries via WhatsApp
- Responses should arrive with same reliability as text message responses

---

## Root Cause

Test fixtures and webhook handling code are missing the required `chatId` field in `senderData`. According to Green API documentation, the `notification.answer()` method requires `chatId` to determine where to send the response.

**Evidence**:
1. Green API docs specify `senderData` MUST contain both `chatId` and `sender`:
   ```json
   "senderData": {
       "chatId": "79001234567@c.us",
       "sender": "79001234567@c.us",
       "chatName": "John",
       "senderName": "John",
       "senderContactName": "John Doe"
   }
   ```

2. Our test fixtures only have `sender` and `senderName` - missing `chatId`

3. The `SendMessage` API requires `chatId` parameter to send messages

4. `notification.answer()` fails silently when `chatId` is missing

**Affected Files**:
- `tests/unit/test_whatsapp_handler_media.py` - test fixtures missing `chatId`
- `tests/integration/test_media_webhook_routing.py` - test fixtures missing `chatId`
- `tests/unit/test_whatsapp_handler_errors.py` - test fixtures missing `chatId`

---

## Test Gap Analysis

**Why Didn't Tests Catch This?**

1. **Unit tests mock `notification.answer()`** - Never actually test if the notification object is valid for Green API
2. **Integration tests don't verify webhook structure** - No validation that test data matches Green API spec
3. **No tests validate response delivery** - Tests check that `answer()` is called but not that it would work in production
4. **Test fixtures don't match real webhooks** - Missing mandatory fields from Green API specification

**Missing Test Cases**:
1. Test that `senderData` contains all required Green API fields
2. Test that `notification.answer()` receives a notification with valid `chatId`
3. Test that validates webhook notification structure matches Green API spec
4. Integration test verifying media responses reach the correct recipient

---

## Fix Strategy

1. **Update Test Fixtures** (All locations):
   - Add `chatId` field to all `senderData` objects in test fixtures
   - Ensure test data matches Green API webhook specification exactly
   - Use realistic values: `chatId` typically equals `sender` for 1-on-1 chats

2. **Add Validation Tests**:
   - Test that verifies `senderData` structure in media notifications
   - Test that `chatId` is present before calling `notification.answer()`
   - Test that validates webhook data against Green API spec

3. **Update Documentation**:
   - Document `chatId` vs `sender` difference in `SenderData` model
   - Add comments explaining Green API requirements

---

## Implementation Plan

### Phase 1: Write Failing Tests ✅
- [ ] Create test that validates `senderData` has `chatId`
- [ ] Create test that `notification.answer()` is called with valid `chatId`
- [ ] Run tests - they should FAIL

### Phase 2: Fix Test Fixtures
- [ ] Update all media message fixtures to include `chatId`
- [ ] Verify fixtures match Green API webhook spec

### Phase 3: Verify Fix
- [ ] Run tests - they should PASS
- [ ] Test with real WhatsApp messages
- [ ] Confirm users receive media responses

---

## Testing Checklist

- [ ] Unit tests pass with corrected fixtures
- [ ] Integration tests pass
- [ ] Real media message → User receives response
- [ ] Group chat media → Response goes to correct chat
- [ ] Error cases still handled correctly

---

## References

- Green API Webhook Format: https://green-api.com/en/docs/api/receiving/notifications-format/incoming-message/ImageMessage/
- SendMessage API: https://green-api.com/en/docs/api/sending/SendMessage/
- `SenderData` Model: `src/models/green_api.py`
