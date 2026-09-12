# Contract: `send_reaction()` (Green API reaction client)

**Location**: `apps/denidin-app/src/utils/green_api_bot.py`, alongside the existing
`mark_message_read`/`send_proactive_message`/`send_typing_indicator` helpers.

**Depends on**: `research.md` R1 (Gate Zero) — the endpoint path/payload below is the best current
assumption from Green API's public documentation, **not yet live-confirmed**. Implementation and
unit tests may proceed against a stubbed `bot.api.raw_request`; nothing calling this in a real
environment should be treated as trustworthy until R1 closes.

## Signature

```python
def send_reaction(bot, chat_id: str, message_id: str, reaction: str) -> bool:
    """Send or clear a native WhatsApp emoji reaction on a specific message.

    Args:
        bot: the live GreenAPIBot instance (same object every other helper in this module takes).
        chat_id: the WhatsApp chat id (@c.us or @g.us).
        message_id: the real Green API idMessage of the target message — NEVER DeniDin's own
            internal Message.message_id UUID.
        reaction: a single unicode emoji, or "" to clear an existing reaction.

    Returns:
        True if Green API accepted the reaction, False on any failure (network, timeout, 4xx/5xx,
        deleted-message error, etc.) — this function NEVER raises.
    """
```

## Behavior contract

1. Builds the request via the SDK's existing `bot.api.raw_request(method="POST", url=..., json=...)`
   escape hatch — never a hand-rolled `requests` call, never a patch onto the vendored SDK.
2. On a 5xx response or a network/timeout exception: retry **exactly once**, after a 1-second sleep
   (CONSTITUTION §XI). On a 4xx response: **never** retry — log and return `False` immediately
   (a 4xx here is expected for the deleted-message edge case per `spec.md`, and retrying it would
   violate the retry policy for no benefit).
3. Every failure path (initial or post-retry) logs at `WARNING` with `chat_id`/`message_id` context
   — never at `ERROR`, and never re-raised — per REQ-084-007 ("reaction failures... MUST be logged
   at WARNING level and MUST NOT fail the active conversation or transaction").
4. Success (`200`) returns `True`; every other outcome returns `False`. Callers never need their
   own `try/except` around this function — the contract is "this always returns cleanly."

## Callers (all three go through this one function — no caller duplicates its own error handling)

- The fast-path pre-dispatch hook (`contracts/fast-path-reaction-heuristic.md`).
- The `react_to_message` AI tool's dispatch (`contracts/react-to-message-tool-schema.md`).
- Any future deferred-flip call site (e.g. ledger-finalization code flipping a document's reaction
  to ✅ — implemented via the AI tool per the spec's own framing, not a separate direct call site,
  but documented here in case a non-AI-driven flip is ever added).

## Testing

Unit-testable in full isolation against a stubbed `bot.api.raw_request` (permitted — CONSTITUTION
§V's no-mocking rule applies to internal components in *integration* tests; a third-party network
call stub at the unit tier is standard practice here, same as elsewhere in this codebase):
- Success path returns `True`.
- 5xx followed by a successful retry returns `True`, and the retry actually happened (one sleep,
  one repeat call).
- 5xx followed by another failure returns `False`, WARNING logged, no second retry attempt.
- 4xx returns `False` immediately, WARNING logged, no retry attempted.
- A raised exception (e.g. connection error) is caught, logged, returns `False`, never propagates.
