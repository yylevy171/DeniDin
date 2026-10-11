# Contract: Turn Cancellation at Round Boundaries

**Feature**: `feature/067-realistic-message-handling`
**Component**: `src/handlers/ai_handler.py` (`AIHandler.get_response` and the local-tool loop),
`src/models/message.py` (`AIResponse`)

---

## New parameter

`get_response` gains one trailing keyword-only-in-spirit parameter, fully defaulted:

```python
def get_response(
    self,
    request: AIRequest,
    chat_id: Optional[str] = None,
    user_role: str = 'client',
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    user_phone: Optional[str] = None,
    is_group: bool = False,
    chat_name: Optional[str] = None,
    sender_phone: Optional[str] = None,
    cancel_check: Callable[[], bool] = lambda: False,   # NEW
) -> AIResponse:
```

- Every existing caller (tests, player path, reconciliation sweep, approval-resolution path)
  passes nothing → `lambda: False` → **byte-for-byte current behaviour**, no round-boundary
  branch ever taken.
- Only the live consumer's merged-text path passes a real `cancel_check`
  (`coordinator.cancel_check_for(chat_id)` — returns `active_turn[chat_id].cancelled.is_set`).

---

## Round-boundary check points (the ONLY places `cancel_check()` is called)

| # | Location (current line) | Check placed | On `True` |
|---|---|---|---|
| 1 | before the initial `_call_openai_api` (`ai_handler.py:2066`) | immediately before the first `responses.create` | return `_cancelled_response(request, journal=[])` — no OpenAI call made at all |
| 2 | top of each `_run_local_tool_dispatch_loop` iteration (`ai_handler.py:2725`, `for _loop_round in range(...)`) | first statement inside the loop body, **before** dispatching any local tool for this round and **before** the follow-up `responses.create` | stop the loop; return `_cancelled_response(request, journal=<collected so far>)` |
| 3 | before `_finalize_response` (`ai_handler.py:2068`) | immediately before the `_finalize_response(...)` call | return `_cancelled_response(request, journal=<collected from this response's mcp_calls + ledger events persisted this turn>)` |

No check is placed **inside** a single `responses.create` call, inside `_finalize_response`
itself, or mid local-tool execution — a round boundary is the granularity (D4).

Between check #2 iterations, a local tool that already ran in a **prior** round stays done
(e.g. `_handle_ledger_event_capture` wrote a JSON file) — those go into the journal. A local
tool the model asked for in the round where the check fires is **not** dispatched.

---

## `_cancelled_response` shape

```python
AIResponse(
    request_id=request.request_id,
    response_text="",              # allowed because cancelled=True
    tokens_used=0, prompt_tokens=0, completion_tokens=0,
    model=request.model,
    finish_reason="cancelled",
    timestamp=<now_local epoch>,
    should_reply=False,
    cancelled=True,                # NEW
    side_effects_journal=[...],     # NEW — list of SideEffectRecord-shaped dicts
)
```

`AIResponse.__post_init__` is relaxed: the existing `should_reply and not has_text → ValueError`
check is **skipped when `cancelled is True`**. Every non-cancelled response keeps the invariant
unchanged.

### Journal contents (`side_effects_journal`)

Built by `AIHandler`, from structured data only — never free model text:

- **MCP calls executed server-side**: from `response.output` items with `type == "mcp_call"` and
  no `error` (same extraction as `_finalize_response` at `ai_handler.py:2936-2945`). One record
  per call: `{source: "mcp", tool_name, identifier: <doc number from output, if parseable>,
  summary_he: <built from tool_name + arguments + output>, raw: <the output item>}`.
- **`mcp_approval_request` items are NOT journalled** (`ai_handler.py:2967-2970`) — nothing
  executed; the approval simply never gets created.
- **Local ledger events persisted this turn**: `_handle_ledger_event_capture` returns the
  `event_id` of each file it wrote; those already written before the cancel point are real.
  One record per event: `{source: "ledger", tool_name: "capture_ledger_event", identifier:
  <event_id>, summary_he: <from the event dict>, raw: <event dict>}`.
- **Reminder writes**: only possible on a "כן" approval-resolution turn, which is
  **non-interruptible** (below) — so in practice no reminder write is ever mid-turn-cancelled.
  If a future path makes reminder writes reachable from an interruptible turn, the same
  "already committed → journal it" rule applies.

---

## What is NOT done on a positive check

- No local function tool is dispatched (ledger capture, reminder create/modify/delete, query).
- No further `responses.create` call is made.
- No `PendingApproval` is committed to `PendingApprovalManager`.
- No `PendingLocalToolApproval` is committed to `PendingLocalToolApprovalManager`.
- The cancelled `AIResponse` is returned to the consumer, which **does not send it** and does
  not persist an assistant message.

## What IS still done

- The interrupted turn's **user message(s) are still persisted** to the session as ordinary
  `role="user"` entries (they were real user input) — done by the consumer around the
  `get_response` call, not by `get_response`. No assistant reply row is written for the
  cancelled turn (US3 scenario 6).

---

## Non-interruptible: the "כן" / "לא" approval-execution turn

`_resolve_pending_approval` / `_resolve_pending_local_tool_approval` and their
`_call_openai_approval_api` (`ai_handler.py:3425`, `.with_options(max_retries=0)`, per
bugfix-022 double-invoice incident) **do NOT receive `cancel_check`** (REQ-RMH-007a, D7).

- An approval-execution turn always runs to completion and sends its reply.
- Any interfering text that arrives while it runs is buffered by the coordinator
  (`pending_text[chat_id]`) and becomes the **next** fresh turn — it does not cancel the
  execution turn, and the execution turn's `active_turn` handle's `cancelled` event, even if
  set by the producer, is simply never read on this path.
- After the execution turn's reply is sent, `on_turn_finished` resets; the buffered text is
  assembled into a new turn on the next consumer loop.

This is the one deliberate asymmetry: a turn that is *about to perform the already-approved
action* is protected, because interrupting it risks exactly the ambiguous "did it run or
not" state bugfix-022 was about.

---

## Immutability

- No existing `get_response` test changes — the new parameter is defaulted and inert.
- New unit tests live in `tests/unit/test_ai_handler_cancellation.py` (NEW file).
