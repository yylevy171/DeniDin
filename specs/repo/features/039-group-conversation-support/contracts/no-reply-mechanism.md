# Integration Contracts: No-Reply Mechanism

**Feature**: 039-group-conversation-support · Per METHODOLOGY.md §VII format. (NEW 2026-08-04,
from test-plan review — see research.md §8.)

Confirmed this capability doesn't exist anywhere in the app today: `WhatsAppHandler.send_response`
unconditionally sends `response.response_text`; every processed message currently always gets a
reply. This contract introduces it for the first time.

---

### `config/runtime_constitution.md` ↔ `AIHandler` Contract

**Constitution guidance MUST**:
- Instruct the model to output the literal sentinel string `[[NO_REPLY]]` (finalized at
  `speckit.tasks`) as its **entire** `response_text` — nothing else — when
  US5's "clearly for someone else" outcome or US7's "`@Name` doesn't refer to me" outcome
  applies. The sentinel must be a string realistically unlikely to occur in a genuine Hebrew
  conversational reply (per this app's `ALWAYS respond in Hebrew only` rule), to avoid false
  positives.
- NOT instruct the model to use this sentinel for US5's "genuinely unclear" outcome — that case
  gets a normal (Hebrew) clarifying-question reply, not silence.

**`AIHandler` MUST**:
- In `_finalize_response` (`ai_handler.py:1102-1284`), check `response_text` for an exact match
  against the sentinel (after trimming whitespace) before any other post-processing.
- On a match: set `AIResponse.should_reply = False`; persist the triggering user message
  normally (`add_message`/`add_message_with_token_limit`, exactly as any other turn); skip
  persisting an assistant-role message for this turn (there is no real reply to record).
- On no match: set `AIResponse.should_reply = True` (the default) and proceed exactly as today.

**`AIHandler` PROVIDES**:
- `AIResponse.should_reply: bool` (new field, default `True`) — the only new public surface
  this mechanism adds. `response_text` is never returned to the caller as the literal sentinel
  when `should_reply` is `False` (callers should not need to special-case the sentinel value
  themselves — checking the flag is sufficient).

---

### `AIHandler` ↔ `denidin.py` Contract

**`denidin.py` (`_process_conversational_message`) MUST**:
- Check `ai_response.should_reply` before calling `WhatsAppHandler.send_response`. When
  `False`, skip the send entirely (no call to `send_response`, no fallback message, no error —
  this is expected, successful "no reply" behavior, not a failure path).
- Continue all other post-response logic (logging, tracking) unchanged — only the actual
  WhatsApp send is conditional.

**`AIHandler` EXPECTS** (unchanged): Same as today — a `WhatsAppMessage` and correctly-threaded
`sender`/`user_phone` arguments. This contract adds no new expectations on the caller beyond
checking the new flag before sending.

---

### Failure/Edge-Case Notes

- If the model's output starts with the sentinel but includes trailing content (a formatting
  slip), `_finalize_response` requires an **exact** trimmed match — any deviation is treated as
  a normal reply and sent as-is (never silently drop a real reply on a near-miss). This favors
  "occasionally answers when it should have stayed silent" over "occasionally goes silent when
  it should have answered" — the latter is a worse user experience (a message that appears to
  vanish with no explanation).
- The no-reply outcome is never treated as an error — no fallback/error message is sent, no
  exception is raised, no retry occurs. It is a first-class, successful outcome of a turn.
