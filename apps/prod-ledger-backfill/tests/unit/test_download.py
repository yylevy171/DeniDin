"""
Tests for download.py (Phase 1 — tasks.md T007).

RED first, per METHODOLOGY §VI's unit/integration TDD discipline — download.py does not exist yet.
No live network call anywhere in this file: MorningClient is either never constructed (the
precondition-failure cases) or replaced with a dependency-injected fake for the pagination cases.
"""
import json

import pytest

import download


# --- CLI parsing (REQ-BACKFILL-001) --------------------------------------------------------

def test_since_is_required():
    """No default or hardcoded start date may exist anywhere (REQ-BACKFILL-001)."""
    parser = download.build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--output-dir", "/tmp/whatever"])


def test_output_dir_is_required():
    parser = download.build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--since", "2025-01-01"])


def test_since_must_be_a_valid_iso_date():
    parser = download.build_arg_parser()
    args = parser.parse_args(["--since", "not-a-date", "--output-dir", "/tmp/whatever"])
    with pytest.raises(download.BackfillPreconditionError):
        download.parse_since_date(args.since)


def test_valid_since_parses_to_a_date():
    parser = download.build_arg_parser()
    args = parser.parse_args(["--since", "2025-01-01", "--output-dir", "/tmp/whatever"])
    parsed = download.parse_since_date(args.since)
    assert parsed.year == 2025 and parsed.month == 1 and parsed.day == 1


# --- Credentials-file validation (REQ-BACKFILL-006) -----------------------------------------
# Every case here must fail BEFORE any MorningClient is constructed — asserted via a
# dependency-injected constructor that raises if ever called, never via mocking internal logic.

def _never_call_morning_client(*_args, **_kwargs):
    raise AssertionError("MorningClient must not be constructed when credentials are invalid")


def test_missing_creds_file_fails_before_any_network_call(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"
    with pytest.raises(download.BackfillPreconditionError):
        download.load_credentials(missing_path)


def test_malformed_json_creds_file_fails_before_any_network_call(tmp_path):
    bad_path = tmp_path / "creds.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(download.BackfillPreconditionError):
        download.load_credentials(bad_path)


@pytest.mark.parametrize("missing_field", ["api_key_id", "api_key_secret", "auth_url", "base_url"])
def test_missing_required_field_fails_before_any_network_call(tmp_path, fixture_creds_dict, missing_field):
    incomplete = dict(fixture_creds_dict)
    del incomplete[missing_field]
    path = tmp_path / "creds.json"
    path.write_text(json.dumps(incomplete), encoding="utf-8")
    with pytest.raises(download.BackfillPreconditionError):
        download.load_credentials(path)


def test_valid_creds_file_loads_all_four_fields(fixture_creds_file, fixture_creds_dict):
    creds = download.load_credentials(fixture_creds_file)
    assert creds == fixture_creds_dict


def test_main_never_constructs_morning_client_on_invalid_creds(tmp_path, monkeypatch, capsys):
    """End-to-end precondition check: main() exits non-zero, never reaching MorningClient."""
    monkeypatch.setattr(download, "MorningClient", _never_call_morning_client)
    missing_creds = tmp_path / "missing.json"
    output_dir = tmp_path / "out"
    exit_code = download.main([
        "--since", "2025-01-01",
        "--output-dir", str(output_dir),
        "--creds-file", str(missing_creds),
    ])
    assert exit_code != 0


# --- Pagination (research.md R3/R4 — no 100-item cap) ---------------------------------------

class _FakeMorningClient:
    """A fake standing in for MorningClient's raw list_invoices/get_invoice — no network call."""

    def __init__(self, pages):
        self._pages = pages
        self.list_invoices_calls = []
        self.get_invoice_calls = []

    def list_invoices(self, params=None):
        page_num = (params or {}).get("page", 1)
        self.list_invoices_calls.append(params)
        return self._pages[page_num - 1]

    def get_invoice(self, invoice_id):
        self.get_invoice_calls.append(invoice_id)
        return {"id": invoice_id, "fetched": True}


def test_pagination_follows_page_pages_total_with_no_cap(fixture_search_page_1, fixture_search_page_2):
    """
    150 total documents (over tools.py's 100-item cap) must all be reachable — Phase 1 must not
    reuse that conversational-reply-oriented limit (research.md R3, REQ-BACKFILL-002).
    """
    client = _FakeMorningClient([fixture_search_page_1, fixture_search_page_2])

    doc_ids = list(download.paginate_document_ids(client, since="2025-01-01"))

    assert len(doc_ids) == 150
    assert len(client.list_invoices_calls) == 2  # both pages fetched


def test_pagination_fetches_full_detail_for_every_document(fixture_search_page_1, fixture_search_page_2):
    client = _FakeMorningClient([fixture_search_page_1, fixture_search_page_2])

    documents = list(download.download_all_documents(client, since="2025-01-01"))

    assert len(documents) == 150
    assert len(client.get_invoice_calls) == 150


def test_single_page_response_terminates_pagination():
    single_page = {"items": [{"id": "only-doc"}], "total": 1, "page": 1, "pages": 1}
    client = _FakeMorningClient([single_page])

    doc_ids = list(download.paginate_document_ids(client, since="2025-01-01"))

    assert doc_ids == ["only-doc"]
    assert len(client.list_invoices_calls) == 1


# --- get_invoice() failure handling ---------------------------------------------------------
# Real gap found 2026-08-26 (user's own scrutiny of the mcp/method-A relationship): production's
# list_invoices(include_full_details=True) fan-out silently falls back to shallower search-page
# data if a per-document get_invoice() call fails, and keeps going. download.py had NO error
# handling at all around this call — human decision (2026-08-26): fail loudly instead, naming the
# failed document, rather than silently degrading a backfill whose whole point is data fidelity.
# Re-running is safe (dedup via overwrite-by-id, REQ-BACKFILL re-run-safety), so a retry is the
# correct recovery, not a silent partial result.

class _FlakyMorningClient(_FakeMorningClient):
    """Like _FakeMorningClient, but get_invoice() raises for one specific id."""

    def __init__(self, pages, failing_id):
        super().__init__(pages)
        self._failing_id = failing_id

    def get_invoice(self, invoice_id):
        self.get_invoice_calls.append(invoice_id)
        if invoice_id == self._failing_id:
            raise ConnectionError("simulated transient network failure")
        return {"id": invoice_id, "fetched": True}


def test_get_invoice_failure_aborts_the_run_naming_the_failed_document():
    single_page = {
        "items": [{"id": "doc-a"}, {"id": "doc-b"}, {"id": "doc-c"}],
        "total": 3, "page": 1, "pages": 1,
    }
    client = _FlakyMorningClient([single_page], failing_id="doc-b")

    with pytest.raises(download.DocumentDownloadError, match="doc-b"):
        list(download.download_all_documents(client, since="2025-01-01"))


def test_main_aborts_on_get_invoice_failure_but_keeps_already_written_files(tmp_path, monkeypatch):
    single_page = {
        "items": [{"id": "doc-a"}, {"id": "doc-b"}, {"id": "doc-c"}],
        "total": 3, "page": 1, "pages": 1,
    }
    client = _FlakyMorningClient([single_page], failing_id="doc-b")
    monkeypatch.setattr(download, "MorningClient", lambda **_kwargs: client)

    output_dir = tmp_path / "output"
    creds_path = tmp_path / "creds.json"
    creds_path.write_text(json.dumps({
        "api_key_id": "x", "api_key_secret": "x", "auth_url": "https://x.invalid",
        "base_url": "https://x.invalid",
    }), encoding="utf-8")

    exit_code = download.main([
        "--since", "2025-01-01", "--output-dir", str(output_dir), "--creds-file", str(creds_path),
    ])

    assert exit_code != 0
    # doc-a was fetched and written before doc-b's failure aborted the run — a re-run is safe
    # (overwrite-by-id), so nothing already-succeeded needs to be thrown away.
    assert (output_dir / "doc-a.json").exists()
    assert not (output_dir / "doc-b.json").exists()
    assert not (output_dir / "doc-c.json").exists()
