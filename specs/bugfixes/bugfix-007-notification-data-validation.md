# Bugfix 007: Notification Data Structure Validation

**Status**: In Progress  
**Priority**: P0  
**Created**: 2026-01-29  

## Bug Description

Media message responses are not being sent to users. Logs show attempts to send, but users receive nothing.

## Root Cause

We are not validating that notification objects have the required `chatId` field before calling `notification.answer()`. The Green API SDK requires `chatId` in `senderData` to route responses correctly, but we're not enforcing this structure.

**The Real Problem**:
- We assume Green API works (it does)
- We don't validate the data structure we send to it
- Test fixtures create notifications WITHOUT `chatId`
- No validation catches this before `notification.answer()` is called

## Solution Approach

### 1. Well-Define the Response Data Model

Create a `NotificationResponse` model that defines what we send to Green API:
- **Mandatory fields**: `chatId` (where to send)
- **Optional fields**: message content, formatting, etc.

### 2. Create Validation Method

Add validation that checks notification objects BEFORE calling `.answer()`:
- Verify `senderData` exists
- Verify `senderData.chatId` exists and is non-empty
- Raise clear error if validation fails

### 3. Write Failing Tests

Create tests that instantiate notification objects **AS THEY ARE CREATED NOW** in our code:
- Test fixtures (unit tests) - currently missing `chatId`
- Factory methods (integration tests) - currently include `chatId`
- These tests will FAIL until fixtures are fixed

### 4. Implementation

Add validation to every code path that sends responses:
- Before `notification.answer()` in handlers
- Centralized validation function
- Clear error messages for debugging

## Files Affected

1. `src/models/green_api.py` - Add validation model and method
2. `src/handlers/whatsapp_handler.py` - Use validation before sending
3. `tests/unit/test_whatsapp_handler_media.py` - Fix fixtures to include `chatId`
4. `tests/unit/test_notification_validation.py` - NEW: Test validation logic

## BDD Workflow

Following `.github/METHODOLOGY.md` Bug-Driven Development:

1. ✅ Root cause identified
2. ✅ Human approval received
3. 🚧 Test gap analysis (this spec)
4. ⏳ Write failing tests
5. ⏳ Get approval
6. ⏳ Fix code
7. ⏳ Verify tests pass
