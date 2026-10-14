# Feature 067 - billed / expensive test audit against the no-turn decisions

Written 2026-10-14. Scope done: A0-A8 (`tests/billed/test_realistic_message_handling_billed.py`,
`tests/expensive/test_realistic_message_handling_expensive.py`, harness `tests/billed/_067_harness.py`).
Purpose: a checklist to apply to every other billed / expensive test. NO billed or expensive test was
run to produce or verify these edits (they are authored only; running needs the human's go-ahead).

Decisions audited against: `no-turn-redesign.md` (1-12) + `user-stories.md` A0-A8.

## What changed in the app that tests can no longer assume

| New fact | What it breaks in a test |
|---|---|
| Every tool sends at once, addressed by chat id (decision 1). | There is no "the reply to this notification". Test doubles route each send to the LATEST notification of the chat (`RecordingBot`), so per-notification `_test_sent_messages` is only valid when a chat has exactly one notification in flight. With several messages sent a second apart, assert on the whole scenario (`rig.sent_texts()`), never on `notification_k._test_sent_messages`. |
| Silence is a normal answer: a model response with no tool call (decision 3). | "There must be a reply to X" is not a valid assertion. After a bare "כן"/"לא", a tap, or a message addressed to someone else, nothing sent is legitimate. Assert on the effect (Morning documents, model calls on the wire, stored state), not on a reply count. |
| Plain output text is ignored (3b). | A test that reads the model's plain text as its answer is wrong. Only text sent via `send_to_user` or approval buttons is visible. |
| `[[NO_REPLY]]` / `should_reply` are gone (3). | Group-etiquette tests that expect the sentinel, or assert `should_reply is False`, test removed behaviour. Rewrite as "no message was sent" (rig/RecordingBot), or delete if redundant. |
| No end-of-turn, no busy marking (11b). | `app._busy_chats`, `mark_chat_busy` waits, "turn finished" polling are gone. Idle = queues empty + no current item (`rig.wait_until_idle`). |
| `denidin_app.last_response` is reset per `handle_message` call (`Backbone._activity_record`). | It holds only the LAST call's `mcp_calls`. A burst can span several calls, so "exactly one document was created" must use a scenario-wide source: `rig.wire.created_documents()` (parses the model responses on the wire). Never `<= 1` (it passes for zero). |
| The chat's model chain persists between messages (decision 10). | The model remembers an unanswered question from an earlier test in the same chat and "answers first". Every test starts every chat clean: autouse `_fresh_conversation_for_every_test` (billed + expensive conftest), which also clears `ai_chain_id`. A test that builds its own app/chat store must call `start_every_chat_fresh()`/`wipe_chat_messages_on_disk`. |
| Wire contexts are `conversation (new chain)`, `conversation (chained)`, `conversation (new chain after expiry)` (no more `_run_resolution_loop`). | Filters on the old context names find nothing. Use `WireCapture.conversation_calls()` (prefix `conversation`). In a chained call `input` holds only the NEW items (tool outputs + new user messages), not the history. |
| Approval: `approval_with_yes_no_buttons` is stateless; the sent id is stored as `Session.approval_message_id`; a tap whose stanza id differs is ignored silently; a typed "כן" runs the approved write (decisions 2, 3). | Tests that look for a `PendingApproval` object, `pending_*_manager`, or "the bot asks for approval again" are stale. A tap is proven by a model call on the wire; a stale/second tap by NO new call and NO message. |
| Ledger capture is in the flows; invoices captured deterministically on a successful `create_*`; no post-reply recognizer (decision 6). | Tests that wait for a ledger event "after the reply" via `_run_post_turn_ledger_recognition`/`LedgerEventRecognizer` are stale; assert the event exists after the flow ran (and that the model called the capture step), not that a separate recognition call happened. |
| Client-role chats are out of scope for the backbone. | Any test driving a CLIENT-role chat expecting an AI answer is stale. |
| Errors: a failed model call sends the friendly error at once and pauses (8). | Expect exactly one friendly error send (see `test_ai_handler_real_api`), not an `AIResponse` with `model == "error-fallback"`. |

## Per-test findings (A0-A8) and what was done

| Test | Finding | Action |
|---|---|---|
| A0 count together | Valid. First call must carry only message 1; later messages reach the model afterwards; last reply contains 4. Relies on the model answering 4 (not silent) - a legitimate residual risk. | none |
| A1 additive, unknown client | Valid, but read `denidin_app.last_response.mcp_calls` (last call only). | now `rig.wire.created_documents()` |
| A2 ten messages | Valid. Final-reply wording check (`1200`, `ייעוץ`) is model-dependent; silence-on-last-message would fail it. Left as is, flagged. | none |
| A3 stop | Stale: asserted a reply to the bare "כן" (`len(sent) > before`) and checked wording `הופקה`/`נוצרה`. Silence is legitimate; the story's real claim is "no document appears in Morning". | asserts no `create_*` in Morning before and after the "כן" |
| A4 approved action + "רגע, תבטל" | Weak: `<= 1` passes for 0 documents, and used last-call-only `mcp_calls`. Story says created exactly once. | `== 1` via `rig.wire.created_documents()`; wording check on the text kept |
| A5 confusing sequence | Valid (settle on Dana or ask). Loose by design. | none |
| A6 group | First run FAILED: asserted the reply contained 700, but the request lacked the (required) service description, so the model correctly asked for it. Also `WireCapture.user_texts` did not strip the group sender tag (`[Bina] text`), so a later group message never matched. | request now carries description + amount + VAT basis (the approval prompt is the expected answer); `user_texts` strips the `[Sender]` tag; wire-level "both reached the model" checks added |
| A7 button after chatter | Stale: assumed a visible reply after a decline tap and compared reply counts; with silence legal that can fail for the wrong reason and the second-tap check could pass vacuously. | proves tap #1 by a new model call on the wire, tap #2 by NO new model call |
| A8 image during text (expensive) | Wrong under chat-id sends: read `text._test_sent_messages` / `image._test_sent_messages`, but both messages' answers land on the LATEST notification of the chat. | scenario-wide `rig.sent_texts()` (>= 2), exactly 1 vision call (not analyzed twice), nothing deferred |
| Harness | `wait_until_idle` used removed `_busy_chats`; context-name filter was stale. `WireCapture` only knew model requests. | fixed both; added `vision_calls`, `morning_calls`, `created_documents()` |

Run results (2026-10-14, human-approved, one at a time): A0-A5 PASSED; A6 failed once (above), PASSED after the fix; A7 PASSED. A8 (expensive) PASSED (human-approved, 1 run).

Harness lesson for every other test: in a group, user messages reach the model as `[USER MESSAGE · time · sent before/after your last output]\n[Sender] text`; the first message of a burst as `[time] text`. Compare texts after stripping those tags.

## Checklist to apply to every other billed / expensive test

1. Does it read `notification._test_sent_messages` of a notification that is not the chat's latest? Move to a chat-wide view.
2. Does it require a reply where silence is legal (after "כן"/"לא", taps, side remarks)? Assert the effect instead.
3. Does it use `last_response.mcp_calls` for a count over several messages? Use the wire-based `created_documents()` / `morning_calls`.
4. Does it use `AIHandler`, `ai_handler`, `pending_*_manager`, `PendingApproval*`, `should_reply`, `[[NO_REPLY]]`, `constitution_config`, `feature_flags.enable_capability_backbone`, `runtime_constitution`, `_busy_chats`, `_run_post_turn_ledger_recognition`? It tests removed behaviour: delete if another test covers the intent, else rewrite to the backbone equivalent.
5. Does it build its own app or `green_api_bot = object()`? Use `install_recording_bot(app)` so sends are captured; and call `start_every_chat_fresh()` if it bypasses the autouse fixture.
6. Does it assume a document approval prompt has a certain shape? Prompts changed: `assert_document_approval_states_vat` ignores "ביטול ..." (cancellation creates no document); other approvals must carry `סוג מסמך:` and `מע״מ:`.
7. Ledger: assert the stored event, not a post-reply recognition step.
8. Redundancy rule: when a unit/integration test (now green, 1712 passing) already proves the mechanism and the billed test only re-proves it with a live model and no model-judgment content, propose deleting it - human signs off per group.
9. Never run a billed/expensive test to find out whether it still passes; audit statically, then ask which to run.
