"""Feature 089 (REQ-089-09..12) - ONE-TIME migration of the ledger's fee agreements into the
Agreements DB, with a one-time rewrite of those events (current ledger schema).

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
agreement are not allowed by the DB, so events sharing a label are MERGED into one component
(human decision 2026-10-11): the latest event's values win, a field the latest leaves empty is
filled from earlier ones, `origin_event_id` is the earliest event, the latest event's status
stands. Every merge is listed in the report (`merged_duplicates`); every contributing event is
still rewritten in place and carries the merged component's status.

Usage (from apps/denidin-app, this clone's venv):
  venv/bin/python3 scripts/migrate_agreements_089.py --data-root <data root> \
      --resolution name_resolution.json [--dry-run]
"""
import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime
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
from src.utils.time_utils import now_local, to_local  # noqa: E402  pylint: disable=wrong-import-position

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


def _event_time(event: Dict[str, Any]) -> datetime:
    """The event's own time, Israel local, naive: `event_datetime` (`DD/MM/YYYY HH:MM`, or ISO), else its
    `message_timestamp` (ISO), else the date/time inside its event id (letter + DDMMYY + HHMM + seq);
    `datetime.min` if none parses."""
    try:
        return datetime.strptime(str(event.get("event_datetime") or ""), "%d/%m/%Y %H:%M")
    except ValueError:
        pass
    for field in ("event_datetime", "message_timestamp"):
        try:
            return to_local(datetime.fromisoformat(str(event.get(field)))).replace(tzinfo=None)
        except ValueError:
            continue
    try:
        return datetime.strptime(str(event.get("event_id") or "")[1:11], "%d%m%y%H%M")
    except ValueError:
        return datetime.min


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
    for path, event in sorted(events, key=lambda pe: (_event_time(pe[1]), pe[0].name)):
        if event.get("source_type") != "הסכם" or not _is_blank(event.get("hours")):
            continue
        raw = _raw_name(event)
        line = _client_line(resolution, raw)
        official = line.get("official_name") or raw
        key = _agreement_key(event)
        group = agreements.setdefault(key, {
            "agreement_id": key, "raw_names": set(), "client_name": official, "payer_name": event.get("payer_name"),
            "partner_name": None, "partner_percent": None, "line": line, "components": [],
            "created_at": _event_time(event),  # events are visited oldest first: the agreement's own date
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
            "vat_status": None if event.get("vat_status") == "לא צוין" else event.get("vat_status"),
            "txn_date": event.get("txn_date"),
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
        merged = _merge_duplicate_labels(group)
        if merged:
            duplicates.append({"agreement_id": key, "labels": sorted(merged)})
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


_MERGE_FIELDS = ("description", "amount", "percent", "percent_base", "trigger_condition", "vat_status", "txn_date")


def _merge_duplicate_labels(group: Dict[str, Any]) -> List[str]:
    """Collapses components that share a label (slug) into one; returns the merged slugs.
    Components arrive in event order (oldest first by `event_datetime`, then event id)."""
    by_slug: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for component in group["components"]:
        by_slug[_slugify(component["label"])].append(component)
    merged_slugs = sorted(slug for slug, comps in by_slug.items() if len(comps) > 1)
    if not merged_slugs:
        return []
    group["merged_events"] = {}
    result: List[Dict[str, Any]] = []
    for component in group["components"]:
        slug = _slugify(component["label"])
        comps = by_slug[slug]
        if len(comps) == 1:
            result.append(component)
            continue
        if component is not comps[-1]:
            continue  # emitted once, at the position of the latest event
        survivor = dict(comps[-1])
        for field in _MERGE_FIELDS:
            if _is_blank(survivor.get(field)):
                for earlier in reversed(comps[:-1]):
                    if not _is_blank(earlier.get(field)):
                        survivor[field] = earlier[field]
                        break
        survivor["origin_event_id"] = comps[0]["origin_event_id"]
        for member in comps:
            group["merged_events"][member["origin_event_id"]] = slug
        result.append(survivor)
    group["components"] = result
    return merged_slugs


def _title_of(group: Dict[str, Any]) -> str:
    parts = group["agreement_id"].split("-", 2)
    return parts[2].replace("_", " ") if len(parts) == 3 and parts[2] else group["agreement_id"]


def _apply_decisions(result: Dict[str, Any], decisions: Dict[str, Any]) -> None:
    """Human decisions (2026-10-15, from reviewing ledger-vs-comment conflicts):
    `skip_agreement_ids` - ledger agreements a client's comment replaces: not created, and their ledger
    events are left exactly as they are; `component_status` - [{agreement_id, label, status}] overrides."""
    skip = set(decisions.get("skip_agreement_ids", []))
    unknown = skip - set(result["agreements"])
    if unknown:
        raise SystemExit(f"skip_agreement_ids not found in the ledger plan: {sorted(unknown)}")
    for key in skip:
        del result["agreements"][key]
    for path in [p for p, info in result["rewrite"].items() if info["agreement_id"] in skip]:
        del result["rewrite"][path]
    for change in decisions.get("component_status", []):
        group = result["agreements"].get(change["agreement_id"])
        match = [c for c in (group or {}).get("components", []) if c["label"] == change["label"]]
        if not match or change["status"] not in (ACTIVE, PENDING, COMPLETED, CANCELLED):
            raise SystemExit(f"bad component_status decision: {change}")
        match[0]["status"] = change["status"]


def _drop_unresolved_clients(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Human decision 2026-10-15: no DB entry without a KNOWN Morning client. An agreement whose client
    name does not resolve to an official client is not created, and its ledger events are left exactly
    as they are. Returns what was skipped, for the report."""
    skipped = []
    for key in [k for k, g in result["agreements"].items() if not g["line"].get("official_name")]:
        group = result["agreements"].pop(key)
        skipped.append({"agreement_id": key, "raw_names": sorted(group["raw_names"]),
                        "components": len(group["components"])})
        for path in [p for p, info in result["rewrite"].items() if info["agreement_id"] == key]:
            del result["rewrite"][path]
    return skipped


def migrate(data_root: Path, resolution_path: Path, dry_run: bool = False,
            decisions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data_root = Path(data_root)
    marker = data_root / "agreements" / MARKER_NAME
    if marker.exists():
        return {"status": "already_migrated", "marker": str(marker)}
    resolution = json.loads(Path(resolution_path).read_text(encoding="utf-8"))
    result = plan(_load_events(data_root / "events"), resolution)
    _apply_decisions(result, decisions or {})
    skipped_unresolved = _drop_unresolved_clients(result)
    zero_filled = []
    for group in result["agreements"].values():
        for component in group["components"]:
            if _is_blank(component.get("amount")) and _is_blank(component.get("percent")):
                component["amount"] = 0  # human decision 2026-10-15: a component with no value gets amount 0
                zero_filled.append({"agreement_id": group["agreement_id"], "label": component.get("label")})
    report: Dict[str, Any] = {
        "skipped_unresolved_clients": skipped_unresolved,
        "zero_filled_components": zero_filled,
        "agreements": len(result["agreements"]),
        "components": sum(len(g["components"]) for g in result["agreements"].values()),
        "events_rewritten": len(result["rewrite"]),
        "status_counts": _counts(result["agreements"]),
        "unresolved_names": result["unresolved"],
        "merged_duplicates": result["duplicates"],
        "dry_run": dry_run,
    }
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
                partner_percent=group["partner_percent"], status=group["status"], components=group["components"],
                created_at=to_local(group["created_at"]).isoformat() if group["created_at"] != datetime.min else None)
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
    merged_slug = group.get("merged_events", {}).get(event.get("event_id"))
    for component in group["components"]:
        if component["origin_event_id"] == event.get("event_id") or (
                merged_slug is not None and _slugify(component["label"]) == merged_slug):
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
    ap.add_argument("--decisions", help="JSON: {skip_agreement_ids: [...], component_status: [{agreement_id, label, status}]}")
    args = ap.parse_args(argv)
    decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8")) if args.decisions else None
    report = migrate(Path(args.data_root), Path(args.resolution), args.dry_run, decisions)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
