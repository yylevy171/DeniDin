"""
Unit tests for Feature 025's accounting-document reconciliation sweep
(tasks.md T011a/T012a): _sweep_accounting_documents / _parse_list_invoices_total /
run_startup_accounting_reconciliation_sweep / start_accounting_reconciliation_scheduler.

A real AIHandler (with a real LedgerEventManager, isolated to tmp_path) is used -
only the OpenAI client itself is a stand-in (external-service, per CONSTITUTION
SS I's unit-tier allowance), matching this codebase's existing pattern for
ai_handler.py unit tests. No real router/webhook entry point exists for this
feature (CONSTITUTION SS V) - unit, not integration, tier.
"""
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.utils.time_utils import now_local
import src.services.accounting_reconciliation_service as svc
from src.services.accounting_reconciliation_service import (
    _sweep_accounting_documents, _parse_list_invoices_total, _build_reconciliation_prompt,
    run_startup_accounting_reconciliation_sweep, start_accounting_reconciliation_scheduler,
    RECONCILIATION_SWEEP_JOB_ID, MAX_CATCHUP_LOOKBACK, MAX_CATCHUP_DOCUMENT_COUNT,
)


@pytest.fixture
def mock_config(tmp_path):
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-5.6-luna"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = str(tmp_path / "data")
    config.memory = {'session': {'storage_dir': str(tmp_path / "data" / "sessions")}, 'longterm': {'enabled': False}}
    config.user_roles = {}
    config.godfather_phone = None
    config.mcp = {'morning_auth_token': 'test-token', 'morning_server_label': 'morning-invoices'}
    return config


@pytest.fixture
def mock_ai_client():
    client = MagicMock()
    # bugfix-047: the sweep now issues its call via
    # client.with_options(timeout=..., max_retries=0).responses.create(...).
    # Self-return so every existing `mock_ai_client.responses.create`
    # assertion in this file keeps addressing the same call.
    client.with_options.return_value = client
    return client


@pytest.fixture
def ai_handler(mock_config, mock_ai_client, monkeypatch):
    handler = AIHandler(mock_ai_client, mock_config)
    # Morning MCP is normally discovered via a live status file - stubbed here
    # to always report a reachable server, matching this file's "only the
    # OpenAI client is a stand-in" scope.
    monkeypatch.setattr(
        handler.morning_mcp_locator, "current_server_url",
        lambda: "https://fake-morning-mcp.example.com/mcp"
    )
    return handler


@pytest.fixture
def global_context(ai_handler):
    return SimpleNamespace(ai_handler=ai_handler)


def _mcp_call_item(name, output):
    return SimpleNamespace(type="mcp_call", name=name, output=output)


def _capture_call_item(event, call_id="call_0"):
    return SimpleNamespace(
        type="function_call", name="capture_ledger_event",
        arguments=json.dumps(event), call_id=call_id,
    )


# creation_date is deliberately RELATIVE to "now", never a frozen literal:
# the reconciliation watermark, the 5-day catch-up cap AND the ~7-day
# cache-retention prune all key off this exact timestamp. A hardcoded date
# silently rotted both `test_gap_within_five_days_proceeds_normally` and the
# cross-tick dedup test the moment wall-clock time moved >7 days past it
# (caught 2026-08-30 - the doc was pinned at 2026-08-20). ~1h ago keeps it
# unambiguously inside every one of those windows for the whole test run.
_ACCOUNTING_DOC_CREATION = now_local() - timedelta(hours=1)
ACCOUNTING_DOC = {
    "display_number": "40406", "internal_morning_id": "056ee93c",
    "type": 300, "type_name": "חשבון עסקה",
    "status": "paid", "status_code": 2, "status_label": "מסמך סומן ידנית כסגור",
    "client_name": "לקוח בדיקה", "description": "חשבונית מס 40406",
    "amount": 1000, "amount_excl_vat": 1000, "vat_amount": 180, "vat_rate": 0.18,
    "currency": "ILS",
    "document_date": _ACCOUNTING_DOC_CREATION.strftime("%Y-%m-%d"), "due_date": None,
    "creation_date": _ACCOUNTING_DOC_CREATION.isoformat(),
    "payment": None, "linked_document": None,
}

ACCOUNTING_EVENT = {
    "source_type": "חשבונית",
    "event_subtype": "הפקה",
    "accounting_document_json": json.dumps(ACCOUNTING_DOC, ensure_ascii=False),
}


class TestParseListInvoicesTotal:
    """Feature 025, T011a/round-4: reads the TRUE total from list_invoices'
    real output text (never the AI's own summary) - the safety cap's
    100-document half's actual enforcement point."""

    def test_no_list_invoices_call_returns_none(self):
        response = SimpleNamespace(output=[_capture_call_item(ACCOUNTING_EVENT)])
        assert _parse_list_invoices_total(response) is None

    def test_none_found_text_returns_zero(self):
        response = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])
        assert _parse_list_invoices_total(response) == 0

    def test_plain_found_text_returns_the_count(self):
        response = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", "נמצאו 7 חשבוניות:\n\n..."),
        ])
        assert _parse_list_invoices_total(response) == 7

    def test_truncated_text_returns_the_true_total_not_the_shown_count(self):
        response = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", "מוצגות 20 מתוך 150 חשבוניות שנמצאו:\n\n..."),
        ])
        assert _parse_list_invoices_total(response) == 150

    def test_too_many_text_returns_the_stated_total(self):
        response = SimpleNamespace(output=[
            _mcp_call_item(
                "list_invoices",
                "נמצאו 340 חשבוניות התואמות את החיפוש - יותר מדי להצגה כרשימה אחת. "
                "אנא צמצם/י את החיפוש.",
            ),
        ])
        assert _parse_list_invoices_total(response) == 340

    def test_multiple_list_invoices_calls_takes_the_max(self):
        response = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", "נמצאו 5 חשבוניות:"),
            _mcp_call_item("list_invoices", "נמצאו 12 חשבוניות:"),
        ])
        assert _parse_list_invoices_total(response) == 12

    def test_unparseable_output_returns_none_and_warns(self, caplog):
        import logging
        response = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", "some unexpected output shape"),
        ])
        with caplog.at_level(logging.WARNING):
            result = _parse_list_invoices_total(response)
        assert result is None
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_ignores_other_mcp_calls(self):
        response = SimpleNamespace(output=[
            _mcp_call_item("get_invoice_details", "חשבונית #40406\n..."),
        ])
        assert _parse_list_invoices_total(response) is None


class TestBuildReconciliationPrompt:
    def test_includes_since_date(self):
        since = now_local().replace(year=2026, month=8, day=15)
        prompt = _build_reconciliation_prompt(since)
        assert "2026-08-15" in prompt

    def test_instructs_one_capture_call_per_document(self):
        prompt = _build_reconciliation_prompt(now_local())
        assert "capture_ledger_event" in prompt
        # Wording updated 2026-08-22 to the live-proven text; intent unchanged
        # (exactly one call per document, never merged, never skipped).
        assert "one call per document" in prompt
        assert "never merged, never skipped" in prompt

    def test_says_this_is_not_a_conversation(self):
        prompt = _build_reconciliation_prompt(now_local())
        assert "never write a text reply" in prompt.lower()
        assert "no human will read one" in prompt.lower()

    def test_is_a_single_tool_call_flow_with_server_side_detail_fanout(self):
        """Superseded the 2026-08-21 "you MUST call get_invoice_details"
        wording (replaced 2026-08-22, user decision, after live playground
        trials). Root cause of that whole detour: /documents/search - the call
        list_invoices already makes - returns creationDate for every document,
        but morning-mcp-app's formatter dropped it, so the sweep was chasing N
        extra get_invoice_details calls to recover data the first call had
        already fetched. Worse, get_invoice_details' own tool description
        scopes it to status-change flows ("mark as paid"/"cancel"), which
        outweighed any user-message instruction - it was never once called
        across 6 live trials. Now that list_invoices' output carries the
        creation timestamp and description, this is a one-tool-call flow:
        proven 18/18 documents fully correct across 3 consecutive live
        trials."""
        prompt = _build_reconciliation_prompt(now_local())
        assert "list_invoices" in prompt
        # Phase 9 final shape: bank details and linkedDocuments DO come from the
        # single-document GET, but morning-mcp-app performs that fan-out
        # server-side, deterministically. Asking the MODEL to chain those N
        # calls was tried live and failed - it stopped after a couple of
        # captures without ever calling get_invoice_details, even after that
        # tool's misleading description was fixed.
        assert "do NOT need get_invoice_details" in prompt
        assert "already complete" in prompt

    def test_asks_for_machine_readable_output_and_verbatim_copying(self):
        """Phase 9 (2026-08-23): the model no longer transcribes ~25 labelled
        Hebrew fields - it requests output_format="json" and copies each
        document's JSON object verbatim into one argument, with ALL mapping
        and derivation done in code. Prose transcription is what produced a
        fabricated 00:00 timestamp and null amounts in real live runs."""
        prompt = _build_reconciliation_prompt(now_local())
        assert 'output_format="json"' in prompt
        assert "accounting_document_json" in prompt
        assert "verbatim" in prompt

    def test_asks_for_full_details_explicitly(self):
        """The per-document fan-out is gated on include_full_details, NOT on
        output_format (user catch, 2026-08-23): Phase 9b makes JSON universal,
        so a format-based gate would make every ordinary list explode. The
        sweep always needs the full detail (bank + linkage), so it always asks
        for it - conversations may ask too, but only when they need it."""
        prompt = _build_reconciliation_prompt(now_local())
        assert "include_full_details=true" in prompt

    def test_forbids_the_model_altering_the_payload(self):
        """The failure mode Phase 9 designs out: the model "helping" by
        summarising/reformatting instead of copying."""
        prompt = _build_reconciliation_prompt(now_local())
        for forbidden in ("summarise", "reorder", "translate", "drop fields"):
            assert forbidden in prompt

    def test_handles_the_empty_list_case_explicitly(self):
        prompt = _build_reconciliation_prompt(now_local())
        assert '"documents" is empty' in prompt


class TestSweepAccountingDocumentsWatermarkAndCap:
    """T011a: watermark derivation, 5-day pre-check, 100-doc post-check."""

    def test_no_known_events_uses_fallback_lookback(self, ai_handler, global_context, mock_ai_client):
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])

        _sweep_accounting_documents(global_context)

        call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        prompt = call_kwargs["input"][0]["content"]
        expected_since = (now_local() - svc.FALLBACK_LOOKBACK).strftime("%Y-%m-%d")
        assert expected_since in prompt

    def test_gap_exceeding_five_days_skips_entire_tick_no_openai_call(
        self, ai_handler, global_context, mock_ai_client
    ):
        """Pre-check: pure local computation, no call needed at all."""
        # Phase 9: the watermark comes from the document's OWN creation_date in
        # the JSON payload, not from message_timestamp - so staleness is seeded
        # there.
        stale_doc = dict(ACCOUNTING_DOC,
                         creation_date=(now_local() - timedelta(days=10)).isoformat())
        ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s",
            event=dict(ACCOUNTING_EVENT, accounting_document_json=json.dumps(stale_doc, ensure_ascii=False)),
            message_id=None, message_timestamp=None,
        )

        _sweep_accounting_documents(global_context)

        mock_ai_client.responses.create.assert_not_called()

    def test_gap_within_five_days_proceeds_normally(self, ai_handler, global_context, mock_ai_client):
        recent_ts = int((now_local() - timedelta(hours=1)).timestamp())
        ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s", event=dict(ACCOUNTING_EVENT), message_id=None,
            message_timestamp=recent_ts,
        )
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])

        _sweep_accounting_documents(global_context)

        mock_ai_client.responses.create.assert_called_once()

    def test_openai_call_sets_an_explicit_max_output_tokens(
        self, ai_handler, global_context, mock_ai_client
    ):
        """Real bug found live (2026-08-22): this was the ONLY OpenAI call in
        the app that set no output cap at all, silently relying on whatever
        the API's own default is. A full sweep emits one capture_ledger_event
        call per document (up to this feature's own 100-document safety cap),
        so an unstated default is a real truncation risk."""
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])

        _sweep_accounting_documents(global_context)

        kwargs = mock_ai_client.responses.create.call_args.kwargs
        assert kwargs["max_output_tokens"] == ai_handler.config.ai_reply_max_tokens

    def test_openai_call_overrides_the_conversational_timeout_and_retry(
        self, ai_handler, global_context, mock_ai_client
    ):
        """bugfix-047: the sweep's OpenAI+MCP turn is far heavier than a
        conversational one and must not inherit the shared client's 30s
        timeout / 1 retry - it issues the call via .with_options() with a
        generous timeout and no client-level retry."""
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])

        _sweep_accounting_documents(global_context)

        mock_ai_client.with_options.assert_called_once_with(
            timeout=svc.RECONCILIATION_CALL_TIMEOUT_SECONDS, max_retries=0
        )
        assert svc.RECONCILIATION_CALL_TIMEOUT_SECONDS >= 300.0

    def test_over_100_documents_discards_entire_turn_nothing_persisted(
        self, ai_handler, global_context, mock_ai_client
    ):
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 250, "shown": 250, "documents": []})),
            _capture_call_item(ACCOUNTING_EVENT),
        ])

        _sweep_accounting_documents(global_context)

        events_dir = ai_handler.ledger_event_manager.storage_dir
        assert list(events_dir.glob("*.json")) == []

    def test_under_100_documents_persists_normally(self, ai_handler, global_context, mock_ai_client):
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 3, "shown": 3, "documents": []})),
            _capture_call_item(ACCOUNTING_EVENT),
        ])

        _sweep_accounting_documents(global_context)

        events_dir = ai_handler.ledger_event_manager.storage_dir
        assert len(list(events_dir.glob("*.json"))) == 1


class TestSweepAccountingDocumentsPersistAndPrune:
    def test_successful_sweep_persists_via_the_reconciliation_handler(
        self, ai_handler, global_context, mock_ai_client
    ):
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 1, "shown": 1, "documents": []})),
            _capture_call_item(ACCOUNTING_EVENT),
        ])

        _sweep_accounting_documents(global_context)

        events_dir = ai_handler.ledger_event_manager.storage_dir
        files = list(events_dir.glob("*.json"))
        assert len(files) == 1
        with files[0].open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["session_id"] == "accounting-reconciliation"

    def test_prune_called_after_successful_sweep(self, ai_handler, global_context, mock_ai_client, monkeypatch):
        prune_mock = MagicMock()
        monkeypatch.setattr(ai_handler.ledger_event_manager, "prune_accounting_document_cache", prune_mock)
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])

        _sweep_accounting_documents(global_context)

        prune_mock.assert_called_once()

    def test_openai_call_failure_logs_error_and_returns_cleanly(
        self, ai_handler, global_context, mock_ai_client, caplog
    ):
        import logging
        mock_ai_client.responses.create.side_effect = RuntimeError("network exploded")

        with caplog.at_level(logging.ERROR):
            _sweep_accounting_documents(global_context)  # must not raise

        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_no_morning_mcp_tools_available_skips_tick_no_crash(
        self, ai_handler, global_context, mock_ai_client, monkeypatch
    ):
        monkeypatch.setattr(ai_handler.morning_mcp_locator, "current_server_url", lambda: None)

        _sweep_accounting_documents(global_context)  # must not raise

        mock_ai_client.responses.create.assert_not_called()


class TestRunStartupAccountingReconciliationSweep:
    def test_invokes_the_shared_sweep_function(self, global_context, mock_ai_client):
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])

        run_startup_accounting_reconciliation_sweep(global_context)  # must not raise

        mock_ai_client.responses.create.assert_called_once()


class TestStartAccountingReconciliationScheduler:
    def test_zero_freq_means_inactive_no_scheduler_started(self, global_context):
        result = start_accounting_reconciliation_scheduler(global_context, update_freq_minutes=0)
        assert result is None

    @pytest.mark.parametrize("freq", [1, 5, 59, 60, 90, 120, 1440])
    def test_default_trigger_valid_for_any_positive_freq(self, global_context, freq):
        """Real live-dev incident (2026-08-21): the original CronTrigger(minute=
        f"*/{n}") pattern raised ValueError for freq=60 ("the step value (60) is
        higher than the total range of the expression") at scheduler-start time -
        an unhandled exception at __main__ scope that crashed the real running
        app, with no auto-restart. Must work for every value this config field
        can actually hold, not just the small values reminder_delivery_service.py's
        own CronTrigger use happens to be configured with."""
        scheduler = start_accounting_reconciliation_scheduler(
            global_context, update_freq_minutes=freq
        )
        try:
            assert scheduler is not None
            assert len(scheduler.get_jobs()) == 1
        finally:
            scheduler.shutdown()

    def test_positive_freq_registers_exactly_one_job_with_max_instances_1(self, global_context):
        scheduler = start_accounting_reconciliation_scheduler(
            global_context, update_freq_minutes=60, trigger=IntervalTrigger(seconds=9999)
        )
        try:
            jobs = scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].id == RECONCILIATION_SWEEP_JOB_ID
            assert jobs[0].max_instances == 1
        finally:
            scheduler.shutdown()

    def test_trigger_override_actually_fires_the_real_wiring(
        self, global_context, mock_ai_client
    ):
        """Testability-seam proof (mirrors reminder_delivery_service.py's own
        precedent) - a short real IntervalTrigger proves add_job()+
        BackgroundScheduler genuinely invokes _sweep_accounting_documents on
        its own, without waiting on a real CronTrigger minute boundary."""
        import time
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])
        scheduler = start_accounting_reconciliation_scheduler(
            global_context, update_freq_minutes=60, trigger=IntervalTrigger(seconds=1)
        )
        try:
            time.sleep(1.5)
            mock_ai_client.responses.create.assert_called()
        finally:
            scheduler.shutdown()


class TestUS2DedupAcrossTwoSweepTicks:
    """Feature 025, T016a (User Story 2): proves the composed flow across two
    REAL _sweep_accounting_documents calls - not re-testing the tri-state
    dedup logic itself (already covered by
    test_ledger_event_manager.py::TestAccountingDocumentTriState), but that
    the sweep worker doesn't do anything (its own watermark/prompt logic)
    that would defeat it. Real LedgerEventManager/AIHandler objects
    throughout - only the OpenAI response is a test-constructed stand-in."""

    def test_second_tick_capturing_the_same_document_persists_nothing_new(
        self, ai_handler, global_context, mock_ai_client
    ):
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 1, "shown": 1, "documents": []})),
            _capture_call_item(ACCOUNTING_EVENT),
        ])
        _sweep_accounting_documents(global_context)
        events_dir = ai_handler.ledger_event_manager.storage_dir
        assert len(list(events_dir.glob("*.json"))) == 1

        # Second tick: the model (synthetically) attempts to capture the
        # SAME document again (same display_number, same creation timestamp)
        # - simulating a re-poll where nothing has actually changed in Morning.
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 1, "shown": 1, "documents": []})),
            _capture_call_item(ACCOUNTING_EVENT, call_id="call_1"),
        ])
        # bugfix-048: drop the in-memory dedup cache so the second tick has to
        # rebuild it from disk - reproducing a process restart between sweeps,
        # the exact scenario where the old exact-timestamp guard let duplicates
        # through (seconds precision in memory vs minute precision from disk).
        ai_handler.ledger_event_manager._accounting_document_cache = None
        _sweep_accounting_documents(global_context)

        # The second tick must genuinely RUN (reach OpenAI and attempt the
        # capture) - otherwise a watermark/cap skip would make this pass for
        # the wrong reason and prove nothing about dedup.
        assert mock_ai_client.responses.create.call_count == 2
        assert len(list(events_dir.glob("*.json"))) == 1, (
            "a document already captured must never be re-captured - the "
            "(date, display_number) guard inside LedgerEventManager, transparently "
            "reached through the sweep worker + reconciliation handler, must still "
            "fire even after the cache is rebuilt from disk"
        )

    def test_sweep_actually_ran_on_second_tick_not_a_silent_noop(
        self, ai_handler, global_context, mock_ai_client, caplog
    ):
        """Distinguishing 'ran and found nothing new' from 'silently did
        nothing' - the sweep must still log that it executed."""
        import logging
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])

        with caplog.at_level(logging.INFO):
            _sweep_accounting_documents(global_context)

        assert any("captured 0 event(s)" in r.message for r in caplog.records)


class TestUS5WatermarkUnchangedAfterFailureOrCapSkip:
    """Feature 025, T022a (User Story 5): proves the cache-derived-not-
    counted watermark design actually self-corrects, not just in theory -
    neither a mid-sweep exception nor a safety-cap skip silently advances
    anything."""

    def test_watermark_unchanged_after_openai_failure(
        self, ai_handler, global_context, mock_ai_client
    ):
        recent_ts = int((now_local() - timedelta(hours=2)).timestamp())
        ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s", event=dict(ACCOUNTING_EVENT), message_id=None,
            message_timestamp=recent_ts,
        )
        watermark_before = ai_handler.ledger_event_manager.get_accounting_document_watermark()

        mock_ai_client.responses.create.side_effect = RuntimeError("boom")
        _sweep_accounting_documents(global_context)

        watermark_after = ai_handler.ledger_event_manager.get_accounting_document_watermark()
        assert watermark_after == watermark_before

    def test_watermark_unchanged_after_100_doc_cap_skip(
        self, ai_handler, global_context, mock_ai_client
    ):
        recent_ts = int((now_local() - timedelta(hours=2)).timestamp())
        ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s", event=dict(ACCOUNTING_EVENT), message_id=None,
            message_timestamp=recent_ts,
        )
        watermark_before = ai_handler.ledger_event_manager.get_accounting_document_watermark()

        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 999, "shown": 999, "documents": []})),
            _capture_call_item(dict(ACCOUNTING_EVENT, accounting_document_display_number="99999")),
        ])
        _sweep_accounting_documents(global_context)

        watermark_after = ai_handler.ledger_event_manager.get_accounting_document_watermark()
        assert watermark_after == watermark_before

    def test_subsequent_successful_tick_after_a_failure_covers_the_full_window(
        self, ai_handler, global_context, mock_ai_client
    ):
        """A failed tick must not narrow the window the NEXT tick covers -
        since is still derived from the same (unchanged) watermark."""
        mock_ai_client.responses.create.side_effect = RuntimeError("boom")
        _sweep_accounting_documents(global_context)

        mock_ai_client.responses.create.side_effect = None
        mock_ai_client.responses.create.return_value = SimpleNamespace(output=[
            _mcp_call_item("list_invoices", json.dumps({"total_matched": 0, "shown": 0, "documents": []})),
        ])
        _sweep_accounting_documents(global_context)

        second_call_kwargs = mock_ai_client.responses.create.call_args.kwargs
        prompt = second_call_kwargs["input"][0]["content"]
        expected_since = (now_local() - svc.FALLBACK_LOOKBACK).strftime("%Y-%m-%d")
        assert expected_since in prompt, (
            "the failed first tick must not have narrowed the fallback window"
        )
