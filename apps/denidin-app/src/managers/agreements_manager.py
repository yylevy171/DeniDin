"""
AgreementsManager - the Agreements DB (Feature 089).

The living source of truth for fee agreements: an agreement container holding fee
components, a four-state component lifecycle, and an append-only revision log. Owns
{data_root}/agreements/agreements.db (SQLite - same precedent as reminders.db and
chat_index.db).

Every write, from the webapp (through the Agreements API), the WhatsApp bot, or the
one-time migration, goes through this class: it validates, applies the state rules and
the agreement-close cascade, commits the DB change plus a revision in one transaction,
and THEN writes the matching ledger events (one `הסכם` event per affected component) via
LedgerEventManager. Nobody else writes agreement ledger events or touches the SQLite
file. Last write wins: every write is serialized under one lock, no version precondition.

Hours-worked lines (a `הסכם` ledger event with `hours`) are never components - they stay
ledger-only (REQ-089-13). See specs/repo/features/089-ui-agreement-edits/data-model.md.
"""

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from src.managers.ledger_event_manager import _normalize_amount, _slugify
from src.utils.logger import get_logger
from src.utils.time_utils import local_isoformat, now_local

logger = get_logger(__name__)

# Component statuses
PENDING = "Pending"
ACTIVE = "Active"
COMPLETED = "Completed"
CANCELLED = "Cancelled"
COMPONENT_STATUSES = (PENDING, ACTIVE, COMPLETED, CANCELLED)
# Agreement statuses
AGREEMENT_STATUSES = (ACTIVE, COMPLETED, CANCELLED)

ACTORS = ("webapp", "whatsapp", "migration")

# Fields a PATCH may touch (everything else, status included, has its own action).
AGREEMENT_EDITABLE_FIELDS = ("payer_name", "partner_name", "partner_percent")
COMPONENT_EDITABLE_FIELDS = (
    "label", "description", "amount", "percent", "percent_base",
    "trigger_condition", "vat_status", "txn_date",
)

COMPONENT_ACTIONS = ("activate", "complete", "cancel", "reopen")
AGREEMENT_ACTIONS = ("complete", "cancel", "reopen")

_LEDGER_SUBTYPE_CREATE = "יצירה"
_LEDGER_SUBTYPE_DELETE = "ביטול"


class AgreementsError(Exception):
    """Base class for every business-rule failure; `code` is the API error code."""

    code = "agreements_error"

    def __init__(self, message: str, fields: Optional[Dict[str, str]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.fields = fields or {}


class NotFoundError(AgreementsError):
    code = "not_found"


class LockedError(AgreementsError):
    code = "locked"


class IllegalTransitionError(AgreementsError):
    code = "illegal_transition"


class ValidationError(AgreementsError):
    code = "validation"


class LedgerCapacityError(AgreementsError):
    """The ledger cannot take this write's events right now: event ids hold one sequence
    digit, so a minute has 10 slots (human decision 2026-10-09: refuse the whole write up
    front, never drop events silently). Nothing was written; retry in a minute."""

    code = "ledger_busy"


class InvalidActorError(AgreementsError):
    code = "invalid_actor"


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_amount(value: Any, field: str) -> Optional[int]:
    """Integer shekels, like the ledger. Accepts ints/floats/strings such as '5,000₪'."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a number", {field: "not a number"})
    if isinstance(value, (int, float)):
        return int(round(value))
    amount = _normalize_amount(str(value))
    if amount is None:
        raise ValidationError(f"{field} must be a number", {field: "not a number"})
    return amount


def _to_percent(value: Any, field: str) -> Optional[float]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a number", {field: "not a number"})
    try:
        number = float(str(value).replace("%", "").strip())
    except ValueError as exc:
        raise ValidationError(f"{field} must be a number", {field: "not a number"}) from exc
    return int(number) if number == int(number) else number


class AgreementsManager:
    """See module docstring. Constructed with the DeniDin object only (REQ-063-08)."""

    def __init__(self, denidin: Any) -> None:
        self.denidin = denidin
        self.db_path = Path(denidin.config.data_root) / "agreements" / "agreements.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()
        logger.info("AgreementsManager initialized at %s", self.db_path)

    # ------------------------------------------------------------------ #
    # Infrastructure
    # ------------------------------------------------------------------ #

    @property
    def ledger_event_manager(self) -> Any:
        return getattr(self.denidin, "ledger_event_manager", None)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """A connection that commits on success, rolls back on error, and always closes."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS agreements (
                    agreement_id    TEXT PRIMARY KEY,
                    title           TEXT NOT NULL,
                    client_name     TEXT NOT NULL,
                    payer_name      TEXT,
                    partner_name    TEXT,
                    partner_percent REAL,
                    status          TEXT NOT NULL,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS components (
                    component_key     TEXT PRIMARY KEY,
                    component_id      TEXT NOT NULL,
                    agreement_id      TEXT NOT NULL REFERENCES agreements(agreement_id),
                    label             TEXT NOT NULL,
                    description       TEXT,
                    amount            INTEGER,
                    percent           REAL,
                    percent_base      TEXT,
                    trigger_condition TEXT,
                    vat_status        TEXT,
                    txn_date          TEXT,
                    status            TEXT NOT NULL,
                    origin_event_id   TEXT,
                    sort_order        INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_components_agreement ON components(agreement_id);
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    agreement_id          TEXT NOT NULL,
                    component_key         TEXT,
                    actor                 TEXT NOT NULL,
                    action                TEXT NOT NULL,
                    snapshot_json         TEXT NOT NULL,
                    changed_json          TEXT NOT NULL,
                    ledger_event_ids_json TEXT NOT NULL,
                    created_at            TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_revisions_agreement ON revisions(agreement_id);
                """
            )

    def _require_ledger_slots(self, needed: int, message_timestamp: Optional[int] = None) -> None:
        """Refuses (before anything is written) when the current minute cannot hold `needed`
        more `הסכם` ledger events."""
        ledger = self.ledger_event_manager
        if ledger is None or needed <= 0:
            return
        free = ledger.free_event_slots("הסכם", message_timestamp)
        if needed > free:
            raise LedgerCapacityError(
                f"this change needs {needed} ledger events but only {free} are free in this minute - "
                "nothing was written; try again in a minute"
            )

    @staticmethod
    def _check_actor(actor: str) -> None:
        if actor not in ACTORS:
            raise InvalidActorError(f"actor must be one of {list(ACTORS)}, got {actor!r}")

    # ------------------------------------------------------------------ #
    # Row -> dict
    # ------------------------------------------------------------------ #

    @staticmethod
    def _component_dict(row: sqlite3.Row, agreement_status: str) -> Dict[str, Any]:
        locked = row["status"] in (COMPLETED, CANCELLED) or agreement_status != ACTIVE
        return {
            "component_key": row["component_key"],
            "component_id": row["component_id"],
            "label": row["label"],
            "description": row["description"],
            "amount": row["amount"],
            "percent": row["percent"],
            "percent_base": row["percent_base"],
            "trigger_condition": row["trigger_condition"],
            "vat_status": row["vat_status"],
            "txn_date": row["txn_date"],
            "status": row["status"],
            "origin_event_id": row["origin_event_id"],
            "locked": locked,
        }

    def _agreement_dict(self, conn: sqlite3.Connection, agreement_id: str) -> Dict[str, Any]:
        row = conn.execute("SELECT * FROM agreements WHERE agreement_id = ?", (agreement_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"agreement {agreement_id!r} not found")
        comps = conn.execute(
            "SELECT * FROM components WHERE agreement_id = ? ORDER BY sort_order, rowid", (agreement_id,)
        ).fetchall()
        return {
            "agreement_id": row["agreement_id"],
            "title": row["title"],
            "client_name": row["client_name"],
            "payer_name": row["payer_name"],
            "partner_name": row["partner_name"],
            "partner_percent": row["partner_percent"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "components": [self._component_dict(c, row["status"]) for c in comps],
        }

    def _component_row(self, conn: sqlite3.Connection, agreement_id: str, component_key: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM components WHERE agreement_id = ? AND component_key = ?",
            (agreement_id, component_key),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"component {component_key!r} not found in agreement {agreement_id!r}")
        return row

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def get_agreement(self, agreement_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            return self._agreement_dict(conn, agreement_id)

    def find_agreements(self, client_name: str) -> List[Dict[str, Any]]:
        """Every agreement of one client (exact official-name match, whitespace-trimmed)."""
        wanted = (client_name or "").strip()
        with self._connect() as conn:
            ids = [r["agreement_id"] for r in conn.execute(
                "SELECT agreement_id FROM agreements WHERE TRIM(client_name) = ? ORDER BY created_at, rowid",
                (wanted,),
            ).fetchall()]
            return [self._agreement_dict(conn, i) for i in ids]

    def list_agreements(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            ids = [r["agreement_id"] for r in conn.execute(
                "SELECT agreement_id FROM agreements ORDER BY client_name, created_at, rowid"
            ).fetchall()]
            return [self._agreement_dict(conn, i) for i in ids]

    def totals(self) -> Dict[str, int]:
        """client_name -> sum of non-Cancelled component amounts (REQ-089-14). Percent-only
        components have no amount and contribute nothing."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT TRIM(a.client_name) AS client_name, SUM(c.amount) AS total
                FROM components c JOIN agreements a ON a.agreement_id = c.agreement_id
                WHERE c.status != ? AND c.amount IS NOT NULL
                GROUP BY TRIM(a.client_name)
                """,
                (CANCELLED,),
            ).fetchall()
        return {r["client_name"]: int(r["total"] or 0) for r in rows}

    def revisions(self, agreement_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM agreements WHERE agreement_id = ?", (agreement_id,)).fetchone() is None \
                    and conn.execute("SELECT 1 FROM revisions WHERE agreement_id = ?", (agreement_id,)).fetchone() is None:
                raise NotFoundError(f"agreement {agreement_id!r} not found")
            rows = conn.execute(
                "SELECT * FROM revisions WHERE agreement_id = ? ORDER BY revision_id", (agreement_id,)
            ).fetchall()
        return [{
            "revision_id": r["revision_id"],
            "created_at": r["created_at"],
            "actor": r["actor"],
            "action": r["action"],
            "component_key": r["component_key"],
            "snapshot": json.loads(r["snapshot_json"]),
            "changed": json.loads(r["changed_json"]),
            "ledger_event_ids": json.loads(r["ledger_event_ids_json"]),
        } for r in rows]

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #

    def _normalize_component_input(self, data: Dict[str, Any], *, require_value: bool) -> Dict[str, Any]:
        """Returns the cleaned component fields present in `data` (only keys given)."""
        fields: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        for key in ("label", "description", "percent_base", "trigger_condition", "vat_status", "txn_date"):
            if key in data:
                fields[key] = _clean_text(data[key])
        if "label" in fields and fields["label"] is None:
            errors["label"] = "required"
        try:
            if "amount" in data:
                fields["amount"] = _to_amount(data["amount"], "amount")
            if "percent" in data:
                fields["percent"] = _to_percent(data["percent"], "percent")
        except ValidationError as exc:
            errors.update(exc.fields)
        if errors:
            raise ValidationError("invalid component", errors)
        if require_value:
            if _blank(fields.get("label")):
                errors["label"] = "required"
            if fields.get("amount") is None and fields.get("percent") is None:
                errors["amount"] = "amount or percent is required"
            if errors:
                raise ValidationError("invalid component", errors)
        return fields

    @staticmethod
    def _assert_label_free(conn: sqlite3.Connection, agreement_id: str, label: str,
                           except_key: Optional[str] = None) -> str:
        """Labels are unique within an agreement (human decision 2026-10-09). Returns the
        ledger-style component_id for the label."""
        component_id = f"{agreement_id}-{_slugify(label)}"
        rows = conn.execute(
            "SELECT component_key FROM components WHERE agreement_id = ? AND component_id = ?",
            (agreement_id, component_id),
        ).fetchall()
        if any(r["component_key"] != except_key for r in rows):
            raise ValidationError(
                f"a component labelled {label!r} already exists in this agreement",
                {"label": "duplicate label within the agreement"},
            )
        return component_id

    @staticmethod
    def _default_status(trigger_condition: Optional[str]) -> str:
        return PENDING if not _blank(trigger_condition) else ACTIVE

    @staticmethod
    def _make_agreement_id(client_name: str, title: str) -> str:
        return f"{now_local().strftime('%m%y')}-{_slugify(client_name)}-{_slugify(title)}"

    # ------------------------------------------------------------------ #
    # Ledger mapping
    # ------------------------------------------------------------------ #

    @staticmethod
    def _ledger_event(agreement: Dict[str, Any], component: Dict[str, Any],
                      original_client_name: Optional[str] = None) -> Dict[str, Any]:
        return {
            "source_type": "הסכם",
            "event_subtype": _LEDGER_SUBTYPE_CREATE,
            "client_name": agreement["client_name"],
            "payer_name": agreement["payer_name"],
            "description": component.get("description"),
            "amount": None if component.get("amount") is None else str(component["amount"]),
            "percent": component.get("percent"),
            "percent_base": component.get("percent_base"),
            "hours": None,
            "hourly_rate": None,
            "txn_date": component.get("txn_date"),
            "vat_status": component.get("vat_status"),
            "trigger_condition": component.get("trigger_condition"),
            "reference_hint": None,
            "agreement_id": agreement["agreement_id"],
            "component_label": component["label"],
            "component_status": component["status"],
            "agreement_status": agreement["status"],
            "split_partner": agreement["partner_name"],
            "split_percent": agreement["partner_percent"],
            "original_client_name": original_client_name,
        }

    def _write_ledger_events(
        self, agreement: Dict[str, Any], components: List[Dict[str, Any]], *,
        session_id: Optional[str] = None, message_id: Optional[str] = None,
        message_timestamp: Optional[int] = None,
    ) -> Dict[str, Optional[str]]:
        """One `יצירה` event per component. Returns component_key -> event_id (None when
        the ledger could not persist it). A ledger failure after the DB commit is logged,
        never raised (out of scope per the 2026-10-05 clarification)."""
        ledger = self.ledger_event_manager
        if ledger is None:
            logger.error("AgreementsManager: no ledger_event_manager - no ledger events written for %s",
                         agreement["agreement_id"])
            return {c["component_key"]: None for c in components}
        timestamp = message_timestamp if message_timestamp is not None else int(now_local().timestamp())
        out: Dict[str, Optional[str]] = {}
        for component in components:
            try:
                event_id = ledger.add_ledger_event(
                    session_id=session_id, event=self._ledger_event(agreement, component),
                    message_id=message_id, message_timestamp=timestamp,
                    agreement_id=agreement["agreement_id"],
                )
            except Exception:  # noqa: BLE001 - DB already committed; log loudly, do not raise
                logger.error("AgreementsManager: ledger write failed for %s/%s",
                             agreement["agreement_id"], component["label"], exc_info=True)
                event_id = None
            out[component["component_key"]] = event_id
        return out

    def _record_origin_events(self, conn: sqlite3.Connection, event_ids: Dict[str, Optional[str]]) -> None:
        for component_key, event_id in event_ids.items():
            if event_id is not None:
                conn.execute(
                    "UPDATE components SET origin_event_id = COALESCE(origin_event_id, ?) WHERE component_key = ?",
                    (event_id, component_key),
                )

    def _add_revision(
        self, conn: sqlite3.Connection, agreement_id: str, component_key: Optional[str], actor: str,
        action: str, snapshot: Dict[str, Any], changed: Dict[str, Any], event_ids: List[str],
    ) -> int:
        cursor = conn.execute(
            "INSERT INTO revisions (agreement_id, component_key, actor, action, snapshot_json, "
            "changed_json, ledger_event_ids_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (agreement_id, component_key, actor, action,
             json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
             json.dumps(changed, ensure_ascii=False, sort_keys=True),
             json.dumps(event_ids), local_isoformat()),
        )
        return int(cursor.lastrowid or 0)

    def _set_revision_events(self, conn: sqlite3.Connection, revision_id: int, event_ids: List[str]) -> None:
        conn.execute("UPDATE revisions SET ledger_event_ids_json = ? WHERE revision_id = ?",
                     (json.dumps(event_ids), revision_id))

    def _finish_write(
        self, conn: sqlite3.Connection, agreement_id: str, revision_id: int, *,
        components_to_log: List[str], session_id: Optional[str] = None, message_id: Optional[str] = None,
        message_timestamp: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Writes ledger events for the given component keys (current state), stores their
        ids on the revision and as origin ids, returns (agreement dict, event ids)."""
        conn.commit()  # DB first (REQ-089-01): the ledger events follow the committed write
        agreement = self._agreement_dict(conn, agreement_id)
        wanted = [c for c in agreement["components"] if c["component_key"] in components_to_log]
        event_map = self._write_ledger_events(
            agreement, wanted, session_id=session_id, message_id=message_id,
            message_timestamp=message_timestamp,
        )
        self._record_origin_events(conn, event_map)
        event_ids = [e for e in event_map.values() if e is not None]
        self._set_revision_events(conn, revision_id, event_ids)
        conn.commit()
        if len(event_ids) != len(wanted):
            logger.error("AgreementsManager: %d of %d ledger events missing for revision %s of %s",
                         len(wanted) - len(event_ids), len(wanted), revision_id, agreement_id)
        return self._agreement_dict(conn, agreement_id), event_ids

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    def create_agreement(
        self, *, client_name: str, title: str, components: List[Dict[str, Any]], actor: str,
        payer_name: Optional[str] = None, partner_name: Optional[str] = None,
        partner_percent: Any = None, agreement_id: Optional[str] = None,
        session_id: Optional[str] = None, message_id: Optional[str] = None,
        message_timestamp: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Creates an agreement with >=1 component. Returns (agreement, ledger_event_ids)."""
        self._check_actor(actor)
        errors: Dict[str, str] = {}
        client_name = _clean_text(client_name) or ""
        title = _clean_text(title) or ""
        if not client_name:
            errors["client_name"] = "required"
        if not title:
            errors["title"] = "required"
        if not components:
            errors["components"] = "at least one component is required"
        if errors:
            raise ValidationError("invalid agreement", errors)
        percent = _to_percent(partner_percent, "partner_percent")
        cleaned = [self._normalize_component_input(c, require_value=True) for c in components]
        with self._lock, self._connect() as conn:
            self._require_ledger_slots(len(cleaned), message_timestamp)
            agreement_id = agreement_id or self._make_agreement_id(client_name, title)
            if conn.execute("SELECT 1 FROM agreements WHERE agreement_id = ?", (agreement_id,)).fetchone():
                raise ValidationError(f"agreement {agreement_id!r} already exists",
                                      {"title": "an agreement with this title already exists for the client this month"})
            now = local_isoformat()
            conn.execute(
                "INSERT INTO agreements (agreement_id, title, client_name, payer_name, partner_name, "
                "partner_percent, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (agreement_id, title, client_name, _clean_text(payer_name), _clean_text(partner_name),
                 percent, ACTIVE, now, now),
            )
            keys: List[str] = []
            for order, fields in enumerate(cleaned):
                component_id = self._assert_label_free(conn, agreement_id, fields["label"])
                key = uuid.uuid4().hex
                keys.append(key)
                conn.execute(
                    "INSERT INTO components (component_key, component_id, agreement_id, label, description, "
                    "amount, percent, percent_base, trigger_condition, vat_status, txn_date, status, "
                    "origin_event_id, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (key, component_id, agreement_id, fields["label"], fields.get("description"),
                     fields.get("amount"), fields.get("percent"), fields.get("percent_base"),
                     fields.get("trigger_condition"), fields.get("vat_status"), fields.get("txn_date"),
                     self._default_status(fields.get("trigger_condition")), None, order),
                )
            snapshot = self._agreement_dict(conn, agreement_id)
            revision_id = self._add_revision(conn, agreement_id, None, actor, "create_agreement",
                                             snapshot, {"created": True}, [])
            return self._finish_write(conn, agreement_id, revision_id, components_to_log=keys,
                                      session_id=session_id, message_id=message_id,
                                      message_timestamp=message_timestamp)

    def edit_agreement(self, agreement_id: str, fields: Dict[str, Any], actor: str,
                       **ledger_kwargs: Any) -> Tuple[Dict[str, Any], List[str]]:
        """Edits payer / partner / partner %. One ledger event per component when anything changed."""
        self._check_actor(actor)
        unknown = [k for k in fields if k not in AGREEMENT_EDITABLE_FIELDS]
        if unknown:
            raise ValidationError("unsupported field(s)", {k: "not editable" for k in unknown})
        with self._lock, self._connect() as conn:
            current = self._agreement_dict(conn, agreement_id)
            new_values: Dict[str, Any] = {}
            if "payer_name" in fields:
                new_values["payer_name"] = _clean_text(fields["payer_name"])
            if "partner_name" in fields:
                new_values["partner_name"] = _clean_text(fields["partner_name"])
            if "partner_percent" in fields:
                new_values["partner_percent"] = _to_percent(fields["partner_percent"], "partner_percent")
            changed = {k: [current[k], v] for k, v in new_values.items() if current[k] != v}
            if not changed:
                return current, []
            self._require_ledger_slots(len(current["components"]), ledger_kwargs.get("message_timestamp"))
            sets = ", ".join(f"{k} = ?" for k in changed)
            conn.execute(f"UPDATE agreements SET {sets}, updated_at = ? WHERE agreement_id = ?",  # noqa: S608
                         [new_values[k] for k in changed] + [local_isoformat(), agreement_id])
            snapshot = self._agreement_dict(conn, agreement_id)
            revision_id = self._add_revision(conn, agreement_id, None, actor, "edit_agreement", snapshot, changed, [])
            return self._finish_write(
                conn, agreement_id, revision_id,
                components_to_log=[c["component_key"] for c in snapshot["components"]], **ledger_kwargs,
            )

    def add_component(self, agreement_id: str, data: Dict[str, Any], actor: str,
                      **ledger_kwargs: Any) -> Tuple[Dict[str, Any], List[str]]:
        self._check_actor(actor)
        fields = self._normalize_component_input(data, require_value=True)
        with self._lock, self._connect() as conn:
            agreement = self._agreement_dict(conn, agreement_id)
            if agreement["status"] != ACTIVE:
                raise LockedError("the agreement is closed - reopen it before adding components")
            self._require_ledger_slots(1, ledger_kwargs.get("message_timestamp"))
            component_id = self._assert_label_free(conn, agreement_id, fields["label"])
            key = uuid.uuid4().hex
            order = len(agreement["components"])
            conn.execute(
                "INSERT INTO components (component_key, component_id, agreement_id, label, description, "
                "amount, percent, percent_base, trigger_condition, vat_status, txn_date, status, "
                "origin_event_id, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, component_id, agreement_id, fields["label"], fields.get("description"),
                 fields.get("amount"), fields.get("percent"), fields.get("percent_base"),
                 fields.get("trigger_condition"), fields.get("vat_status"), fields.get("txn_date"),
                 self._default_status(fields.get("trigger_condition")), None, order),
            )
            conn.execute("UPDATE agreements SET updated_at = ? WHERE agreement_id = ?",
                         (local_isoformat(), agreement_id))
            snapshot = self._component_snapshot(conn, agreement_id, key)
            revision_id = self._add_revision(conn, agreement_id, key, actor, "add_component", snapshot,
                                             {"created": True}, [])
            return self._finish_write(conn, agreement_id, revision_id, components_to_log=[key], **ledger_kwargs)

    def _component_snapshot(self, conn: sqlite3.Connection, agreement_id: str, key: str) -> Dict[str, Any]:
        agreement = self._agreement_dict(conn, agreement_id)
        for comp in agreement["components"]:
            if comp["component_key"] == key:
                return comp
        raise NotFoundError(f"component {key!r} not found")

    def edit_component(self, agreement_id: str, component_key: str, fields: Dict[str, Any], actor: str,
                       **ledger_kwargs: Any) -> Tuple[Dict[str, Any], List[str]]:
        self._check_actor(actor)
        unknown = [k for k in fields if k not in COMPONENT_EDITABLE_FIELDS]
        if unknown:
            raise ValidationError("unsupported field(s)", {k: "not editable" for k in unknown})
        cleaned = self._normalize_component_input(fields, require_value=False)
        with self._lock, self._connect() as conn:
            agreement = self._agreement_dict(conn, agreement_id)
            row = self._component_row(conn, agreement_id, component_key)
            comp = self._component_dict(row, agreement["status"])
            if comp["locked"]:
                raise LockedError("the component is locked")
            changed = {k: [comp[k], v] for k, v in cleaned.items() if comp[k] != v}
            if not changed:
                return agreement, []
            merged_amount = cleaned["amount"] if "amount" in cleaned else comp["amount"]
            merged_percent = cleaned["percent"] if "percent" in cleaned else comp["percent"]
            if merged_amount is None and merged_percent is None:
                raise ValidationError("a component needs an amount or a percent",
                                      {"amount": "amount or percent is required"})
            self._require_ledger_slots(1, ledger_kwargs.get("message_timestamp"))
            updates = dict(cleaned)
            if "label" in changed:
                updates["component_id"] = self._assert_label_free(conn, agreement_id, cleaned["label"], component_key)
            sets = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE components SET {sets} WHERE component_key = ?",  # noqa: S608
                         list(updates.values()) + [component_key])
            conn.execute("UPDATE agreements SET updated_at = ? WHERE agreement_id = ?",
                         (local_isoformat(), agreement_id))
            snapshot = self._component_snapshot(conn, agreement_id, component_key)
            revision_id = self._add_revision(conn, agreement_id, component_key, actor, "edit_component",
                                             snapshot, changed, [])
            return self._finish_write(conn, agreement_id, revision_id, components_to_log=[component_key],
                                      **ledger_kwargs)

    def set_component_status(self, agreement_id: str, component_key: str, action: str, actor: str,
                             **ledger_kwargs: Any) -> Tuple[Dict[str, Any], List[str]]:
        self._check_actor(actor)
        if action not in COMPONENT_ACTIONS:
            raise ValidationError(f"action must be one of {list(COMPONENT_ACTIONS)}", {"action": "invalid"})
        with self._lock, self._connect() as conn:
            agreement = self._agreement_dict(conn, agreement_id)
            row = self._component_row(conn, agreement_id, component_key)
            current = row["status"]
            if agreement["status"] != ACTIVE:
                raise LockedError("the agreement is closed - reopen it first")
            target = self._component_target(current, action)
            self._require_ledger_slots(1, ledger_kwargs.get("message_timestamp"))
            conn.execute("UPDATE components SET status = ? WHERE component_key = ?", (target, component_key))
            conn.execute("UPDATE agreements SET updated_at = ? WHERE agreement_id = ?",
                         (local_isoformat(), agreement_id))
            snapshot = self._component_snapshot(conn, agreement_id, component_key)
            revision_id = self._add_revision(conn, agreement_id, component_key, actor, "set_component_status",
                                             snapshot, {"status": [current, target]}, [])
            return self._finish_write(conn, agreement_id, revision_id, components_to_log=[component_key],
                                      **ledger_kwargs)

    @staticmethod
    def _component_target(current: str, action: str) -> str:
        legal = {
            "activate": ({PENDING}, ACTIVE),
            "complete": ({ACTIVE}, COMPLETED),
            "cancel": ({PENDING, ACTIVE}, CANCELLED),
            "reopen": ({COMPLETED, CANCELLED}, ACTIVE),
        }
        sources, target = legal[action]
        if current not in sources:
            if current in (COMPLETED, CANCELLED) and action != "reopen":
                raise LockedError(f"the component is {current} - only Reopen is available")
            raise IllegalTransitionError(f"cannot {action} a component that is {current}")
        return target

    def set_agreement_status(self, agreement_id: str, action: str, actor: str,
                             **ledger_kwargs: Any) -> Tuple[Dict[str, Any], List[str]]:
        """complete / cancel (with the component cascade) / reopen (agreement only)."""
        self._check_actor(actor)
        if action not in AGREEMENT_ACTIONS:
            raise ValidationError(f"action must be one of {list(AGREEMENT_ACTIONS)}", {"action": "invalid"})
        with self._lock, self._connect() as conn:
            agreement = self._agreement_dict(conn, agreement_id)
            current = agreement["status"]
            changed: Dict[str, Any] = {}
            if action == "reopen":
                if current == ACTIVE:
                    raise IllegalTransitionError("the agreement is already Active")
                target = ACTIVE
            else:
                if current != ACTIVE:
                    raise IllegalTransitionError(f"cannot {action} an agreement that is {current}")
                target = COMPLETED if action == "complete" else CANCELLED
            self._require_ledger_slots(len(agreement["components"]), ledger_kwargs.get("message_timestamp"))
            if action != "reopen":
                for comp in agreement["components"]:
                    new_status = self._cascade_status(target, comp["status"])
                    if new_status != comp["status"]:
                        conn.execute("UPDATE components SET status = ? WHERE component_key = ?",
                                     (new_status, comp["component_key"]))
                        changed[comp["component_key"]] = [comp["status"], new_status]
            conn.execute("UPDATE agreements SET status = ?, updated_at = ? WHERE agreement_id = ?",
                         (target, local_isoformat(), agreement_id))
            snapshot = self._agreement_dict(conn, agreement_id)
            revision_id = self._add_revision(
                conn, agreement_id, None, actor,
                "cascade" if changed else "set_agreement_status", snapshot,
                {"status": [current, target], "components": changed}, [])
            return self._finish_write(
                conn, agreement_id, revision_id,
                components_to_log=[c["component_key"] for c in snapshot["components"]], **ledger_kwargs)

    @staticmethod
    def _cascade_status(agreement_target: str, component_status: str) -> str:
        """Close cascade (human decision 2026-10-09)."""
        if component_status in (COMPLETED, CANCELLED):
            return component_status
        if agreement_target == COMPLETED:
            return COMPLETED if component_status == ACTIVE else CANCELLED  # Pending -> Cancelled
        return CANCELLED  # agreement Cancelled: every non-Completed component

    def delete_component(self, agreement_id: str, component_key: str, actor: str,
                         **ledger_kwargs: Any) -> Tuple[Dict[str, Any], List[str]]:
        """Hard delete; pushes one `ביטול` event referencing the component's original event."""
        self._check_actor(actor)
        with self._lock, self._connect() as conn:
            agreement = self._agreement_dict(conn, agreement_id)
            row = self._component_row(conn, agreement_id, component_key)
            comp = self._component_dict(row, agreement["status"])
            if comp["locked"]:
                raise LockedError("the component is locked")
            self._require_ledger_slots(1, ledger_kwargs.get("message_timestamp"))
            conn.execute("DELETE FROM components WHERE component_key = ?", (component_key,))
            conn.execute("UPDATE agreements SET updated_at = ? WHERE agreement_id = ?",
                         (local_isoformat(), agreement_id))
            revision_id = self._add_revision(conn, agreement_id, component_key, actor, "delete_component",
                                             comp, {"deleted": True}, [])
            conn.commit()  # DB first, then the ledger event
            after = self._agreement_dict(conn, agreement_id)
            event_ids: List[str] = []
            ledger = self.ledger_event_manager
            if ledger is not None:
                event = self._ledger_event(after, comp)
                event["event_subtype"] = _LEDGER_SUBTYPE_DELETE
                timestamp = ledger_kwargs.get("message_timestamp")
                try:
                    event_id = ledger.add_ledger_event(
                        session_id=ledger_kwargs.get("session_id"), event=event,
                        message_id=ledger_kwargs.get("message_id"),
                        message_timestamp=timestamp if timestamp is not None else int(now_local().timestamp()),
                        agreement_id=agreement_id, reference_override=comp["origin_event_id"],
                    )
                except Exception:  # noqa: BLE001
                    logger.error("AgreementsManager: ledger delete event failed for %s", agreement_id,
                                 exc_info=True)
                    event_id = None
                if event_id:
                    event_ids.append(event_id)
            self._set_revision_events(conn, revision_id, event_ids)
            conn.commit()
            return after, event_ids

    # ------------------------------------------------------------------ #
    # Capture (WhatsApp / documents) and migration entry points
    # ------------------------------------------------------------------ #

    def create_from_capture(
        self, event: Dict[str, Any], session_id: Optional[str], message_id: Optional[str],
        message_timestamp: Optional[int],
    ) -> List[str]:
        """The shared post-turn agreement capture (called from LedgerEventManager.
        persist_recognized_event for `הסכם` verdicts). `event` is the assembled recognition
        event: agreement-level fields (client_name, description = the agreement's title,
        payer_name, vat_status, agreement_id) plus a `components` list. Components with
        `hours` are hours-worked lines and stay ledger-only; the rest become agreement
        components. If the agreement already exists, matching labels are amended in place
        and new labels are added. A capture the DB cannot accept (e.g. a missing client name
        or a component with neither amount nor percent) is never dropped: it falls back to the
        flagged ledger-only path the ledger always used. Returns every ledger event id."""
        shared = {k: v for k, v in event.items() if k not in ("components", "component_count")}
        components = event.get("components") or []
        priced, work_lines = [], []
        for component in components:
            (work_lines if not _blank({**shared, **component}.get("hours")) else priced).append(component)
        ledger_kwargs = {"session_id": session_id, "message_id": message_id, "message_timestamp": message_timestamp}
        event_ids: List[str] = []
        ledger_only = list(work_lines)

        if priced:
            merged = [{**shared, **c} for c in priced]
            try:
                component_inputs = [self._capture_component(c) for c in merged]
                event_ids.extend(self._capture_into_db(shared, component_inputs, ledger_kwargs))
            except AgreementsError as exc:
                logger.error("create_from_capture: the Agreements DB refused this capture (%s %s) - "
                             "falling back to the ledger-only path so nothing is lost",
                             exc.code, exc.fields)
                ledger_only = list(components)

        if ledger_only:
            ledger = self.ledger_event_manager
            if ledger is not None:
                event_ids.extend(ledger.add_ledger_events_from_call(
                    session_id=session_id,
                    call_arguments={**shared, "components": ledger_only, "component_count": len(ledger_only)},
                    message_id=message_id, message_timestamp=message_timestamp,
                ))
        return event_ids

    def _capture_into_db(self, shared: Dict[str, Any], component_inputs: List[Dict[str, Any]],
                         ledger_kwargs: Dict[str, Any]) -> List[str]:
        client_name = _clean_text(shared.get("client_name")) or ""
        title = _clean_text(shared.get("description")) or "הסכם"
        agreement_id = shared.get("agreement_id")
        with self._lock:
            existing = None
            if agreement_id:
                try:
                    existing = self.get_agreement(agreement_id)
                except NotFoundError:
                    existing = None
            if existing is None:
                _, ids = self.create_agreement(
                    client_name=client_name, title=title, components=component_inputs, actor="whatsapp",
                    payer_name=shared.get("payer_name"), agreement_id=agreement_id, **ledger_kwargs)
                return ids
            return self._amend_from_capture(existing, shared, component_inputs, ledger_kwargs)

    @staticmethod
    def _capture_component(merged: Dict[str, Any]) -> Dict[str, Any]:
        label = merged.get("component_label") or merged.get("description") or "רכיב"
        return {
            "label": label,
            "description": merged.get("description"),
            "amount": merged.get("amount"),
            "percent": merged.get("percent"),
            "percent_base": merged.get("percent_base"),
            "trigger_condition": merged.get("trigger_condition"),
            "vat_status": merged.get("vat_status"),
            "txn_date": merged.get("txn_date"),
        }

    def _amend_from_capture(self, existing: Dict[str, Any], shared: Dict[str, Any],
                            component_inputs: List[Dict[str, Any]], ledger_kwargs: Dict[str, Any]) -> List[str]:
        event_ids: List[str] = []
        agreement_id = existing["agreement_id"]
        payer = _clean_text(shared.get("payer_name"))
        if payer is not None and payer != existing["payer_name"]:
            _, ids = self.edit_agreement(agreement_id, {"payer_name": payer}, "whatsapp")
            event_ids.extend(ids)
        by_id = {c["component_id"]: c for c in existing["components"]}
        for data in component_inputs:
            cid = f"{agreement_id}-{_slugify(data['label'])}"
            current = by_id.get(cid)
            try:
                if current is None:
                    _, ids = self.add_component(agreement_id, data, "whatsapp", **ledger_kwargs)
                else:
                    _, ids = self.edit_component(agreement_id, current["component_key"], {
                        k: data.get(k) for k in COMPONENT_EDITABLE_FIELDS if k != "label" and k in data
                    }, "whatsapp", **ledger_kwargs)
                event_ids.extend(ids)
            except LockedError:
                logger.warning("create_from_capture: component %s of %s is locked - capture skipped for it",
                               cid, agreement_id)
        return event_ids
