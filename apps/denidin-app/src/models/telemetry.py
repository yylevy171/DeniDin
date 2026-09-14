"""Feature 080: RequestTelemetry - one structured record per inbound message DeniDin
processes to completion, capturing end-to-end/LLM/tool timing and token counts.

See specs/repo/features/080-higher-verbosity-speed/data-model.md for the full field-level
contract. Write-once (built up across a turn, persisted a single time at turn completion) -
no update-in-place, no retry on a crashed/failed turn (mirrors the best-effort, no-retry
posture of send_typing_indicator/log_outbound elsewhere in this codebase for non-critical-path
observability concerns).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RequestTelemetry:
    """Immutable, write-once telemetry record for one processed inbound message.

    All timestamps are timezone-aware Israel-local ISO 8601 strings (utils.time_utils.now_local()
    - never bare/naive datetimes, per CLAUDE.md's Israel-local-time rule).
    """

    request_id: str
    chat_id: str
    timestamp_received: str
    timestamp_completed: str
    total_duration_ms: int
    llm_total_inference_time_ms: int
    llm_turns_count: int
    tool_total_execution_time_ms: int
    tool_calls_count: int
    slowest_tool_name: Optional[str] = None
    slowest_tool_duration_ms: Optional[int] = None
    morning_api_request_times_ms: Optional[str] = None  # JSON object text, keyed by tool name
    input_tokens_count: int = 0
    output_tokens_count: int = 0
    had_progress_update: bool = False

    def __post_init__(self) -> None:
        """Validation rules per data-model.md - fails fast on an internally inconsistent
        record rather than persisting garbage."""
        if self.total_duration_ms < 0:
            raise ValueError(f"total_duration_ms must be >= 0, got {self.total_duration_ms}")
        if self.llm_total_inference_time_ms < 0:
            raise ValueError(
                f"llm_total_inference_time_ms must be >= 0, got {self.llm_total_inference_time_ms}"
            )
        if self.tool_total_execution_time_ms < 0:
            raise ValueError(
                f"tool_total_execution_time_ms must be >= 0, got {self.tool_total_execution_time_ms}"
            )
        if self.llm_turns_count < 0:
            raise ValueError(f"llm_turns_count must be >= 0, got {self.llm_turns_count}")
        if self.tool_calls_count < 0:
            raise ValueError(f"tool_calls_count must be >= 0, got {self.tool_calls_count}")
        if self.llm_turns_count == 0 and self.llm_total_inference_time_ms != 0:
            raise ValueError("llm_turns_count is 0 but llm_total_inference_time_ms is non-zero")
        if self.tool_calls_count == 0 and self.tool_total_execution_time_ms != 0:
            raise ValueError("tool_calls_count is 0 but tool_total_execution_time_ms is non-zero")
        has_name = self.slowest_tool_name is not None
        has_duration = self.slowest_tool_duration_ms is not None
        if has_name != has_duration:
            raise ValueError(
                "slowest_tool_name and slowest_tool_duration_ms must both be set or both be None"
            )
