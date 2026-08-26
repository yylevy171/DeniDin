#!/usr/bin/env python3
"""
Phase 2 (Method Selection Experiment) — Feature 061, prod-morning-ledger-backfill.

**Redesigned 2026-08-26, per direct user direction**: compares Method A vs Method B at the
CANONICAL JSON level (Stage 1+2 only — `format_invoice_json`'s output), not at the final
LedgerEvent level (Stage 3) the original design used. Rationale (verbatim): "The goal is to
compare the raw inputs (assuming AI doesn't botch the passthrough, which is also sort of tested
in this setup)" — i.e. does our own direct Stage1+2 code (Method A: MorningClient fetch, no
server, no AI) produce byte-identical canonical JSON to what a REAL live morning-mcp-app server +
a REAL AI relay (Method B) delivers for the same document. Comparing at the final LedgerEvent
level would conflate two separate questions (does Stage1+2 round-trip correctly through a live
AI relay? vs does Stage 3's own derivation logic work?) — this isolates the first, which is what
"does the mcp layer manipulate the data" is actually asking.

Hash-based, not field-by-field (2026-08-26): each method's "run" computes a sha256 per document
ONCE and stores it in a manifest — comparison itself never recomputes anything, just diffs two
already-computed manifests. Method A's generator (`generate_method_a_manifest`) is pure local
code, runnable now.

Method B's generator (`generate_method_b_manifest`) is now fully implemented (2026-08-26): a real
OpenAI Responses API call per document, with a real remote `type: "mcp"` tool attached to the
actual live morning-mcp-app server (dev/sandbox), asking the model to fetch that document via
`get_invoice_details(output_format="json")` over the real MCP protocol and relay the exact
canonical JSON string it gets back — verbatim, via a local `relay_canonical_json` function-tool
call — rather than just reading the MCP tool's own raw output directly, so this setup actually
exercises "does the model botch the passthrough" (`research.md` R7's stated goal), not just
"does the server return the right bytes". The server-URL-discovery and MCP-tool-attachment
mechanisms below are independent reimplementations (no import) of the real, already-verified
patterns in `apps/denidin-app/src/handlers/morning_mcp_locator.py` (`MorningMcpLocator`) and
`apps/denidin-app/src/handlers/ai_handler.py`'s remote-MCP-tool construction — this feature never
imports denidin-app or morning-mcp-app runtime code beyond the existing, established
`denidin_mcp_morning` library dependency (`method_a.py`/`method_b.py`'s own imports).

Actually RUNNING this generator for real still needs a live morning-mcp-app dev/sandbox server —
its own environment-start approval (root CLAUDE.md), separate from and later than writing this
code. The unit tests below inject a fake OpenAI client and a fake MCP status file, so no real
network call happens in the test suite.

`diff_ledger_events`/`format_verdict` below are UNCHANGED and NOT part of this redesign — they
compare full LedgerEvent dicts and are still relied on by `validate.py`'s Phase 3.5 sampled
field comparison (a different, already-approved check: does the real persisted LedgerEvent match
what Method A alone would independently derive from the same raw document — nothing to do with
Method B or the live MCP layer at all).

Never touches prod (research.md R7) — run once, by a human, during implementation; not part of
the real per-run pipeline. See contracts/cli-contract.md for the full CLI contract.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Optional

# Same sys.path bootstrap conftest.py applies for the test suite — needed here too so this
# script also runs standalone (per contracts/cli-contract.md), not only under pytest. Both
# entries are needed: morning-mcp-app/src for method_a's denidin_mcp_morning import, and
# denidin-app's own root for _ledger_event_manager_loader's src.utils.time_utils import.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
for _extra_path in (
    _REPO_ROOT / "apps" / "morning-mcp-app" / "src",
    _REPO_ROOT / "apps" / "denidin-app",
):
    _extra_path_str = str(_extra_path)
    if _extra_path_str not in sys.path:
        sys.path.insert(0, _extra_path_str)

_IGNORED_FIELDS = frozenset({"event_id"})

_DEFAULT_MCP_CREDS_FILE = Path(__file__).parent / "config" / "backfill_mcp_creds.local.json"
_REQUIRED_MCP_CREDS_FIELDS = ("mcp_status_file", "mcp_auth_token")


class MethodBUnavailableError(Exception):
    """
    Raised when Method B's live-MCP prerequisites aren't met: no MCP creds file, no MCP status
    file, or the status file doesn't report a running server. Distinct from NotImplementedError
    (which meant "this code doesn't exist yet") — this means "the code exists but the live
    server/creds it needs aren't there right now", the expected steady state until a human
    explicitly starts morning-mcp-app dev/sandbox (its own environment-start approval).
    """


_RELAY_CANONICAL_JSON_TOOL = {
    "type": "function",
    "name": "relay_canonical_json",
    "description": (
        "Relay the exact canonical JSON string get_invoice_details returned for this document, "
        "completely verbatim and unmodified, as a single string."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "accounting_document_json": {
                "type": "string",
                "description": (
                    "The exact string get_invoice_details returned for this document, copied "
                    "verbatim, character for character — do not reformat, reorder, translate, "
                    "summarize, or drop anything."
                ),
            },
        },
        "required": ["accounting_document_json"],
        "additionalProperties": False,
    },
}


def diff_ledger_events(event_a: Dict, event_b: Dict, ignore_fields=_IGNORED_FIELDS) -> Dict:
    """
    Field-by-field comparison of two LedgerEvent-shaped dicts, excluding `event_id` (capture-
    timestamp-derived — expected to differ trivially between two separate runs).

    Returns {"identical": bool, "differing_fields": [sorted field names]}.
    """
    all_keys = (set(event_a) | set(event_b)) - set(ignore_fields)
    differing = sorted(
        key for key in all_keys
        if event_a.get(key) != event_b.get(key)
    )
    return {"identical": not differing, "differing_fields": differing}


def format_verdict(diff_result: Dict) -> str:
    """One-line verdict string, per contracts/cli-contract.md's exact wording."""
    if diff_result["identical"]:
        return "IDENTICAL — adopt Method A"
    fields = ", ".join(diff_result["differing_fields"])
    return f"DIFFERS on: {fields} — adopt Method B"


def generate_method_a_manifest(input_dir, output_dir) -> Dict[str, str]:
    """
    Method A's "run" (2026-08-26 redesign): for every raw document file in input_dir, computes
    the canonical JSON (Stage 1+2 only, via method_a.compute_canonical_json — no Stage 3, no
    AI) and writes it to output_dir/{doc_id}.json, plus a manifest.json mapping doc_id -> sha256
    hash. Keyed on the raw document's own `id` (not accounting_document_display_number) since
    Method A and Method B both iterate the SAME raw document ids directly — no LedgerEvent
    involved anywhere in this comparison.

    Pure local code, no network beyond whatever already-downloaded local raw files provide — no
    live server needed, runnable now.
    """
    import method_a

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, str] = {}
    for path in sorted(input_dir.glob("*.json")):
        raw_document = json.loads(path.read_text(encoding="utf-8"))
        doc_id = raw_document.get("id")
        if not doc_id:
            continue
        canonical_json = method_a.compute_canonical_json(raw_document)
        (output_dir / f"{doc_id}.json").write_text(canonical_json, encoding="utf-8")
        manifest[doc_id] = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def _load_mcp_creds(path) -> Dict[str, str]:
    """
    Loads/validates the MCP credentials file (contracts/backfill-mcp-creds-file.md) — a NEW,
    separate, gitignored local file from `backfill_prod_creds.local.json`/
    `backfill_sandbox_creds.local.json` (those deliberately hold zero MCP fields, per
    contracts/backfill-creds-file.md's "What this file deliberately does NOT contain"). Fails
    closed, same discipline as download.py's load_credentials.
    """
    path = Path(path)
    if not path.exists():
        raise MethodBUnavailableError(
            f"Method B needs an MCP credentials file, not found: {path}. See "
            "contracts/backfill-mcp-creds-file.md for the expected shape (mcp_status_file, "
            "mcp_auth_token, optional mcp_server_label)."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MethodBUnavailableError(
            f"MCP credentials file is not valid JSON: {path} ({exc})"
        ) from exc

    missing = [field for field in _REQUIRED_MCP_CREDS_FIELDS if field not in data]
    if missing:
        raise MethodBUnavailableError(
            f"MCP credentials file {path} is missing required field(s): {', '.join(missing)}"
        )
    return data


def _discover_mcp_server_url(status_file_path) -> str:
    """
    Reads the shared MCP status file morning-mcp-app publishes (e.g. `shared/mcp-status-dev/...`,
    per root CLAUDE.md) — an independent reimplementation (no import) of
    `apps/denidin-app/src/handlers/morning_mcp_locator.py`'s `MorningMcpLocator`: checks
    `status == "running"`, returns `server_url`. That class's own docstring confirms this
    file-reading approach (never importing morning-mcp-app code, never pinging the server
    directly) is this repo's sanctioned cross-app discovery pattern.
    """
    path = Path(status_file_path)
    if not path.exists():
        raise MethodBUnavailableError(
            f"MCP status file not found: {path}. morning-mcp-app dev/sandbox must be running "
            "(its own environment-start approval) before Method B can be generated."
        )
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MethodBUnavailableError(
            f"MCP status file is not valid JSON: {path} ({exc})"
        ) from exc

    if status.get("status") != "running":
        raise MethodBUnavailableError(
            f"MCP status file {path} reports status={status.get('status')!r}, not 'running' — "
            "morning-mcp-app dev/sandbox must be up before Method B can be generated."
        )
    server_url = status.get("server_url")
    if not server_url:
        raise MethodBUnavailableError(f"MCP status file {path} has no server_url.")
    return server_url


def _build_mcp_tool(server_url: str, auth_token: str, server_label: str) -> dict:
    """
    Independent reimplementation (no import) of the real remote-MCP-tool shape
    `apps/denidin-app/src/handlers/ai_handler.py` attaches for godfather/admin turns: `type:
    "mcp"`, `server_label`/`server_url`, a `require_approval` dict, and a bearer Authorization
    header. Scoped down to the one read-only tool this script ever calls
    (`get_invoice_details`) in the "never" (no human approval) bucket — nothing else is
    auto-approved, so the model could not silently execute any mutating tool on that server even
    if it tried.
    """
    return {
        "type": "mcp",
        "server_label": server_label,
        "server_url": server_url,
        "require_approval": {"never": {"tool_names": ["get_invoice_details"]}},
        "headers": {"Authorization": f"Bearer {auth_token}"},
    }


def _build_relay_prompt(doc_id: str) -> str:
    return (
        "Automated document-relay task. Make exactly two tool calls, in this order, and no text "
        "reply — no human will read one.\n\n"
        f"1. Call get_invoice_details with internal_morning_id=\"{doc_id}\" and "
        "output_format=\"json\".\n"
        "2. Call relay_canonical_json exactly once, passing the EXACT string get_invoice_details "
        "returned as accounting_document_json — copied verbatim, character for character. Do "
        "not reformat, reorder, translate, summarize, or drop anything."
    )


def _extract_relay_arguments(response) -> Optional[dict]:
    """Extracts the first relay_canonical_json call's arguments from a Responses API result."""
    for item in getattr(response, "output", None) or []:
        if (
            getattr(item, "type", None) == "function_call"
            and getattr(item, "name", None) == "relay_canonical_json"
        ):
            return json.loads(item.arguments)
    return None


def _relay_one_document_via_mcp(doc_id: str, mcp_tool: dict, openai_client) -> str:
    """One real OpenAI Responses API call for one document — see module docstring for why this
    goes through a local relay tool call rather than reading the MCP call's own output directly."""
    response = openai_client.responses.create(
        model="gpt-4o-mini",
        instructions=_build_relay_prompt(doc_id),
        input="Fetch and relay this document.",
        tools=[mcp_tool, _RELAY_CANONICAL_JSON_TOOL],
    )

    args = _extract_relay_arguments(response)
    if args is None:
        raise ValueError(
            f"Method B: model made no relay_canonical_json call for document {doc_id!r}"
        )
    canonical_json = args.get("accounting_document_json")
    if not canonical_json:
        raise ValueError(
            f"Method B: relay_canonical_json call for document {doc_id!r} had no "
            "accounting_document_json"
        )
    return canonical_json


def generate_method_b_manifest(
    input_dir, output_dir, *, mcp_creds_file=None, openai_client=None
) -> Dict[str, str]:
    """
    Method B's "run": for every raw document id already present in input_dir (only the `id` is
    used — Method B re-fetches its own copy live, it never reads the raw document's own content),
    make a real OpenAI Responses API call with a real remote MCP tool attached to the live
    morning-mcp-app server, asking the model to fetch that document via `get_invoice_details`
    over the real MCP protocol and relay the canonical JSON it gets back verbatim — then
    hash+store it exactly like generate_method_a_manifest does, so compare_manifests works
    unmodified on either pairing.

    `mcp_creds_file` defaults to config/backfill_mcp_creds.local.json
    (contracts/backfill-mcp-creds-file.md). `openai_client` is injected for testability, matching
    method_b.py's existing pattern; a real `OpenAI()` client (requires a real API key, picked up
    from the environment the same way method_b.py's does) is constructed if not supplied.

    Raises MethodBUnavailableError before any OpenAI call if the MCP creds/status file
    prerequisites aren't met — actually running this for real needs a live morning-mcp-app
    dev/sandbox server, its own environment-start approval (root CLAUDE.md).
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    creds = _load_mcp_creds(mcp_creds_file or _DEFAULT_MCP_CREDS_FILE)
    server_url = _discover_mcp_server_url(creds["mcp_status_file"])
    mcp_tool = _build_mcp_tool(
        server_url, creds["mcp_auth_token"], creds.get("mcp_server_label", "morning-invoices"),
    )

    if openai_client is None:
        from openai import OpenAI  # local import: no openai dependency unless Method B runs
        openai_client = OpenAI()

    manifest: Dict[str, str] = {}
    for path in sorted(input_dir.glob("*.json")):
        raw_document = json.loads(path.read_text(encoding="utf-8"))
        doc_id = raw_document.get("id")
        if not doc_id:
            continue
        canonical_json = _relay_one_document_via_mcp(doc_id, mcp_tool, openai_client)
        (output_dir / f"{doc_id}.json").write_text(canonical_json, encoding="utf-8")
        manifest[doc_id] = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def compare_manifests(manifest_a: Dict[str, str], manifest_b: Dict[str, str]) -> Dict:
    """
    Diffs two already-computed manifests — no hashing, no re-fetching, no transformation of any
    kind happens here (2026-08-26 user direction: "no computing on the fly during the run").
    """
    keys_a = set(manifest_a)
    keys_b = set(manifest_b)
    only_in_a = sorted(keys_a - keys_b)
    only_in_b = sorted(keys_b - keys_a)
    common = sorted(keys_a & keys_b)
    mismatched = sorted(key for key in common if manifest_a[key] != manifest_b[key])

    return {
        "count_a": len(manifest_a),
        "count_b": len(manifest_b),
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
        "mismatched_hashes": mismatched,
        "identical": not (only_in_a or only_in_b or mismatched),
    }


def format_manifest_verdict(compare_result: Dict) -> str:
    """Same wording convention as format_verdict above, for a compare_manifests() result."""
    if compare_result["identical"]:
        return "IDENTICAL — adopt Method A"
    differing = sorted(
        set(compare_result["only_in_a"])
        | set(compare_result["only_in_b"])
        | set(compare_result["mismatched_hashes"])
    )
    fields = ", ".join(differing)
    return f"DIFFERS on: {fields} — adopt Method B"


def build_generate_arg_parser() -> argparse.ArgumentParser:
    """Parser for `--generate-a`/`--generate-b` mode."""
    parser = argparse.ArgumentParser(
        description="Phase 2 — generate one method's canonical-JSON hash manifest."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--generate-a", action="store_true", help="Run Method A's generator.")
    group.add_argument("--generate-b", action="store_true", help="Run Method B's generator.")
    parser.add_argument(
        "--input-dir", required=True,
        help="Directory of raw sandbox document files (a download.py run against sandbox creds).",
    )
    parser.add_argument(
        "--output-dir", required=True, help="Where to write canonical JSON files + manifest.json.",
    )
    return parser


def build_compare_arg_parser() -> argparse.ArgumentParser:
    """Parser for `--compare` mode — separate from build_generate_arg_parser() above, same
    reasoning as validate.py's build_arg_parser()/build_approve_arg_parser() split."""
    parser = argparse.ArgumentParser(
        description="Phase 2 — compare two already-generated manifests."
    )
    parser.add_argument("--compare", action="store_true", required=True)
    parser.add_argument("--manifest-a", required=True, help="Path to Method A's manifest.json.")
    parser.add_argument("--manifest-b", required=True, help="Path to Method B's manifest.json.")
    parser.add_argument("--report-out", required=True, help="Path to write the comparison report.")
    return parser


def _run_generate(argv) -> int:
    parser = build_generate_arg_parser()
    args = parser.parse_args(argv)

    if args.generate_b:
        try:
            manifest = generate_method_b_manifest(args.input_dir, args.output_dir)
        except MethodBUnavailableError as exc:
            print(f"⚠️ {exc}", file=sys.stderr)
            return 1
        print(f"Method B: {len(manifest)} document(s) hashed, manifest written to {args.output_dir}")
        return 0

    manifest = generate_method_a_manifest(args.input_dir, args.output_dir)
    print(f"Method A: {len(manifest)} document(s) hashed, manifest written to {args.output_dir}")
    return 0


def _run_compare(argv) -> int:
    parser = build_compare_arg_parser()
    args = parser.parse_args(argv)

    manifest_a = json.loads(Path(args.manifest_a).read_text(encoding="utf-8"))
    manifest_b = json.loads(Path(args.manifest_b).read_text(encoding="utf-8"))
    result = compare_manifests(manifest_a, manifest_b)

    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Compared {result['count_a']} vs {result['count_b']} document(s).")
    print(format_manifest_verdict(result))
    print(f"Full report written to {report_path}")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--compare" in argv:
        return _run_compare(argv)
    return _run_generate(argv)


if __name__ == "__main__":
    sys.exit(main())
