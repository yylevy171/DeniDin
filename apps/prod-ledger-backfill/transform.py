#!/usr/bin/env python3
"""
Phase 3 (Transform) — Feature 061, prod-morning-ledger-backfill.

Reads raw document files from --input-dir (Phase 1's own output — never a live Morning API call,
REQ-BACKFILL-003) and persists correctly-shaped LedgerEvent files to --output-dir via the real
LedgerEventManager.add_ledger_event, so dedup and the tri-state new/duplicate/anomaly guard come
for real, unmodified, from that existing mechanism (research.md R7/R8) — every anomaly outcome is
retained on disk (LedgerEventManager's own pending_review.json) for Phase 3.5 (validate.py) to
read, not just logged and dropped.

**Method A only, for now**: `research.md` R7's real sandbox comparison (Acceptance-phase T031,
still pending) decides whether Method A (deterministic, this default) or Method B (AI-mediated)
is what Phase 3 is really built with. `build_envelope_fn` exists specifically so that swap is a
one-line change (or a future --method flag) rather than a rewrite — see method_a.py's/
method_b.py's `build_capture_envelope` docstrings for why transform.py calls that function and
not `transform()` (which is Phase 2's own, differently-shaped, comparison-only helper).
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict, Iterator, Tuple

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
    for path in sorted(input_dir.glob("*.json")):
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
    event_datetime are derived from the document's own accounting_document_creation_date, not
    from these, confirmed by reading add_ledger_event directly).
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
