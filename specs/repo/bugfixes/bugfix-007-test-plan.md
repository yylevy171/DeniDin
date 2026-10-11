# Bugfix-007: Test Plan - Failing Tests Documentation

## Tests Written (Step 4 - BDD Workflow)

### Unit Tests (test_whatsapp_handler_media.py)

**New Test Class: `TestGreenApiWebhookStructure`**

Tests that will FAIL (demonstrating the bug):

1. ✅ `test_image_notification_has_required_chatid` - WILL FAIL
   - Validates image notification has `chatId` in `senderData`
   - Current fixture: MISSING `chatId`
   
2. ✅ `test_document_notification_has_required_chatid` - WILL FAIL
   - Validates document notification has `chatId` in `senderData`
   - Current fixture: MISSING `chatId`

3. ✅ `test_chatid_matches_sender_for_personal_chat` - WILL FAIL
   - Validates that for 1-on-1 chats, `chatId` == `sender`
   - Current fixture: MISSING `chatId`

4. ✅ `test_all_required_senderdata_fields_present` - WILL FAIL
   - Validates all mandatory Green API fields exist
   - Current fixture: MISSING `chatId`

### Integration Tests (test_media_webhook_routing.py)

**New Test Class: `TestGreenApiWebhookStructureCompliance`**

Tests that will PASS (factory methods already include chatId):

1. ✅ `test_image_notification_has_required_chatid_field` - WILL PASS
   - Tests `GreenApiNotification.create_image_message()` includes `chatId`
   - Factory method: ALREADY INCLUDES `chatId` ✓

2. ✅ `test_document_notification_has_required_chatid_field` - WILL PASS
   - Tests `GreenApiNotification.create_document_message()` includes `chatId`
   - Factory method: ALREADY INCLUDES `chatId` ✓

3. ✅ `test_existing_integration_test_notifications_validate` - WILL PASS
   - Validates that integration test notification structures are correct
   - Using factory methods: ALREADY CORRECT ✓

---

## Current Status Analysis

### ✅ CORRECT (No fixes needed):
- `src/models/green_api.py` - Factory methods include `chatId`
- Integration tests using factory methods - Already correct
- `SenderData` model - Has `chatId` as required field

### ❌ BROKEN (Needs fixing):
- Unit test fixtures in `test_whatsapp_handler_media.py`:
  - `mock_notification_image` - MISSING `chatId`
  - `mock_notification_document` - MISSING `chatId`
  - `mock_notification_video` - MISSING `chatId`
  - `mock_notification_audio` - MISSING `chatId`
  
- Unit test fixtures in `test_whatsapp_handler_errors.py` - Need to check

- Any other test files creating manual notification objects

---

## Next Steps

### Step 5: Run Tests to Confirm Failures

```bash
# Unit tests - should FAIL
pytest tests/unit/test_whatsapp_handler_media.py::TestGreenApiWebhookStructure -xvs

# Integration tests - should PASS
pytest tests/integration/test_media_webhook_routing.py::TestGreenApiWebhookStructureCompliance -xvs
```

### Step 6: Fix Test Fixtures

Once failures are confirmed, fix all unit test fixtures by adding `chatId`:

```python
'senderData': {
    'chatId': '972501234567@c.us',  # ADD THIS
    'sender': '972501234567@c.us',
    'senderName': 'David Cohen'
}
```

### Step 7: Verify Fix

After adding `chatId` to all fixtures:
- All unit tests should PASS
- All integration tests should still PASS
- Real WhatsApp media messages should receive responses

---

## Files to Fix

1. `tests/unit/test_whatsapp_handler_media.py`:
   - Line 43: `mock_notification_image` fixture
   - Line 67: `mock_notification_document` fixture
   - Line 91: `mock_notification_video` fixture
   - Line 114: `mock_notification_audio` fixture
   - Line 230: `test_caption_extraction_from_webhook` notification
   - Line 269: `test_missing_caption_sends_empty_string` notification

2. Check and fix if needed:
   - `tests/unit/test_whatsapp_handler_errors.py`
   - `tests/unit/test_message.py`
   - `tests/integration/test_message_flow.py`
   - Any other files creating notifications manually

---

## Success Criteria

- [ ] Unit tests FAIL initially (demonstrating bug)
- [ ] Integration tests PASS (factory methods correct)
- [ ] After fix: All unit tests PASS
- [ ] After fix: All integration tests still PASS
- [ ] Real media messages receive responses
