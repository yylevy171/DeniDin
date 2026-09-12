# Data Model: Higher Verbosity, Active Feedback, and Latency Telemetry

## Entity: `RequestTelemetry`

New model, `apps/denidin-app/src/models/telemetry.py`. One instance per inbound user message
processed to completion (conversational or media). Persisted by `TelemetryManager`
(`managers/telemetry_manager.py`) into `{data_root}/telemetry/telemetry.db` (SQLite, one table
`request_telemetry`).

| Field | Type | Notes |
|---|---|---|
| `request_id` | `str` (UUID4) | Primary key. Minted at webhook receipt, before any processing. |
| `chat_id` | `str` | The chat the request belongs to (not in REQ-080-04's literal field list, but required to make the record useful/queryable per-chat — an addition justified by SC-003's "queryable... for future performance audits"). |
| `timestamp_received` | `str` (ISO 8601, `Asia/Jerusalem`, via `now_local()`) | Exact webhook-receipt time. |
| `timestamp_completed` | `str` (ISO 8601, `Asia/Jerusalem`) | When the final message was dispatched (or, for a no-reply turn, when processing concluded). |
| `total_duration_ms` | `int` | `timestamp_completed - timestamp_received`, in ms. |
| `llm_total_inference_time_ms` | `int` | Sum of wall-clock time across every `responses.create()` call in this turn. |
| `llm_turns_count` | `int` | Number of `responses.create()` round-trips in this turn. |
| `tool_total_execution_time_ms` | `int` | Sum of wall-clock time across every tool invocation (local function tools + remote MCP tool calls) in this turn. |
| `tool_calls_count` | `int` | Total tool invocations. |
| `slowest_tool_name` | `Optional[str]` | `None` if no tools were called. |
| `slowest_tool_duration_ms` | `Optional[int]` | `None` if no tools were called. |
| `morning_api_request_times_ms` | `Optional[str]` | JSON object text, e.g. `{"list_clients": 300, "get_invoice_details": 1200}` — `None` if no Morning MCP tools were called this turn. Keyed by tool name (the closest available proxy for "endpoint type", since denidin-app only observes MCP tool-call boundaries, not Morning's internal HTTP routes — see plan.md's Project Structure note on why deeper Morning-side instrumentation is out of scope). |
| `input_tokens_count` | `int` | Summed `response.usage.input_tokens` across all `responses.create()` calls this turn. |
| `output_tokens_count` | `int` | Summed `response.usage.output_tokens` across all `responses.create()` calls this turn. |
| `had_progress_update` | `bool` | Whether the AI sent at least one proactive interim text this turn (REQ-080-02 / SC-002 observability — lets a later audit correlate `total_duration_ms` against whether the user actually got kept in the loop). |

### Validation rules
- `request_id` unique (PK).
- `total_duration_ms`, `llm_total_inference_time_ms`, `tool_total_execution_time_ms` ≥ 0.
- `llm_turns_count`, `tool_calls_count` ≥ 0; if 0, the corresponding `*_time_ms` must be 0.
- `slowest_tool_name`/`slowest_tool_duration_ms` are both `None` or both set (never one without
  the other).
- All timestamps are timezone-aware Israel-local ISO 8601 strings (per CLAUDE.md's Israel-local
  rule) — never bare/naive datetimes.

### State transitions
None — `RequestTelemetry` is write-once (built up in memory across a turn, then persisted a
single time at turn completion). No update-in-place after the row is written; a failed/crashed
turn simply never produces a row (accepted gap, not retried — mirrors the "best-effort, no
retry" posture of `send_typing_indicator`/`log_outbound` elsewhere in this codebase for
non-critical-path telemetry/logging concerns).

### Relationships
None to other persisted entities (`Message`, `LedgerEvent`, `Reminder`, etc.) — `chat_id` is a
soft reference for querying, not a foreign key; telemetry is deliberately decoupled from
conversational state so a telemetry-store issue can never affect message processing.

## No other new persisted entities

The keep-alive renewal (REQ-080-01) and the constitution directive (REQ-080-02) introduce no new
persisted data — the renewal job lives only in the `APScheduler` in-memory job store for the
duration of one turn (cancelled/removed when the turn ends, nothing written to disk), and the
constitution addition is plain text in the already-existing `runtime_constitution.md` file.
