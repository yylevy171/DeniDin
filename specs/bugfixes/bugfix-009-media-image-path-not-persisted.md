# Bugfix Spec: Media image_path Not Persisted to Session

## Bug ID
bugfix-009-media-image-path-not-persisted

## Title
Image/media messages leave no session record, so `image_path` is never persisted

## Status
Open

## Date Opened
2026-07-07

## Reported By
yaronlev171

## Affected Area
- `src/handlers/whatsapp_handler.py` (media message handling)
- `src/handlers/ai_handler.py` (session message storage)
- `src/managers/session_manager.py` (`Message.image_path`, RBAC storage wrappers)
- `denidin.py` (`initialize_app` wiring)

## Description
When a user sends an image (or other media) to the live bot, the media is downloaded, analyzed,
and saved to disk, and a summary is sent back to the user. However, the session message JSON files
under `data/sessions/<session_id>/messages/*.json` always show `"image_path": null`. There is no
pointer from the persisted conversation to the saved media file on disk.

## Steps to Reproduce
1. Run the live bot with `enable_memory_system` and `enable_rbac` enabled.
2. Send an image to the bot from WhatsApp.
3. Observe that the image is analyzed and a summary is returned.
4. Inspect `data/sessions/<session_id>/messages/`.
5. No message file carries the saved image's path in `image_path` (in fact, no session message is
   created for the media message at all).

## Expected Behavior
- Sending an image persists a session message (role `user`) whose `image_path` field points to the
  saved media file on disk (`data/media/DD-<sender>-<uuid>.<ext>`).

## Actual Behavior
- Media messages create **no** session message. The saved file path
  (`MediaAttachment.file_path`) is discarded inside `MediaHandler`, and `image_path` is `null`
  everywhere.

## Root Cause Analysis
The persistence machinery exists but is never fed:

- `Message` dataclass has an `image_path` field and `SessionManager.add_message(image_path=...)`
  persists it to JSON correctly (`session_manager.py:36,134,171`).
- **Gap A (primary):** `WhatsAppHandler.handle_media_message` (`whatsapp_handler.py:249-300`) never
  calls `session_manager.add_message`. On success it only calls `notification.answer(summary)`. So
  media messages produce no session record, and `result["media_attachment"].file_path` (built in
  `media_handler.py:114-138`) is discarded. `WhatsAppHandler` holds no `session_manager`/`ai_handler`
  reference (`whatsapp_handler.py:30-38`).
- **Gap B (secondary):** the RBAC storage wrappers `add_message_with_tokens` and
  `add_message_with_token_limit` (`session_manager.py:549-628`) do not accept or forward
  `image_path`, so even the text/AI path could never populate it.

## Why Existing Tests Didn't Catch It (Test-Gap Analysis)
Existing media integration/expensive tests assert that a summary is *sent* to the user, but none
assert that a session message was created, and none assert that `image_path` points to the saved
file. The persistence side-effect of the media flow was completely unverified.

## Fix Approach (decided)
Persist a single `user` message carrying `image_path` when media is processed (no separate
AI-analysis message):

1. Thread an optional `image_path` param (default `None`) through `add_message_with_tokens` and
   `add_message_with_token_limit`, forwarding to `add_message`. Backward-compatible: behavior is
   identical when omitted.
2. Add `AIHandler.store_media_message(chat_id, content, sender, recipient, image_path, user_phone)`
   that stores one `role="user"` message through the existing RBAC token-limit path with
   `image_path` set (reuses the storage logic at `ai_handler.py:386-434`).
3. Wire `ai_handler` into `WhatsAppHandler.__init__`; in the success branch of
   `handle_media_message`, call `ai_handler.store_media_message(...)` with
   `content = caption or filename/placeholder` and
   `image_path = result["media_attachment"].file_path`. Update `initialize_app`
   (`denidin.py:206-260`) to pass `ai_handler` (created before `WhatsAppHandler`).

## Acceptance Criteria
- [ ] Failing test(s) reproduce the missing `image_path` persistence.
- [ ] Sending a media message persists a `user` session message with `image_path` = saved file path.
- [ ] `add_message_with_token_limit(..., image_path=...)` persists `image_path` to JSON (unit).
- [ ] Integration test drives an `imageMessage` webhook through `bot.router` (no internal mocks) and
      asserts the on-disk session message has `image_path` pointing at the `data/media/DD-*` file.
- [ ] Expensive tests for every media type assert both (a) the file is persisted on disk and (b) the
      session message's `image_path` equals that path.
- [ ] No regression to text-message storage or the media summary reply.

## References
- `.github/CONSTITUTION.md`
- `.github/METHODOLOGY.md` (§VII Bug-Driven Development)
- `.github/BUG_DRIVEN_DEVELOPMENT.md`
- `specs/bugfixes/README.md`

## Next Steps
1. Write failing tests (unit + component + integration). 🚨 HUMAN APPROVAL gate.
2. Implement minimal fix.
3. Verify (tests green; optional live image send). 🚨 Approval for any expensive-test run.
4. Update this spec, commit, PR.
