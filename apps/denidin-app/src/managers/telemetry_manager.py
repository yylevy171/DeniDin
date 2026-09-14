"""Feature 080: TelemetryBuilder + TelemetryManager - per-request latency/token telemetry.

TelemetryBuilder accumulates timing/token data across one in-flight request, threaded through
AIHandler.get_response() and its helpers (never global/thread-local state - AIHandler already
serves concurrent chats, so telemetry must be scoped to the single in-flight request).
TelemetryManager persists the finished RequestTelemetry into a SQLite store, one row per
request, mirroring the RollMarkerStore/ReminderManager connection idiom already established in
this codebase.

See specs/repo/features/080-higher-verbosity-speed/contracts/telemetry-recorder.md for the
full interface contract and data-model.md for the RequestTelemetry field-level contract.
Recording is entirely best-effort: neither TelemetryBuilder nor TelemetryManager.record() may
ever raise into the request path - a telemetry failure must never be able to break message
processing (mirrors send_typing_indicator/log_outbound's existing posture in this codebase).
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Optional

from src.models.telemetry import RequestTelemetry
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS request_telemetry (
    request_id                     TEXT PRIMARY KEY,
    chat_id                        TEXT NOT NULL,
    timestamp_received             TEXT NOT NULL,
    timestamp_completed             TEXT NOT NULL,
    total_duration_ms              INTEGER NOT NULL,
    llm_total_inference_time_ms    INTEGER NOT NULL,
    llm_turns_count                INTEGER NOT NULL,
    tool_total_execution_time_ms   INTEGER NOT NULL,
    tool_calls_count               INTEGER NOT NULL,
    slowest_tool_name              TEXT,
    slowest_tool_duration_ms       INTEGER,
    morning_api_request_times_ms   TEXT,
    input_tokens_count             INTEGER NOT NULL,
    output_tokens_count            INTEGER NOT NULL,
    had_progress_update            INTEGER NOT NULL
);
"""


class TelemetryBuilder:
    """One instance per in-flight request. Accumulates timing/token data as the turn
    progresses; finalize() builds the immutable RequestTelemetry record once, at turn
    completion. Never raises - every accumulation method is a pure in-memory append."""

    def __init__(self, request_id: str, chat_id: str, timestamp_received: str) -> None:
        self.request_id = request_id
        self.chat_id = chat_id
        self.timestamp_received = timestamp_received
        self._start_monotonic_ms = monotonic_ms()
        self._llm_total_ms = 0
        self._llm_turns = 0
        self._tool_total_ms = 0
        self._tool_calls = 0
        self._slowest_tool_name: Optional[str] = None
        self._slowest_tool_ms: Optional[int] = None
        self._morning_times: Dict[str, int] = {}
        self._input_tokens = 0
        self._output_tokens = 0
        self._had_progress_update = False

    def record_llm_call(self, duration_ms: int, input_tokens: int, output_tokens: int) -> None:
        """Call immediately after every responses.create() call site returns - success or
        error alike, since a timed-out/errored call still consumed wall-clock time."""
        self._llm_total_ms += max(duration_ms, 0)
        self._llm_turns += 1
        self._input_tokens += max(input_tokens, 0)
        self._output_tokens += max(output_tokens, 0)

    def record_tool_call(self, tool_name: str, duration_ms: int, *, is_morning_tool: bool = False) -> None:
        """Call immediately after every local function-tool dispatch and every remote MCP
        tool-call result is observed."""
        duration_ms = max(duration_ms, 0)
        self._tool_total_ms += duration_ms
        self._tool_calls += 1
        if self._slowest_tool_ms is None or duration_ms > self._slowest_tool_ms:
            self._slowest_tool_name = tool_name
            self._slowest_tool_ms = duration_ms
        if is_morning_tool:
            self._morning_times[tool_name] = self._morning_times.get(tool_name, 0) + duration_ms

    def mark_progress_update_sent(self) -> None:
        self._had_progress_update = True

    def finalize(self, timestamp_completed: str) -> RequestTelemetry:
        """Builds the immutable RequestTelemetry record. Call once, at the point the turn's
        outbound message is actually dispatched (or processing concludes with no reply).
        total_duration_ms is measured from this builder's own construction (a monotonic clock,
        never wall-clock, for the *duration* measurement itself - only the persisted timestamp
        fields use now_local(), per data-model.md)."""
        morning_times_json = json.dumps(self._morning_times) if self._morning_times else None
        total_duration_ms = max(monotonic_ms() - self._start_monotonic_ms, 0)
        return RequestTelemetry(
            request_id=self.request_id,
            chat_id=self.chat_id,
            timestamp_received=self.timestamp_received,
            timestamp_completed=timestamp_completed,
            total_duration_ms=max(total_duration_ms, 0),
            llm_total_inference_time_ms=self._llm_total_ms,
            llm_turns_count=self._llm_turns,
            tool_total_execution_time_ms=self._tool_total_ms,
            tool_calls_count=self._tool_calls,
            slowest_tool_name=self._slowest_tool_name,
            slowest_tool_duration_ms=self._slowest_tool_ms,
            morning_api_request_times_ms=morning_times_json,
            input_tokens_count=self._input_tokens,
            output_tokens_count=self._output_tokens,
            had_progress_update=self._had_progress_update,
        )


class TelemetryManager:
    """Persists RequestTelemetry rows into {data_root}/telemetry/telemetry.db (SQLite),
    mirroring the RollMarkerStore/ReminderManager connection idiom (one long-lived connection,
    check_same_thread=False, idempotent executescript schema)."""

    def __init__(self, data_root: str) -> None:
        storage_dir = Path(data_root) / "telemetry"
        storage_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = storage_dir / "telemetry.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record(self, telemetry: RequestTelemetry) -> None:
        """Persists one row. Best-effort: catches and logs any storage failure at ERROR
        (visible, since silent telemetry loss should be diagnosable), never raises into the
        request path - telemetry must never be able to break message processing."""
        try:
            self._conn.execute(
                "INSERT INTO request_telemetry ("
                "request_id, chat_id, timestamp_received, timestamp_completed, "
                "total_duration_ms, llm_total_inference_time_ms, llm_turns_count, "
                "tool_total_execution_time_ms, tool_calls_count, slowest_tool_name, "
                "slowest_tool_duration_ms, morning_api_request_times_ms, "
                "input_tokens_count, output_tokens_count, had_progress_update"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    telemetry.request_id,
                    telemetry.chat_id,
                    telemetry.timestamp_received,
                    telemetry.timestamp_completed,
                    telemetry.total_duration_ms,
                    telemetry.llm_total_inference_time_ms,
                    telemetry.llm_turns_count,
                    telemetry.tool_total_execution_time_ms,
                    telemetry.tool_calls_count,
                    telemetry.slowest_tool_name,
                    telemetry.slowest_tool_duration_ms,
                    telemetry.morning_api_request_times_ms,
                    telemetry.input_tokens_count,
                    telemetry.output_tokens_count,
                    int(telemetry.had_progress_update),
                ),
            )
            self._conn.commit()
        except Exception as error:  # pylint: disable=broad-except
            logger.error(
                f"TelemetryManager.record failed for request_id={telemetry.request_id!r}: {error}",
                exc_info=True,
            )

    def get(self, request_id: str) -> Optional[sqlite3.Row]:
        """Read-only lookup, used by tests/manual inspection - not on the request path."""
        return self._conn.execute(
            "SELECT * FROM request_telemetry WHERE request_id = ?", (request_id,)
        ).fetchone()

    def get_latest_by_chat(self, chat_id: str) -> Optional[sqlite3.Row]:
        """Read-only lookup of the most recently recorded row for a chat - used by
        billed/expensive tests (Feature 080 acceptance scenarios), which know the chat_id
        they sent a turn on but not that turn's internal request_id. rowid is
        insertion-order, so MAX(rowid) is "most recent" without needing a separate
        timestamp-ordering column."""
        return self._conn.execute(
            "SELECT * FROM request_telemetry WHERE chat_id = ? ORDER BY rowid DESC LIMIT 1",
            (chat_id,),
        ).fetchone()


def monotonic_ms() -> int:
    """Shared helper for callers bracketing a timed span - milliseconds, monotonic clock
    (never wall-clock/now_local() for a *duration* measurement - only for the persisted
    timestamp fields themselves, per data-model.md)."""
    return int(time.monotonic() * 1000)
