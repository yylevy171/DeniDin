# Contract: Telemetry Recorder

## Participants
- `AIHandler` (accumulates timing/token data across a turn)
- New: `TelemetryManager` (`managers/telemetry_manager.py`) — persists the finished record
- `RequestTelemetry` model (`models/telemetry.py`)
- `{data_root}/telemetry/telemetry.db` (SQLite)

## Interface

```python
class TelemetryBuilder:
    """One instance per in-flight request, created at webhook receipt, threaded through
    get_response() and its helpers (never global/thread-local state - see research.md R3)."""

    def __init__(self, request_id: str, chat_id: str, timestamp_received: str) -> None: ...

    def record_llm_call(self, duration_ms: int, input_tokens: int, output_tokens: int) -> None:
        """Called immediately after every responses.create() call site returns (success or
        error - a timed-out/errored call still consumed wall-clock time and must count)."""

    def record_tool_call(self, tool_name: str, duration_ms: int, *, is_morning_tool: bool = False) -> None:
        """Called immediately after every local function-tool dispatch and every remote MCP
        tool-call result is observed in the response output."""

    def mark_progress_update_sent(self) -> None: ...

    def finalize(self, timestamp_completed: str) -> RequestTelemetry:
        """Builds the immutable RequestTelemetry record. Called once, at the point the turn's
        outbound message is actually dispatched (or processing concludes with no reply)."""


class TelemetryManager:
    def __init__(self, data_root: Path) -> None: ...
    def record(self, telemetry: RequestTelemetry) -> None:
        """Persists one row. Best-effort: catches and logs any storage failure, never raises
        into the request path (telemetry must never be able to break message processing)."""
```

## Preconditions
- `feature_flags.verbosity_and_telemetry_080` is on (when off, `TelemetryBuilder` is still
  constructed cheaply — timing calls are no-ops or simply unused — but `TelemetryManager.record`
  is never called, so the path is otherwise byte-identical to today per CLAUDE.md's feature-flag
  rule).
- `TelemetryManager` is constructed once at app startup (`initialize_app`), same lifecycle shape
  as `SessionManager`/`MemoryManager`.

## Postconditions
- Exactly one `RequestTelemetry` row per successfully-completed inbound message when the flag is
  on (per data-model.md's "write-once, no retry on failure" rule — a crashed turn simply
  produces no row, not a partial/corrupt one).
- `record()` never raises.

## Error handling
- SQLite write failure (disk full, lock contention, etc.): caught, logged at ERROR (visible,
  since silent telemetry loss should be diagnosable), never re-raised or retried — consistent
  with this feature being observability tooling, not user-facing functionality whose failure
  should degrade the user experience.
