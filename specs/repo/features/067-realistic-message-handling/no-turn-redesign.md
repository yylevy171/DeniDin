# Feature 067 - "No turn" redesign (decisions)

Status: decisions recorded 2026-10-13 (human); implemented 2026-10-14 (unit/integration green; billed/expensive audit in `billed-expensive-audit.md`).
Implementation notes: the chain uses `truncation="auto"` (no length cap); `/health` carries `intake_pipeline`.

Principle: there is no turn. The app reacts: the model acts through tools, the app does what the
model says, immediately. The model works whenever it has something to do and pauses when it has
nothing to do. There is no "final reply", no "end of turn", no work that happens "afterwards".

## Decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Delivery | Every tool acts at once (send, store). No `AIResponse` carrying a reply to be sent later. |
| 2 | Approval buttons | `approval_with_yes_no_buttons` sends at once; the sent message id is stored on the chat (stale-tap guard unchanged). No flag carried to an end. |
| 3 | Silence | One way only: a model response with no tool call. The `[[NO_REPLY]]` sentinel and `should_reply` are removed. |
| 3b | Plain text | Output text is ignored (logged). If a response has plain text and no tool call, ONE more call tells the model its text was ignored (information reaches the user only through tools). Prompts say this strongly. An empty response pauses at once. |
| 4 | Duplicate-write note | Dropped. The model sees both results. |
| 5 | Length cut | In the send itself, for every message. |
| 6 | Ledger capture | Moves into flows: `הסכם` (new, corrected, cancelled) and `הפקדה` get capture steps in their flows; `חשבונית` is captured deterministically when `create_*` succeeds, the 60-minute reconciliation sweep stays as backup. The post-reply recognition step is removed. No `CURRENT_SCHEMA_VERSION` change. |
| 7 | Telemetry | Recorded per model call and per Morning call, as they happen. The hallucinated-confirmation check runs per sent message (log only). |
| 8 | Errors | A model call that fails after its retries sends the friendly error text at once and pauses. |
| 10 | State | Nothing per-message in memory. The session stores the model chain id (`previous_response_id`) and last-activity time; every model call continues the chat's chain. The chain is dropped (a new one is built from the rolling window + summaries) by the same idle timer as `capabilities_reset_minutes`. |
| 11 | Typing | Typing indicator is on exactly while an OpenAI call is in flight. |
| 11b | Busy marking | `mark_chat_busy`/`mark_chat_idle`/`_busy_chats` removed. Sends are addressed by chat id; blocked-user lookup happens when typing is needed. |
| 12 | Legacy | The legacy `AIHandler` path (flag off) is deleted. One implementation. |

## Open
- Hard cap on chain length for a very long active conversation (value: human).
- Unverified OpenAI behaviours (CONSTITUTION: confirm with a real call before relying): chain
  continuation across separate calls and idle gaps, response expiry, truncation, prompt-cache
  behaviour when instructions change mid-chain. A Gate Zero probe settles these.
- Which existing tests change or are deleted (human sign-off per test group).
