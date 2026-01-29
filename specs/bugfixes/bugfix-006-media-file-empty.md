# Bugfix Spec: Media Flow Integration - File Empty Issue

## Bug ID
bugfix-006-media-file-empty

## Title
Media Flow Integration: File Empty Error in Real Life Test

## Status
Open

## Date Opened
2026-01-29

## Reported By
yylevy171

## Affected Area
- Integration: Media Flow
- File Handling/Analysis

## Description
In a real-life test of the media flow integration, the system returns a "file empty" error, even though the file is not empty. This issue was observed in the integration test logs and is reproducible in production-like scenarios. The previous bugfix attempt did not resolve the problem.

## Steps to Reproduce
1. Run the integration test for media flow with a real media file (not a synthetic test file).
2. Observe the log output.
3. The system reports "file empty" unexpectedly.

## Expected Behavior
- The system should correctly detect and process non-empty media files.
- "File empty" should only be reported for truly empty files.

## Actual Behavior
- The system reports "file empty" for non-empty files in real-life scenarios.

## Impact
- Media files are not processed as expected.
- User experience is negatively affected.

## Evidence
- Production log file: `logs/denidin.log` (line 15278)
- Log shows: `Processing media message: unknown () from 972522968679@c.us`
- Error: `Media processing failed: File is empty (0 bytes)`
- Green API documentation: https://green-api.com/en/docs/api/receiving/notifications-format/incoming-message/ImageMessage/

## Test Gap Analysis

### Why Tests Didn't Catch This

**Root cause: Integration tests use INCORRECT webhook payload structure**

The test file `tests/integration/test_media_webhook_routing.py` DOES call the production webhook handler path:
```python
# Line 137: test_image_message_user_gets_response()
handle_image_message(notification)  # ✓ Calls production code
```

Which calls:
```python
# denidin.py:393
denidin_app.whatsapp_handler.handle_media_message(notification)  # ✓ Production path
```

**However, the test mock uses WRONG webhook structure:**

```python
# tests/integration/test_media_webhook_routing.py:37-51 (FakeNotification)
self.event = {
    'messageData': {
        'typeMessage': message_type,
        'downloadUrl': 'https://example.com/media.jpg',    # ❌ Should be in fileMessageData
        'fileName': 'test.jpg',                             # ❌ Should be in fileMessageData
        'mimeType': 'image/jpeg',                          # ❌ Should be in fileMessageData
        'fileSize': 1024,                                  # ❌ Should be in fileMessageData (and doesn't exist in real API)
        'caption': ''
    }
}
```

**Correct Green API structure:**
```python
{
    'messageData': {
        'typeMessage': 'imageMessage',
        'fileMessageData': {                               # ✓ Nested object
            'downloadUrl': 'https://...',
            'fileName': 'test.jpg',
            'mimeType': 'image/jpeg'
            # Note: fileSize NOT provided by Green API
        }
    }
}
```

**Why the bug wasn't caught:**
- Test mock provides `fileSize: 1024` directly in `messageData`
- Production code reads `message_data.get('fileSize', 0)` and gets `1024` from the wrong location
- Test passes because mock structure accidentally works with buggy code
- Real Green API webhooks have nested structure and no `fileSize`, causing `0` default → "file empty" error

**The test mock and the buggy code have the SAME mistake** - both assume flat structure instead of nested `fileMessageData`.

## Root Cause Analysis

### Confirmed Root Cause
**Location:** `src/handlers/whatsapp_handler.py:265-268`

The code incorrectly extracts file metadata from the Green API webhook payload. According to [Green API documentation](https://green-api.com/en/docs/api/receiving/notifications-format/incoming-message/ImageMessage/), file metadata is nested inside `messageData.fileMessageData`, but the code looks for it directly in `messageData`.

**Incorrect extraction:**
```python
# src/handlers/whatsapp_handler.py:265-268
file_url = message_data.get('downloadUrl', '')        # ❌ WRONG
filename = message_data.get('fileName', 'unknown')     # ❌ WRONG  
mime_type = message_data.get('mimeType', '')           # ❌ WRONG
file_size = message_data.get('fileSize', 0)            # ❌ WRONG - also doesn't exist in API
```

**Correct Green API webhook structure:**
```json
{
  "messageData": {
    "typeMessage": "imageMessage",
    "fileMessageData": {
      "downloadUrl": "https://...",
      "caption": "Image",
      "fileName": "example.jpg",
      "mimeType": "image/jpeg"
    }
  }
}
```

**Note:** Green API does NOT provide `fileSize` in the webhook. The file must be downloaded first to determine its size.

### Impact Chain
1. Code reads `messageData.get('fileSize', 0)` → returns `0` (field doesn't exist)
2. `MediaFileManager.validate_file_size(0)` raises `ValueError("File is empty (0 bytes)")`
3. User sees error message even though file is valid

### Production Evidence
```
2026-01-29 12:19:20 - Processing media message: unknown () from 972522968679@c.us
2026-01-29 12:19:20 - Media processing failed: File is empty (0 bytes)
```

Notice: `filename="unknown"`, `mime_type=""` (empty parentheses) - all defaults were used.

## Acceptance Criteria
- [x] The bug is reproducible in a test
- [ ] A failing test is added to cover the scenario
- [x] The root cause is identified and documented
- [ ] The bug is fixed and the test passes
- [ ] No regression in related media flow functionality

## Test Proposal

### Integration Test: Fix FakeNotification to Use Correct Green API Structure

**File:** `tests/integration/test_media_webhook_routing.py` (existing file - FIX IT)

**Problem:** The existing `FakeNotification` class uses INCORRECT webhook structure (flat instead of nested).

**Fix Required:**

**Current (WRONG) structure in FakeNotification:**
```python
self.event = {
    'messageData': {
        'typeMessage': message_type,
        'downloadUrl': 'https://example.com/media.jpg',    # ❌ Wrong location
        'fileName': 'test.jpg',                             # ❌ Wrong location
        'mimeType': 'image/jpeg',                          # ❌ Wrong location
        'fileSize': 1024,                                  # ❌ Wrong location & doesn't exist in API
        'caption': ''
    }
}
```

**Correct Green API structure (what FakeNotification SHOULD use):**
```python
self.event = {
    'messageData': {
        'typeMessage': message_type,
        'fileMessageData': {                               # ✓ Nested object
            'downloadUrl': 'https://example.com/media.jpg',
            'fileName': 'test.jpg',
            'mimeType': 'image/jpeg',
            'caption': ''
        }
        # Note: No fileSize - Green API doesn't provide it
    },
    'senderData': {
        'sender': '972522968679@c.us',
        'senderName': 'Test User'
    }
}
```

**Test Approach (NO MOCKING per CONSTITUTION §V):**
1. Fix `FakeNotification` to use correct nested Green API webhook structure
2. Run existing test `test_image_message_user_gets_response()`
3. Test will call REAL `handle_image_message()` → REAL `whatsapp_handler.handle_media_message()`
4. **Expected to FAIL** with production code (extracts from wrong location, gets defaults)
5. After fix: **Expected to PASS** (extracts from correct nested location)

**Why this is NOT mocking:**
- `FakeNotification` is a REAL notification object implementing the Notification interface
- It simulates the REAL Green API webhook payload structure
- Test calls REAL handlers, REAL routers, REAL application code
- Only external service (Green API download URL) is fake (per CONSTITUTION §V: "MUST mock external services")
- This is integration testing from user perspective: "User sends imageMessage → Does bot respond correctly?"

## References
- `.github/CONSTITUTION.md`
- `.github/METHODOLOGY.md`
- `specs/bugfixes/README.md`
- `tests/integration/test_media_flow_integration.py`

## Next Steps
1. Investigate and document the root cause.
2. Add a failing test that reproduces the issue.
3. Implement a fix following TDD/BDD workflow.
4. Validate with real-life file scenario.
5. Document the fix and update the bug status.
