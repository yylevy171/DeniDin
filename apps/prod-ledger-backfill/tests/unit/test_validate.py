"""
Task A (RED) for Phase 3.5 — Feature 061, prod-morning-ledger-backfill (T018).

`validate.py` reads --raw-dir (Phase 1's output) and --ledger-dir (Phase 3's output) only — no
live Morning API call, and NEVER writes under --ledger-dir (strictly read-only, REQ-BACKFILL-010).
It produces a report with two checks: document-count reconciliation, and surfaced anomalies
(LedgerEventManager's own pending_review.json, a SIBLING of --ledger-dir, not nested inside it —
confirmed by reading _append_pending_review directly).

A third check ("sampled field-level comparison" against a method_a.transform() oracle) was
removed 2026-09-01 (Feature 062 real prod run, explicit user direction) — the oracle stopped one
pipeline stage short of the real save path, so it always reported every sampled document as
"not identical" regardless of correctness, and the Method A/B comparison it existed for was
already settled. See validate.py's own module docstring for the full removal note.
"""
import json

import pytest

import method_a
import validate


def _raw_document(doc_id, number, creation_iso="2025-01-15T09:30:00", amount=117.0,
                   client_name="Test Client Ltd."):
    """Same real shape used by test_method_a.py / test_transform.py."""
    return {
        "id": doc_id,
        "number": number,
        "type": 305,
        "client": {"id": f"client-{doc_id}", "name": client_name},
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


def _write_raw_document(raw_dir, doc):
    (raw_dir / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _write_ledger_event(ledger_dir, event_id, event):
    (ledger_dir / f"{event_id}.json").write_text(json.dumps(event, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def clean_fixture_dirs(tmp_path):
    """One raw document with a correctly-matching LedgerEvent — everything should report clean."""
    raw_dir = tmp_path / "raw"
    ledger_dir = tmp_path / "ledger"
    raw_dir.mkdir()
    ledger_dir.mkdir()

    doc = _raw_document("doc-clean", 70001)
    _write_raw_document(raw_dir, doc)
    expected_event = method_a.transform(doc)
    _write_ledger_event(ledger_dir, "E01022500010", expected_event)

    return raw_dir, ledger_dir


@pytest.fixture
def mismatched_fixture_dirs(tmp_path):
    """
    Three raw documents:
    - doc-a: has a correctly-matching LedgerEvent (clean)
    - doc-b: has NO corresponding LedgerEvent at all (count mismatch)
    - doc-c: has a LedgerEvent with a deliberately wrong field (field-level mismatch)
    """
    raw_dir = tmp_path / "raw"
    ledger_dir = tmp_path / "ledger"
    raw_dir.mkdir()
    ledger_dir.mkdir()

    doc_a = _raw_document("doc-a", 70010, client_name="Client A Ltd.")
    doc_b = _raw_document("doc-b", 70011, client_name="Client B Ltd.")
    doc_c = _raw_document("doc-c", 70012, client_name="Client C Ltd.")
    for doc in (doc_a, doc_b, doc_c):
        _write_raw_document(raw_dir, doc)

    _write_ledger_event(ledger_dir, "E01022500011", method_a.transform(doc_a))
    # doc_b: deliberately no LedgerEvent written at all.
    wrong_event = method_a.transform(doc_c)
    wrong_event["client_name"] = "A Totally Different Client"  # deliberate wrong field
    _write_ledger_event(ledger_dir, "E01022500012", wrong_event)

    return raw_dir, ledger_dir


# --- CLI parsing --------------------------------------------------------------------------

def test_raw_dir_is_required():
    parser = validate.build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--ledger-dir", "/tmp/x", "--report-out", "/tmp/report.json"])


def test_ledger_dir_is_required():
    parser = validate.build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--raw-dir", "/tmp/x", "--report-out", "/tmp/report.json"])


def test_report_out_is_required():
    parser = validate.build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--raw-dir", "/tmp/x", "--ledger-dir", "/tmp/y"])


# --- Count reconciliation + field-level comparison ----------------------------------------

def test_clean_pair_reports_no_discrepancy_and_no_mismatch(clean_fixture_dirs, tmp_path):
    raw_dir, ledger_dir = clean_fixture_dirs
    report_path = tmp_path / "report.json"

    exit_code = validate.main([
        "--raw-dir", str(raw_dir), "--ledger-dir", str(ledger_dir), "--report-out", str(report_path),
    ])
    assert exit_code == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["count_reconciliation"]["unexplained_discrepancy"] is False
    assert report["count_reconciliation"]["raw_document_count"] == 1
    assert report["count_reconciliation"]["ledger_event_count"] == 1
    assert report["sign_off"]["signed"] is False


def test_missing_ledger_event_flagged_in_count_reconciliation(mismatched_fixture_dirs, tmp_path):
    raw_dir, ledger_dir = mismatched_fixture_dirs
    report_path = tmp_path / "report.json"

    validate.main([
        "--raw-dir", str(raw_dir), "--ledger-dir", str(ledger_dir), "--report-out", str(report_path),
    ])

    report = json.loads(report_path.read_text(encoding="utf-8"))
    reconciliation = report["count_reconciliation"]
    assert reconciliation["unexplained_discrepancy"] is True
    assert reconciliation["raw_document_count"] == 3
    assert reconciliation["ledger_event_count"] == 2
    assert "70011" in reconciliation["missing_document_numbers"]  # doc-b's number


def test_anomalies_are_read_from_the_sibling_accounting_reconciliation_dir(mismatched_fixture_dirs, tmp_path):
    """pending_review.json lives at ledger_dir.parent/accounting_reconciliation/pending_review.json
    — a SIBLING of --ledger-dir, not nested inside it (confirmed against
    LedgerEventManager._append_pending_review directly, not assumed)."""
    raw_dir, ledger_dir = mismatched_fixture_dirs
    review_dir = ledger_dir.parent / "accounting_reconciliation"
    review_dir.mkdir()
    fixture_anomaly = [{
        "accounting_document_display_number": "70012",
        "prior_event_id": "E01022500001",
        "prior_creation_date": "15/01/2025 09:00",
        "new_event_id": "E01022500012",
        "new_creation_date": "15/01/2025 10:00",
        "detected_at": "15/01/2025 10:05",
    }]
    (review_dir / "pending_review.json").write_text(json.dumps(fixture_anomaly), encoding="utf-8")

    report_path = tmp_path / "report.json"
    validate.main([
        "--raw-dir", str(raw_dir), "--ledger-dir", str(ledger_dir), "--report-out", str(report_path),
    ])

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["anomalies"] == fixture_anomaly


def test_no_pending_review_file_means_empty_anomalies_not_an_error(clean_fixture_dirs, tmp_path):
    raw_dir, ledger_dir = clean_fixture_dirs
    report_path = tmp_path / "report.json"

    exit_code = validate.main([
        "--raw-dir", str(raw_dir), "--ledger-dir", str(ledger_dir), "--report-out", str(report_path),
    ])
    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["anomalies"] == []


# --- Read-only guarantee (REQ-BACKFILL-010) -------------------------------------------------

def test_never_writes_under_ledger_dir(mismatched_fixture_dirs, tmp_path):
    raw_dir, ledger_dir = mismatched_fixture_dirs
    before = sorted(p.name for p in ledger_dir.iterdir())

    report_path = tmp_path / "report.json"
    validate.main([
        "--raw-dir", str(raw_dir), "--ledger-dir", str(ledger_dir), "--report-out", str(report_path),
    ])

    after = sorted(p.name for p in ledger_dir.iterdir())
    assert before == after


# --- Sign-off mechanism (T020, REQ-BACKFILL-010) --------------------------------------------

def test_report_starts_unsigned(clean_fixture_dirs, tmp_path):
    raw_dir, ledger_dir = clean_fixture_dirs
    report_path = tmp_path / "report.json"
    validate.main([
        "--raw-dir", str(raw_dir), "--ledger-dir", str(ledger_dir), "--report-out", str(report_path),
    ])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["sign_off"] == {"signed": False, "signed_by": None, "signed_at": None}


def test_approve_marks_the_report_signed(clean_fixture_dirs, tmp_path):
    raw_dir, ledger_dir = clean_fixture_dirs
    report_path = tmp_path / "report.json"
    validate.main([
        "--raw-dir", str(raw_dir), "--ledger-dir", str(ledger_dir), "--report-out", str(report_path),
    ])

    exit_code = validate.main([
        "--approve", "--report-in", str(report_path), "--signed-by", "Yaron Levy",
    ])
    assert exit_code == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["sign_off"]["signed"] is True
    assert report["sign_off"]["signed_by"] == "Yaron Levy"
    assert report["sign_off"]["signed_at"]  # non-empty timestamp


def test_approve_requires_signed_by():
    """--approve/--report-in/--signed-by live on their own parser (build_approve_arg_parser),
    separate from the normal-mode build_arg_parser() above — argparse can't cleanly express
    "required only if --approve is set" on one shared parser, so main() dispatches to whichever
    parser matches the invocation instead."""
    parser = validate.build_approve_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--approve", "--report-in", "/tmp/report.json"])


def test_approve_missing_report_fails_cleanly(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    exit_code = validate.main(["--approve", "--report-in", str(missing), "--signed-by", "Yaron"])
    assert exit_code != 0
