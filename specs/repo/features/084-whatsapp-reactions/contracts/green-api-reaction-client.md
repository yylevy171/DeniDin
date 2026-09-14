# Contract: `send_reaction()` (Green API reaction client)

**Location**: `apps/denidin-app/src/utils/green_api_bot.py`, alongside the existing
`mark_message_read`/`send_proactive_message`/`send_typing_indicator` helpers.

**Status**: mechanism and endpoint shape are **live-confirmed** — see `research.md` R1 (Gate Zero,
closed 2026-09-12). Group-chat (`@g.us`) behavior is assumed identical by analogy, not
independently live-verified (`research.md` R1 item 6).

## Signature

```python
def send_reaction(bot, chat_id: str, id_message: str, reaction: str) -> bool:
    """Send or clear a native WhatsApp emoji reaction on a specific message.

    Args:
        bot: the live GreenAPIBot instance (same object every other helper in this module takes).
        chat_id: the WhatsApp chat id (@c.us or @g.us).
        id_message: the real Green API idMessage of the target message — NEVER DeniDin's own
            internal Message.message_id UUID. Must be a message the USER sent; reacting to a
            message DeniDin itself sent returns 200 but never renders (research.md R4) — this is
            never expected to be called with such an id given this feature's actual use cases.
        reaction: a single unicode emoji, or "" to clear an existing reaction.

    Returns:
        True if Green API accepted the request (HTTP 200), False on any failure (network,
        timeout, 4xx/5xx) — this function NEVER raises. Note: a 200 does NOT guarantee the target
        message still exists or that the reaction is visibly applied (research.md R1 item 5 —
        Green API does not synchronously validate the target id) — callers must not treat True as
        proof of a visible effect, only as "the call was accepted."
    """
```

## Behavior contract

1. Builds the request via `bot.api.request("POST", url, payload)` — the SDK's existing higher-level
   wrapper (used internally by every other `Sending` method, e.g. `sendMessage`), which performs
   its own `{{host}}`/`{{idInstance}}`/`{{apiTokenInstance}}` URL templating. **Not** `raw_request`
   (superseded during Gate Zero — `raw_request` takes literal `requests.Session.request` kwargs
   with no templating and is a worse fit than the SDK's own idiom).
2. Confirmed live endpoint/payload (`research.md` R1):
   ```
   POST {{host}}/waInstance{{idInstance}}/sendReaction/{{apiTokenInstance}}
   Body: {"chatId": chat_id, "idMessage": id_message, "reaction": reaction}
   ```
3. On a 5xx response or a network/timeout exception: retry **exactly once**, after a 1-second sleep
   (CONSTITUTION §XI). On a 4xx response: **never** retry — log and return `False` immediately.
   Note: a deleted/nonexistent target message does **not** surface as a 4xx (confirmed live — it
   returns 200 like any other call), so this retry-vs-no-retry distinction in practice only ever
   fires for genuine validation errors (e.g. a malformed `chat_id`), not for the deleted-message
   edge case, which resolves itself silently via the 200-regardless-of-target-validity behavior.
4. Every failure path (initial or post-retry) logs at `WARNING` with `chat_id`/`id_message` context
   — never at `ERROR`, and never re-raised — per REQ-084-007.
5. Success (`200`) returns `True`; every other outcome returns `False`. Callers never need their
   own `try/except` around this function.

## Deleted-message edge case (spec.md) — resolved behavior, no special code needed

Per `research.md` R1 item 5, Green API accepts a reaction call against a message that no longer
exists exactly the same way it accepts one against a message that does — both return `200`. This
means the deleted-message edge case requires **no explicit detection or suppression logic**: the
call simply succeeds (from this codebase's point of view) and has no visible effect, which is
already the correct, silent, non-blocking behavior REQ-084-007 and the spec's edge case both call
for. Do not add speculative error-handling for a 4xx-on-deleted-message scenario — it does not
occur.

## Callers (all three go through this one function — no caller duplicates its own error handling)

- The fast-path pre-dispatch hook (`contracts/fast-path-reaction-heuristic.md`).
- The `react_to_message` AI tool's dispatch (`contracts/react-to-message-tool-schema.md`).

## Testing

Unit-testable in full isolation against a stubbed `bot.api.request` (permitted — CONSTITUTION §V's
no-mocking rule applies to internal components in *integration* tests; a third-party network call
stub at the unit tier is standard practice here, same as elsewhere in this codebase):
- Success path returns `True`, called with the confirmed `sendReaction` URL and
  `{chatId, idMessage, reaction}` payload shape.
- 5xx followed by a successful retry returns `True`, and the retry actually happened (one sleep,
  one repeat call).
- 5xx followed by another failure returns `False`, WARNING logged, no second retry attempt.
- 4xx returns `False` immediately, WARNING logged, no retry attempted.
- A raised exception (e.g. connection error) is caught, logged, returns `False`, never propagates.
