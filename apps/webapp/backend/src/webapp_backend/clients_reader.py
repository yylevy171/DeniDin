"""Clients Management data service (Feature 087).

Ports ``reports/mapping_tool/generate_client_status.py``'s aggregation/matching/
status logic plus ``mapping_server.py``'s section-routing logic into one
importable, read-composed service. Behavior is preserved as-is per the feature's
Clarifications session (2026-09-17) — only the data-source plumbing changes:
official clients come from a live Morning fetch (``morning_client_source.py``)
instead of a CSV, and events come from the same ``LedgerEventManager``-backed
source the Events tab uses instead of a hardcoded sshfs path or a separate
Morning-docs CSV merge (ledger events already include Morning-sourced חשבונית
events via Feature 025's reconciliation sweep).

``get_report()`` still writes ``removed_clients.json``/``new_morning_clients.json``
as a side effect on every call — preserved exactly, per Clarifications.
"""
import collections
import difflib
import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from utils.time_utils import now_local  # apps/denidin-app/src on path (webapp_backend/__init__)
from webapp_backend.ledger_reader import LedgerEventManager

logger = logging.getLogger("webapp_backend")

PAST_CUTOFF = datetime(2025, 9, 1)
# Feature 092: explicit per-line status (client_status.json) replaces the לסגור/לבדוק/לקוח פעיל
# comment keywords as the source of a line's check/active/closed routing.
LINE_STATUSES = ("closed", "check", "active")
LINE_ACTIONS = ("close", "reopen", "check", "active")
MIGRATION_092_KEY = "092_comment_line_status"


class ClientNotFoundError(LookupError):
    """No visible client line with that official name."""


class LineStatusNotAllowedError(RuntimeError):
    """The line is in the gray (past) section - it takes no status buttons."""


class MappingNotFoundError(LookupError):
    """No explicit client_mapping.json entry for that raw name."""


_PLUS_INVOICE_SUBTYPES = {"חשבונית מס קבלה", "חשבונית מס / קבלה", "קבלה", "320", "400", 320, 400}


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _load_json_list(path: Path) -> List[Any]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []
    return []


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_any_date(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        date_part = str(raw).split(" ")[0]
        if "/" in date_part:
            d, m, y = (int(x) for x in date_part.split("/"))
        else:
            y, m, d = (int(x) for x in date_part.split("-"))
        return datetime(y, m, d)
    except (ValueError, TypeError):
        return None


def _fuzzy_match(name: Optional[str], official_clients: List[str],
                  manual_mapping: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    if not name:
        return None, name
    name = name.strip()
    if name in manual_mapping and manual_mapping[name]:
        if manual_mapping[name] == "Unknown":
            return None, name
        if manual_mapping[name] in official_clients:
            return manual_mapping[name], name
    if name in official_clients:
        return name, name
    matches = difflib.get_close_matches(name, official_clients, n=1, cutoff=0.8)
    if matches:
        return matches[0], name
    return None, name


def _new_stat() -> Dict[str, Any]:
    return {
        "agreements": 0.0, "deposits": 0.0, "invoices_net": 0.0,
        "raw_names": set(), "events": [], "latest_activity": None,
        "agreed_status": "WHITE", "paid_status": "WHITE",
    }


def _raw_client_name(data: Dict[str, Any]) -> str:
    """Feature 092: an event with no client name gets its own stable raw name,
    ``Unknown-<event_id>``, so each one is resolved independently (they belong to different
    clients). event_id is immutable per ledger event, so the name never shifts."""
    raw = data.get("client_name") or data.get("payer_name") or ""
    if str(raw).strip() and str(raw).strip() != "Unknown":
        return raw
    event_id = data.get("event_id")
    if event_id:
        return f"Unknown-{event_id}"
    logger.warning("ledger event with no client name and no event_id - grouped as 'Unknown'")
    return "Unknown"


def _aggregate_events(
    all_events: List[Dict[str, Any]], official_clients: List[str], manual_mapping: Dict[str, str]
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[float, set]]:
    stats = {c: _new_stat() for c in official_clients}
    unmatched: Dict[str, Dict[str, Any]] = collections.defaultdict(
        lambda: {"agreements": 0.0, "deposits": 0.0, "raw_text": set()}
    )
    amount_to_clients: Dict[float, set] = collections.defaultdict(set)

    for data in all_events:
        event_datetime = data.get("event_datetime") or data.get("txn_date") or data.get("event_date") or ""
        event_date_obj = _parse_any_date(event_datetime)

        raw_client = _raw_client_name(data)
        matched_client, original_name = _fuzzy_match(raw_client, official_clients, manual_mapping)

        if event_date_obj and matched_client:
            current = stats[matched_client]["latest_activity"]
            if current is None or event_date_obj > current:
                stats[matched_client]["latest_activity"] = event_date_obj

        if event_date_obj and event_date_obj < PAST_CUTOFF:
            continue

        src_type = data.get("source_type")
        if not src_type:
            continue

        amount_val = data.get("amount")
        if amount_val is None:
            continue
        try:
            amount = float(amount_val)
        except (TypeError, ValueError):
            continue

        subtype = data.get("event_subtype", "") or ""

        if src_type == "חשבונית" and matched_client:
            amount_to_clients[amount].add(matched_client)

        if matched_client:
            target = stats[matched_client]
            if original_name != matched_client:
                target["raw_names"].add(original_name)
            desc = data.get("description") or data.get("trigger_condition") or data.get("component_label") or ""
            target["events"].append({
                "date": event_datetime, "amount": amount, "type": src_type,
                "subtype": subtype, "desc": desc,
            })
        else:
            target = unmatched[original_name]

        prefix = f"[{event_date_obj.strftime('%d.%m.%y')}] " if event_date_obj else ""
        if src_type == "הסכם":
            target["agreements"] += amount
            if not matched_client:
                text = data.get("description") or data.get("trigger_condition") or "הסכם ללא פירוט"
                unmatched[original_name]["raw_text"].add(f"{prefix}הסכם (₪{amount:,.2f}): {text}")
        elif src_type == "בנק":
            if not matched_client:
                text = data.get("description") or data.get("trigger_condition") or "הפקדת בנק / שיק"
                unmatched[original_name]["raw_text"].add(f"{prefix}הפקדת בנק (₪{amount:,.2f}): {text}")
        elif src_type == "חשבונית":
            if matched_client:
                if subtype in _PLUS_INVOICE_SUBTYPES:
                    target["invoices_net"] += amount
            else:
                text = data.get("description") or data.get("trigger_condition") or subtype or "מסמך מורנינג"
                unmatched[original_name]["raw_text"].add(f"{prefix}חשבונית/מסמך (₪{amount:,.2f}): {text}")

    return stats, unmatched, amount_to_clients


def _apply_comment_rules(stats: Dict[str, Dict[str, Any]], client_comments: Dict[str, str]) -> None:
    """Hebrew free-text-comment-driven status overrides — ported verbatim from
    generate_client_status.py's get_report_data()."""
    for c, data in stats.items():
        comment = client_comments.get(c, "")
        if not comment:
            continue
        unclear_flags = ["לבדוק", "לא ברור", "חסר"]
        is_unclear = any(flag in comment for flag in unclear_flags)

        if "הסכם" in comment:
            date_match = re.search(r"הסכם\s+(\d{1,2})[./](\d{1,2})[./](\d{2,4})", comment)
            if date_match:
                try:
                    d, m, y = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                    if y < 100:
                        y += 2000
                    comment_date_obj = datetime(y, m, d)
                    current = data["latest_activity"]
                    if current is None or comment_date_obj > current:
                        data["latest_activity"] = comment_date_obj
                except (ValueError, TypeError):
                    pass

            total_match = re.search(r"סה[״\"']כ הסכמים\s*(?:-\s*)?([1-9][\d,]*)", comment)
            if total_match:
                try:
                    data["manual_agreement_amount"] = float(total_match.group(1).replace(",", ""))
                    data["agreed_status"] = "YELLOW" if is_unclear else "GRAY"
                except ValueError:
                    data["agreed_status"] = "YELLOW"
            else:
                matches = re.findall(
                    r"הסכם\s+(?:\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\s+)?(?:-\s*)?([1-9][\d,+]{2,})", comment
                )
                if matches:
                    try:
                        total_amt = 0.0
                        for m in matches:
                            clean_m = m.rstrip(",").rstrip(".").strip()
                            if "+" in clean_m:
                                total_amt += sum(
                                    float(part.replace(",", "").strip())
                                    for part in clean_m.split("+") if part.replace(",", "").strip()
                                )
                            else:
                                total_amt += float(clean_m.replace(",", ""))
                        if total_amt > 0:
                            data["manual_agreement_amount"] = total_amt
                            data["agreed_status"] = "YELLOW" if is_unclear else "GRAY"
                    except ValueError:
                        data["agreed_status"] = "YELLOW"
                elif is_unclear:
                    data["agreed_status"] = "YELLOW"
        elif is_unclear:
            data["agreed_status"] = "YELLOW"

        if "remove" in comment.lower() or "להוריד" in comment:
            dep_events = [ev for ev in data["events"] if ev["type"] == "בנק"]
            if dep_events:
                amounts = [ev["amount"] for ev in dep_events]
                counts = collections.Counter(amounts)
                dups = [amt for amt, count in counts.items() if count > 1]
                if len(dups) == 1:
                    data["deposits"] -= dups[0]
                    data["paid_status"] = "YELLOW" if is_unclear else "GRAY"
                else:
                    data["paid_status"] = "YELLOW"
            else:
                data["paid_status"] = "YELLOW"
        elif is_unclear and data["paid_status"] == "WHITE":
            data["paid_status"] = "YELLOW"

        if data["latest_activity"] and hasattr(data["latest_activity"], "isoformat"):
            data["latest_activity"] = data["latest_activity"].isoformat()

        data["raw_names"] = list(data["raw_names"])

        def _sort_key(e: Dict[str, Any]) -> str:
            dt = e["date"]
            if not dt:
                return "00000000"
            parts = dt.split(" ")
            d_parts = parts[0].split("/")
            d_str = (d_parts[2] + d_parts[1] + d_parts[0]) if len(d_parts) == 3 else dt
            if len(parts) > 1:
                d_str += parts[1]
            return d_str

        data["events"].sort(key=_sort_key)

    # finalize latest_activity/raw_names/events sort for clients with no comment too
    for c, data in stats.items():
        if isinstance(data["latest_activity"], datetime):
            data["latest_activity"] = data["latest_activity"].isoformat()
        if not isinstance(data["raw_names"], list):
            data["raw_names"] = list(data["raw_names"])


_STRIP_CHARS = str.maketrans("", "", "׳״'\"")


def _apply_merge_directives(
    stats: Dict[str, Dict[str, Any]], official_clients: List[str], client_comments: Dict[str, str]
) -> None:
    """Merge (לאחד / אוחד) directives — ported verbatim."""
    merges: List[Tuple[str, str]] = []
    for c, comment_text in client_comments.items():
        if not comment_text or ("לאחד" not in comment_text and "אוחד" not in comment_text):
            continue
        m = re.search(r'[״"\'׳]([^״"\'׳]+)[״"\'׳]', comment_text)
        if not m:
            continue
        target_raw = m.group(1).strip()
        norm = target_raw.translate(_STRIP_CHARS).strip()
        resolved_target = None
        if target_raw in stats:
            resolved_target = target_raw
        else:
            for oc in official_clients:
                if norm == oc.translate(_STRIP_CHARS).strip():
                    resolved_target = oc
                    break
            if not resolved_target:
                words = [w for w in norm.split() if len(w) > 2]
                best_candidate, best_score = None, 0
                for oc in official_clients:
                    if "קאולה" in oc and (
                        "קואלה" in norm or "פאות" in norm
                    ):
                        best_candidate, best_score = oc, 999
                        break
                    score = sum(1 for w in words if w in oc)
                    if score > best_score:
                        best_score, best_candidate = score, oc
                if best_score > 0:
                    resolved_target = best_candidate
                else:
                    fuzzy = difflib.get_close_matches(target_raw, official_clients, n=1, cutoff=0.4)
                    if fuzzy:
                        resolved_target = fuzzy[0]
        if resolved_target and resolved_target in stats and resolved_target != c:
            merges.append((c, resolved_target))

    for src, tgt in merges:
        if src not in stats or tgt not in stats:
            continue
        src_data, tgt_data = stats[src], stats[tgt]
        tgt_data["agreements"] += src_data["agreements"]
        tgt_data["deposits"] += src_data["deposits"]
        tgt_data["invoices_net"] += src_data["invoices_net"]
        if src_data.get("manual_agreement_amount") is not None:
            if tgt_data.get("manual_agreement_amount") is not None:
                tgt_data["manual_agreement_amount"] += src_data["manual_agreement_amount"]
            else:
                tgt_data["manual_agreement_amount"] = tgt_data["agreements"] + src_data["manual_agreement_amount"]
        tgt_data["events"].extend(src_data["events"])
        for r in src_data["raw_names"]:
            if r not in tgt_data["raw_names"]:
                tgt_data["raw_names"].append(r)
        if src not in tgt_data["raw_names"]:
            tgt_data["raw_names"].append(src)
        src_data["is_merged_away"] = True


def _apply_status_directives(
    stats: Dict[str, Dict[str, Any]], client_comments: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Delete directives — ported verbatim. Returns the removed-clients list (also the
    side-effect payload for removed_clients.json).

    Feature 092: the check / active / close comment keywords no longer route a line (the
    persisted client_status.json does - see ``_apply_line_status``), and closing no longer
    rewrites agreed/paid amounts (bugfix-068)."""
    removed_clients: List[Dict[str, Any]] = []
    for c, data in stats.items():
        comment_text = client_comments.get(c, "")
        if not comment_text:
            continue
        if (
            "למחוק" in comment_text
            or comment_text.strip() == "להסיר"
            or ("להסיר מהרשימה" in comment_text and not data.get("is_merged_away"))
        ):
            data["is_delete_past"] = True
            removed_clients.append({
                "client_name": c, "reason": comment_text,
                "agreements": data["agreements"], "invoices_net": data["invoices_net"],
            })
    return removed_clients


def _legacy_comment_status(comment_text: str, is_merged_away: bool) -> Optional[str]:
    """FROZEN pre-092 comment→routing detection, used ONLY by the one-time migration
    (research R-4). Returns the single status that reproduces the section the comment
    produced before 092: the highest of check > active > closed, or None."""
    if not comment_text or is_merged_away:
        return None
    is_active = "לקוח פעיל" in comment_text or "לקוחה פעילה" in comment_text
    is_delete = (
        "למחוק" in comment_text
        or comment_text.strip() == "להסיר"
        or "להסיר מהרשימה" in comment_text
    )
    is_check = is_close = False
    if not is_delete:
        is_check = "לבדוק" in comment_text
        is_close = ("לסגור" in comment_text or "אפשר לסגור" in comment_text) and not is_check
    if is_check:
        return "check"
    if is_active:
        return "active"
    if is_close:
        return "closed"
    return None


def _valid_statuses(client_status: Dict[str, Any]) -> Dict[str, str]:
    valid: Dict[str, str] = {}
    for c, value in client_status.items():
        if value in LINE_STATUSES:
            valid[c] = value
        else:
            logger.warning("client_status.json: ignoring unknown status %r for %r", value, c)
    return valid


def _apply_line_status(stats: Dict[str, Dict[str, Any]], client_status: Dict[str, str]) -> None:
    """Feature 092: set the routing flags ``_row_status`` reads from the persisted status."""
    for c, value in client_status.items():
        data = stats.get(c)
        if data is None:
            continue
        data["line_status"] = value
        if value == "check":
            data["is_check"] = True
        elif value == "active":
            data["is_active_client"] = True
        elif value == "closed":
            data["is_manually_settled"] = True


def _split_unmatched(
    unmatched: Dict[str, Dict[str, Any]], notes: Dict[str, str], hidden: Optional[set] = None
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    final_unmatched: Dict[str, Dict[str, Any]] = {}
    new_morning_clients: List[Dict[str, Any]] = []
    hidden = hidden or set()
    for u, udata in unmatched.items():
        udata["raw_text"] = list(udata["raw_text"])
        if u in hidden:  # Feature 092: "הסר מהרשימה"
            continue
        note = notes.get(u, "").lower()
        if any(term in note for term in
               ["להסיר", "לא לקוחה",
                "אוחד", "שיניתי את השם",
                "remove from the list"]):
            continue
        if "לקוח חדש במורנינג" in note or "need a new morning client" in note:
            new_morning_clients.append({
                "raw_name": u, "agreements": udata["agreements"],
                "deposits": udata["deposits"], "note": notes.get(u, ""),
            })
            continue
        final_unmatched[u] = udata
    return final_unmatched, new_morning_clients


def _row_status(data: Dict[str, Any], display_agreed: float, display_paid: float,
                 is_past: bool) -> str:
    """Section-routing priority — ported verbatim from mapping_server.py's render loop."""
    if data.get("is_check"):
        return "check"
    if data.get("is_active_client"):
        return "active"
    if data.get("is_manually_settled"):
        return "settled"
    if is_past:
        return "past"
    agreed_round, paid_round = round(display_agreed, 2), round(display_paid, 2)
    if agreed_round > 0 and paid_round == agreed_round:
        return "settled"
    if agreed_round > 0 and paid_round < agreed_round:
        return "debt"
    return "missing_agreement"


def _build_client_rows(
    official_clients: List[str], stats: Dict[str, Dict[str, Any]], client_comments: Dict[str, str],
    manual_mapping: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    manual_mapping = manual_mapping or {}
    rows: List[Dict[str, Any]] = []
    for client in sorted(official_clients):
        data = stats[client]
        if data.get("is_merged_away"):
            continue

        agreed = data["agreements"]
        invoices_net = data.get("invoices_net", 0.0)
        manual_agreed = data.get("manual_agreement_amount")
        latest_act = data.get("latest_activity")

        is_past = True
        if latest_act:
            try:
                if datetime.fromisoformat(latest_act) > PAST_CUTOFF:
                    is_past = False
            except (ValueError, TypeError):
                pass
        if data.get("is_delete_past"):
            is_past = True
        if is_past and not data.get("is_manually_settled"):
            manual_agreed = None

        display_agreed = manual_agreed if manual_agreed is not None else agreed
        display_paid = invoices_net
        status = _row_status(data, display_agreed, display_paid, is_past)

        if status in ("past", "missing_agreement") and display_agreed == 0 and data["deposits"] == 0 and invoices_net == 0:
            # mirrors mapping_server.py's "skip empty non-past rows" rule (only applies
            # to the non-past branch there, but an empty past client is equally inert)
            if status != "past":
                continue

        rows.append({
            "official_name": client,
            "raw_names": data["raw_names"],
            "agreements_total": agreed,
            "deposits_total": data["deposits"],
            "invoices_net": invoices_net,
            "manual_agreement_amount": manual_agreed,
            "agreed_status": data.get("agreed_status", "WHITE"),
            "paid_status": data.get("paid_status", "WHITE"),
            "display_agreed": display_agreed,
            "display_paid": display_paid,
            "status": status,
            "is_manually_settled": bool(data.get("is_manually_settled")),
            "latest_activity": latest_act,
            "comment": client_comments.get(client, ""),
            "events": data["events"],
            "line_status": data.get("line_status"),
            # Feature 092: only explicit client_mapping.json aliases of THIS client can be
            # unlinked (fuzzy matches / merge sources also appear in raw_names).
            "mapped_aliases": sorted(
                r for r in data["raw_names"] if manual_mapping.get(r) == client
            ),
        })
    return rows


def _build_unmatched_rows(
    final_unmatched: Dict[str, Dict[str, Any]], notes: Dict[str, str],
    amount_to_clients: Dict[float, set], official_clients: List[str], stats: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Port of mapping_server.py's "Smart Candidate Generation": for each unmatched raw
    name, suggest official clients by (a) an exact matching transaction amount, (b) fuzzy
    name similarity, (c) sharing a family/last name — each candidate carries the reason(s)
    it was suggested for, and the full active official-client list is returned separately
    so the frontend can render a searchable dropdown (all clients, smart candidates first)
    rather than a free-text field."""
    active_official = [c for c in official_clients if not stats.get(c, {}).get("is_merged_away")]
    rows = []
    for raw_name, data in sorted(final_unmatched.items()):
        agreed_val = data["agreements"]
        amount_candidates = amount_to_clients.get(agreed_val, set()) if agreed_val > 0 else set()
        fuzzy_candidates = set(difflib.get_close_matches(raw_name, active_official, n=3, cutoff=0.5))
        family_candidates: set = set()
        words = raw_name.split()
        if len(words) > 1:
            last_word = words[-1]
            for oc in active_official:
                if last_word in oc:
                    family_candidates.add(oc)

        all_candidates = amount_candidates | fuzzy_candidates | family_candidates
        all_candidates &= set(active_official)
        suggestions = []
        for oc in sorted(all_candidates):
            reasons = []
            if oc in amount_candidates:
                reasons.append("סכום זהה")
            if oc in fuzzy_candidates:
                reasons.append("דמיון בשם")
            if oc in family_candidates:
                reasons.append("שם משפחה")
            suggestions.append({"name": oc, "reasons": reasons})

        rows.append({
            "raw_name": raw_name,
            "suggested_matches": suggestions,
            "event_count": len(data["raw_text"]),
            "raw_text": data["raw_text"],
            "note": notes.get(raw_name, ""),
        })
    return rows


class ClientsReader:
    """Read-composed service backing ``GET /api/clients`` and the comment/mapping
    write endpoints. ``official_clients_fn`` is injected (``morning_client_source``)
    so this module has no direct Morning dependency of its own."""

    def __init__(
        self,
        data_root: str,
        clients_data_root: str,
        official_clients_fn: Callable[[], List[str]],
        events_fn: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        generation_fn: Callable[[], int] = lambda: 0,
    ) -> None:
        self._events_dir = str(Path(data_root) / "events")
        self._clients_dir = Path(clients_data_root)
        self._official_clients_fn = official_clients_fn
        # When wired to the app's shared LedgerReader, events come from its in-memory index
        # instead of a fresh per-call re-read of every event file from disk.
        self._events_fn = events_fn
        self._generation_fn = generation_fn
        # The Morning client list and the computed report are kept until a refresh (or, for
        # the report, a save / a ledger reload) - recomputing them costs a Morning round-trip
        # per page plus the full aggregation.
        self._official_cache: Optional[List[str]] = None
        self._report_cache: Optional[Tuple[int, Dict[str, Any]]] = None
        self._lock = threading.Lock()

    def _paths(self) -> Dict[str, Path]:
        d = self._clients_dir
        return {
            "mapping": d / "client_mapping.json",
            "notes": d / "mapping_notes.json",
            "comments": d / "client_comments.json",
            "removed": d / "removed_clients.json",
            "new_morning": d / "new_morning_clients.json",
            # Feature 092
            "status": d / "client_status.json",
            "hidden": d / "hidden_unmatched.json",
            "migrations": d / "migrations.json",
        }

    def get_report(self, refresh: bool = False) -> Dict[str, Any]:
        with self._lock:
            if refresh:
                self._official_cache = None
                self._report_cache = None
            return self._report_locked()

    def _report_locked(self) -> Dict[str, Any]:
        generation = self._generation_fn()
        if self._report_cache is not None and self._report_cache[0] == generation:
            return self._report_cache[1]
        report = self._compute_report()
        self._report_cache = (generation, report)
        return report

    def warm(self) -> None:
        try:
            self.get_report()
        except Exception:  # noqa: BLE001 - warming is an optimisation; the request path reports errors
            logger.warning("clients report warm-up failed", exc_info=True)

    def warm_in_background(self) -> None:
        threading.Thread(target=self.warm, name="clients-warm", daemon=True).start()

    def _compute_report(self, status_override: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if self._official_cache is None:
            self._official_cache = self._official_clients_fn()
        official_clients = self._official_cache
        paths = self._paths()
        manual_mapping = _load_json(paths["mapping"])
        notes = _load_json(paths["notes"])
        client_comments = _load_json(paths["comments"])
        hidden = set(_load_json_list(paths["hidden"]))

        if self._events_fn is not None:
            all_events = self._events_fn()
        else:
            all_events = LedgerEventManager(self._events_dir).list_events()

        stats, unmatched, amount_to_clients = _aggregate_events(all_events, official_clients, manual_mapping)
        _apply_comment_rules(stats, client_comments)
        _apply_merge_directives(stats, official_clients, client_comments)
        self._migrate_comment_status_once(stats, client_comments)
        removed_clients = _apply_status_directives(stats, client_comments)
        if status_override is None:
            client_status = _valid_statuses(_load_json(paths["status"]))
        else:
            client_status = dict(status_override)
        _apply_line_status(stats, client_status)
        final_unmatched, new_morning_clients = _split_unmatched(unmatched, notes, hidden)

        # Preserved side effect (Clarifications 2026-09-17): write on every (re)compute.
        _save_json(paths["removed"], removed_clients)
        _save_json(paths["new_morning"], new_morning_clients)

        return {
            "clients": _build_client_rows(official_clients, stats, client_comments, manual_mapping),
            "unmatched": _build_unmatched_rows(final_unmatched, notes, amount_to_clients, official_clients, stats),
        }

    def _migrate_comment_status_once(
        self, stats: Dict[str, Dict[str, Any]], client_comments: Dict[str, str]
    ) -> None:
        """Feature 092 R10: one-time conversion of today's comment routing keywords into
        persisted line statuses, so no line changes section on deploy. Never overwrites an
        existing status; never touches client_comments.json; recorded in migrations.json so
        it runs exactly once. Called under ``self._lock`` (via ``_compute_report``)."""
        paths = self._paths()
        migrations = _load_json(paths["migrations"])
        if MIGRATION_092_KEY in migrations:
            return
        client_status = _load_json(paths["status"])
        added: Dict[str, int] = collections.Counter()
        for c, data in stats.items():
            if c in client_status:
                continue
            value = _legacy_comment_status(client_comments.get(c, ""), bool(data.get("is_merged_away")))
            if value:
                client_status[c] = value
                added[value] += 1
        _save_json(paths["status"], client_status)
        migrations[MIGRATION_092_KEY] = now_local().isoformat()
        _save_json(paths["migrations"], migrations)
        logger.info("Feature 092 migration: comment keywords -> line statuses %s", dict(added))

    def set_line_status(self, client_id: str, action: str) -> Dict[str, Any]:
        """Feature 092 R5-R8: the line-status buttons. ``reopen`` stores ``active`` when the
        line's numbers alone would route it straight back to green (agreed == paid);
        otherwise it clears the status so the numbers route it (research R-3)."""
        if action not in LINE_ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        with self._lock:
            report = self._report_locked()
            row = next((r for r in report["clients"] if r["official_name"] == client_id), None)
            if row is None:
                raise ClientNotFoundError(client_id)
            if row["status"] == "past":
                raise LineStatusNotAllowedError(client_id)

            path = self._paths()["status"]
            statuses = _load_json(path)
            new_value: Optional[str]
            if action == "reopen":
                cleared = _valid_statuses({k: v for k, v in statuses.items() if k != client_id})
                preview = self._compute_report(status_override=cleared)
                preview_row = next(
                    (r for r in preview["clients"] if r["official_name"] == client_id), None
                )
                new_value = "active" if preview_row and preview_row["status"] == "settled" else None
            else:
                new_value = {"close": "closed", "check": "check", "active": "active"}[action]

            if new_value is None:
                statuses.pop(client_id, None)
            else:
                statuses[client_id] = new_value
            _save_json(path, statuses)
            self._report_cache = None
        logger.info("client line status: client=%r action=%s -> %s", client_id, action, new_value)
        return {"client_id": client_id, "line_status": new_value}

    def unlink_mapping(self, raw_name: str) -> Dict[str, str]:
        """Feature 092 R3: undo an explicit name mapping. Notes are kept, so the raw name
        returns to the resolve list exactly as it was."""
        with self._lock:
            path = self._paths()["mapping"]
            mapping = _load_json(path)
            if raw_name not in mapping:
                raise MappingNotFoundError(raw_name)
            official = mapping.pop(raw_name)
            _save_json(path, mapping)
            self._report_cache = None
        logger.info("client mapping unlinked: raw=%r from=%r", raw_name, official)
        return {"raw_name": raw_name, "unlinked_from": official}

    def hide_unmatched(self, raw_name: str) -> Dict[str, Any]:
        """Feature 092 R1: "הסר מהרשימה" - permanently drop a name from the resolve list."""
        with self._lock:
            path = self._paths()["hidden"]
            hidden = set(_load_json_list(path))
            hidden.add(raw_name)
            _save_json(path, sorted(hidden))
            self._report_cache = None
        logger.info("unmatched name hidden: raw=%r", raw_name)
        return {"raw_name": raw_name, "hidden": True}

    def save_comment(self, client_id: str, comment: str) -> Dict[str, str]:
        path = self._paths()["comments"]
        comments = _load_json(path)
        comments[client_id] = comment
        _save_json(path, comments)
        self._report_cache = None
        return {"client_id": client_id, "comment": comment}

    def save_mapping(
        self, raw_name: str, official_name: Optional[str] = None, note: Optional[str] = None
    ) -> Dict[str, str]:
        result: Dict[str, str] = {"raw_name": raw_name}
        if official_name is not None:
            path = self._paths()["mapping"]
            mapping = _load_json(path)
            mapping[raw_name] = official_name
            _save_json(path, mapping)
            self._report_cache = None
            result["official_name"] = official_name
        if note is not None:
            path = self._paths()["notes"]
            notes = _load_json(path)
            notes[raw_name] = note
            _save_json(path, notes)
            self._report_cache = None
            result["note"] = note
        return result
