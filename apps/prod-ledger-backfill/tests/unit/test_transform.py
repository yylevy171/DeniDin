"""
Task A (RED) for Phase 3 — Feature 061, prod-morning-ledger-backfill (T015).

`transform.py` reads raw document files from --input-dir (never a live Morning API call —
REQ-BACKFILL-003) and persists correctly-shaped LedgerEvent files to --output-dir via the real
LedgerEventManager.add_ledger_event, so dedup/anomaly detection come for free (research.md R7/R8).
"""
import json

import pytest

import transform


def _raw_document(doc_id, display_number, creation_iso, amount=117.0):
    """A raw document in MorningClient.get_invoice()'s real shape — the same shape
    test_method_a.py's `_real_shaped_raw_document` uses, parameterized for bulk generation."""
    return {
        "id": doc_id,
        "number": display_number,
        "type": 305,  # חשבונית מס
        "client": {"id": f"client-{doc_id}", "name": "Test Client Ltd."},
        "status": 2,
        "amount": amount,
        "total": amount,
        "vat": 0.0,
        "documentDate": creation_iso[:10],
        "creationDate": creation_iso,
        "income": [
            {"description": "Consulting", "quantity": 1, "price": amount, "amountTotal": amount}
        ],
        "payment": [{"name": "מזומן", "type": 1, "date": creation_iso[:10], "amount": amount}],
    }


def _write_fixture_documents(input_dir, documents):
    for doc in documents:
        (input_dir / f"{doc['id']}.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8"
        )


def test_transform_produces_correctly_shaped_ledger_events(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"

    doc = _raw_document("doc-a", 50001, "2025-01-15T09:30:00")
    _write_fixture_documents(input_dir, [doc])

    exit_code = transform.main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)])
    assert exit_code == 0

    written_files = list(output_dir.glob("*.json"))
    assert len(written_files) == 1

    event = json.loads(written_files[0].read_text(encoding="utf-8"))
    # No assertion on schema_version's value (2026-08-26 policy — see root CLAUDE.md's "LEDGER
    # SCHEMA VERSION BUMPS ARE HUMAN-ONLY" rule): presence only, never a literal or a comparison.
    assert "schema_version" in event
    assert event["source_type"] == "חשבונית"
    assert event["accounting_document_display_number"] == "50001"
    assert event["event_subtype"]  # Morning's own type_name, non-empty
    assert event["client_name"] == "Test Client Ltd."
    # accounting_document_creation_date was removed from the persisted schema entirely
    # (2026-08-26, master's Feature 044) — event_datetime is now the sole creation-date field.
    assert event["event_datetime"]


def test_transform_makes_no_live_network_call():
    """transform.py never imports anything that could reach Morning's real API (REQ-BACKFILL-003)
    — unlike download.py, it has no reason to import MorningClient at all."""
    assert not hasattr(transform, "MorningClient")
    assert "requests" not in dir(transform)


def test_transform_empty_input_dir_fails_cleanly(tmp_path):
    input_dir = tmp_path / "empty_input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"

    exit_code = transform.main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)])
    assert exit_code != 0


def test_transform_large_input_produces_no_artificial_output_cap(tmp_path):
    """speckit.analyze finding U1 (REQ-BACKFILL-005): 150+ raw documents in --input-dir must
    produce 150+ LedgerEvent files — proving transform.py itself imposes no cap on top of
    LedgerEventManager's own (per-minute, not per-run) event_id exhaustion guard."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"

    documents = [
        # One document per minute (creationDate spaced 60s apart) so none of the 155 documents
        # ever collide on LedgerEventManager's real per-minute event_id sequence-digit cap
        # (research.md's own event_id format is letter+DDMMYY+HHMM+one sequence digit — at most
        # 10 events per source-type per minute).
        _raw_document(f"doc-{i:03d}", 60000 + i, f"2025-02-01T{(6 + i // 60):02d}:{i % 60:02d}:00")
        for i in range(155)
    ]
    _write_fixture_documents(input_dir, documents)

    exit_code = transform.main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)])
    assert exit_code == 0

    written_files = list(output_dir.glob("*.json"))
    assert len(written_files) == 155
