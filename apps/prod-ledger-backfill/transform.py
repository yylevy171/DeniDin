#!/usr/bin/env python3
"""
Phase 3 (Transform) — Feature 061, prod-morning-ledger-backfill.

Reads raw document files from --input-dir (Phase 1's own output — never a live Morning API call,
REQ-BACKFILL-003) and persists correctly-shaped LedgerEvent files to --output-dir via the real
LedgerEventManager.add_ledger_event, so dedup and the tri-state new/duplicate/anomaly guard come
for real, unmodified, from that existing mechanism (research.md R7/R8) — every anomaly outcome is
retained on disk (LedgerEventManager's own pending_review.json) for Phase 3.5 (validate.py) to
read, not just logged and dropped.

**Method A — decided (2026-08-26, T031)**: `research.md` R7's real sandbox comparison (18 real
documents) found Method B (AI-mediated relay) unreliable at even a simple verbatim copy — it
crashed mid-run on a truncated relay, and 2 of the 13 documents that did complete had real
Hebrew-text corruption (a dropped character, a substituted look-alike letter), found via a plain
diff against Method A's output. Method A completed all 18 documents with no incident. Human
decision: Method A adopted, Method B rejected — not pursued further. `build_envelope_fn` is kept
as a parameter (rather than hardcoding the call inline) purely for testability, not because a
method swap is still anticipated — see method_a.py's/method_b.py's `build_capture_envelope`
docstrings for why transform.py calls that function and not `transform()` (which is Phase 2's
own, differently-shaped, comparison-only helper).
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict, Iterator, Tuple

# Same sys.path bootstrap conftest.py applies for the test suite — needed here too so this
# script also runs standalone (per contracts/cli-contract.md), not only under pytest.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
for _extra_path in (
    _REPO_ROOT / "apps" / "morning-mcp-app" / "src",
    _REPO_ROOT / "apps" / "denidin-app",
):
    _extra_path_str = str(_extra_path)
    if _extra_path_str not in sys.path:
        sys.path.insert(0, _extra_path_str)

import method_a

from _ledger_event_manager_loader import get_ledger_event_manager_class

_DEFAULT_BUILD_ENVELOPE_FN = method_a.build_capture_envelope


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 3 — map downloaded raw documents into LedgerEvent files."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory previously populated by download.py — raw document files.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Local directory for output LedgerEvent files (LedgerEventManager storage_dir).",
    )
    return parser


def _load_raw_documents(input_dir: Path) -> Iterator[Tuple[str, dict]]:
    """
    Bugfix, 2026-09-01 (Feature 062 backfill, real prod run): previously sorted by filename
    (the raw document's own UUID `id`) - effectively random relative to real creation order.
    `LedgerEventManager.add_ledger_event` resolves a document's cross-reference (`reference`/
    `reference_hint`) only against whatever is ALREADY in the ledger at the moment it's
    processed ("no end-of-sweep second pass" - see ledger_event_manager.py's own comment,
    correct for live conversational capture where events naturally arrive in chronological
    order). A single-shot bulk backfill has no such natural ordering, so UUID-sort left roughly
    half of all genuine same-batch links unresolved purely by processing-order luck (measured:
    74/146 unresolved on the real 2025-09-01 prod backfill).

    Sorting by Morning's own real `creationDate` (ascending) does NOT make every reference
    resolve on both sides - `linkedDocuments` is bidirectional and real links commonly point
    FORWARD in time too (e.g. a חשבון עסקה links forward to the invoice it was later converted
    into), so a document's own reference can still legitimately land on 'צריך למצוא' if it was
    itself the earlier side of the pair. What forward-chronological order DOES guarantee: for
    any pair where BOTH documents are present in this batch, the LATER one's own linkedDocuments
    entry (pointing back to the earlier one) resolves correctly, since the earlier document has
    already been written by the time the later one is processed - verified empirically on the
    real prod run: 62/73 same-batch pairs resolve on the later side (0 pairs unresolved on both
    sides); the remaining 11 reference a document outside the backfill's own --since window and
    are genuinely unrecoverable regardless of ordering. So every real relationship present in
    the batch ends up captured at least once, discoverable from either event.

    Falls back to the filename sort for any document missing `creationDate` (put after every
    dated document, stable order) rather than raising - a backfill must not silently drop
    documents Morning didn't stamp a creation time on.
    """
    def _sort_key(path: Path):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return (1, path.name)
        creation_date = doc.get("creationDate")
        if isinstance(creation_date, (int, float)):
            return (0, creation_date)
        return (1, path.name)

    for path in sorted(input_dir.glob("*.json"), key=_sort_key):
        yield path.stem, json.loads(path.read_text(encoding="utf-8"))


def run_transform(
    raw_documents: Iterator[Tuple[str, dict]],
    ledger_event_manager,
    build_envelope_fn: Callable[[dict], dict] = _DEFAULT_BUILD_ENVELOPE_FN,
) -> Dict[str, int]:
    """
    Maps every raw document into an un-expanded capture envelope (via the selected method) and
    persists it through LedgerEventManager.add_ledger_event — the manager's own event_id
    generation and dedup/anomaly guard run for real, never re-derived here. session_id/message_id/
    message_timestamp are synthetic placeholders (safe for חשבונית events — real event_id/
    event_datetime are derived from the document's own creation instant (Morning's raw
    creation_date, consumed internally as _source_creation_ts_raw), not from these —
    confirmed by reading add_ledger_event directly. accounting_document_creation_date, a
    separate persisted field that used to duplicate this same value, was removed entirely
    2026-08-26, master's Feature 044).
    """
    seen = written = skipped = 0
    for doc_id, raw_document in raw_documents:
        seen += 1
        envelope = build_envelope_fn(raw_document)
        event_id = ledger_event_manager.add_ledger_event(
            session_id="backfill",
            event=envelope,
            message_id=f"backfill-transform:{doc_id}",
            message_timestamp=None,
        )
        if event_id is None:
            skipped += 1
            print(f"⏭  {doc_id}: skipped (duplicate or unparseable)")
        else:
            written += 1
            print(f"✅ {doc_id} → {event_id}")
    return {"seen": seen, "written": written, "skipped": skipped}


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir)
    raw_documents = list(_load_raw_documents(input_dir))

    if not raw_documents:
        print(f"⚠️ No documents found in {input_dir}", file=sys.stderr)
        return 1

    ledger_event_manager_cls = get_ledger_event_manager_class()
    ledger_event_manager = ledger_event_manager_cls(storage_dir=args.output_dir)

    summary = run_transform(iter(raw_documents), ledger_event_manager)

    print(
        f"Done: {summary['seen']} seen, {summary['written']} written, "
        f"{summary['skipped']} skipped."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
