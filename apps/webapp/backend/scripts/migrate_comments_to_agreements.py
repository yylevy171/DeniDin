"""One-time, human-run migration: agreements written in Clients-tab comments -> the Agreements DB.

The Clients tab used to read `הסכם <date> <amount>` / `סה״כ הסכמים <amount>` out of free-text comments
to override a client's agreed total. That parsing is gone (agreements live in the Agreements DB), so
this script walks every comment that defines an agreement, ONE CLIENT AT A TIME, proposes the
agreements it reads, and creates only what you confirm - comments are often unclear, so nothing is
created without you.

Per clause you choose: [a]ccept (create as proposed), [e]dit (type title / label / amount /
description), [s]kip, [q]uit (resume later - decisions are saved in --state). A clause whose amount
already exists on one of the client's agreements (any status) is flagged DUPLICATE and defaults to skip.

Writes go through denidin-app's Agreements API (DB first, then the usual `הסכם` ledger events;
actor "webapp"), so the dev/prod stack must be up. Nothing under --clients-dir is modified.

Usage (from apps/webapp/backend, this clone's venv; never against prod without an explicit go-ahead):
  venv/bin/python scripts/migrate_comments_to_agreements.py \\
      --clients-dir <webapp_data/clients> --config config/config.dev.json \\
      --state comment_agreements_state.json [--client "<name>"] [--dry-run]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND / "src") not in sys.path:
    sys.path.insert(0, str(_BACKEND / "src"))

from webapp_backend.agreements_client import AgreementsClient  # noqa: E402  pylint: disable=wrong-import-position

LEDGER_BUSY_WAIT_SECONDS = 65
_CLAUSE = re.compile(
    r"הסכם\s+(?:(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\s*)?(?:-\s*)?([1-9][\d,+]{2,})")
_TOTAL = re.compile(r"סה[״\"']כ הסכמים\s*(?:-\s*)?([1-9][\d,]*)")


def _to_number(text: str) -> int:
    return int(text.replace(",", "").strip())


def parse_comment(comment: str) -> Dict[str, Any]:
    """Reads the `הסכם …` clauses of one comment. Returns {"clauses": [...], "stated_total": int|None}.
    Each clause: date_text (as written, may lack a year), amount (int), parts (list of ints when written
    `a+b`), text (the words after the amount up to `;`/newline)."""
    clauses: List[Dict[str, Any]] = []
    last_year: Optional[str] = None
    for m in _CLAUSE.finditer(comment):
        day, month, year, amount_text = m.groups()
        parts = [_to_number(p) for p in amount_text.rstrip(",.").split("+") if p.replace(",", "").strip()]
        if not parts or sum(parts) <= 0:
            continue
        if year:
            last_year = year
        date_text = None
        if day:
            date_text = f"{day}.{month}" + (f".{year}" if year else (f".{last_year}" if last_year else ""))
        rest = comment[m.end():]
        text = re.split(r"[;\n]|הסכם\s", rest, maxsplit=1)[0].strip(" ,.-")
        # the chat-pasted tail ("10/15/24, 19:17 - אילה: …") is noise, not a description
        text = re.sub(r"^\d{1,2}/\d{1,2}/\d{2,4},?\s*\d{1,2}:\d{2}\s*-\s*", "", text).strip(" ,.-")
        clauses.append({"date_text": date_text, "amount": sum(parts), "parts": parts, "text": text})
    total = _TOTAL.search(comment)
    return {"clauses": clauses, "stated_total": _to_number(total.group(1)) if total else None}


def existing_amounts(agreements: List[Dict[str, Any]]) -> Dict[int, str]:
    """amount -> 'agreement title / component label' for every component (any status) of the client."""
    found: Dict[int, str] = {}
    for agreement in agreements:
        for component in agreement.get("components", []):
            if component.get("amount") is not None:
                found.setdefault(int(component["amount"]), f"{agreement.get('title')} / {component.get('label')}")
    return found


def propose(clause: Dict[str, Any], index: int, taken_titles: set) -> Dict[str, Any]:
    base = f"הסכם {clause['date_text']}" if clause["date_text"] else f"הסכם מהערה {index + 1}"
    title, n = base, 2
    while title in taken_titles:
        title, n = f"{base} ({n})", n + 1
    label = (clause["text"] or "שכר טרחה")[:60]
    return {"title": title, "label": label, "amount": clause["amount"], "description": clause["text"] or None}


def _create_body(client: str, proposal: Dict[str, Any], source_comment: str) -> Dict[str, Any]:
    return {
        "client_name": client, "title": proposal["title"],
        "agreement_description": "נוצר מהערת הלקוח: " + source_comment[:300],
        "components": [{"label": proposal["label"], "amount": proposal["amount"],
                        "description": proposal["description"]}],
    }


def _load_state(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save_state(path: Path, state: Dict[str, Any]) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _ask_edit(proposal: Dict[str, Any], input_fn: Callable[[str], str]) -> Dict[str, Any]:
    edited = dict(proposal)
    for key, label in (("title", "title"), ("label", "component label"), ("amount", "amount"),
                       ("description", "description")):
        answer = input_fn(f"  {label} [{edited[key] if edited[key] is not None else ''}]: ").strip()
        if answer:
            edited[key] = _to_number(answer) if key == "amount" else answer
    return edited


def run(clients_dir: Path, client: AgreementsClient, state_path: Path, *, only: Optional[str] = None,
        dry_run: bool = False, input_fn: Callable[[str], str] = input, out: Callable[[str], None] = print,
        sleep_fn: Callable[[float], None] = time.sleep) -> Dict[str, int]:
    """Walks the comments. Returns counters {"created": n, "skipped": n, "duplicates": n, "quit": 0|1}."""
    comments = json.loads((Path(clients_dir) / "client_comments.json").read_text(encoding="utf-8"))
    state = _load_state(state_path)
    counts = {"created": 0, "skipped": 0, "duplicates": 0, "quit": 0}
    for name, comment in comments.items():
        if only and name != only:
            continue
        parsed = parse_comment(comment or "")
        if not parsed["clauses"] and "הסכם" not in (comment or ""):
            continue
        done = state.setdefault(name, {})
        status, data = client.request("GET", "/agreements", params={"client_name": name})
        if status != 200:
            raise RuntimeError(f"could not read agreements of {name!r}: {status} {data}")
        agreements = data.get("agreements", [])
        out(f"\n=== {name}\n  comment: {comment}")
        if parsed["stated_total"] is not None:
            out(f"  stated total in the comment: {parsed['stated_total']:,}")
        out("  existing agreements: " + (", ".join(
            f"{a['title']} ({a['status']})" for a in agreements) or "none"))
        if not parsed["clauses"]:
            out("  (mentions הסכם but no amount could be read - handle by hand in the UI)")
            continue
        taken = {a["title"] for a in agreements}
        for index, clause in enumerate(parsed["clauses"]):
            key = str(index)
            if key in done:
                continue
            proposal = propose(clause, index, taken)
            same = existing_amounts(agreements).get(clause["amount"])
            out(f"  [{index + 1}/{len(parsed['clauses'])}] {proposal['title']} | {proposal['label']} | "
                f"{proposal['amount']:,}" + (f"   <-- DUPLICATE of {same}" if same else ""))
            if dry_run:
                continue
            default = "s" if same else "a"
            while True:
                choice = (input_fn(f"  [a]ccept [e]dit [s]kip [q]uit (default {default}): ").strip().lower()
                          or default)
                if choice in ("a", "e", "s", "q"):
                    break
            if choice == "q":
                _save_state(state_path, state)
                counts["quit"] = 1
                return counts
            if choice == "s":
                done[key] = "skipped"
                counts["skipped"] += 1
                counts["duplicates"] += 1 if same else 0
                _save_state(state_path, state)
                continue
            if choice == "e":
                proposal = _ask_edit(proposal, input_fn)
            body = _create_body(name, proposal, comment)
            while True:
                status, data = client.request("POST", "/agreements", body=body)
                if status == 503 and data.get("error", {}).get("code") == "ledger_busy":
                    out(f"  ledger is busy, waiting {LEDGER_BUSY_WAIT_SECONDS}s ...")
                    sleep_fn(LEDGER_BUSY_WAIT_SECONDS)
                    continue
                break
            if status != 200:
                out(f"  FAILED ({status}): {data}  - left undecided, rerun to retry")
                continue
            created = data["agreement"]
            agreements.append(created)
            taken.add(created["title"])
            done[key] = f"created:{created['agreement_id']}"
            counts["created"] += 1
            _save_state(state_path, state)
            out(f"  created {created['agreement_id']}")
    _save_state(state_path, state)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clients-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path, help="webapp backend config (Agreements API url/token)")
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--client", help="only this client")
    parser.add_argument("--dry-run", action="store_true", help="print proposals, ask nothing, write nothing")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    client = AgreementsClient(config["denidin_agreements_url"], config["denidin_agreements_token"])
    counts = run(args.clients_dir, client, args.state, only=args.client, dry_run=args.dry_run)
    print(f"\nDone: {counts}")


if __name__ == "__main__":
    main()
