"""
Acceptance tests for Feature 025 - Morning-sourced ledger events (Phase 9).

Covers tasks.md's 👤 scenarios T015/T017/T019/T021/T023, written and run
together as one pass per METHODOLOGY.md §VI.a, after every unit/integration
task was GREEN.

`billed` tier: real, text-only OpenAI calls plus the real Morning **dev
sandbox** over the live MCP tunnel. No mocking anywhere - the sweep runs its
own real code path end to end, and assertions are made against the ledger
files it actually persisted.

Read-only against Morning: these tests never create sandbox documents. They
reconcile whatever documents already exist in the window, which is exactly
what the sweep does in production, and keeps the suite re-runnable without
accumulating test data in a real account.
"""
import json
import shutil
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from openai import OpenAI

import src.services.accounting_reconciliation_service as svc
from src.handlers.ai_handler import AIHandler
from src.utils.time_utils import now_local

pytestmark = pytest.mark.billed


# These tests reconcile whatever the dev sandbox already contains, so the
# window is a real dependency on ambient data and has to be chosen carefully:
# too narrow finds nothing, too wide trips the sweep's own 100-document safety
# cap. Measured 2026-08-23: a 3-day window held 18 documents, a 4-day window
# held 168 - the sandbox has days with ~150 documents in them. Both failure
# modes are handled by _sweep_or_skip below with an actionable message rather
# than a confusing assertion failure.
_TEST_LOOKBACK = timedelta(days=3)


def _events_dir(config) -> Path:
    return Path(config.data_root) / "events"


def _accounting_events(config) -> list:
    """Every חשבונית event currently persisted, newest-id first."""
    out = []
    for f in sorted(_events_dir(config).glob("H*.json")):
        with f.open(encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


@pytest.fixture
def clean_ledger(denidin_config):
    """Start each scenario from an empty חשבונית ledger AND a fresh in-memory
    cache, so a test's own captures are unambiguous.

    The cache matters as much as the files: it is built once per
    LedgerEventManager instance, so deleting files without rebuilding the
    manager would leave a stale dedup view behind.
    """
    events = _events_dir(denidin_config)
    for f in events.glob("H*.json"):
        f.unlink()
    recon = Path(denidin_config.data_root) / "accounting_reconciliation"
    if recon.exists():
        shutil.rmtree(recon)
    yield
    # left in place afterwards on purpose - inspectable when a run fails


@pytest.fixture
def sweep_context(denidin_config, live_morning_tunnel):
    """A real AIHandler (real LedgerEventManager, real OpenAI client, real
    Morning MCP attachment) in the shape _sweep_accounting_documents expects.

    Deliberately NOT the `denidin_app` fixture: the sweep is a headless
    background job with no session/chat, and building only what it actually
    needs keeps the test honest about that.
    """
    handler = AIHandler(OpenAI(api_key=denidin_config.ai_api_key), denidin_config)
    return SimpleNamespace(ai_handler=handler)


def _run_sweep(context, lookback=_TEST_LOOKBACK, log_prefix="[BILLED] "):
    """One real sweep tick with an explicit window (production derives it from
    the watermark; here it must reach documents this test did not create)."""
    original = svc.FALLBACK_LOOKBACK
    svc.FALLBACK_LOOKBACK = lookback
    try:
        svc._sweep_accounting_documents(context, log_prefix=log_prefix)
    finally:
        svc.FALLBACK_LOOKBACK = original


def _sweep_or_skip(context, config, **kwargs):
    """Run a sweep and return its captured events, skipping with an actionable
    message when the ambient sandbox data makes the scenario untestable.

    Deliberately NOT a silent pass: an empty ledger could mean the feature is
    broken OR that the window happens to hold nothing, and those must not look
    alike. The safety-cap case is distinguished by its own ERROR line, so a
    capped tick is reported as such rather than as "captured nothing".
    """
    import logging
    import _pytest.logging  # noqa: F401  (caplog machinery already active under pytest)

    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record)          # type: ignore[method-assign]
    svc_logger = logging.getLogger(svc.__name__)
    svc_logger.addHandler(handler)
    try:
        _run_sweep(context, **kwargs)
    finally:
        svc_logger.removeHandler(handler)

    if any("safety cap" in r.getMessage() or "> 100" in r.getMessage() for r in records):
        pytest.skip(
            "the dev sandbox holds more than the sweep's 100-document cap in the last "
            f"{kwargs.get('lookback', _TEST_LOOKBACK).days} days, so the tick was correctly "
            "discarded - narrow _TEST_LOOKBACK for this suite (this is the cap working, "
            "not a defect; see TestSafetyCapIsEnforcedLive)"
        )

    events = _accounting_events(config)
    if not events:
        pytest.skip(
            f"no Morning documents in the last {kwargs.get('lookback', _TEST_LOOKBACK).days} "
            "days of the dev sandbox - widen _TEST_LOOKBACK (staying under the 100-document "
            "cap) or create a sandbox document, then re-run"
        )
    return events


class TestUS1CapturesDocumentsNeverSeenInConversation:
    """T015: a Morning document created outside any DeniDin conversation is
    discovered and persisted as a real LedgerEvent."""

    def test_sweep_captures_real_sandbox_documents_with_faithful_fields(
        self, denidin_config, sweep_context, clean_ledger
    ):
        events = _sweep_or_skip(sweep_context, denidin_config)

        for e in events:
            num = e["accounting_document_display_number"]
            assert e["source_type"] == "חשבונית", num
            assert e["session_id"] == "accounting-reconciliation", num
            assert e["message_id"] is None, num
            assert e["schema_version"] == 3, num
            assert num, "every captured document must carry its display number"

            # The bug this feature spent the longest on: a fabricated midnight
            # timestamp, from reading the date-only field instead of the real
            # creation instant.
            created = e["accounting_document_creation_date"]
            assert created, f"{num}: no creation timestamp"
            assert not created.endswith(" 00:00"), (
                f"{num}: creation time is exactly midnight ({created}) - the signature "
                "of a defaulted/fabricated time rather than Morning's real one"
            )
            assert e["event_datetime"] == created, f"{num}: event_datetime must be the document's own instant"

    def test_event_subtype_is_the_real_morning_document_type(
        self, denidin_config, sweep_context, clean_ledger
    ):
        """User decision (2026-08-23): the document type IS the subtype, using
        Morning's own label - never the old flat "הפקה" bucket."""
        _sweep_or_skip(sweep_context, denidin_config)

        known_types = {
            "חשבון עסקה", "חשבונית מס", "חשבונית מס / קבלה", "חשבונית זיכוי", "קבלה",
        }
        subtypes = {e["event_subtype"] for e in _accounting_events(denidin_config)}
        assert subtypes, "no events captured"
        assert subtypes <= known_types, f"unexpected subtype(s): {subtypes - known_types}"
        assert "הפקה" not in subtypes, "the retired flat bucket must not reappear"

    def test_retired_fields_are_absent_from_every_record(
        self, denidin_config, sweep_context, clean_ledger
    ):
        _sweep_or_skip(sweep_context, denidin_config)

        retired = (
            "accounting_document_type",      # now carried by event_subtype
            "morning_document_id", "invoice_number", "invoice_type",
            "invoice_status", "invoice_actual_creation_date",
        )
        for e in _accounting_events(denidin_config):
            for field in retired:
                assert field not in e, f"{e['accounting_document_display_number']}: {field} resurfaced"


class TestUS2NeverRecapturesTheSameDocument:
    """T017: a second tick with no new Morning documents persists nothing new,
    and is distinguishable from a sweep that silently didn't run."""

    def test_second_identical_tick_adds_no_new_events(
        self, denidin_config, sweep_context, clean_ledger, caplog
    ):
        after_first = {e["event_id"] for e in _sweep_or_skip(sweep_context, denidin_config)}

        import logging
        with caplog.at_level(logging.INFO):
            _run_sweep(sweep_context, log_prefix="[BILLED-2] ")

        after_second = {e["event_id"] for e in _accounting_events(denidin_config)}
        assert after_second == after_first, (
            f"second sweep created {len(after_second - after_first)} duplicate event(s): "
            f"{sorted(after_second - after_first)}"
        )
        assert any("[BILLED-2]" in r.message for r in caplog.records), (
            "the second sweep must be visible in the log - 'ran and found nothing new' "
            "has to be distinguishable from 'never ran'"
        )


class TestUS3MultipleDocumentsInOneWindow:
    """T021: every document in the window is captured, not just the first."""

    def test_each_document_becomes_its_own_event_with_a_unique_id(
        self, denidin_config, sweep_context, clean_ledger
    ):
        events = _sweep_or_skip(sweep_context, denidin_config)
        if len(events) < 2:
            pytest.skip(
                f"needs >=2 documents in the last {_TEST_LOOKBACK.days} days; "
                f"found {len(events)}"
            )

        numbers = [e["accounting_document_display_number"] for e in events]
        event_ids = [e["event_id"] for e in events]
        assert len(set(numbers)) == len(numbers), f"duplicate display numbers: {numbers}"
        assert len(set(event_ids)) == len(event_ids), f"duplicate event_ids: {event_ids}"
        assert all(i.startswith("H") for i in event_ids), "חשבונית events use the H prefix"


class TestUS4ConversationalTurnsAreUnaffected:
    """T019: the regression check for this whole feature. A real Morning
    question must still answer correctly, and must NOT create ledger events -
    _handle_ledger_event_capture's same-turn-mcp_call suppression is
    deliberately untouched by Feature 025."""

    def test_morning_question_answers_and_creates_no_ledger_event(
        self, denidin_config, denidin_app, clean_ledger
    ):
        from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID, _send_turn

        reply, ai_response = _send_turn(
            GODFATHER_CHAT_ID,
            "כמה חשבוניות הופקו בחודש האחרון?",
            "025-us4",
        )

        assert reply, (
            "empty reply - this is the exact 2026-07-28 symptom this feature "
            "descends from (the model calling capture_ledger_event on its own "
            "list_invoices output instead of answering)"
        )
        assert not _accounting_events(denidin_config), (
            "a conversational turn must never create a חשבונית ledger event - "
            "that path belongs solely to the background sweep"
        )


class TestUS5FailureNeverSilentlySkipsAWindow:
    """T023: a failed tick must not advance the watermark, so the next tick
    still covers the same window."""

    def test_failed_tick_leaves_the_watermark_untouched(
        self, denidin_config, sweep_context, clean_ledger
    ):
        events_before = {e["event_id"] for e in _sweep_or_skip(sweep_context, denidin_config)}
        manager = sweep_context.ai_handler.ledger_event_manager
        watermark_before = manager.get_accounting_document_watermark()

        # A real failure mode: the Morning MCP tunnel unreachable for one tick.
        locator = sweep_context.ai_handler.morning_mcp_locator
        original = locator.current_server_url
        locator.current_server_url = lambda: None
        try:
            _run_sweep(sweep_context, log_prefix="[BILLED-FAIL] ")
        finally:
            locator.current_server_url = original

        assert manager.get_accounting_document_watermark() == watermark_before, (
            "a failed tick advanced the watermark - the next sweep would skip that window"
        )
        assert {e["event_id"] for e in _accounting_events(denidin_config)} == events_before, (
            "a failed tick must not persist anything"
        )

    def test_recovering_tick_still_covers_the_same_window(
        self, denidin_config, sweep_context, clean_ledger
    ):
        """After a failure, a normal tick re-reaches the same documents and
        re-recognises them as already captured (rather than either missing
        them or duplicating them)."""
        baseline = {e["event_id"] for e in _sweep_or_skip(sweep_context, denidin_config)}

        locator = sweep_context.ai_handler.morning_mcp_locator
        original = locator.current_server_url
        locator.current_server_url = lambda: None
        try:
            _run_sweep(sweep_context, log_prefix="[BILLED-FAIL] ")
        finally:
            locator.current_server_url = original

        _run_sweep(sweep_context, log_prefix="[BILLED-RECOVER] ")

        assert {e["event_id"] for e in _accounting_events(denidin_config)} == baseline, (
            "the recovering tick either lost or duplicated documents"
        )


class TestSafetyCapIsEnforcedLive:
    """Not a numbered user story, but the guard that stops this becoming a
    backfill mechanism - worth proving against the real sandbox, since the
    5-day/100-document bounds only ever fire against real data volumes."""

    def test_a_stale_watermark_skips_the_tick_entirely(
        self, denidin_config, sweep_context, clean_ledger, caplog
    ):
        import logging
        with caplog.at_level(logging.ERROR):
            _run_sweep(sweep_context, lookback=timedelta(days=30), log_prefix="[BILLED-CAP] ")

        assert not _accounting_events(denidin_config), (
            "a window beyond the safety cap must capture nothing at all"
        )
        assert any(
            "[BILLED-CAP]" in r.message and r.levelno == logging.ERROR
            for r in caplog.records
        ), "a capped-out tick must say so loudly - it needs admin attention"
