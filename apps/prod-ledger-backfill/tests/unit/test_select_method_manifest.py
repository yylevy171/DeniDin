"""
Phase 2 redesign (2026-08-26, per user direction): compare canonical JSON (Stage 1+2 only, NOT
the final LedgerEvent) between Method A (direct fetch + our own Stage1+2 code) and Method B (a
real live-MCP relay through an actual AI call) via sha256 hashes, computed once per "run" and
stored in a manifest — never recomputed on the fly during comparison.

Method A's generator is buildable and testable now (no live server needed — pure local code,
`method_a.compute_canonical_json`). Method B's generator needs a real running morning-mcp-app
server + a real OpenAI call and is deferred (its own environment-start approval); its manifest
format is intentionally identical to Method A's so compare_manifests works on either pairing.

Does NOT touch diff_ledger_events/format_verdict — those stay as they are, still relied on by
validate.py's sampled field comparison (test_validate.py) and their own existing tests.
"""
import hashlib
import json

import pytest

import select_method


def _raw_document(doc_id, number=70001, amount=117.0):
    """Same real shape used throughout this suite (test_method_a.py/test_transform.py)."""
    return {
        "id": doc_id,
        "number": number,
        "type": 305,
        "client": {"id": f"client-{doc_id}", "name": "Test Client Ltd."},
        "status": 2,
        "amount": amount,
        "total": amount,
        "vat": 0.0,
        "documentDate": "2025-01-15",
        "creationDate": "2025-01-15T09:30:00",
        "income": [{"description": "Consulting", "quantity": 1, "price": amount, "amountTotal": amount}],
        "payment": [{"name": "מזומן", "type": 1, "date": "2025-01-15", "amount": amount}],
    }


def _write_raw_document(input_dir, doc):
    (input_dir / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


# --- _canonicalize_for_hashing (2026-08-26, real single-doc live-run finding) ---------------

def test_canonicalize_normalizes_ascii_escaped_unicode_to_raw_utf8():
    """The exact real-world case: Hebrew text came back \\u-escaped through the MCP transport
    although format_invoice_json itself always writes raw UTF-8 (ensure_ascii=False)."""
    escaped = '{"client_name": "\\u05d0\\u05dc\\u05d9\\u05e0\\u05d4"}'
    result = select_method._canonicalize_for_hashing(escaped)
    assert result == '{"client_name": "אלינה"}'


def test_canonicalize_is_key_order_independent():
    a = select_method._canonicalize_for_hashing('{"b": 1, "a": 2}')
    b = select_method._canonicalize_for_hashing('{"a": 2, "b": 1}')
    assert a == b


def test_canonicalize_still_distinguishes_real_content_differences():
    a = select_method._canonicalize_for_hashing('{"amount": 100}')
    b = select_method._canonicalize_for_hashing('{"amount": 200}')
    assert a != b


# --- generate_method_a_manifest -------------------------------------------------------------

def test_generate_method_a_manifest_writes_canonical_json_and_hash_per_document(tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "folder_a"
    input_dir.mkdir()

    doc = _raw_document("doc-1")
    _write_raw_document(input_dir, doc)

    manifest = select_method.generate_method_a_manifest(input_dir, output_dir)

    canonical_path = output_dir / "doc-1.json"
    assert canonical_path.exists()
    canonical_json = canonical_path.read_text(encoding="utf-8")
    expected_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    assert manifest == {"doc-1": expected_hash}
    # Manifest is also persisted to disk — a later `--compare` run reads it, no recomputation.
    persisted_manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert persisted_manifest == manifest


def test_generate_method_a_manifest_covers_every_document_no_sampling(tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "folder_a"
    input_dir.mkdir()
    for i in range(20):
        _write_raw_document(input_dir, _raw_document(f"doc-{i:03d}", number=70000 + i))

    manifest = select_method.generate_method_a_manifest(input_dir, output_dir)

    assert len(manifest) == 20


def test_generate_method_a_manifest_is_deterministic_across_two_runs(tmp_path):
    """Same input -> byte-identical canonical JSON -> identical hash, run twice independently."""
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    _write_raw_document(input_dir, _raw_document("doc-1"))

    manifest_1 = select_method.generate_method_a_manifest(input_dir, tmp_path / "run1")
    manifest_2 = select_method.generate_method_a_manifest(input_dir, tmp_path / "run2")

    assert manifest_1 == manifest_2


# --- compare_manifests --------------------------------------------------------------------

def test_compare_manifests_identical():
    manifest_a = {"doc-1": "hash1", "doc-2": "hash2"}
    manifest_b = {"doc-1": "hash1", "doc-2": "hash2"}

    result = select_method.compare_manifests(manifest_a, manifest_b)

    assert result["identical"] is True
    assert result["count_a"] == 2 and result["count_b"] == 2
    assert result["only_in_a"] == []
    assert result["only_in_b"] == []
    assert result["mismatched_hashes"] == []


def test_compare_manifests_flags_hash_mismatch():
    manifest_a = {"doc-1": "hash1", "doc-2": "hash2"}
    manifest_b = {"doc-1": "hash1", "doc-2": "DIFFERENT_HASH"}

    result = select_method.compare_manifests(manifest_a, manifest_b)

    assert result["identical"] is False
    assert result["mismatched_hashes"] == ["doc-2"]


def test_compare_manifests_flags_missing_document_either_side():
    manifest_a = {"doc-1": "hash1", "doc-2": "hash2"}
    manifest_b = {"doc-1": "hash1", "doc-3": "hash3"}

    result = select_method.compare_manifests(manifest_a, manifest_b)

    assert result["identical"] is False
    assert result["only_in_a"] == ["doc-2"]
    assert result["only_in_b"] == ["doc-3"]


def test_format_manifest_verdict_identical():
    result = select_method.compare_manifests({"doc-1": "h"}, {"doc-1": "h"})
    assert select_method.format_manifest_verdict(result) == "IDENTICAL — adopt Method A"


def test_format_manifest_verdict_differs():
    result = select_method.compare_manifests({"doc-1": "h1"}, {"doc-1": "h2"})
    verdict = select_method.format_manifest_verdict(result)
    assert verdict.startswith("DIFFERS on:")
    assert "doc-1" in verdict
    assert verdict.endswith("— adopt Method B")


# --- CLI: --generate-a / --compare / --generate-b (deferred) -------------------------------

def test_generate_a_cli_requires_input_and_output_dir():
    parser = select_method.build_generate_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--generate-a", "--input-dir", "/tmp/x"])


def test_compare_cli_requires_both_manifests_and_report_out():
    parser = select_method.build_compare_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--compare", "--manifest-a", "/tmp/a.json"])


def test_main_generate_a_end_to_end(tmp_path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "folder_a"
    input_dir.mkdir()
    _write_raw_document(input_dir, _raw_document("doc-1"))

    exit_code = select_method.main([
        "--generate-a", "--input-dir", str(input_dir), "--output-dir", str(output_dir),
    ])

    assert exit_code == 0
    assert (output_dir / "manifest.json").exists()


def test_main_compare_end_to_end(tmp_path):
    manifest_a_path = tmp_path / "a_manifest.json"
    manifest_b_path = tmp_path / "b_manifest.json"
    manifest_a_path.write_text(json.dumps({"doc-1": "h"}), encoding="utf-8")
    manifest_b_path.write_text(json.dumps({"doc-1": "h"}), encoding="utf-8")
    report_path = tmp_path / "report.json"

    exit_code = select_method.main([
        "--compare", "--manifest-a", str(manifest_a_path), "--manifest-b", str(manifest_b_path),
        "--report-out", str(report_path),
    ])

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["identical"] is True


class _FakeFunctionCall:
    """Mimics a Responses API `function_call` output item just enough for
    _extract_relay_arguments to read it."""

    def __init__(self, name, arguments):
        self.type = "function_call"
        self.name = name
        self.arguments = json.dumps(arguments, ensure_ascii=False)


class _FakeMcpCall:
    """Mimics a Responses API `mcp_call` output item — a real remote-tool invocation, as opposed
    to just mcp_list_tools or a local function_call. Added 2026-08-26 alongside
    _response_actually_called_mcp_tool (see select_method.py's own comment for why: gpt-4o-mini's
    first real run fabricated a document without ever producing one of these)."""

    def __init__(self, name):
        self.type = "mcp_call"
        self.name = name


class _FakeResponse:
    def __init__(self, output):
        self.output = output


class _FakeOpenAIClient:
    """
    Records every responses.create() call and returns a canned relay_canonical_json call per
    document id — no real network call, matching method_b.py's existing injected-client pattern.
    Includes a real mcp_call item by default (the honest case); set include_mcp_call=False to
    simulate the hallucination this session actually hit in production.
    """

    def __init__(self, canonical_json_by_doc_id, include_mcp_call=True):
        self._canonical_json_by_doc_id = canonical_json_by_doc_id
        self._include_mcp_call = include_mcp_call
        self.calls = []
        self.responses = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        # The doc id is embedded in the prompt (_build_relay_prompt) — pull it back out so the
        # fake can return the right canonical JSON for whichever document this call is about.
        doc_id = next(
            doc_id for doc_id in self._canonical_json_by_doc_id if doc_id in kwargs["instructions"]
        )
        canonical_json = self._canonical_json_by_doc_id[doc_id]
        output = []
        if self._include_mcp_call:
            output.append(_FakeMcpCall("get_invoice_details"))
        output.append(_FakeFunctionCall(
            "relay_canonical_json", {"accounting_document_json": canonical_json}
        ))
        return _FakeResponse(output)


@pytest.fixture
def fixture_mcp_creds_file(tmp_path):
    """A valid backfill_mcp_creds.local.json-shaped file pointing at a fixture status file."""
    status_file = tmp_path / "mcp-status.json"
    status_file.write_text(
        json.dumps({"status": "running", "server_url": "https://fixture.example.invalid/mcp"}),
        encoding="utf-8",
    )
    creds_file = tmp_path / "backfill_mcp_creds.local.json"
    creds_file.write_text(
        json.dumps({
            "mcp_status_file": str(status_file),
            "mcp_auth_token": "fixture-mcp-token",
        }),
        encoding="utf-8",
    )
    return creds_file


def test_generate_method_b_manifest_relays_canonical_json_per_document(tmp_path, fixture_mcp_creds_file):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "folder_b"
    input_dir.mkdir()
    _write_raw_document(input_dir, _raw_document("doc-1"))

    fake_client = _FakeOpenAIClient({"doc-1": '{"fake": "canonical json for doc-1"}'})

    manifest = select_method.generate_method_b_manifest(
        input_dir, output_dir,
        mcp_creds_file=fixture_mcp_creds_file, openai_client=fake_client,
    )

    canonical_path = output_dir / "doc-1.json"
    assert canonical_path.read_text(encoding="utf-8") == '{"fake": "canonical json for doc-1"}'
    expected_hash = hashlib.sha256(canonical_path.read_bytes()).hexdigest()
    assert manifest == {"doc-1": expected_hash}
    assert len(fake_client.calls) == 1
    # A real remote MCP tool + the local relay tool are both attached, in that order.
    tools = fake_client.calls[0]["tools"]
    assert tools[0]["type"] == "mcp"
    assert tools[0]["server_url"] == "https://fixture.example.invalid/mcp"
    assert tools[0]["headers"]["Authorization"] == "Bearer fixture-mcp-token"
    assert tools[1]["name"] == "relay_canonical_json"
    # 2026-08-26: gpt-4o-mini's first real run hallucinated a document instead of calling the
    # real MCP tool — the model must match production's actual configured model
    # (config.dev.json's ai_model), not a cheaper stand-in that can't reliably chain tool calls.
    assert fake_client.calls[0]["model"] == "gpt-5.6-luna"


def test_generate_method_b_manifest_rejects_a_relay_with_no_real_mcp_call(
    tmp_path, fixture_mcp_creds_file
):
    """
    Real incident, 2026-08-26: the model listed the server's tools (mcp_list_tools) and then
    fabricated an entirely invented document for relay_canonical_json, on all 18 documents in
    the first live run, without ever calling get_invoice_details. This must be caught and
    refused, not silently accepted as a "relay".
    """
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "folder_b"
    input_dir.mkdir()
    _write_raw_document(input_dir, _raw_document("doc-1"))

    fake_client = _FakeOpenAIClient(
        {"doc-1": '{"fabricated": true}'}, include_mcp_call=False,
    )

    with pytest.raises(ValueError, match="WITHOUT ever calling get_invoice_details"):
        select_method.generate_method_b_manifest(
            input_dir, output_dir,
            mcp_creds_file=fixture_mcp_creds_file, openai_client=fake_client,
        )
    # Nothing gets written for a rejected document — no half-fabricated file left behind.
    assert not (output_dir / "doc-1.json").exists()


def test_generate_method_b_manifest_covers_every_document(tmp_path, fixture_mcp_creds_file):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "folder_b"
    input_dir.mkdir()
    canonical_by_id = {}
    for i in range(5):
        doc_id = f"doc-{i:03d}"
        _write_raw_document(input_dir, _raw_document(doc_id, number=70000 + i))
        canonical_by_id[doc_id] = json.dumps({"id": doc_id})

    fake_client = _FakeOpenAIClient(canonical_by_id)
    manifest = select_method.generate_method_b_manifest(
        input_dir, output_dir,
        mcp_creds_file=fixture_mcp_creds_file, openai_client=fake_client,
    )

    assert len(manifest) == 5
    assert len(fake_client.calls) == 5


def test_generate_method_b_manifest_missing_creds_file_raises_unavailable(tmp_path):
    with pytest.raises(select_method.MethodBUnavailableError, match="credentials file"):
        select_method.generate_method_b_manifest(
            tmp_path / "raw", tmp_path / "folder_b",
            mcp_creds_file=tmp_path / "does_not_exist.json", openai_client=object(),
        )


def test_generate_method_b_manifest_server_not_running_raises_unavailable(tmp_path):
    status_file = tmp_path / "mcp-status.json"
    status_file.write_text(json.dumps({"status": "stopped"}), encoding="utf-8")
    creds_file = tmp_path / "backfill_mcp_creds.local.json"
    creds_file.write_text(
        json.dumps({"mcp_status_file": str(status_file), "mcp_auth_token": "t"}),
        encoding="utf-8",
    )

    with pytest.raises(select_method.MethodBUnavailableError, match="running"):
        select_method.generate_method_b_manifest(
            tmp_path / "raw", tmp_path / "folder_b",
            mcp_creds_file=creds_file, openai_client=object(),
        )
