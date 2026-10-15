"""Feature 089 - OFFLINE builder: turns a reviewed proposal into a ready-to-copy Agreements DB plus its
`הסכם` ledger events, in a STAGING folder. It never touches a dev or prod data root.

The proposal is the JSON list written by hand after reading each client's comment (same shape as
`apps/webapp/backend/scripts/build_agreements_from_proposal.py`):

  [{"client", "title", "agreement_date" (YYYY-MM-DD), "description", "status" (Active|Completed|Cancelled),
    "components": [{"label", "amount", "percent", "percent_base", "trigger_condition",
                    "vat_status", "description", "status" (Active|Pending|Completed|Cancelled)}]}]

Output (under --out):
  agreements/agreements.db     the Agreements DB
  events/*.json                the `הסכם` ledger events it wrote

Release-day rehearsal (dev first, then prod): stop the environment, copy those two into its data root
(`agreements/agreements.db` and the files in `events/`), start the environment. The builder refuses an
--out folder that already holds an agreements DB.

Ledger events carry the agreement's own date (not today): every write is given a message_timestamp on
the agreement date, spread over distinct minutes so the ledger's 10-events-a-minute cap is never hit.

Usage (from apps/denidin-app, this clone's venv):
  venv/bin/python3 scripts/build_agreements_staging_089.py --proposal prod_decided.json --out staging_prod [--dry-run]
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.managers.agreements_manager import AgreementsManager, ValidationError  # noqa: E402  pylint: disable=wrong-import-position
from src.managers.ledger_event_manager import LedgerEventManager  # noqa: E402  pylint: disable=wrong-import-position
from src.utils.time_utils import to_local  # noqa: E402  pylint: disable=wrong-import-position

_COMPONENT_FIELDS = ("label", "description", "amount", "percent", "percent_base", "trigger_condition", "vat_status")
_FIRST_MINUTE_OF_DAY = 8 * 60  # events of a day start at 08:00 local
_EVENTS_PER_MINUTE = 10


class _MinuteAllocator:
    """Hands out message timestamps on a given date, one fresh minute per write (each write emits
    at most `_EVENTS_PER_MINUTE` events), so the per-minute cap is never reached."""

    def __init__(self) -> None:
        self._next: Dict[str, int] = defaultdict(lambda: _FIRST_MINUTE_OF_DAY)

    def next_timestamp(self, day: str) -> int:
        minute = self._next[day]
        self._next[day] += 1
        if minute >= 24 * 60:
            raise SystemExit(f"too many agreement writes on {day} to give each its own minute")
        base = to_local(datetime.strptime(day, "%Y-%m-%d"))
        return int(base.timestamp()) + minute * 60


def build(proposal: List[Dict[str, Any]], out_root: Path) -> Dict[str, int]:
    app = SimpleNamespace(config=SimpleNamespace(data_root=str(out_root)), ledger_event_manager=None,
                          session_manager=None)
    app.ledger_event_manager = LedgerEventManager(app)
    manager = AgreementsManager(app)
    minutes = _MinuteAllocator()
    counts = {"agreements": 0, "components": 0, "rejected": 0}
    for n, item in enumerate(proposal, 1):
        day = str(item["agreement_date"])[:10]
        components = [{k: c[k] for k in _COMPONENT_FIELDS if k in c} for c in item["components"]]
        try:
            agreement, _ = manager.create_agreement(
                client_name=item["client"], title=item["title"], components=components, actor="migration",
                agreement_description=item.get("description"), agreement_date=day,
                message_timestamp=minutes.next_timestamp(day))
        except ValidationError as exc:
            print(f"[{n}/{len(proposal)}] REJECTED {item['client']} | {item['title']}: {exc.message} {exc.fields}")
            counts["rejected"] += 1
            continue
        agreement_id = agreement["agreement_id"]
        # Components first (only possible while the agreement is Active), the agreement's own status last.
        for wanted, created in zip(item["components"], agreement["components"]):
            target = wanted.get("status")
            if target and target != created["status"]:
                manager.set_component_status_to(agreement_id, created["component_key"], target, "migration",
                                                message_timestamp=minutes.next_timestamp(day))
        target = item.get("status", "Active")
        if target != "Active":
            manager.set_agreement_status_to(agreement_id, target, "migration",
                                            message_timestamp=minutes.next_timestamp(day))
        counts["agreements"] += 1
        counts["components"] += len(components)
        print(f"[{n}/{len(proposal)}] {item['client']} | {item['title']} | {day} | {target}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="staging folder (must not hold an agreements DB yet)")
    parser.add_argument("--append", action="store_true",
                        help="add to a staging folder that already holds the migrated DB + events")
    args = parser.parse_args()
    if not args.append and (args.out / "agreements" / "agreements.db").exists():
        raise SystemExit(f"{args.out} already holds an agreements DB - refusing to build into it")
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    counts = build(proposal, args.out)
    events = len(list((args.out / "events").glob("*.json")))
    print(f"\nDone: {counts}, ledger events written: {events}\nStaging folder: {args.out}")


if __name__ == "__main__":
    main()
