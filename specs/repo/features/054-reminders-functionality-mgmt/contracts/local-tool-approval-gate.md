# Integration Contracts: Local-Tool Approval Gate

**Feature**: 054-reminders-functionality-mgmt · Per METHODOLOGY.md §VII format.

---

### `PendingLocalToolApproval` / `PendingLocalToolApprovalManager` (new file:
`src/managers/pending_local_tool_approval_manager.py`)

**Deliberately NOT added to `pending_approval_manager.py`** — CONSTITUTION's test-immutability
rule protects Feature 047's existing approval-gate tests, and `PendingApproval` is structurally
tied to OpenAI's MCP-specific `mcp_approval_request`/`mcp_approval_response` mechanism, which is
meaningless for a local `function_call` in the sense that matters for the ACTION itself: there is
no server-side pending state on OpenAI's side to resolve against for approve/decline, since the
call's arguments are already fully known from `response.output`.

```python
@dataclass
class PendingLocalToolApproval:
    tool_name: str           # "create_reminder" | "modify_reminder" | "delete_reminder"
    response_id: str = ""    # the id of the Responses API call that produced this function_call
    call_id: str = ""        # that function_call item's own call_id
    arguments: dict = field(default_factory=dict)  # already json.loads'd - NOT a JSON string (unlike PendingApproval.arguments)
    created_at: str = ""     # local_isoformat(), diagnostics only, no expiry (same as PendingApproval)
    sent_message_id: Optional[str] = None   # button-tap staleness binding, same mechanism as Feature 047
```

**Correction to the original draft of this contract** (caught while implementing, 2026-08-16): an
earlier version of this dataclass dropped `response_id`/`call_id` entirely, reasoning the approved
ACTION doesn't need them (true — it dispatches straight to `ReminderManager`, no
`mcp_approval_response`-style round-trip). What that reasoning missed: the **confirmation**
follow-up call (§3 below, letting the model phrase a natural reply once the action succeeds) still
needs to chain via `previous_response_id`/reference the original `call_id` for its
`function_call_output` — and by the time the user replies "כן" on a LATER WhatsApp turn, the
original `response` object from the proposal turn is long out of scope. Only what's stored on
`PendingLocalToolApproval` survives across turns, so both fields are required after all.

`PendingLocalToolApprovalManager`: in-memory `Dict[str, PendingLocalToolApproval]` keyed by
`chat_id`, same shape as `PendingApprovalManager` — `get(chat_id)`, `set(chat_id, approval)`,
`clear(chat_id)`, `attach_sent_message_id(chat_id, id_message)`. Not disk-persisted (losing one on
restart just means the user re-issues the request, same rationale as the existing manager).

Reuses `BUTTON_ID_APPROVE`/`BUTTON_ID_DECLINE` (imported from `pending_approval_manager.py`, not
redefined) and `AIResponse.offer_approval_buttons` verbatim — both are already tool-mechanism-
agnostic (`WhatsAppHandler.send_response()`'s buttons-vs-text branch only checks
`offer_approval_buttons`, nothing MCP-specific).

---

### `AIHandler` ↔ both approval managers — dual-check dispatch contract

**`get_response()` (text-reply path) MUST**, in this fixed order:

```python
mcp_pending = self.pending_approval_manager.get(effective_chat_id) if user_obj else None
if mcp_pending is not None:
    resolved = self._resolve_pending_approval(mcp_pending, request, ...)
    if resolved is not None:
        return resolved
else:
    local_pending = self.pending_local_tool_approval_manager.get(effective_chat_id) if user_obj else None
    if local_pending is not None:
        resolved = self._resolve_pending_local_tool_approval(local_pending, request, ...)
        if resolved is not None:
            return resolved
# else: fresh-turn processing, as today
```

MCP-first-then-local-tool is deterministic and cheap: at most one of the two managers will ever
have an entry for a given `chat_id` in practice (a user doesn't have two simultaneous approval
flows), and checking `local_pending` only inside the MCP `else` branch avoids a redundant lookup
on the common case.

**`resolve_button_tap()` (button-tap path) MUST** apply the identical MCP-first-then-local-tool
check, matching `stanza_id` against whichever manager's pending entry is found.

---

### `_resolve_pending_local_tool_approval` (new method, parallel to `_resolve_pending_approval`)

```python
def _resolve_pending_local_tool_approval(
    self, pending: PendingLocalToolApproval, request: AIRequest,
    effective_chat_id: str, user_obj, user_role: str,
    sender: Optional[str], recipient: Optional[str],
) -> Optional[AIResponse]:
```

Uses `_is_affirmative_reply(request.user_prompt)` (reused verbatim — parses `"כן"`/`"לא"` exactly
as the MCP path does).

**On decline**: clear the pending entry, return `None` (falls through to fresh-turn processing —
identical in spirit to the MCP path's decline behavior).

**On approve**:
1. Dispatch directly to `ReminderManager`, selecting the method by `pending.tool_name` +
   `pending.arguments["scope"]` (for modify/delete) — using the already-parsed `arguments` dict.
   **No second OpenAI round-trip is needed for the action itself** (unlike MCP's
   `mcp_approval_response`, which requires a real server-side round-trip because OpenAI, not
   DeniDin, holds the pending call's execution state — a local `function_call`'s arguments are
   already fully known, nothing to resolve server-side).
2. On a manager-level failure (re-checked at THIS point, not just at proposal time, to close a
   TOCTOU gap — e.g. the cap was hit by a second concurrent proposal, or a slow approval flow let
   a "future" time become "past" mid-conversation): return a friendly fallback response (new
   constant in `error_messages.py`, e.g. `REMINDER_ACTION_FAILED_TRY_AGAIN`) and clear the
   pending entry regardless.
3. On success: issue **one** follow-up OpenAI Responses API call
   (`_call_openai_reminder_followup_api`, `previous_response_id`-chained to the response that
   produced the original tool call), submitting a `function_call_output` reporting the concrete
   result (e.g. `{"status": "created", "reminder_id": ..., "next_due_at": <post-rounding ISO
   datetime>}`), letting the model phrase the natural Hebrew confirmation — structurally identical
   to `_call_openai_ledger_followup_api`'s pattern (confirmed as the preferred approach over a
   hardcoded template, per user decision).
4. Clear `pending_local_tool_approval_manager` for the chat either way.

`AIResponse.offer_approval_buttons` is set `True` at the point a new `PendingLocalToolApproval` is
first `set()` — the same field Feature 047 already built, zero changes needed to
`WhatsAppHandler`/`denidin.py`'s button-send/attach-message-id wiring.
