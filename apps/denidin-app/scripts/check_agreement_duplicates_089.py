#!/usr/bin/env python3
"""Feature 089 - READ-ONLY census of duplicate component labels in an events directory.

Writes nothing, creates nothing, touches no DB. Reuses the migration's own pure planning step
(`plan`) with an empty name resolution so the answer is exactly what the migration would hit.

    python3 scripts/check_agreement_duplicates_089.py ~/denidin-winprod-data/events
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import migrate_agreements_089 as mig  # noqa: E402


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 1
    events = mig._load_events(Path(argv[1]).expanduser())
    result = mig.plan(events, {})
    agreements = result["agreements"]
    print(f"agreement events scanned : {sum(1 for _, e in events if e.get('source_type') == 'הסכם')}")
    print(f"agreements the migration would create : {len(agreements)}")
    print(f"agreements with duplicate labels      : {len(result['duplicates'])}")
    for dup in result["duplicates"]:
        group = agreements[dup["agreement_id"]]
        print(f"\n== {dup['agreement_id']}  client={group['client_name']!r}")
        by_label = defaultdict(list)
        for comp in group["components"]:
            by_label[mig._slugify(comp["label"])].append(comp)
        for label in dup["labels"]:
            for comp in by_label[label]:
                print(f"   label={comp['label']!r} amount={comp['amount']} percent={comp['percent']} "
                      f"status={comp['status']} event={comp['origin_event_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
