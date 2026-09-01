"""
Tests for select_method.py's diff helper (Phase 2 — tasks.md T010).

RED first — select_method.py does not exist yet. Only the field-by-field diff logic is unit-
tested here; the real Method A vs Method B sandbox comparison itself is a billed/Acceptance-phase
concern (tasks.md T031), not a unit test.
"""
import pytest

import select_method


def _sample_ledger_event(**overrides):
    event = {
        "event_id": "A02022604480",
        "schema_version": 2,
        "source_type": "חשבונית",
        "event_subtype": "invoice",
        "accounting_document_display_number": "INV-2025-001",
        "accounting_document_type": "invoice",
        "accounting_document_client_name": "Fixture Client Ltd.",
        "accounting_document_creation_timestamp": "2025-01-15T09:30:00+02:00",
    }
    event.update(overrides)
    return event


def test_identical_pair_reports_identical():
    event_a = _sample_ledger_event()
    event_b = _sample_ledger_event()

    result = select_method.diff_ledger_events(event_a, event_b)

    assert result["identical"] is True
    assert result["differing_fields"] == []


def test_pair_differing_only_by_event_id_still_reports_identical():
    """event_id is capture-timestamp-derived — always excluded from the comparison."""
    event_a = _sample_ledger_event(event_id="A02022604480")
    event_b = _sample_ledger_event(event_id="A02022605551")

    result = select_method.diff_ledger_events(event_a, event_b)

    assert result["identical"] is True
    assert result["differing_fields"] == []


def test_one_mismatched_field_is_named_exactly():
    event_a = _sample_ledger_event()
    event_b = _sample_ledger_event(accounting_document_client_name="Wrong Client Name")

    result = select_method.diff_ledger_events(event_a, event_b)

    assert result["identical"] is False
    assert result["differing_fields"] == ["accounting_document_client_name"]


def test_multiple_mismatched_fields_are_all_named():
    event_a = _sample_ledger_event()
    event_b = _sample_ledger_event(
        accounting_document_client_name="Wrong Client Name",
        accounting_document_type="credit_note",
    )

    result = select_method.diff_ledger_events(event_a, event_b)

    assert result["identical"] is False
    assert set(result["differing_fields"]) == {
        "accounting_document_client_name",
        "accounting_document_type",
    }


def test_verdict_string_for_identical_pair():
    result = select_method.diff_ledger_events(_sample_ledger_event(), _sample_ledger_event())
    assert select_method.format_verdict(result) == "IDENTICAL — adopt Method A"


def test_verdict_string_for_differing_pair():
    event_a = _sample_ledger_event()
    event_b = _sample_ledger_event(accounting_document_type="credit_note")
    result = select_method.diff_ledger_events(event_a, event_b)
    verdict = select_method.format_verdict(result)
    assert verdict.startswith("DIFFERS on:")
    assert "accounting_document_type" in verdict
    assert verdict.endswith("— adopt Method B")


def test_diff_raises_on_unequal_key_sets():
    """A method producing a differently-shaped LedgerEvent entirely is itself a real mismatch."""
    event_a = _sample_ledger_event()
    event_b = _sample_ledger_event()
    del event_b["accounting_document_type"]

    result = select_method.diff_ledger_events(event_a, event_b)

    assert result["identical"] is False
    assert "accounting_document_type" in result["differing_fields"]
