# Bugfix Spec: Media image_path Not Persisted to Session

## Bug ID
bugfix-009-media-image-path-not-persisted

## Title
Image/media messages leave no `image_path` pointer in the session, so the persisted
conversation can't be traced back to the saved media file on disk

## Status
**Fix applied and fully verified 2026-07-30** (see "Acceptance Criteria" below — all
four real-image E2E tests reconfirmed GREEN live, each individually approved and run).
Originally fixed 2026-07-08 (see
"Original Fix (2026-07-08)" below), verified GREEN, and moved to `specs/done/bugfixes/`.
The fix regressed at some point after `bugfix-017` (session-linkage for media turns)
replaced the original call site with a new one that never re-threaded `image_path`.
Found while investigating `bugfix-015` (image-extraction vision refusal) — unrelated to
that bug's own root cause, but discovered via the same session's live inspection of a
real test run's persisted session data.

## Date Opened
2026-07-07 (original) / Reopened 2026-07-30

## Reported By
yaronlev171

## Affected Area (current, 2026-07-30)
- `apps/denidin-app/src/handlers/media_handler.py` (`MediaHandler.process_media_message`,
  `MediaHandler._store_media_turn`) — **current regression site**
- `apps/denidin-app/src/managers/session_manager.py` (`Message.image_path`,
  `SessionManager.add_message`) — plumbing still intact and functioning correctly, just
  never fed a value by the current caller
- `apps/denidin-app/tests/unit/test_session_manager.py` (`test_image_path_storage`) —
  tests `SessionManager.add_message` directly with an explicit `image_path` argument,
  so it could never have caught this regression (the bug is entirely in the caller,
  `MediaHandler`, never reaching `add_message` with a real value) — this is being
  rewritten as part of this reopened cycle, see "Test-Gap Analysis (2026-07-30)" below.

## Description
When a user sends an image (or other media) to the live bot, the media is downloaded,
analyzed, saved to disk, and a summary is sent back to the user, and (since `bugfix-017`)
a `user` + `assistant` message pair IS persisted to the session. However, the `user`
message's `image_path` field is always `null` — there is no pointer from the persisted
conversation back to the saved media file on disk, even though the file itself is saved
successfully and its path is known at the time the session message is created.

## Evidence (2026-07-30, real test run)
Captured from a real, approved, billed run of
`tests/expensive/test_media_e2e.py::TestWhatsAppE2E::test_e2e_image_no_caption`
(chat `972522968679@c.us`, session `3ea14b08-49c3-4e05-8a2c-0d7872ff7447`):

- The image WAS persisted correctly to disk:
  `test_data/media/DD-972522968679@c.us-d37de960-c520-41b6-bb72-9f1a09eba03c.jpeg`
  (91,923 bytes — matches the logged `Media file size: 91923 bytes` from
  `ImageExtractor._vision_extract`).
- The session's `user` message for this turn
  (`test_data/sessions/3ea14b08-.../messages/cd602fe2-....json`) shows:
  ```json
  {
    "role": "user",
    "content": "[image sent]",
    "image_path": null
  }
  ```

## Root Cause Analysis (2026-07-30)
The persistence machinery bugfix-009 originally built is still fully intact and correct:

- `SessionManager.add_message()` (`session_manager.py:131-151`) accepts and correctly
  persists an `image_path: Optional[str] = None` parameter — unchanged and working.

**The regression**: `bugfix-017` ("media messages were never linked to the session at
all") introduced `MediaHandler._store_media_turn()` (`media_handler.py:204-222`) as a
*new* call site replacing the original `WhatsAppHandler._persist_media_message` this
bug's original fix added. `_store_media_turn`'s signature
(`chat_id, sender_phone, media_type, caption, summary`) **has no `image_path` parameter
at all**, and its call to `self.session_manager.add_message(...)` (`media_handler.py:213-220`)
never passes one — even though `process_media_message` computes the real saved
`file_path` at `media_handler.py:130` (`self.media_file_manager.save_file(...)`) and
uses it for `MediaAttachment.file_path` at `media_handler.py:149`, just 11 lines before
calling `_store_media_turn` at `media_handler.py:160` without it.

In short: `bugfix-017` rewired *which* code path stores media turns into the session
(a real, separate, correct fix for a different problem — media turns being invisible to
conversation history entirely) but didn't carry forward `image_path` from the earlier
`bugfix-009` fix into the new call site.

## Test-Gap Analysis (2026-07-30)
Two independent coverage gaps let this regress silently:

1. **`tests/unit/test_session_manager.py::test_image_path_storage`** tests
   `SessionManager.add_message(image_path=...)` directly, with the value passed
   explicitly by the test itself. This proves `SessionManager` can store an
   `image_path` when given one — it says nothing about whether any real caller
   (`MediaHandler`) actually provides one. This test would pass identically whether or
   not `MediaHandler` was wired correctly, which is exactly why it didn't catch the
   regression. Being rewritten to exercise `MediaHandler._store_media_turn` (the actual
   call site that broke) instead, so it fails against the current (unfixed) code and
   passes once `image_path` is threaded through correctly.
2. **The real E2E image tests** (`test_media_e2e.py::test_e2e_image_no_caption`,
   `test_ledger_event_capture_e2e.py`'s three real-image tests) drive the full pipeline
   and do persist a real session, but none of them assert on `image_path` at all —
   `test_given_real_agreement_image_when_processed_then_ledger_event_captured_via_image_path`'s
   name is misleading here: "via image path" refers to the *pipeline* (image → extractor,
   as opposed to text), not the `image_path` *field* — it only asserts
   `len(session.message_ids) >= 2` (bugfix-017's coverage), never the field itself. All
   four are being updated to also assert the persisted `user` message's `image_path` is
   non-null and resolves to a real file under `data_root`.

## Original Fix (2026-07-08)
<details>
<summary>Original root cause, fix, and acceptance criteria (superseded by the regression above; kept for history)</summary>

### Original Root Cause Analysis
The persistence machinery existed but was never fed:
- `Message` dataclass has an `image_path` field and `SessionManager.add_message(image_path=...)`
  persisted it to JSON correctly (`session_manager.py:36,134,171`).
- **Gap A (primary):** `WhatsAppHandler.handle_media_message` never called
  `session_manager.add_message`. On success it only called `notification.answer(summary)`.
  So media messages produced no session record at all, and
  `result["media_attachment"].file_path` was discarded.
- **Gap B (secondary):** the RBAC storage wrappers `add_message_with_tokens` and
  `add_message_with_token_limit` did not accept or forward `image_path`.

### Original Fix Approach (implemented 2026-07-08)
1. Threaded an optional `image_path` param through `add_message_with_tokens` and
   `add_message_with_token_limit`.
2. Added `WhatsAppHandler._persist_media_message(...)`, reached via the `DeniDin`
   singleton, storing a `user` message (`image_path` set) and an `assistant` message.
3. `WhatsAppHandler` gained a `self.denidin` context attribute; `handle_media_message`
   called `_persist_media_message` on success.

This call site (`WhatsAppHandler._persist_media_message`) no longer exists in the
codebase — it was superseded by `MediaHandler._store_media_turn` (`bugfix-017`), which
is where the regression now lives.

### Original Acceptance Criteria (met at the time, now regressed)
- [x] Failing test(s) reproduced the missing persistence (RED confirmed).
- [x] Sending a media message persisted a `user` session message with `image_path`
      (relative to `data_root`) pointing at the saved `media/DD-*` file, plus an
      `assistant` message with the analysis.
- [x] Expensive E2E tests (image/DOCX/PDF) drove the real pipeline and asserted both
      (a) the file exists on disk and (b) the session `user` message's `image_path`
      resolves to it; all three GREEN after fix.
- [x] No regression to text-message storage or the media summary reply.

</details>

## Steps to Reproduce (current regression)
1. Run the live bot (or an expensive E2E test) with `enable_memory_system` enabled.
2. Send an image to the bot from WhatsApp.
3. Observe the image is analyzed and a summary is returned, and (per bugfix-017) a
   session record IS created.
4. Inspect `{data_root}/sessions/<session_id>/messages/`.
5. The `user` message for the image turn shows `"image_path": null`, even though the
   file was saved successfully to `{data_root}/media/DD-*`.

## Expected Behavior
Sending an image persists a `user` session message whose `image_path` field points to
the saved media file on disk (relative to `data_root`, e.g. `media/DD-<sender>-<uuid>.<ext>`),
matching the original bugfix-009 fix's behavior.

## Acceptance Criteria (this reopened cycle)
- [x] `test_session_manager.py::test_image_path_storage` rewritten to exercise
      `MediaHandler` (not `SessionManager` directly) — confirmed failing against the
      pre-fix code (`TypeError: _store_media_turn() got an unexpected keyword argument
      'image_path'`), passing after the fix.
- [x] All four real-image E2E tests (`test_media_e2e.py::test_e2e_image_no_caption`;
      `test_ledger_event_capture_e2e.py`'s three real-image tests) assert the persisted
      `user` message's `image_path` is non-null and resolves to a real file under
      `data_root`, via a new shared `assert_image_path_persisted()` helper in
      `e2e_helpers.py`.
- [x] Minimal fix applied: `file_path` threaded from `MediaHandler.process_media_message`
      into `_store_media_turn` into `session_manager.add_message(image_path=...)`
      (relative to `config.data_root`, matching the original fix's convention).
- [x] Unit-level regression test passes locally (no billing required — `_store_media_turn`
      touches no external service). Full local suite (549 unit + integration tests)
      re-verified green, no regressions.
- [x] All four real-image E2E runs reconfirm GREEN live, each individually approved
      and run 2026-07-30: `test_e2e_image_no_caption`,
      `test_given_real_agreement_image_when_processed_then_ledger_event_captured_via_image_path`,
      `test_given_real_bank_deposit_screenshot_when_processed_then_captured_as_bank_deposit`,
      `test_given_non_agreement_image_when_processed_then_no_ledger_event_captured` —
      all PASSED, including the new `image_path` assertions.
- [x] No regression to text-message storage or bugfix-017's session-linkage behavior
      (verified via the full local suite + the live E2E run above).

## References
- `.github/CONSTITUTION.md`
- `.github/METHODOLOGY.md` (§VII Bug-Driven Development)
- `specs/bugfixes/README.md`
- `specs/bugfixes/bugfix-015-image-extraction-vision-refusal.md` (moved to
  `specs/obsolete/bugfixes/` — this regression was discovered while investigating it,
  but is an unrelated, separate root cause)
- `apps/denidin-app/src/handlers/media_handler.py`
- `apps/denidin-app/src/managers/session_manager.py`
