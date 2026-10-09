"""Feature 089 (REQ-089-09..12) - ONE-TIME migration of the ledger's fee agreements into the
Agreements DB, with a one-time rewrite of those events to ledger schema v4.

Inputs: the app's data root (`{data_root}/events/*.json`) and the Clients-tab hand-off file written
by `apps/webapp/backend/scripts/export_name_resolution.py` (`--resolution`).

What it does, in order:
  1. refuses to run again once `{data_root}/agreements/migration_089.json` exists (no-op);
  2. selects agreement-component events: source_type `הסכם`, no `hours` (hours-worked lines,
     bank and invoice events are never read as components and never rewritten);
  3. groups them into agreements by `agreement_id`; legacy `מבוטל`/`ביטול` events mark the
     component they refer to (same agreement + component label) Cancelled instead of being one;
  4. status: a client whose Clients-tab line is closed gets Completed (paid >= agreed) or
     Cancelled (otherwise) on the agreement and on every component not already Cancelled;
     everyone else gets the normal defaults (trigger -> Pending, else Active);
  5. before anything is rewritten, copies every event file it will rewrite to
     `{data_root}/agreements/migration_089_backup_<timestamp>/`;
  6. creates the DB rows (actor `migration`, no new ledger events) and rewrites the events in
     place (event_id kept, so `reference` links hold): `client_name` = official name when
     resolved, `original_client_name` = the old name, `component_status`/`agreement_status`,
     `schema_version` = the current one;
  7. writes the marker.

`--dry-run` prints the same counts and writes nothing. Duplicate component labels inside one
agreement are not allowed by the DB; the script LISTS them and refuses to migrate until a
human decides how they are handled (it never merges or renames on its own).

Usage (from apps/denidin-app, this clone's venv):
  venv/bin/python3 scripts/migrate_agreements_089.py --data-root <data root> \
      --resolution name_resolution.json [--dry-run]
"""
import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.managers.agreements_manager import (  # noqa: E402  pylint: disable=wrong-import-position
    ACTIVE, CANCELLED, COMPLETED, PENDING, AgreementsManager, ValidationError,
)
from src.managers.ledger_event_manager import (  # noqa: E402  pylint: disable=wrong-import-position
    CURRENT_SCHEMA_VERSION, _slugify,
)
from src.utils.time_utils import now_local  # noqa: E402  pylint: disable=wrong-import-position

MARKER_NAME = "migration_089.json"
_CANCEL_SUBTYPES = ("מבוטל", "ביטול")


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _load_events(events_dir: Path) -> List[Tuple[Path, Dict[str, Any]]]:
    out = []
    for path in sorted(events_dir.glob("*.json")):
        try:
            out.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            print(f"WARNING: unreadable event file skipped: {path.name}", file=sys.stderr)
    return out


def _raw_name(event: Dict[str, Any]) -> str:
    return str(event.get("client_name") or event.get("payer_name") or "").strip()


def _agreement_key(event: Dict[str, Any]) -> str:
    if not _is_blank(event.get("agreement_id")):
        return str(event["agreement_id"])
    month = str(event.get("event_datetime") or "")[2:4] + str(event.get("event_datetime") or "")[5:7]
    return f"{month}-{_slugify(_raw_name(event))}-legacy"


def _client_line(resolution: Dict[str, Any], raw: str) -> Dict[str, Any]:
    return resolution.get("clients", {}).get(raw) or {"official_name": None, "line_closed": False}


def _closed_status(line: Dict[str, Any]) -> str:
    agreed, paid = line.get("agreed"), line.get("paid")
    return COMPLETED if (agreed is not None and paid is not None and paid >= agreed) else CANCELLED


def plan(events: List[Tuple[Path, Dict[str, Any]]], resolution: Dict[str, Any]) -> Dict[str, Any]:
    """Pure planning step: what would be created / rewritten / refused."""
    agreements: Dict[str, Dict[str, Any]] = {}
    cancellations: List[Dict[str, Any]] = []
    rewrite: Dict[Path, Dict[str, Any]] = {}
    for path, event in events:
        if event.get("source_type") != "הסכם" or not _is_blank(event.get("hours")):
            continue
        raw = _raw_name(event)
        line = _client_line(resolution, raw)
        official = line.get("official_name") or raw
        key = _agreement_key(event)
        group = agreements.setdefault(key, {
            "agreement_id": key, "raw_names": set(), "client_name": official, "payer_name": event.get("payer_name"),
            "partner_name": None, "partner_percent": None, "line": line, "components": [],
        })
        group["raw_names"].add(raw)
        if group["partner_name"] is None and not _is_blank(event.get("split_partner")):
            group["partner_name"], group["partner_percent"] = event.get("split_partner"), event.get("split_percent")
        rewrite[path] = {"event": event, "raw": raw, "official": official, "agreement_id": key}
        if event.get("event_subtype") in _CANCEL_SUBTYPES:
            cancellations.append({"agreement_id": key, "label": event.get("component_label"),
                                  "description": event.get("description")})
            continue
        group["components"].append({
            "label": event.get("component_label") or event.get("description") or f"רכיב {len(group['components']) + 1}",
            "description": event.get("description"), "amount": event.get("amount"), "percent": event.get("percent"),
            "percent_base": event.get("percent_base"), "trigger_condition": event.get("trigger_condition"),
            "vat_status": event.get("vat_status"), "txn_date": event.get("txn_date"),
            "origin_event_id": event.get("event_id"),
            "status": PENDING if not _is_blank(event.get("trigger_condition")) else ACTIVE,
        })
    for cancel in cancellations:
        for component in agreements.get(cancel["agreement_id"], {}).get("components", []):
            if component["label"] == cancel["label"] or (
                    _is_blank(cancel["label"]) and component["description"] == cancel["description"]):
                component["status"] = CANCELLED
    duplicates: List[Dict[str, Any]] = []
    for key, group in list(agreements.items()):
        if not group["components"]:
            del agreements[key]  # only cancellation events: nothing to create
            continue
        labels = defaultdict(int)
        for component in group["components"]:
            labels[_slugify(component["label"])] += 1
        dup = sorted(label for label, count in labels.items() if count > 1)
        if dup:
            duplicates.append({"agreement_id": key, "labels": dup})
        if group["line"].get("line_closed"):
            closed = _closed_status(group["line"])
            group["status"] = closed
            for component in group["components"]:
                if component["status"] != CANCELLED:
                    component["status"] = closed
        else:
            group["status"] = ACTIVE
    return {"agreements": agreements, "rewrite": rewrite, "duplicates": duplicates,
            "unresolved": sorted({r for g in agreements.values() for r in g["raw_names"]
                                  if not _client_line(resolution, r).get("official_name")})}


def _title_of(group: Dict[str, Any]) -> str:
    parts = group["agreement_id"].split("-", 2)
    return parts[2].replace("_", " ") if len(parts) == 3 and parts[2] else group["agreement_id"]


def migrate(data_root: Path, resolution_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    data_root = Path(data_root)
    marker = data_root / "agreements" / MARKER_NAME
    if marker.exists():
        return {"status": "already_migrated", "marker": str(marker)}
    resolution = json.loads(Path(resolution_path).read_text(encoding="utf-8"))
    result = plan(_load_events(data_root / "events"), resolution)
    report: Dict[str, Any] = {
        "agreements": len(result["agreements"]),
        "components": sum(len(g["components"]) for g in result["agreements"].values()),
        "events_rewritten": len(result["rewrite"]),
        "status_counts": _counts(result["agreements"]),
        "unresolved_names": result["unresolved"],
        "duplicate_labels": result["duplicates"],
        "dry_run": dry_run,
    }
    if result["duplicates"]:
        report["status"] = "blocked_duplicate_labels"
        return report
    if dry_run:
        report["status"] = "dry_run"
        return report

    stamp = now_local().strftime("%Y%m%d_%H%M%S")
    backup = data_root / "agreements" / f"migration_089_backup_{stamp}"
    backup.mkdir(parents=True)
    for path in result["rewrite"]:
        shutil.copy2(path, backup / path.name)
    manager = AgreementsManager(SimpleNamespace(config=SimpleNamespace(data_root=str(data_root))))
    for group in result["agreements"].values():
        try:
            manager.import_migrated_agreement(
                agreement_id=group["agreement_id"], title=_title_of(group), client_name=group["client_name"],
                payer_name=group["payer_name"], partner_name=group["partner_name"],
                partner_percent=group["partner_percent"], status=group["status"], components=group["components"])
        except ValidationError as exc:
            raise SystemExit(f"cannot migrate agreement {group['agreement_id']!r}: {exc.message} {exc.fields}") from exc
    for path, info in result["rewrite"].items():
        event = info["event"]
        group = result["agreements"].get(info["agreement_id"])
        event["original_client_name"] = info["raw"]
        event["client_name"] = info["official"]
        event["agreement_status"] = group["status"] if group else None
        event["component_status"] = _component_status_of(group, event)
        event["schema_version"] = CURRENT_SCHEMA_VERSION
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(event, sort_keys=True, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    marker.write_text(json.dumps({"migrated_at": now_local().isoformat(), "backup": backup.name, **{
        k: report[k] for k in ("agreements", "components", "events_rewritten")}}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    report["status"] = "migrated"
    report["backup"] = str(backup)
    return report


def _component_status_of(group: Optional[Dict[str, Any]], event: Dict[str, Any]) -> Optional[str]:
    if group is None:
        return None
    for component in group["components"]:
        if component["origin_event_id"] == event.get("event_id"):
            return component["status"]
    return CANCELLED if event.get("event_subtype") in _CANCEL_SUBTYPES else None


def _counts(agreements: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for group in agreements.values():
        for component in group["components"]:
            counts[component["status"]] += 1
    return dict(counts)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--resolution", required=True, help="name_resolution.json from export_name_resolution.py")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    report = migrate(Path(args.data_root), Path(args.resolution), args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked_duplicate_labels" else 0


if __name__ == "__main__":
    sys.exit(main())
