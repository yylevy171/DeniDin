# Tasks: Group Conversation Support

**Input**: Design documents from `specs/in-progress/039-group-conversation-support/`
**Prerequisites**: `plan.md`, `spec.md`, `user-stories.md`, `research.md`, `data-model.md`,
`contracts/group-rbac-resolution.md`, `contracts/message-sender-role.md`,
`contracts/no-reply-mechanism.md`, `quickstart.md` — all present.

---

**IMPORTANT**: Complies with CONSTITUTION.md §I-III (config-only, UTC timestamps, feature
branch workflow) and METHODOLOGY.md §VI (TDD, human approval gates, tests IMMUTABLE once
approved).

**Tests**: TDD — every "a" task (tests) requires explicit human approval before its
matching "b" task (implementation) begins. Once approved, a test is immutable without a
fresh, explicit re-approval. Component-integration tests use real internal objects (no
`unittest.mock`), real Green API calls where the story requires one (`getGroupData`), per
CONSTITUTION §V. `billed/` tests (real, text-only OpenAI calls) need no per-run approval —
`expensive/` rules don't apply here; there are no new expensive tests in this feature.

**Design decision finalized at this phase**: the no-reply sentinel string (US4a/US5/US7) is
`[[NO_REPLY]]` — double-bracketed to make accidental collision with genuine Hebrew
conversational output as close to impossible as a plain-text sentinel can get.

**Path Conventions**: Single project — `apps/denidin-app/src/`, `apps/denidin-app/tests/`
(per `plan.md`'s Project Structure).

## Version Control steps (applied at the end of every phase below)

- **VC0**: Confirm `git branch --show-current` is `feature/039-group-conversation-support`.
- **VC1**: `git add` only the files touched by that phase (never a broad `git add -A`).
- **VC2**: `git commit` with a conventional-commit message referencing the phase's US# ids
  (per CONSTITUTION §III format).
- **VC3**: Push — **only when the user explicitly asks to push**, per this project's
  standing rule: no push without its own fresh approval.
- **VC4**: (end of feature only) Open PR — own explicit approval required.
- **VC5**: (end of feature only) Merge + deploy — own explicit approval required, never
  inferred from an earlier "yes" to something else (see CLAUDE.md's environment-start and
  haleluya rules).

---

## Phase 1: Setup

- [x] T001 Confirm `git branch --show-current` is `feature/039-group-conversation-support`
  (already created). No new dependencies needed (research.md: `whatsapp_api_client_python`
  already a project dependency).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two new shared data-model fields both US3/US6 (sender name) and
US4a/US5/US7 (no-reply) depend on, added and independently tested before any behavior is
wired on top of them. **No story-specific wiring starts until this phase's tests are
approved and implementation passes.**

- [x] T002a [P] Write tests for `WhatsAppMessage.sender_display_name` in
  `tests/unit/test_message.py`: `senderContactName` present and non-empty → used as-is;
  `senderContactName` absent/empty, `senderName` present → falls back to `senderName`;
  both absent/empty → falls back to raw `sender_id`; existing `sender_name`/`sender_id`
  fields unaffected (still populated exactly as today).
- [x] T002b [P] Implement `sender_display_name` resolution (the 3-step fallback chain) in
  `WhatsAppMessage.from_notification`, `src/models/message.py` (BLOCKED until T002a
  approved).

- [x] T003a [P] Write tests for `AIResponse.should_reply` in `tests/unit/test_message.py`
  (co-located with `AIResponse`'s other tests, not a separate `test_ai_handler.py` file —
  matches this repo's existing convention of testing models in `test_message.py`): a fresh
  `AIResponse` defaults `should_reply=True`; constructing one with `should_reply=False`
  round-trips correctly (plain field, no derived logic at the model level).
- [x] T003b [P] Add `should_reply: bool = True` field to `AIResponse`,
  `src/models/message.py:146` (BLOCKED until T003a approved).

**Checkpoint**: Both new fields exist, independently tested, unused by any behavior yet.
Run `tests/unit/test_message.py` (28/28 passed, no regressions); all green before
proceeding.

VC0-VC2 for this phase.

---

## Phase 3: User Story 1 — Group text gets a reply without needing "denidin" (Priority: P1) 🎯 MVP

**Goal**: A group message with no "denidin" substring, no `"@"` pattern, reaches the AI
pipeline and gets a normal reply — matching the target godfather+admin scenario.

**Independent Test**: `quickstart.md` US1 (real WhatsApp group message).

**Design note (2026-08-04, corrected twice after review)**: First draft of T004a tried to
prove "message reaches the AI pipeline" inside `tests/integration/` without a real OpenAI
call, using an RBAC-blocked sender as a side-channel signal — rejected as an unnatural
simulation. Second draft replaced it with a unit test asserting `is_bot_mentioned_in_group`
no longer exists — also rejected: that tests an *absence* of code, not a block of logic
being written; there's no real unit here to test, since T004b is a pure deletion with no new
behavior of its own. **Corrected**: no unit test for this task at all. The real functionality
question ("does an unmentioned group message get answered") is inherently an AI-behavior
question, honestly answerable only by a real call — that's exactly what the billed suite
(Phase 10, T015 case #1) is for, and per direct user confirmation that's sufficient; no
substitute unit test is needed.

- [x] T004a [US1] No unit test for this task — nothing new to unit-test (T004b is a
  deletion, not new logic). Skipped by design; see note above. Functional verification
  deferred to the billed suite (Phase 10, T015 case #1).
- [x] T004b [US1] Remove the gate at `denidin.py:340-341` (the call to
  `WhatsAppHandler.is_bot_mentioned_in_group`) so group messages reach
  `ai_handler.create_request`/`get_response` unconditionally, same as 1:1. Delete
  `is_bot_mentioned_in_group` (`whatsapp_handler.py:82-108`) entirely — not repurposed, not
  kept as dead code.

**Checkpoint**: Group text messages get replies by default — actual reply content confirmed
via the billed suite (Phase 10). Verify via `quickstart.md` US1.

VC0-VC2 for this phase.

---

## Phase 4: User Story 2 — Group session stays separate from 1:1 (Priority: P1)

**Goal**: Regression guard — confirm session separation, which already holds by
construction (`chat_id`-keyed), survives US1's gate removal.

**Independent Test**: `quickstart.md` US2.

**Design note (2026-08-04, corrected twice after review)**: First draft tested this through
a full webhook dispatch using the same RBAC-blocked-sender trick as T004a — rejected for the
same reason. Second draft replaced it with a direct `SessionManager.get_session` unit test —
also rejected: `SessionManager`'s chat_id-keying is pre-existing, untouched code (no line of
it changes for this feature); a "unit test" of code nobody is writing or changing isn't a
unit test, it's a characterization test dressed up as one. **Corrected**: no dedicated
automated test for this phase at all — there is no code change to drive with TDD. This
requirement is covered by (a) the fact that nothing in this feature touches
`SessionManager`'s keying logic, confirmed in research.md §3/user-stories.md US2's baseline
investigation, and (b) `quickstart.md` US2's manual verification step, plus the full
regression suite (Phase 12, T019) catching any accidental interaction from other phases.

- [x] T005a [US2] No test written — no code changes for this story, nothing to unit-test
  (see note above).
- [x] T005b [US2] No implementation — confirmed via code inspection (research.md §3) that
  `SessionManager.get_session`/`add_message` are chat_id-keyed and untouched by any other
  phase of this feature. Manual confirmation via `quickstart.md` US2 remains the
  verification step for this story.

**Checkpoint**: Session separation requirement satisfied by inspection — no new code, no new
test. Verify via `quickstart.md` US2 (manual).

VC0-VC2 for this phase.

---

## Phase 5: User Story 3 + 3a — Sender display-name attribution + "AI" sentinel retired, text path (Priority: P1 / P2)

**Goal**: `Message.sender` holds a resolved human name (not a raw phone number, not `"AI"`);
the conversation history sent to OpenAI for group sessions labels who said each turn.

**Independent Test**: `quickstart.md` US3, US3a.

- [x] T006a/T006b [US3/US3a] `SessionManager.add_message` now forces `recipient=None`
  for `role="user"` and `sender=None` for `role="assistant"`, centrally (one place, all
  three persistence methods inherit it since `add_message_with_tokens`/
  `add_message_with_token_limit` both delegate to `add_message`) — regardless of what a
  caller passes. Tests in `tests/unit/test_session_manager.py`
  (`TestSenderRecipientAISentinelRetired`).

- [x] T007a/T007b [US3] `get_conversation_history_for_session` now prefixes each
  `role="user"` entry's `content` with `f"[{sender}] "` when `"@g.us" in
  session.whatsapp_chat`; 1:1 sessions and `role="assistant"` entries unprefixed. Tests
  in `tests/unit/test_session_manager.py` (`test_group_session_history_prefixes_user_turns_with_sender`,
  `test_one_on_one_session_history_unprefixed`).

- [x] T008a/T008b [US3/US3a] (Design note: no dedicated new test — this is a caller-side
  argument change at existing call sites, exercised by the full regression suite,
  consistent with "unit tests are the implementer's judgment call, not something
  requiring a bespoke new test for every argument change" per direct user guidance.)
  `denidin.py`'s `_process_conversational_message` and `DeniDin.handle_message` now pass
  `sender=message.sender_display_name` (not `message.sender_id`) to
  `AIHandler.get_response`; `WhatsAppHandler.handle_media_message` passes a new
  `sender_display_name=message.sender_display_name` argument through
  `MediaHandler.process_media_message` to `_store_media_turn` (renamed parameter
  `sender_phone` → `sender_display` there, to reflect its new meaning — filenames and
  `LedgerEvent.sender` keep using the raw `sender_phone`, unaffected). `ai_handler.py`'s
  `_finalize_response` no longer passes the `"AI"` literal at all (redundant now that
  `SessionManager` enforces it centrally per T006b). 3 pre-existing tests
  (`test_session_manager.py::TestImagePathStorage::test_image_path_storage`,
  `test_whatsapp_handler_media.py::test_route_media_to_media_handler_and_send_summary`,
  `test_ai_handler_memory.py::test_get_response_stores_messages_in_session`) asserted the
  old `"AI"`/`sender_phone`-kwarg behavior and were updated to match the new, intentional
  behavior (not weakened — same coverage, correct expected values).

**Checkpoint**: Text-path sender attribution and "AI" sentinel retirement both work — full
suite green (709 passed, 0 failed). Verify via `quickstart.md` US3, US3a.

VC0-VC2 for this phase.

---

## Phase 6: User Story 4 — Most-permissive-role RBAC for group turns (Priority: P1)

**Goal**: A group turn's token limit/tool attachment is governed by the most-permissive
role among the group's members, not the individual sender alone.

**Independent Test**: `quickstart.md` US4.

- [x] T009a/T009b [US4] `GroupMembershipResolver` implemented in
  `src/managers/group_membership_resolver.py` — `resolve(chat_id)` calls
  `groups_client.getGroupData(chat_id)` (constructor-injected, real `bot.api.groups`, no
  mocking of this external service), picks the member with the highest `User.token_limit`
  (ADMIN/GODFATHER equivalent per research.md §2), caches successes per `chat_id` (failures
  NOT cached, so a transient error doesn't poison future turns), returns `None` on any
  failure (exception, non-200, empty participants) — never raises. Tests in
  `tests/unit/test_group_membership_resolver.py` (8 tests, real `UserManager`, mocked
  `groups_client` — the Green API HTTP boundary — matching this project's unit-tier
  convention).
- [x] T010a/T010b [US4] Wired into `denidin.py`: new `_resolve_group_user_phone(message)`
  helper (`None` for 1:1, missing resolver, or resolution failure); `initialize_app`
  constructs `GroupMembershipResolver(bot.api.groups, ai_handler.user_manager)` and passes
  it into `DeniDin.__init__`; `_process_conversational_message` resolves once per turn and
  passes the result as `user_phone=` to both `create_request` and `get_response`. Full
  suite green (717 passed) — no regression from the `initialize_app` change.

**Checkpoint**: Group RBAC resolution works end to end. Verify via `quickstart.md` US4.

VC0-VC2 for this phase.

---

## Phase 7: User Story 4a — No-reply mechanism (Priority: P1)

**Goal**: The model can signal "send nothing" for a turn; DeniDin honors it, still
persisting the triggering message.

**Independent Test**: `quickstart.md` US4a.

- [x] T011a/T011b [US4a] `NO_REPLY_SENTINEL = "[[NO_REPLY]]"` (module constant,
  `ai_handler.py`). `_finalize_response` computes `should_reply = response_text.strip() !=
  NO_REPLY_SENTINEL` before persistence; skips the assistant-message persist call when
  `False` (user message always still persisted); threads `should_reply` into the returned
  `AIResponse` (and into `AIResponse.truncate_for_whatsapp`'s reconstruction, for
  robustness, even though truncation can never actually co-occur with the short sentinel
  text in practice). Tests in `tests/unit/test_ai_handler_no_reply.py` (5 tests, mocked
  OpenAI client per this project's established `AIHandler` unit-test convention) — covers
  exact match, whitespace-trimmed match, a near-miss with trailing content (must NOT
  trigger no-reply — never silently drop a real reply), and the normal case.
- [x] T012a/T012b [US4a] `_process_conversational_message` checks
  `ai_response.should_reply` and returns before calling `send_response` when `False` — no
  error, no fallback message, a first-class successful outcome. Tests in
  `tests/unit/test_denidin_no_reply_dispatch.py` (3 tests, mocked `ai_handler`/
  `whatsapp_handler` on `denidin_app` — isolates the dispatch branch from any real OpenAI
  call, which belongs in the billed suite instead).

**Checkpoint**: No-reply plumbing works end to end (deterministically); the real-model
trigger case is verified later via the billed suite (Phase 10). Verify via `quickstart.md`
US4a.

VC0-VC2 for this phase.

---

## Phase 8: User Story 5 — Silent / ask / answer three-way split (Priority: P2)

**Goal**: New `config/runtime_constitution.md` guidance: clear-for-DeniDin → answer;
clear-for-someone-else (no `"@"` pattern) → `[[NO_REPLY]]`; genuinely unclear → a short
clarifying question. No `"@Name"` pattern present is a precondition (US7 takes precedence
when one is).

This phase is prompt-authoring, not code — no unit tests apply (there is no deterministic
function to unit-test; correctness is verified by the real-model billed tests in Phase 10).

- [x] T013 [US5] Add a new "Group Conversation Etiquette" section to
  `config/runtime_constitution.md`: (1) by default, a group message is addressed to you —
  answer normally; (2) if a message's content is clearly directed at another human
  participant (uses their name, 2nd-person phrasing that doesn't fit you) and does NOT
  contain a literal `"@Name"` pattern, respond with exactly `[[NO_REPLY]]` and nothing
  else — no clarifying question, this is not ambiguous; (3) only when it's genuinely unclear
  whether a message is for you or for another participant, ask a short Hebrew clarifying
  question instead of guessing either way; (4) this section only applies to text messages,
  not images (cross-reference the existing image-analysis section so the two don't
  conflict).

**Checkpoint**: Constitution guidance authored. Behavioral verification deferred to Phase
10 (billed tests) — prompt correctness can't be unit-tested.

VC0-VC2 for this phase.

---

## Phase 9: User Story 7 — "@Name" self-referential check (Priority: P2)

**Goal**: Extend the same constitution section: a literal `"@Name"` pattern is checked only
against DeniDin's own identity — never against a roster of real participants.

- [x] T014 [US7] Extend the "Group Conversation Etiquette" section
  (`config/runtime_constitution.md`, T013) with: if the message contains a literal
  `"@Name"` pattern, check ONLY whether `Name` plausibly refers to you (DeniDin, per your
  own "Core Identity") — do not attempt to identify who else it might refer to. If `Name`
  does not refer to you (any other name, nickname, or arbitrary text), respond with exactly
  `[[NO_REPLY]]`, regardless of surrounding content. If `Name` does refer to you, answer
  normally even if the surrounding content would otherwise look ambiguous. This check takes
  precedence over the plain content-based judgment above (T013) whenever a `"@Name"`
  pattern is present.

**Checkpoint**: Constitution guidance complete for both US5 and US7. Behavioral
verification in Phase 10.

**REVISED 2026-08-04, after real billed-test failures (see Phase 10 below)**: T013/T014's
original structure (separate "@Name present" vs. "no @Name" top-level cases) was rewritten
during Phase 10's debugging into a single unified structure once real failures showed the
model wasn't recognizing plain (non-@) named addressees at all:
1. **Case 1** (merged both stories): does the message name a specific person, `@`-tagged or
   not? Check ONLY whether that name is DeniDin/a close variant — mechanical, not a judgment
   call. Not-DeniDin → `[[NO_REPLY]]`, full stop, regardless of content. Is-DeniDin →
   answer normally, overriding any surrounding ambiguity.
2. **Case 2**: no name anywhere → default, answer normally (the common case).
3. **Case 3**: no name, but phrasing still genuinely unclear who it's for → ask a
   clarifying question (narrow exception).

Two iterations were needed to get here — see Phase 10's notes for the actual failures and
fixes; current text is in `config/runtime_constitution.md`'s "Group Conversation Etiquette"
section.

VC0-VC2 for this phase.

---

## Phase 10: Billed Test Suite (real, text-only OpenAI calls — no approval needed to run per
CONSTITUTION §VII, but per this session's explicit user instruction, EVERY run in this
session — initial and every re-run — required asking first; treat that as standing
guidance for this feature going forward, overriding the blanket exemption)

**Purpose**: Verify T013/T014's prompt guidance actually produces the intended model
behavior — the one thing this feature can't verify with deterministic unit/integration
tests, since it's genuinely about model judgment.

- [x] T015 [P] Written: `tests/billed/test_group_etiquette_billed.py`, 7 cases (case 5 split
  into 5a/5b — real name vs. arbitrary text, both asserting identical no-reply behavior):
  1. `test_case1_default_address_gets_substantive_reply` — plain group message, no signal.
  2. `test_case2_clearly_for_someone_else_gets_no_reply` — named addressee, not DeniDin,
     no `"@"`. **Deliberately a neutral, non-actionable question** ("רותי, את יודעת איזה יום
     היום?"), not task/reminder-shaped — changed mid-debugging (see below) to isolate
     addressee-recognition from task-shaped-request confounds.
  3. `test_case3_genuinely_unclear_gets_clarifying_question` — no name, ambiguous who "you"
     means.
  4. `test_case4_ordinary_message_negative_control` — ordinary message, no signal either way.
  5. `test_case5a_at_name_not_denidin_real_name_gets_no_reply` /
     `test_case5b_at_name_not_denidin_arbitrary_text_gets_no_reply` — `"@"` + a real name vs.
     `"@lalalal"`, both must behave identically.
  6. `test_case6_at_denidin_overrides_ambiguous_content` — ambiguous content + `"@DeniDin"`.

  **Test-isolation bug found and fixed mid-debugging**: originally all 7 cases shared one
  hardcoded `GROUP_CHAT_ID` constant — since `test_data/` persists across runs, later cases
  inherited earlier cases' conversation history (confirmed via logs: 12 prior messages
  present on a supposedly-fresh run), which could bias the model toward whatever pattern
  the earlier turns established. Fixed: `_group_event(text, case_id)` now generates a
  unique `chat_id` per case per run (`case_id` + timestamp), so every case is judged on a
  single-message context, never contaminated by sibling cases.

- [x] T016 Ran `pytest tests/billed/test_group_etiquette_billed.py -m billed -v`, case by
  case, **with explicit approval requested before every single run** (per this session's
  standing instruction — see Phase 10 heading note). Findings:
  - Cases 1, 3, 4, 5a, 5b, 6 passed on the **first** full-suite run, no changes needed.
  - **Case 2 failed twice** before passing:
    1. First failure (original task-shaped message, "רותי, תזכירי לי להתקשר ללקוח מחר
       בבוקר" — "Ruti, remind me to call the client tomorrow"): DeniDin answered as if
       addressed to itself ("אני לא יכול להגדיר תזכורת בפועל..."). Root-caused (with user
       input) as the model treating a named vocative as an aside rather than the actual
       addressee, once the request looked like something DeniDin itself could help with.
    2. First constitution fix attempt (added an "opens with a vocative" rule + the literal
       test sentence as an example) — **rejected by user as overfitting to the test**:
       positional wording ("opens with") and reusing the exact test string aren't
       generalizable guidance.
    3. Rewrote as a general principle (no positional language, no literal example: "judge
       addressee like a human bystander would, not by your own capability to help") — retested
       with the SAME task-shaped message: **still failed**, and re-running with a freshly
       isolated session (the T015 fix above) ruled out session contamination as the cause —
       confirmed a genuine wording gap, not a test artifact.
    4. Per user suggestion, swapped the test message to something neutral/non-task ("רותי,
       את יודעת איזה יום היום?" — "Ruti, do you know what day it is?") to isolate whether
       the failure was specific to task-shaped requests. **Still failed** (DeniDin answered
       the date directly) — this proved the gap wasn't about tasks specifically; the model
       wasn't picking up on a named addressee AT ALL when there was no `"@"`.
    5. Per direct user instruction ("The bot's name is DeniDin or some variation on that.
       Anything that's not close to that can be regarded as not intended for the bot. This
       is not rocket science..."), rewrote the whole section: merged the `"@Name"`-specific
       case (US7) and the plain-named-addressee case (US5) into ONE unified, simple
       mechanical check — "does this message name someone? Is that name DeniDin or a close
       variant? If not, `[[NO_REPLY]]`, no further reasoning needed" — applying identically
       whether or not there's an `@`. **This passed.**
  - Final restructured constitution text is in `config/runtime_constitution.md`'s "Group
    Conversation Etiquette" section (see Phase 8/9's revised checkpoint note above for the
    3-case structure this produced).
  - **Final full 7-case re-run (2026-08-04, next session)**: confirmed the case-2 rewrite
    did NOT regress the other 6 cases — all 7 passed against the current, rewritten
    constitution text: `pytest tests/billed/test_group_etiquette_billed.py -m billed -v` →
    `7 passed in 36.87s`.

**Checkpoint**: REACHED — all 7 billed cases pass against the current constitution text.

VC0-VC2 for this phase (not yet run — no commit has been made this session; see HANDOFF.md).

---

## Phase 11: User Story 6 — Media path regression guard + sender-name fix (Priority: P3)

**Goal**: Media messages keep working exactly as today, gain the same sender-name/"AI"-
sentinel fix as the text path (US3/US3a), and explicitly do NOT gain any of US1/US4a/US5/
US7's etiquette logic.

**Independent Test**: `quickstart.md` US6.

- [x] T017a [US6] Written and passing: `tests/integration/test_group_conversation_routing.py`
  (2 cases, component-integration — real router-registered `handle_image_message`, real
  `WhatsAppHandler`/`MediaHandler`/`SessionManager`; only the two genuine external
  boundaries stood in for — Green API file download, OpenAI vision call — same seam
  `tests/unit/test_media_handler.py` already uses):
  1. `test_group_image_processed_normally_with_resolved_sender_name` — a real image sent in
     a group by an admin is processed identically to today (extraction, reply content); the
     resulting stored media-turn user message has `sender` set to the resolved display name
     ("Admin User", not the phone JID, not the retired `"AI"` sentinel), `recipient=None`,
     and the assistant reply has `recipient="Admin User"`/`sender=None` — same rule as
     T006a, read directly from the persisted per-message JSON files (no public
     `Session.messages` accessor exists — `Session` only holds `message_ids`; messages live
     one-JSON-file-per-message under `{session_dir}/messages/`).
  2. `test_group_image_with_named_addressee_caption_still_gets_full_reply` — an image
     captioned with text that would trigger US5's `[[NO_REPLY]]` path if it were plain text
     (`"רותי, תראי את זה"` — names someone other than DeniDin) still gets the full,
     substantive analysis reply — proves the scope boundary from research.md §9 holds:
     media never reaches `AIHandler.get_response`/the no-reply sentinel at all.
- [x] T017b [US6] Confirmed already correct, no code change needed: T006b/T008b's
  sender-name fix was already threaded onto the media path (`message.sender_display_name` →
  `WhatsAppHandler.handle_media_message` → `MediaHandler.process_media_message` →
  `_store_media_turn`, `src/handlers/media_handler.py`) by earlier Phase 5 work, and
  `SessionManager.add_message`'s central `role`-based `sender`/`recipient` forcing (T006b)
  applies uniformly regardless of call site — T017a's test 1 above is the verification that
  was still missing, not a fix.

**Checkpoint**: REACHED — media path confirmed unaffected by etiquette, sender-name fix
confirmed correct via T017a. Verify via `quickstart.md` US6.

VC0-VC2 for this phase (not yet run — no commit has been made this session; see HANDOFF.md).

---

## Phase 12: Polish & Cross-Cutting Concerns

- [x] T018 [P] Ran `python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc` (9.31/10,
  well above threshold) and `python3 -m mypy src/ --config-file=mypy.ini`. Two new findings
  introduced by this feature, both fixed:
  - `ai_handler.py`: a debug-log f-string I'd added exceeded 120 chars — split into a
    `storage_note` variable + shorter log call.
  - `group_membership_resolver.py` (new file): `GroupResolution.role` used a bare
    `'Role'  # noqa: F821` string annotation instead of a real import (avoiding an assumed
    circular import that doesn't actually exist — `user_manager.py` already imports `Role`
    from `src.models.user` directly at module level, so this file does the same now).
  All other pylint findings across `src/` are pre-existing, not touched by this feature.
- [x] T019 [P] Ran the full non-billed, non-expensive suite:
  `python3 -m pytest tests/ -v --tb=short` → `727 passed, 83 deselected in 82.36s`, 0
  failures.
- [x] T020 Updated `CLAUDE.md`'s Architecture section: `### Message flow` diagram now shows
  `GroupMembershipResolver` and the `[[NO_REPLY]]` sentinel check, plus a new "Group
  conversations (Feature 039)" paragraph explaining the mention-gate removal, the no-reply
  mechanism, group RBAC resolution, the sender/recipient display-name change, and the
  media-path exclusion. `### Key components` gained a `group_membership_resolver.py` bullet
  and the `whatsapp_handler.py` bullet was corrected to drop the now-inaccurate
  "group-mention detection" claim.

---

## Dependencies & Execution Order (TDD-Aware)

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories — both new fields
  (`sender_display_name`, `should_reply`) are prerequisites for later phases. T002a/T002b
  and T003a/T003b are independent of each other (different files), parallelizable as pairs.
- **US1 (Phase 3)**: Depends on Setup only (not Foundational) — the gate removal doesn't
  touch either new field. Could technically run before Phase 2, but sequenced after for
  narrative clarity; no hard blocker either way.
- **US2 (Phase 4)**: Depends on Phase 3 (tests the post-gate-removal state).
- **US3/US3a (Phase 5)**: Depends on Phase 2 (`sender_display_name`).
- **US4 (Phase 6)**: Depends on Setup only — independent of Phase 2/3/5 (different code
  path entirely: RBAC resolution, not sender display or no-reply). Could run in parallel
  with Phase 3/5 in practice.
- **US4a (Phase 7)**: Depends on Phase 2 (`should_reply` field).
- **US5 (Phase 8)** / **US7 (Phase 9)**: Both depend on Phase 7 (US4a — the `[[NO_REPLY]]`
  sentinel must actually do something before instructing the model to use it). US7 (Phase
  9) extends the same constitution section US5 (Phase 8) creates — sequenced, not parallel.
- **Billed Suite (Phase 10)**: Depends on Phases 3, 8, 9 all being implemented (US1, US5,
  US7's actual guidance must exist before testing whether it works).
- **US6 (Phase 11)**: Depends on Phase 5 (reuses T006b/T008b's fixes) — independent of
  Phases 6-10.
- **Polish (Phase 12)**: Depends on all prior phases.

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 (Setup) → Phase 3 (US1) → **STOP, validate via `quickstart.md` US1** — this
   alone already fixes the core "silently dropped" problem for the target scenario's
   unmarked messages.

### Incremental Delivery

Phase 2 (Foundational) → US1 (MVP) → US2 → US3/US3a → US4 → US4a → US5 → US7 → Billed Suite
→ US6 → Polish. Each checkpoint is independently demonstrable. US4 (Phase 6) can be pulled
forward or run in parallel with US3/US3a (Phase 5) if desired — they touch disjoint code.

Note: phase numbering follows dependency order, not strict P1→P2→P3 priority order — US6
(P3) sits at Phase 11, after the P2 stories (US5/US7, Phases 8-9) and the billed suite
(Phase 10), because it depends on Phase 5's fixes and has no reason to block on anything in
between. See "Dependencies & Execution Order" above for the authoritative ordering rationale.

## Notes

- The no-reply sentinel (`[[NO_REPLY]]`) is the single piece of cross-cutting state every
  later phase (US4a onward) depends on getting right — if a future change ever needs to
  alter it, every reference in `config/runtime_constitution.md` (T013, T014) and
  `AIHandler._finalize_response` (T011b) must change together, atomically, in one commit.
- Images are explicitly, permanently out of scope for US1/US4a/US5/US7's etiquette logic
  (research.md §9) — T017a's negative assertion exists specifically to catch any future
  regression where someone assumes the constitution's group-etiquette section (which the
  image pipeline's vision call happens to also load, incidentally) "just works" for images
  too. It doesn't, by design — the image pipeline never checks `should_reply` at all.
- **Regression found and fixed 2026-08-04, during a full billed-suite sweep (all of
  `tests/billed/`, not just this feature's own suite)**: US3's sender-display-name change
  (Phase 5 — `sender` now carries `message.sender_display_name`, not a phone) broke
  `AIHandler.get_response`'s RBAC phone resolution for every 1:1 conversation.
  `get_response`'s own fallback is `effective_user_phone = user_phone or sender`
  (`ai_handler.py:876`); `denidin.py`'s `_process_conversational_message` only ever passed
  `user_phone=group_user_phone`, which is `None` for any 1:1 chat, so `get_response` fell
  back to resolving RBAC against a display name instead of a phone - silently defaulting
  every 1:1 sender to `CLIENT`, regardless of their real role. Caught via
  `tests/billed/test_denidin_morning_mcp_e2e.py::test_godfather_marks_transaction_account_invoice_paid_via_whatsapp`
  failing with the model reporting no access to the Morning MCP tool at all (no
  "Attaching Morning MCP tools" log line, and no warning either - that RBAC-role early
  return in `_build_morning_mcp_tools` was never logged). `AIHandler.create_request` was
  never affected - it takes `message` directly and already falls back to
  `message.sender_id` internally, unlike `get_response`.
  Fix (both real call sites in `denidin.py`, no other production call site of
  `get_response` exists besides docx_extractor.py's, which passes neither `sender` nor
  `user_phone` and was never in RBAC scope):
  - `_process_conversational_message`: `user_phone=group_user_phone or message.sender_id`
    (was `user_phone=group_user_phone`).
  - `DeniDin.handle_message` (the programmatic test-helper API): added
    `user_phone=message.sender_id` (was omitted entirely).
  Full non-billed suite re-run clean after the fix (727 passed). Per explicit user
  direction, this was fixed directly as part of Feature 039 (not spun out as a separate
  bugfix-###), tests were not touched, and the previously-failing billed test is the
  acceptance check for the fix.
