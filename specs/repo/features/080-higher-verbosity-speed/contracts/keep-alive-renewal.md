# Contract: Keep-Alive Typing Renewal

## Participants
- `WhatsAppHandler`/`denidin.py` (turn start/end boundary — already the call site for feature
  048's `send_typing_indicator`)
- New: a renewal job registered on the app's existing `APScheduler` scheduler instance
- Green API `sendTyping` endpoint (external, real, no mocking)

## Interface

```python
def start_typing_keepalive(
    scheduler: BackgroundScheduler,
    bot: Any,
    chat_id: str,
    is_blocked: bool,
    *,
    interval_seconds: int = 15,
    max_duration_seconds: int = 180,
) -> Optional[str]:
    """Starts a renewal job (unique job id, returned) that re-sends sendTyping every
    interval_seconds until stop_typing_keepalive() is called or max_duration_seconds elapses
    (safety cap - mirrors feature 048's original cap). Returns None (no job started) if
    is_blocked. Never raises - identical best-effort/log-only posture as
    send_typing_indicator()."""

def stop_typing_keepalive(scheduler: BackgroundScheduler, job_id: Optional[str]) -> None:
    """Cancels the renewal job. No-op if job_id is None or already gone. Called the instant
    DeniDin's turn ends (a reply, interim clarification, or approval prompt is sent) -
    identical 'DeniDin's turn' semantics as feature 048's Q4."""
```

## Preconditions
- `scheduler` is already running (the app's shared `BackgroundScheduler`, same instance used by
  `reminder_delivery_service`/`accounting_reconciliation_service` — reusing the existing
  scheduler rather than spinning up a second one).
- Called only from the two existing feature-048 call sites (`_process_conversational_message`,
  the shared media-message wrapper) — `start_typing_keepalive` replaces the current single
  `send_typing_indicator` call at each when `feature_flags.verbosity_and_telemetry_080` is on;
  `stop_typing_keepalive` is called wherever the turn's outbound send happens.

## Postconditions
- On success: Green API receives a `sendTyping` call at turn start (immediate,
  `next_run_time=now_local()`) and every `interval_seconds` thereafter, until stopped or capped.
- On failure of an individual renewal tick (network error, etc.): logged at WARNING, job keeps
  running for the next tick — mirrors `send_typing_indicator`'s existing best-effort posture,
  never raises into the request path.
- Never blocks: `start_typing_keepalive`/`stop_typing_keepalive` are non-blocking scheduler
  calls (`add_job`/`remove_job`), not the HTTP call itself.

## Error handling
Same as `send_typing_indicator` today: catch broad `Exception` around the `sendTyping` call
itself inside the job body, log at WARNING, never propagate — a keep-alive failure is purely
cosmetic and must never affect message processing (CLAUDE.md retry-policy precedent).
