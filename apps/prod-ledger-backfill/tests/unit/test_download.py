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


# --- --until (optional stop date, 2026-08-26 — user directive) -----------------------------
# A real prod backfill run legitimately wants "--since forward, no cap" (REQ-BACKFILL-001/002's
# whole point) — --until stays optional, defaulting to no upper bound, so that behavior is
# unchanged. It exists so a bounded sandbox/experiment run (Phase 2's ~20-doc comparison, or any
# other scoped pull) doesn't have to over-fetch and filter locally after the fact, the way this
# session's first real Method A run had to (--since 2026-08-20 alone pulled 97 documents spanning
# a week; the operator wanted just the one day).

def test_until_is_optional():
    """No --until at all must not raise — the unbounded-forward-sweep default stays intact."""
    parser = download.build_arg_parser()
    args = parser.parse_args(["--since", "2025-01-01", "--output-dir", "/tmp/whatever"])
    assert args.until is None


def test_until_must_be_a_valid_iso_date():
    parser = download.build_arg_parser()
    args = parser.parse_args([
        "--since", "2025-01-01", "--until", "not-a-date", "--output-dir", "/tmp/whatever",
    ])
    with pytest.raises(download.BackfillPreconditionError):
        download.parse_until_date(args.until)


def test_none_until_parses_to_none():
    """parse_until_date(None) must not raise — the common "no --until given" case."""
    assert download.parse_until_date(None) is None


def test_valid_until_parses_to_a_date():
    parsed = download.parse_until_date("2025-01-31")
    assert parsed.year == 2025 and parsed.month == 1 and parsed.day == 31


def test_until_before_since_fails_before_any_network_call():
    with pytest.raises(download.BackfillPreconditionError, match="before"):
        download.validate_date_range(
            download.parse_since_date("2025-01-31"), download.parse_until_date("2025-01-01"),
        )


def test_until_equal_to_since_is_allowed():
    """A single-day window (since == until) is a legitimate, common case — not an error."""
    download.validate_date_range(
        download.parse_since_date("2025-01-01"), download.parse_until_date("2025-01-01"),
    )


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


def test_until_is_passed_through_as_toDate_param():
    """toDate is a real, confirmed-live Morning search param (denidin_mcp_morning/tools.py's
    own _map_list_invoices_filters) — server-side date-range filtering, not a local post-fetch
    filter, so a bounded pull never over-fetches in the first place."""
    single_page = {"items": [{"id": "only-doc"}], "total": 1, "page": 1, "pages": 1}
    client = _FakeMorningClient([single_page])

    list(download.paginate_document_ids(client, since="2025-01-01", until="2025-01-31"))

    assert client.list_invoices_calls[0]["toDate"] == "2025-01-31"


def test_no_until_means_no_toDate_param():
    """The unbounded-forward-sweep default (REQ-BACKFILL-002) must not send toDate at all —
    not even an empty/None value that could be misread as "up to nothing"."""
    single_page = {"items": [{"id": "only-doc"}], "total": 1, "page": 1, "pages": 1}
    client = _FakeMorningClient([single_page])

    list(download.paginate_document_ids(client, since="2025-01-01"))

    assert "toDate" not in client.list_invoices_calls[0]


def test_download_all_documents_also_accepts_until():
    single_page = {"items": [{"id": "only-doc"}], "total": 1, "page": 1, "pages": 1}
    client = _FakeMorningClient([single_page])

    documents = list(download.download_all_documents(client, since="2025-01-01", until="2025-01-31"))

    assert len(documents) == 1
    assert client.list_invoices_calls[0]["toDate"] == "2025-01-31"


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


def test_main_rejects_until_before_since_before_any_network_call(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "MorningClient", _never_call_morning_client)
    exit_code = download.main([
        "--since", "2025-01-31", "--until", "2025-01-01", "--output-dir", str(tmp_path / "out"),
        "--creds-file", str(tmp_path / "missing.json"),
    ])
    assert exit_code != 0


def test_main_passes_until_through_to_the_real_pagination_call(tmp_path, monkeypatch):
    single_page = {"items": [{"id": "only-doc"}], "total": 1, "page": 1, "pages": 1}
    client = _FakeMorningClient([single_page])
    monkeypatch.setattr(download, "MorningClient", lambda **_kwargs: client)

    creds_path = tmp_path / "creds.json"
    creds_path.write_text(json.dumps({
        "api_key_id": "x", "api_key_secret": "x", "auth_url": "https://x.invalid",
        "base_url": "https://x.invalid",
    }), encoding="utf-8")

    exit_code = download.main([
        "--since", "2025-01-01", "--until", "2025-01-31",
        "--output-dir", str(tmp_path / "out"), "--creds-file", str(creds_path),
    ])

    assert exit_code == 0
    assert client.list_invoices_calls[0]["toDate"] == "2025-01-31"


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


# --- Skip-if-already-downloaded (real gap found 2026-08-26) ---------------------------------
# A prior real dev-sandbox backfill run (709/4040 documents fetched before Morning returned a
# live 403) proved that re-running the same command to "resume" would silently re-fetch every
# already-downloaded document via a fresh get_invoice call before ever reaching new material —
# wasteful, and risks re-triggering whatever rate limit caused the original failure even sooner.
# "Dedup via overwrite-by-id" was previously true only at the file-write level, not at the
# network-call level. Human directive (2026-08-26): "you need to know how to filter at the list
# level and not make a get details call if we already have the data."

def test_download_all_documents_skips_ids_already_downloaded():
    single_page = {
        "items": [{"id": "doc-a"}, {"id": "doc-b"}, {"id": "doc-c"}],
        "total": 3, "page": 1, "pages": 1,
    }
    client = _FakeMorningClient([single_page])

    documents = list(download.download_all_documents(
        client, since="2025-01-01", already_downloaded_ids={"doc-b"},
    ))

    assert [doc["id"] for doc in documents] == ["doc-a", "doc-c"]
    assert client.get_invoice_calls == ["doc-a", "doc-c"]  # doc-b never fetched


def test_download_all_documents_default_already_downloaded_ids_is_empty(
    fixture_search_page_1, fixture_search_page_2,
):
    """Omitting the new parameter must be byte-for-byte the old behavior — every prior test in
    this file already relies on this implicitly by never passing it."""
    client = _FakeMorningClient([fixture_search_page_1, fixture_search_page_2])

    documents = list(download.download_all_documents(client, since="2025-01-01"))

    assert len(documents) == 150
    assert len(client.get_invoice_calls) == 150


def test_main_skips_already_present_files_without_refetching(tmp_path, monkeypatch):
    single_page = {
        "items": [{"id": "doc-a"}, {"id": "doc-b"}],
        "total": 2, "page": 1, "pages": 1,
    }
    client = _FakeMorningClient([single_page])
    monkeypatch.setattr(download, "MorningClient", lambda **_kwargs: client)

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    # doc-a already has a local file from a prior run — its exact content must be left untouched,
    # proving main() never re-fetched (and thus never re-wrote) it.
    preexisting = output_dir / "doc-a.json"
    preexisting.write_text(json.dumps({"id": "doc-a", "fetched": "from a prior run"}), encoding="utf-8")

    creds_path = tmp_path / "creds.json"
    creds_path.write_text(json.dumps({
        "api_key_id": "x", "api_key_secret": "x", "auth_url": "https://x.invalid",
        "base_url": "https://x.invalid",
    }), encoding="utf-8")

    exit_code = download.main([
        "--since", "2025-01-01", "--output-dir", str(output_dir), "--creds-file", str(creds_path),
    ])

    assert exit_code == 0
    assert client.get_invoice_calls == ["doc-b"]  # doc-a never re-fetched
    assert json.loads(preexisting.read_text()) == {"id": "doc-a", "fetched": "from a prior run"}
    assert json.loads((output_dir / "doc-b.json").read_text())["fetched"] is True
