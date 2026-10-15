"""One-time, human-run: builds the Agreements DB from a reviewed proposal file.

The proposal is a JSON list, written by hand after reading each client's comment (nothing here
parses a comment - comments are free text). Each item:

  {"client": "<client name>", "title": "הסכם 14.6.26", "agreement_date": "2026-06-14",
   "description": "<free text or null>", "status": "Active|Completed|Cancelled",
   "components": [{"label", "amount", "percent", "percent_base", "trigger_condition",
                   "vat_status" ("כולל" | "לא כולל" | omitted), "description",
                   "status": "Active|Pending|Completed|Cancelled"}]}

Writes go through denidin-app's Agreements API (DB first, then the usual `הסכם` ledger events;
actor "webapp"), so the target stack must be up. Idempotent: an agreement whose title already
exists for the client is left alone. The ledger takes 10 agreement events a minute, so the
script waits out `ledger_busy` answers. `--dry-run` prints what it would do and writes nothing.

Usage (from apps/webapp/backend, this clone's venv; never against prod without an explicit go-ahead):
  venv/bin/python scripts/build_agreements_from_proposal.py --config config/config.local.json \\
      --proposal proposal.json [--dry-run]
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND / "src") not in sys.path:
    sys.path.insert(0, str(_BACKEND / "src"))

from webapp_backend.agreements_client import AgreementsClient  # noqa: E402  pylint: disable=wrong-import-position

LEDGER_BUSY_WAIT_SECONDS = 65
_COMPONENT_FIELDS = ("label", "description", "amount", "percent", "percent_base", "trigger_condition", "vat_status")


def _call(client: AgreementsClient, method: str, path: str, *, params=None, body=None,
          sleep_fn: Callable[[float], None] = time.sleep, out: Callable[[str], None] = print):
    while True:
        status, data = client.request(method, path, params=params, body=body)
        if status == 503 and data.get("error", {}).get("code") == "ledger_busy":
            out(f"    ledger is busy, waiting {LEDGER_BUSY_WAIT_SECONDS}s ...")
            sleep_fn(LEDGER_BUSY_WAIT_SECONDS)
            continue
        return status, data


def build(client: AgreementsClient, proposal: List[Dict[str, Any]], *, dry_run: bool = False,
          out: Callable[[str], None] = print, sleep_fn: Callable[[float], None] = time.sleep) -> Dict[str, int]:
    counts = {"created": 0, "existing": 0, "failed": 0}
    for n, item in enumerate(proposal, 1):
        name, title = item["client"], item["title"]
        out(f"[{n}/{len(proposal)}] {name} | {title} | {item.get('agreement_date')} | {item.get('status', 'Active')}")
        status, data = _call(client, "GET", "/agreements", params={"client_name": name}, sleep_fn=sleep_fn, out=out)
        if status != 200:
            out(f"    FAILED reading agreements: {status} {data}")
            counts["failed"] += 1
            continue
        if any(a["title"] == title for a in data.get("agreements", [])):
            out("    already exists - left alone")
            counts["existing"] += 1
            continue
        if dry_run:
            continue
        body = {"client_name": name, "title": title, "agreement_description": item.get("description"),
                "agreement_date": item.get("agreement_date"),
                "components": [{k: c[k] for k in _COMPONENT_FIELDS if k in c} for c in item["components"]]}
        status, data = _call(client, "POST", "/agreements", body=body, sleep_fn=sleep_fn, out=out)
        if status != 200:
            out(f"    FAILED creating: {status} {data}")
            counts["failed"] += 1
            continue
        agreement = data["agreement"]
        agreement_id = agreement["agreement_id"]
        # Components first (only possible while the agreement is Active), the agreement's own status last.
        for wanted, created in zip(item["components"], agreement["components"]):
            target = wanted.get("status")
            if target and target != created["status"]:
                status, data = _call(client, "POST", f"/agreements/{agreement_id}/components/{created['component_key']}/status",
                                     body={"status": target}, sleep_fn=sleep_fn, out=out)
                if status != 200:
                    out(f"    FAILED setting component {created['label']!r} to {target}: {status} {data}")
                    counts["failed"] += 1
        target = item.get("status", "Active")
        if target != "Active":
            status, data = _call(client, "POST", f"/agreements/{agreement_id}/status", body={"status": target},
                                 sleep_fn=sleep_fn, out=out)
            if status != 200:
                out(f"    FAILED setting agreement to {target}: {status} {data}")
                counts["failed"] += 1
        out(f"    created {agreement_id}")
        counts["created"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path, help="webapp backend config (Agreements API url/token)")
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    client = AgreementsClient(config["denidin_agreements_url"], config["denidin_agreements_token"])
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    print(f"\nDone: {build(client, proposal, dry_run=args.dry_run)}")


if __name__ == "__main__":
    main()
