#!/usr/bin/env python3
"""Copy the 595 validated/signed-off LedgerEvent files (Feature 062, prod backfill,
--since 2025-09-01) into prod's real events/ folder, via the temporary rw sshfs mount.
Approved 2026-09-01. Mirrors specs/done/v0.5.4/065-august-ledger-audit-apply/scripts/
apply_type1_add_new_to_prod.py's structure (plain byte-for-byte copy of already-
reviewed files - no LedgerEventManager re-invocation here, so no risk of re-deriving
different event_ids/timestamps than what was already validated and signed).

RESUMABLE (added after a real mid-run sshfs disconnect, 2026-09-01 - same failure
mode spec 065 documented: "the rw mount was found to have silently died mid-run
once"). For each source file:
  - dest missing -> copy fresh, then verify round-trip
  - dest present AND byte-identical to source -> already applied by a prior partial
    run, skip (not an error)
  - dest present AND differs from source -> real conflict, ABORT (never overwrite
    silently)

Defensive checks before any write:
  - accounting_document_display_number dedup: none of the 595 target numbers may
    already be present on any PRE-EXISTING prod event (i.e. one NOT itself part of
    this same backfill's own filenames) - checked fresh each run.
"""
import json
import shutil
from pathlib import Path

SRC = Path("/Users/yaron/Projects/DeniDin/coder1/apps/prod-ledger-backfill/ledger_events/prod_backfill_sep2025")
DEST = Path.home() / "denidin-winprod-data-rw" / "events"


def main():
    src_files = sorted(SRC.glob("*.json"))
    src_names = {f.name for f in src_files}
    print(f"Source: {len(src_files)} ledger event files.")

    dest_before = list(DEST.glob("*.json"))
    print(f"Prod events/ current count (pre-run): {len(dest_before)}")

    # Display-number dedup check against PRE-EXISTING prod events only (i.e.
    # events not part of this backfill's own filename set - excludes anything
    # a prior partial run of this same script already wrote).
    prod_display_numbers = set()
    for f in dest_before:
        if f.name in src_names:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"WARNING: could not parse existing prod file {f.name}: {e}")
            continue
        n = d.get("accounting_document_display_number")
        if n:
            prod_display_numbers.add(str(n))

    our_numbers = set()
    for f in src_files:
        d = json.loads(f.read_text(encoding="utf-8"))
        n = d.get("accounting_document_display_number")
        if n:
            our_numbers.add(str(n))

    overlap = our_numbers & prod_display_numbers
    if overlap:
        print(f"ABORT: {len(overlap)} accounting_document_display_number(s) already present in prod:")
        for n in sorted(overlap):
            print(f"    {n}")
        return

    print("Dedup pre-flight clean. Copying (resumable)...")

    already_applied = []
    freshly_copied = []
    conflicts = []

    for f in src_files:
        dst = DEST / f.name
        original = json.loads(f.read_text(encoding="utf-8"))

        if dst.exists():
            try:
                existing = json.loads(dst.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                conflicts.append((f.name, f"existing dest unreadable: {e}"))
                continue
            if existing == original:
                already_applied.append(f.name)
                continue
            conflicts.append((f.name, "existing dest content differs from source"))
            continue

        shutil.copyfile(f, dst)
        # Verify immediately (real remote read-back, not just an assumption)
        round_trip = json.loads(dst.read_text(encoding="utf-8"))
        if round_trip == original:
            freshly_copied.append(f.name)
        else:
            conflicts.append((f.name, "post-copy round-trip mismatch"))

    print(f"\nAlready applied (skipped, byte-identical): {len(already_applied)}")
    print(f"Freshly copied + verified this run: {len(freshly_copied)}")
    print(f"Conflicts (investigate!): {len(conflicts)}")
    for name, reason in conflicts:
        print(f"    {name}: {reason}")

    total_prod_now = len(list(DEST.glob("*.json")))
    print(f"\nprod events/ now contains {total_prod_now} .json files total.")
    print(f"Total of our 595 accounted for (already_applied + freshly_copied): "
          f"{len(already_applied) + len(freshly_copied)} / {len(src_files)}")


if __name__ == "__main__":
    main()
