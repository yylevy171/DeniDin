#!/usr/bin/env python3
"""
Phase 3.5 (Validate) — Feature 061, prod-morning-ledger-backfill.

Human sign-off gate between Transform (Phase 3) and Load (Phase 4) — added per explicit user
direction ("We will have phase 3.5 - validation of results"). Reads --raw-dir (Phase 1's output)
and --ledger-dir (Phase 3's output) ONLY — no live Morning API call, and NEVER writes anything
under --ledger-dir (strictly read-only, REQ-BACKFILL-010). Produces a report with three checks
(data-model.md entity 4):

- Document-count reconciliation: matches raw documents to LedgerEvents by
  accounting_document_display_number — NOT by the raw document's own `id` (internal Morning id),
  which is dropped entirely between Stage 2 (format_invoice_json) and Stage 3
  (_expand_accounting_document_json) and never appears on a persisted LedgerEvent at all.
- Surfaced anomalies: read from LedgerEventManager's own pending_review.json, which lives at
  ledger_dir.parent/"accounting_reconciliation"/pending_review.json — a SIBLING of --ledger-dir,
  not nested inside it (confirmed directly against _append_pending_review's real source).
- Sampled field-level comparison: reuses method_a.transform() as a deterministic ground-truth
  oracle (Method A is pure code, so it can recompute "what should this LedgerEvent look like"
  regardless of which method Phase 3 actually used to produce the real file) and
  select_method.diff_ledger_events() for the comparison itself — no new mapping/diff logic here.

Sign-off itself is a separate mode (--approve --report-in <path> --signed-by <name>), never
automatic and never inferred from the report simply existing.

See contracts/cli-contract.md for the full CLI contract.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

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
from select_method import diff_ledger_events

from _ledger_event_manager_loader import get_ledger_event_manager_class  # noqa: F401 (loader
# import kept for consistency with transform.py/select_method.py's import style; not otherwise
# used here, since anomalies are read as a plain file, not via a LedgerEventManager instance)

_DEFAULT_SAMPLE_SIZE = 20


def build_arg_parser() -> argparse.ArgumentParser:
    """The normal-mode parser: read raw+ledger dirs, write a report."""
    parser = argparse.ArgumentParser(
        description="Phase 3.5 — validate Phase 3's output before Phase 4 is allowed to run."
    )
    parser.add_argument(
        "--raw-dir", required=True, help="The same --output-dir used for this window's download.py run.",
    )
    parser.add_argument(
        "--ledger-dir", required=True,
        help="The same --output-dir used for this window's transform.py run.",
    )
    parser.add_argument(
        "--report-out", required=True, help="Path for this window's validation report.",
    )
    parser.add_argument(
        "--sample-size", type=int, default=_DEFAULT_SAMPLE_SIZE,
        help=f"How many matched documents to field-compare (default: {_DEFAULT_SAMPLE_SIZE}).",
    )
    return parser


def build_approve_arg_parser() -> argparse.ArgumentParser:
    """The sign-off mode parser — separate from build_arg_parser() above, since argparse can't
    cleanly express "required only if --approve is set" on one shared parser."""
    parser = argparse.ArgumentParser(
        description="Phase 3.5 — sign off an existing validation report."
    )
    parser.add_argument("--approve", action="store_true", required=True)
    parser.add_argument("--report-in", required=True, help="Path to the report to sign off.")
    parser.add_argument("--signed-by", required=True, help="The human approver's name.")
    return parser


def load_raw_documents_by_display_number(raw_dir: Path) -> Dict[str, dict]:
    """Keys raw documents by str(document.get('number')) — the same field format_invoice_json
    reads as `display_number`, which is what a LedgerEvent's own
    accounting_document_display_number is ultimately derived from."""
    documents = {}
    for path in sorted(raw_dir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        number = doc.get("number")
        if number is not None:
            documents[str(number)] = doc
    return documents


def load_ledger_events_by_display_number(ledger_dir: Path) -> Dict[str, List[dict]]:
    """Keyed as a list per display number since an anomaly (same display number, two different
    timestamps) can legitimately produce more than one LedgerEvent for it — load_anomalies below
    is what surfaces that case, not this function refusing to represent it."""
    events: Dict[str, List[dict]] = {}
    for path in sorted(ledger_dir.glob("*.json")):
        event = json.loads(path.read_text(encoding="utf-8"))
        number = event.get("accounting_document_display_number")
        if number is not None:
            events.setdefault(str(number), []).append(event)
    return events


def reconcile_counts(raw_by_number: Dict[str, dict], ledger_by_number: Dict[str, List[dict]]) -> dict:
    raw_numbers = set(raw_by_number)
    ledger_numbers = set(ledger_by_number)
    missing = sorted(raw_numbers - ledger_numbers)
    extra = sorted(ledger_numbers - raw_numbers)
    return {
        "raw_document_count": len(raw_by_number),
        "ledger_event_count": sum(len(events) for events in ledger_by_number.values()),
        "missing_document_numbers": missing,
        "unexplained_extra_ledger_numbers": extra,
        "unexplained_discrepancy": bool(missing or extra),
    }


def load_anomalies(ledger_dir: Path) -> list:
    """Reads pending_review.json from its real location — a SIBLING of ledger_dir, not nested
    inside it (LedgerEventManager._append_pending_review: `self.storage_dir.parent /
    "accounting_reconciliation"`). Missing file (the common case: a clean window) is not an
    error — just no anomalies to report."""
    review_file = ledger_dir.parent / "accounting_reconciliation" / "pending_review.json"
    if not review_file.exists():
        return []
    try:
        return json.loads(review_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def sample_field_comparison(
    raw_by_number: Dict[str, dict], ledger_by_number: Dict[str, List[dict]], sample_size: int
) -> list:
    """
    For up to sample_size documents that DO have a corresponding LedgerEvent, recomputes the
    expected LedgerEvent via method_a.transform() (a deterministic ground-truth oracle,
    independent of whichever method Phase 3 actually used) and diffs it against the real
    persisted LedgerEvent via diff_ledger_events — reusing both already-tested functions rather
    than writing new comparison logic a second time.
    """
    common_numbers = sorted(set(raw_by_number) & set(ledger_by_number))
    results = []
    for number in common_numbers[:sample_size]:
        expected = method_a.transform(raw_by_number[number])
        actual = ledger_by_number[number][0]  # multiple-per-number is an anomaly, surfaced separately
        diff_result = diff_ledger_events(expected, actual)
        results.append({
            "display_number": number,
            "identical": diff_result["identical"],
            "differing_fields": diff_result["differing_fields"],
        })
    return results


def build_report(raw_dir: Path, ledger_dir: Path, sample_size: int) -> dict:
    raw_by_number = load_raw_documents_by_display_number(raw_dir)
    ledger_by_number = load_ledger_events_by_display_number(ledger_dir)
    return {
        "raw_dir": str(raw_dir),
        "ledger_dir": str(ledger_dir),
        "count_reconciliation": reconcile_counts(raw_by_number, ledger_by_number),
        "anomalies": load_anomalies(ledger_dir),
        "sampled_field_comparison": sample_field_comparison(raw_by_number, ledger_by_number, sample_size),
        "sign_off": {"signed": False, "signed_by": None, "signed_at": None},
    }


def _run_validate(argv) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    raw_dir = Path(args.raw_dir)
    ledger_dir = Path(args.ledger_dir)
    report_out = Path(args.report_out)

    report = build_report(raw_dir, ledger_dir, args.sample_size)

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    reconciliation = report["count_reconciliation"]
    mismatches = [item for item in report["sampled_field_comparison"] if not item["identical"]]
    print(
        f"Raw: {reconciliation['raw_document_count']}, "
        f"Ledger: {reconciliation['ledger_event_count']}, "
        f"discrepancy: {reconciliation['unexplained_discrepancy']}, "
        f"anomalies: {len(report['anomalies'])}, "
        f"sampled mismatches: {len(mismatches)}/{len(report['sampled_field_comparison'])}"
    )
    print(f"Report written to {report_out} — UNSIGNED. Review it, then run with --approve.")
    return 0


def _run_approve(argv) -> int:
    parser = build_approve_arg_parser()
    args = parser.parse_args(argv)

    report_path = Path(args.report_in)
    if not report_path.exists():
        print(f"⚠️ Report not found: {report_path}", file=sys.stderr)
        return 1

    from src.utils.time_utils import now_local  # local import: only needed for --approve

    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["sign_off"] = {
        "signed": True,
        "signed_by": args.signed_by,
        "signed_at": now_local().isoformat(),
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Signed off by {args.signed_by}: {report_path}")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--approve" in argv:
        return _run_approve(argv)
    return _run_validate(argv)


if __name__ == "__main__":
    sys.exit(main())
