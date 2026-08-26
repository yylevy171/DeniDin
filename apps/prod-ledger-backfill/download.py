#!/usr/bin/env python3
"""
Phase 1 (Download) — Feature 061, prod-morning-ledger-backfill.

Constructs `MorningClient` directly (real Green Invoice credentials, from a dedicated gitignored
creds file) and downloads every matching accounting document from an operator-supplied start date
forward, writing each as a raw local file in Morning's own response shape.

Deliberately does NOT use `apps/morning-mcp-app`'s higher-level `tools.list_invoices` wrapper —
that function caps results at 100 items and refuses (rather than truncates) above that, a limit
that exists purely to keep a conversational WhatsApp reply short (see research.md R3). This module
paginates the raw `/documents/search` response itself, with no such cap.

No live MCP server, no `AIHandler`, no OpenAI call anywhere in this module (REQ-BACKFILL-002).

See contracts/cli-contract.md for the full CLI contract.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, Optional

# Same sys.path bootstrap conftest.py applies for the test suite — needed here too so this
# script also runs standalone (`python3 download.py ...`, per contracts/cli-contract.md), not
# only under pytest.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
for _extra_path in (_REPO_ROOT / "apps" / "morning-mcp-app" / "src",):
    _extra_path_str = str(_extra_path)
    if _extra_path_str not in sys.path:
        sys.path.insert(0, _extra_path_str)

from denidin_mcp_morning.morning_client import MorningClient

_REQUIRED_CREDS_FIELDS = ("api_key_id", "api_key_secret", "auth_url", "base_url")
_DEFAULT_CREDS_FILE = Path(__file__).parent / "config" / "backfill_prod_creds.local.json"


class BackfillPreconditionError(Exception):
    """Raised for any precondition failure that must stop the run before any network call."""


class DocumentDownloadError(Exception):
    """
    Raised when get_invoice() fails for a specific document mid-run.

    Human decision (2026-08-26): fail loudly and abort the whole run, naming the failed
    document — do NOT mirror production's list_invoices(include_full_details=True) fan-out,
    which silently falls back to shallower search-page data and keeps going. That's the right
    tradeoff for a live conversational reply (don't lose the whole sweep over one document); a
    backfill's whole point is data fidelity, so silently persisting a document with less data
    than a full fetch would have given is worse than stopping. Re-running is safe (dedup via
    overwrite-by-id) — every document already written before the failure stays written, so a
    retry simply resumes rather than needing to redo lost work.
    """


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI surface per contracts/cli-contract.md's `download.py` section."""
    parser = argparse.ArgumentParser(
        description="Phase 1 — download real Morning accounting documents to local files."
    )
    parser.add_argument(
        "--since",
        required=True,
        help="ISO date (YYYY-MM-DD), Israel-local. No default anywhere (REQ-BACKFILL-001).",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="Optional ISO date (YYYY-MM-DD), Israel-local — stop date, inclusive. Omit for the "
             "default unbounded-forward sweep (a real prod backfill run's whole point, "
             "REQ-BACKFILL-001/002); useful for bounding a sandbox/experiment pull to a known "
             "window instead of over-fetching and filtering locally after the fact (2026-08-26 "
             "user directive).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Local directory for raw downloaded document files. Reuse across runs for dedup.",
    )
    parser.add_argument(
        "--creds-file",
        default=str(_DEFAULT_CREDS_FILE),
        help="Path to a backfill_*_creds.local.json-shaped credentials file "
             "(contracts/backfill-creds-file.md). Defaults to the prod creds file's usual path.",
    )
    return parser


def parse_since_date(since_str: str):
    """Parses --since; raises BackfillPreconditionError on anything that isn't YYYY-MM-DD."""
    try:
        return datetime.strptime(since_str, "%Y-%m-%d").date()
    except (ValueError, TypeError) as exc:
        raise BackfillPreconditionError(
            f"--since must be an ISO date (YYYY-MM-DD), got: {since_str!r}"
        ) from exc


def parse_until_date(until_str: Optional[str]):
    """
    Parses --until; None (the "no stop date" default) passes through unchanged rather than
    raising, so callers don't need a separate "was --until even given" branch. Anything else that
    isn't YYYY-MM-DD raises BackfillPreconditionError, same as parse_since_date.
    """
    if until_str is None:
        return None
    try:
        return datetime.strptime(until_str, "%Y-%m-%d").date()
    except (ValueError, TypeError) as exc:
        raise BackfillPreconditionError(
            f"--until must be an ISO date (YYYY-MM-DD), got: {until_str!r}"
        ) from exc


def validate_date_range(since_date, until_date) -> None:
    """
    Raises BackfillPreconditionError if --until is given and falls before --since — before any
    network call. until_date=None (no stop date) always passes. since_date == until_date (a
    single-day window) is explicitly allowed, not an error.
    """
    if until_date is not None and until_date < since_date:
        raise BackfillPreconditionError(
            f"--until ({until_date.isoformat()}) is before --since ({since_date.isoformat()})"
        )


def load_credentials(path) -> Dict[str, str]:
    """
    Loads and validates the four-field credentials file (contracts/backfill-creds-file.md).
    Fails closed (REQ-BACKFILL-006): missing file, malformed JSON, or any missing required field
    all raise BackfillPreconditionError, before any network call is ever made.
    """
    path = Path(path)
    if not path.exists():
        raise BackfillPreconditionError(f"Credentials file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackfillPreconditionError(
            f"Credentials file is not valid JSON: {path} ({exc})"
        ) from exc

    missing = [field for field in _REQUIRED_CREDS_FIELDS if field not in data]
    if missing:
        raise BackfillPreconditionError(
            f"Credentials file {path} is missing required field(s): {', '.join(missing)}"
        )

    return {field: data[field] for field in _REQUIRED_CREDS_FIELDS}


def _extract_items(response):
    """
    Morning's /documents/search response may be a dict with items/data keys, or a bare list —
    same shape-handling as apps/morning-mcp-app/src/denidin_mcp_morning/tools.py's own
    _extract_items (research.md R3/R4), reimplemented here since Phase 1 deliberately avoids
    importing that module's higher-level wrappers.
    """
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        return response.get("items") or response.get("data") or []
    return []


def paginate_document_ids(client, since: str, until: Optional[str] = None) -> Iterator[str]:
    """
    Yields every document id matching `since` forward (and, if given, up to `until` inclusive —
    a real, confirmed-live Morning search param, `toDate`; same key
    denidin_mcp_morning/tools.py's own _map_list_invoices_filters uses), following the real
    page/pages/total fields with NO artificial cap (research.md R3 — unlike tools.list_invoices's
    100-item limit). `until=None` omits `toDate` entirely rather than sending it as None/empty,
    preserving the default unbounded-forward-sweep behavior byte-for-byte when not given.
    """
    params_base = {"fromDate": since}
    if until is not None:
        params_base["toDate"] = until

    page = 1
    while True:
        response = client.list_invoices(params={**params_base, "page": page})
        for item in _extract_items(response):
            doc_id = item.get("id") if isinstance(item, dict) else None
            if doc_id:
                yield doc_id

        total_pages = response.get("pages") if isinstance(response, dict) else None
        if not total_pages or page >= total_pages:
            break
        page += 1


def download_all_documents(
    client, since: str, until: Optional[str] = None, already_downloaded_ids=frozenset(),
) -> Iterator[dict]:
    """
    Yields the full raw document (via get_invoice) for every id paginate_document_ids finds,
    except ids already present in `already_downloaded_ids` — those are skipped entirely (no
    get_invoice call, nothing yielded for them).

    `already_downloaded_ids` defaults to empty, so omitting it is byte-for-byte the old
    behavior (every existing caller/test relies on this implicitly).

    Real gap found 2026-08-26, from an actual dev-sandbox backfill run: "dedup via
    overwrite-by-id" (this module's own DocumentDownloadError docstring) was previously true
    only at the file-write level — re-running the same command to "resume" after a partial
    failure still re-fetched every already-downloaded document via a fresh get_invoice call
    before ever reaching new material (709 wasted calls in that real run), risking
    re-triggering whatever rate limit caused the original failure even sooner. Human directive:
    "you need to know how to filter at the list level and not make a get details call if we
    already have the data."

    Raises DocumentDownloadError, naming the failed document, if get_invoice() fails for any
    one of them — see that class's docstring for why this fails loudly rather than silently
    degrading, unlike production's own fan-out.
    """
    for doc_id in paginate_document_ids(client, since, until):
        if doc_id in already_downloaded_ids:
            continue
        try:
            yield client.get_invoice(doc_id)
        except Exception as exc:
            raise DocumentDownloadError(
                f"get_invoice failed for document {doc_id!r}: {exc}"
            ) from exc


def _write_document(output_dir: Path, document: dict) -> Optional[Path]:
    """
    Writes one raw document file keyed on its own Morning id — overwrites byte-identically on a
    second run over an overlapping window (cross-cutting re-run-safety requirement), no special
    dedup code needed since the filename itself is the dedup key.
    """
    doc_id = document.get("id")
    if not doc_id:
        return None
    out_path = output_dir / f"{doc_id}.json"
    out_path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        since_date = parse_since_date(args.since)
        until_date = parse_until_date(args.until)
        validate_date_range(since_date, until_date)
        creds = load_credentials(args.creds_file)
    except BackfillPreconditionError as exc:
        print(f"⚠️ {exc}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    already_downloaded_ids = {path.stem for path in output_dir.glob("*.json")}

    client = MorningClient(
        api_key_id=creds["api_key_id"],
        api_key_secret=creds["api_key_secret"],
        auth_url=creds["auth_url"],
        base_url=creds["base_url"],
    )

    since_str = since_date.isoformat()
    until_str = until_date.isoformat() if until_date else None
    seen = 0
    written = 0
    skipped_no_id = 0

    try:
        for document in download_all_documents(
            client, since_str, until_str, already_downloaded_ids,
        ):
            seen += 1
            out_path = _write_document(output_dir, document)
            if out_path is None:
                skipped_no_id += 1
                print(f"⚠️ Skipping a document with no id: {document}", file=sys.stderr)
                continue
            written += 1
            print(f"  {document.get('id')} -> {out_path}")
    except DocumentDownloadError as exc:
        print(f"⚠️ {exc}", file=sys.stderr)
        print(
            f"Aborted after {written} file(s) written to {output_dir} — already-written "
            "files are safe to keep; re-run this same command to resume (dedup via "
            "overwrite-by-id).",
            file=sys.stderr,
        )
        return 1

    print(
        f"Done. {seen} document(s) seen, {written} file(s) written to {output_dir}"
        + (f", {skipped_no_id} skipped (no id)" if skipped_no_id else "")
        + (
            f", {len(already_downloaded_ids)} already present locally (skipped re-fetch)"
            if already_downloaded_ids else ""
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
