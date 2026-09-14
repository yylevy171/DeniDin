"""Feature 080 — TelemetryBuilder + TelemetryManager (T004/T016).

Pins the accumulation contract from contracts/telemetry-recorder.md and the field-level
validation rules from data-model.md.
"""
import sqlite3
import time

import pytest

from src.managers.telemetry_manager import TelemetryBuilder, TelemetryManager
from src.models.telemetry import RequestTelemetry


@pytest.fixture
def manager(tmp_path):
    return TelemetryManager(str(tmp_path))


class TestTelemetryBuilder:
    def test_no_calls_finalizes_to_zeroed_record(self):
        builder = TelemetryBuilder("req-1", "chat-1", "2026-09-12T10:00:00+03:00")
        record = builder.finalize("2026-09-12T10:00:01+03:00")
        assert record.llm_turns_count == 0
        assert record.llm_total_inference_time_ms == 0
        assert record.tool_calls_count == 0
        assert record.tool_total_execution_time_ms == 0
        assert record.slowest_tool_name is None
        assert record.slowest_tool_duration_ms is None
        assert record.had_progress_update is False

    def test_record_llm_call_accumulates_turns_and_tokens(self):
        builder = TelemetryBuilder("req-2", "chat-1", "2026-09-12T10:00:00+03:00")
        builder.record_llm_call(duration_ms=500, input_tokens=100, output_tokens=50)
        builder.record_llm_call(duration_ms=300, input_tokens=80, output_tokens=20)
        record = builder.finalize("2026-09-12T10:00:01+03:00")
        assert record.llm_turns_count == 2
        assert record.llm_total_inference_time_ms == 800
        assert record.input_tokens_count == 180
        assert record.output_tokens_count == 70

    def test_record_tool_call_tracks_slowest(self):
        builder = TelemetryBuilder("req-3", "chat-1", "2026-09-12T10:00:00+03:00")
        builder.record_tool_call("list_clients", 300)
        builder.record_tool_call("get_invoice_details", 1200)
        builder.record_tool_call("query_ledger_events", 50)
        record = builder.finalize("2026-09-12T10:00:01+03:00")
        assert record.tool_calls_count == 3
        assert record.tool_total_execution_time_ms == 1550
        assert record.slowest_tool_name == "get_invoice_details"
        assert record.slowest_tool_duration_ms == 1200

    def test_morning_tool_calls_captured_as_json_breakdown(self):
        builder = TelemetryBuilder("req-4", "chat-1", "2026-09-12T10:00:00+03:00")
        builder.record_tool_call("list_clients", 300, is_morning_tool=True)
        builder.record_tool_call("query_ledger_events", 50, is_morning_tool=False)
        record = builder.finalize("2026-09-12T10:00:01+03:00")
        assert record.morning_api_request_times_ms == '{"list_clients": 300}'

    def test_mark_progress_update_sent(self):
        builder = TelemetryBuilder("req-5", "chat-1", "2026-09-12T10:00:00+03:00")
        builder.mark_progress_update_sent()
        record = builder.finalize("2026-09-12T10:00:01+03:00")
        assert record.had_progress_update is True

    def test_total_duration_ms_measured_from_construction(self):
        builder = TelemetryBuilder("req-6", "chat-1", "2026-09-12T10:00:00+03:00")
        time.sleep(0.05)
        record = builder.finalize("2026-09-12T10:00:01+03:00")
        assert record.total_duration_ms >= 40  # allow scheduling slack, still clearly > 0


class TestRequestTelemetryValidation:
    def _base_kwargs(self, **overrides):
        kwargs = dict(
            request_id="req-x",
            chat_id="chat-x",
            timestamp_received="2026-09-12T10:00:00+03:00",
            timestamp_completed="2026-09-12T10:00:01+03:00",
            total_duration_ms=1000,
            llm_total_inference_time_ms=500,
            llm_turns_count=1,
            tool_total_execution_time_ms=0,
            tool_calls_count=0,
        )
        kwargs.update(overrides)
        return kwargs

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError):
            RequestTelemetry(**self._base_kwargs(total_duration_ms=-1))

    def test_zero_turns_with_nonzero_llm_time_rejected(self):
        with pytest.raises(ValueError):
            RequestTelemetry(**self._base_kwargs(llm_turns_count=0, llm_total_inference_time_ms=500))

    def test_slowest_tool_name_without_duration_rejected(self):
        with pytest.raises(ValueError):
            RequestTelemetry(**self._base_kwargs(slowest_tool_name="foo", slowest_tool_duration_ms=None))

    def test_valid_record_constructs(self):
        record = RequestTelemetry(**self._base_kwargs())
        assert record.request_id == "req-x"


class TestTelemetryManager:
    def test_record_and_get_round_trips(self, manager):
        builder = TelemetryBuilder("req-7", "chat-1", "2026-09-12T10:00:00+03:00")
        builder.record_llm_call(200, 10, 5)
        builder.record_tool_call("list_clients", 100, is_morning_tool=True)
        record = builder.finalize("2026-09-12T10:00:01+03:00")

        manager.record(record)

        row = manager.get("req-7")
        assert row is not None
        assert row["request_id"] == "req-7"
        assert row["llm_turns_count"] == 1
        assert row["tool_calls_count"] == 1
        assert row["morning_api_request_times_ms"] == '{"list_clients": 100}'
        assert bool(row["had_progress_update"]) is False

    def test_get_missing_request_returns_none(self, manager):
        assert manager.get("does-not-exist") is None

    def test_record_failure_is_caught_and_never_raises(self, manager):
        class _BoomConnection:
            def execute(self, *args, **kwargs):
                raise sqlite3.OperationalError("disk full (simulated)")

        manager._conn = _BoomConnection()  # pylint: disable=protected-access
        builder = TelemetryBuilder("req-8", "chat-1", "2026-09-12T10:00:00+03:00")
        record = builder.finalize("2026-09-12T10:00:01+03:00")

        manager.record(record)  # must not raise

    def test_two_managers_same_data_root_share_the_same_db_file(self, tmp_path):
        m1 = TelemetryManager(str(tmp_path))
        builder = TelemetryBuilder("req-9", "chat-1", "2026-09-12T10:00:00+03:00")
        m1.record(builder.finalize("2026-09-12T10:00:01+03:00"))

        m2 = TelemetryManager(str(tmp_path))
        assert m2.get("req-9") is not None
