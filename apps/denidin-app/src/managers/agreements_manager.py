"""
AgreementsManager - the Agreements DB (Feature 089).

The living source of truth for fee agreements: an agreement container holding fee
components and a four-state component lifecycle. Owns
{data_root}/agreements/agreements.db (SQLite - same precedent as reminders.db and
chat_index.db).

Every write, from the webapp (through the Agreements API), the WhatsApp bot, or the
one-time migration, goes through this class: it validates, applies the state rules and
the agreement-close cascade, commits the DB change in one transaction,
and THEN writes the matching ledger events (one `הסכם` event per affected component) via
LedgerEventManager. Nobody else writes agreement ledger events or touches the SQLite
file. Last write wins: every write is serialized under one lock, no version precondition.

Hours-worked lines (a `הסכם` ledger event with `hours`) are never components - they stay
ledger-only (REQ-089-13). See specs/repo/features/089-ui-agreement-edits/data-model.md.
"""

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, cast

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
AGREEMENT_EDITABLE_FIELDS = ("title", "agreement_description", "payer_name", "partner_name", "partner_percent")
COMPONENT_EDITABLE_FIELDS = (
    "label", "description", "amount", "percent", "percent_base",
    "trigger_condition", "vat_status",
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
                    row_id          TEXT PRIMARY KEY,
                    agreement_id    TEXT NOT NULL,
                    title           TEXT NOT NULL,
                    agreement_description TEXT,
                    client_name     TEXT NOT NULL,
                    payer_name      TEXT,
                    partner_name    TEXT,
                    partner_percent REAL,
                    status          TEXT NOT NULL,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    is_active       INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS components (
                    component_key     TEXT PRIMARY KEY,
                    component_id      TEXT NOT NULL,
                    agreement_id      TEXT NOT NULL,
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
                    sort_order        INTEGER NOT NULL,
                    is_active         INTEGER NOT NULL DEFAULT 1
                );
                CREATE INDEX IF NOT EXISTS idx_components_agreement ON components(agreement_id);
                """
            )
            self._upgrade_legacy_schema(conn)
            if "agreement_description" not in {r["name"] for r in conn.execute("PRAGMA table_info(agreements)").fetchall()}:
                conn.execute("ALTER TABLE agreements ADD COLUMN agreement_description TEXT")  # added 2026-10-13
            # An agreement_id only has to be unique among ACTIVE rows: a deleted agreement's id can be reused.
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agreements_active_id "
                         "ON agreements(agreement_id) WHERE is_active = 1")

    @staticmethod
    def _upgrade_legacy_schema(conn: sqlite3.Connection) -> None:
        """Databases created before `is_active` / the internal `row_id` existed: add the flag
        (existing rows = active) and rebuild `agreements` with a uuid primary key."""
        for table in ("agreements", "components"):
            columns = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}  # noqa: S608
            if "is_active" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")  # noqa: S608
        conn.execute("PRAGMA foreign_keys = OFF")
        # `components.agreement_id` used to be a FOREIGN KEY on agreements(agreement_id), which is no
        # longer unique across deleted rows: rebuild the table without the constraint.
        if conn.execute("PRAGMA foreign_key_list(components)").fetchall():
            conn.execute("ALTER TABLE components RENAME TO components_legacy")
            conn.execute(
                """CREATE TABLE components (
                    component_key TEXT PRIMARY KEY, component_id TEXT NOT NULL, agreement_id TEXT NOT NULL,
                    label TEXT NOT NULL, description TEXT, amount INTEGER, percent REAL, percent_base TEXT,
                    trigger_condition TEXT, vat_status TEXT, txn_date TEXT, status TEXT NOT NULL,
                    origin_event_id TEXT, sort_order INTEGER NOT NULL, is_active INTEGER NOT NULL DEFAULT 1)"""
            )
            conn.execute("INSERT INTO components SELECT component_key, component_id, agreement_id, label, "
                         "description, amount, percent, percent_base, trigger_condition, vat_status, txn_date, "
                         "status, origin_event_id, sort_order, is_active FROM components_legacy")
            conn.execute("DROP TABLE components_legacy")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_components_agreement ON components(agreement_id)")
        if "row_id" in {r["name"] for r in conn.execute("PRAGMA table_info(agreements)").fetchall()}:
            conn.execute("PRAGMA foreign_keys = ON")
            return
        conn.execute("ALTER TABLE agreements RENAME TO agreements_legacy")
        conn.execute(
            """CREATE TABLE agreements (
                row_id TEXT PRIMARY KEY, agreement_id TEXT NOT NULL, title TEXT NOT NULL, client_name TEXT NOT NULL,
                payer_name TEXT, partner_name TEXT, partner_percent REAL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1)"""
        )
        for old in conn.execute("SELECT * FROM agreements_legacy").fetchall():
            conn.execute(
                "INSERT INTO agreements (row_id, agreement_id, title, client_name, payer_name, partner_name, "
                "partner_percent, status, created_at, updated_at, is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, old["agreement_id"], old["title"], old["client_name"], old["payer_name"],
                 old["partner_name"], old["partner_percent"], old["status"], old["created_at"], old["updated_at"],
                 old["is_active"]),
            )
        conn.execute("DROP TABLE agreements_legacy")
        conn.execute("PRAGMA foreign_keys = ON")

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
            "status": row["status"],
            "origin_event_id": row["origin_event_id"],
            "locked": locked,
        }

    def _agreement_dict(self, conn: sqlite3.Connection, agreement_id: str) -> Dict[str, Any]:
        row = conn.execute("SELECT * FROM agreements WHERE agreement_id = ? AND is_active = 1",
                           (agreement_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"agreement {agreement_id!r} not found")
        comps = conn.execute(
            "SELECT * FROM components WHERE agreement_id = ? AND is_active = 1 ORDER BY sort_order, rowid",
            (agreement_id,)
        ).fetchall()
        return {
            "agreement_id": row["agreement_id"],
            "title": row["title"],
            "agreement_description": row["agreement_description"],
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
            "SELECT * FROM components WHERE agreement_id = ? AND component_key = ? AND is_active = 1",
            (agreement_id, component_key),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"component {component_key!r} not found in agreement {agreement_id!r}")
        return cast(sqlite3.Row, row)

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
                "SELECT agreement_id FROM agreements WHERE TRIM(client_name) = ? AND is_active = 1 "
                "ORDER BY created_at, rowid",
                (wanted,),
            ).fetchall()]
            return [self._agreement_dict(conn, i) for i in ids]

    def list_agreements(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            ids = [r["agreement_id"] for r in conn.execute(
                "SELECT agreement_id FROM agreements WHERE is_active = 1 ORDER BY client_name, created_at, rowid"
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
                WHERE c.status != ? AND c.amount IS NOT NULL AND c.is_active = 1 AND a.is_active = 1
                GROUP BY TRIM(a.client_name)
                """,
                (CANCELLED,),
            ).fetchall()
        return {r["client_name"]: int(r["total"] or 0) for r in rows}

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #

    def _normalize_component_input(self, data: Dict[str, Any], *, require_value: bool) -> Dict[str, Any]:
        """Returns the cleaned component fields present in `data` (only keys given)."""
        fields: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        for key in ("label", "description", "percent_base", "trigger_condition", "vat_status"):
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
            "SELECT component_key FROM components WHERE agreement_id = ? AND component_id = ? AND is_active = 1",
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

    def _finish_write(
        self, conn: sqlite3.Connection, agreement_id: str, *,
        components_to_log: List[str], session_id: Optional[str] = None, message_id: Optional[str] = None,
        message_timestamp: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Writes ledger events for the given component keys (current state), stores their
        ids as origin ids, returns (agreement dict, event ids)."""
        conn.execute("UPDATE agreements SET updated_at = ? WHERE agreement_id = ? AND is_active = 1",
                     (local_isoformat(), agreement_id))  # "last modified" covers its components too
        conn.commit()  # DB first (REQ-089-01): the ledger events follow the committed write
        agreement = self._agreement_dict(conn, agreement_id)
        wanted = [c for c in agreement["components"] if c["component_key"] in components_to_log]
        event_map = self._write_ledger_events(
            agreement, wanted, session_id=session_id, message_id=message_id,
            message_timestamp=message_timestamp,
        )
        self._record_origin_events(conn, event_map)
        event_ids = [e for e in event_map.values() if e is not None]
        conn.commit()
        if len(event_ids) != len(wanted):
            logger.error("AgreementsManager: %d of %d ledger events missing for a write to %s",
                         len(wanted) - len(event_ids), len(wanted), agreement_id)
        return self._agreement_dict(conn, agreement_id), event_ids

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    def create_agreement(
        self, *, client_name: str, title: str, components: List[Dict[str, Any]], actor: str,
        payer_name: Optional[str] = None, partner_name: Optional[str] = None,
        partner_percent: Any = None, agreement_id: Optional[str] = None,
        session_id: Optional[str] = None, message_id: Optional[str] = None,
        message_timestamp: Optional[int] = None, agreement_description: Optional[str] = None,
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
            if conn.execute("SELECT 1 FROM agreements WHERE agreement_id = ? AND is_active = 1",
                            (agreement_id,)).fetchone():
                raise ValidationError(f"agreement {agreement_id!r} already exists",
                                      {"title": "an agreement with this title already exists for the client this month"})
            now = local_isoformat()
            conn.execute(
                "INSERT INTO agreements (row_id, agreement_id, title, agreement_description, client_name, "
                "payer_name, partner_name, partner_percent, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, agreement_id, title, _clean_text(agreement_description), client_name,
                 _clean_text(payer_name), _clean_text(partner_name), percent, ACTIVE, now, now),
            )
            keys: List[str] = []
            for order, fields in enumerate(cleaned):
                component_id = self._assert_label_free(conn, agreement_id, fields["label"])
                key = uuid.uuid4().hex
                keys.append(key)
                conn.execute(
                    "INSERT INTO components (component_key, component_id, agreement_id, label, description, "
                    "amount, percent, percent_base, trigger_condition, vat_status, status, "
                    "origin_event_id, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (key, component_id, agreement_id, fields["label"], fields.get("description"),
                     fields.get("amount"), fields.get("percent"), fields.get("percent_base"),
                     fields.get("trigger_condition"), fields.get("vat_status"),
                     self._default_status(fields.get("trigger_condition")), None, order),
                )
            return self._finish_write(conn, agreement_id, components_to_log=keys,
                                      session_id=session_id, message_id=message_id,
                                      message_timestamp=message_timestamp)

    def edit_agreement(self, agreement_id: str, fields: Dict[str, Any], actor: str,
                       **ledger_kwargs: Any) -> Tuple[Dict[str, Any], List[str]]:
        """Edits title / description / payer / partner / partner %. One ledger event per component when anything changed
        (the description is DB-only: it is not part of the approved ledger event fields)."""
        self._check_actor(actor)
        unknown = [k for k in fields if k not in AGREEMENT_EDITABLE_FIELDS]
        if unknown:
            raise ValidationError("unsupported field(s)", {k: "not editable" for k in unknown})
        with self._lock, self._connect() as conn:
            current = self._agreement_dict(conn, agreement_id)
            new_values: Dict[str, Any] = {}
            if "title" in fields:
                title = _clean_text(fields["title"])
                if title is None:
                    raise ValidationError("invalid agreement", {"title": "required"})
                new_values["title"] = title
            if "agreement_description" in fields:
                new_values["agreement_description"] = _clean_text(fields["agreement_description"])
            if "payer_name" in fields:
                new_values["payer_name"] = _clean_text(fields["payer_name"])
            if "partner_name" in fields:
                new_values["partner_name"] = _clean_text(fields["partner_name"])
            if "partner_percent" in fields:
                new_values["partner_percent"] = _to_percent(fields["partner_percent"], "partner_percent")
            changed = {k: [current[k], v] for k, v in new_values.items() if current[k] != v}
            if not changed:
                return current, []
            ledger_visible = any(k not in ("title", "agreement_description") for k in changed)
            if ledger_visible:
                self._require_ledger_slots(len(current["components"]), ledger_kwargs.get("message_timestamp"))
            sets = ", ".join(f"{k} = ?" for k in changed)
            conn.execute(f"UPDATE agreements SET {sets}, updated_at = ? WHERE agreement_id = ? AND is_active = 1",  # noqa: S608
                         [new_values[k] for k in changed] + [local_isoformat(), agreement_id])
            if not ledger_visible:  # title / description never appear in a ledger event: DB only
                conn.commit()
                return self._agreement_dict(conn, agreement_id), []
            return self._finish_write(
                conn, agreement_id,
                components_to_log=[c["component_key"] for c in current["components"]], **ledger_kwargs,
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
                "amount, percent, percent_base, trigger_condition, vat_status, status, "
                "origin_event_id, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, component_id, agreement_id, fields["label"], fields.get("description"),
                 fields.get("amount"), fields.get("percent"), fields.get("percent_base"),
                 fields.get("trigger_condition"), fields.get("vat_status"),
                 self._default_status(fields.get("trigger_condition")), None, order),
            )
            conn.execute("UPDATE agreements SET updated_at = ? WHERE agreement_id = ? AND is_active = 1",
                         (local_isoformat(), agreement_id))
            return self._finish_write(conn, agreement_id, components_to_log=[key], **ledger_kwargs)

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
            conn.execute("UPDATE agreements SET updated_at = ? WHERE agreement_id = ? AND is_active = 1",
                         (local_isoformat(), agreement_id))
            return self._finish_write(conn, agreement_id, components_to_log=[component_key],
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
            conn.execute("UPDATE agreements SET updated_at = ? WHERE agreement_id = ? AND is_active = 1",
                         (local_isoformat(), agreement_id))
            return self._finish_write(conn, agreement_id, components_to_log=[component_key],
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
            conn.execute("UPDATE agreements SET status = ?, updated_at = ? WHERE agreement_id = ? AND is_active = 1",
                         (target, local_isoformat(), agreement_id))
            return self._finish_write(
                conn, agreement_id,
                components_to_log=[c["component_key"] for c in agreement["components"]], **ledger_kwargs)

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
        """Soft delete (is_active = 0, the row stays); pushes one `ביטול` event referencing the
        component's original event."""
        self._check_actor(actor)
        with self._lock, self._connect() as conn:
            agreement = self._agreement_dict(conn, agreement_id)
            row = self._component_row(conn, agreement_id, component_key)
            comp = self._component_dict(row, agreement["status"])
            if comp["locked"]:
                raise LockedError("the component is locked")
            self._require_ledger_slots(1, ledger_kwargs.get("message_timestamp"))
            conn.execute("UPDATE components SET is_active = 0 WHERE component_key = ?", (component_key,))
            conn.execute("UPDATE agreements SET updated_at = ? WHERE agreement_id = ? AND is_active = 1",
                         (local_isoformat(), agreement_id))
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
            return after, event_ids

    def delete_agreement(self, agreement_id: str, actor: str) -> None:
        """Soft delete of a whole agreement (is_active = 0 on the agreement and all its components;
        nothing is removed). Reachable only through the Agreements API - neither the UI nor
        WhatsApp offers it. Writes NO ledger events (the ledger keeps what it recorded)."""
        self._check_actor(actor)
        with self._lock, self._connect() as conn:
            self._agreement_dict(conn, agreement_id)  # NotFoundError if absent/already deleted
            conn.execute("UPDATE components SET is_active = 0 WHERE agreement_id = ? AND is_active = 1", (agreement_id,))
            conn.execute("UPDATE agreements SET is_active = 0, updated_at = ? WHERE agreement_id = ? AND is_active = 1",
                         (local_isoformat(), agreement_id))

    # ------------------------------------------------------------------ #
    # Capture (WhatsApp / documents) and migration entry points
    # ------------------------------------------------------------------ #

    def import_migrated_agreement(
        self, *, agreement_id: str, title: str, client_name: str, payer_name: Optional[str],
        partner_name: Optional[str], partner_percent: Any, status: str, components: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """One-time migration entry (REQ-089-09): stores an agreement and its components exactly
        as given - explicit statuses and `origin_event_id`s, the ledger events already exist
        (the script rewrites them in place) so NONE are written here. Raises ValidationError on a bad value or a duplicate agreement/label."""
        if status not in AGREEMENT_STATUSES:
            raise ValidationError("invalid agreement", {"status": f"must be one of {list(AGREEMENT_STATUSES)}"})
        percent = _to_percent(partner_percent, "partner_percent")
        with self._lock, self._connect() as conn:
            if conn.execute("SELECT 1 FROM agreements WHERE agreement_id = ? AND is_active = 1",
                            (agreement_id,)).fetchone():
                raise ValidationError(f"agreement {agreement_id!r} already exists", {"agreement_id": "duplicate"})
            now = local_isoformat()
            conn.execute(
                "INSERT INTO agreements (row_id, agreement_id, title, client_name, payer_name, partner_name, "
                "partner_percent, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, agreement_id, title, client_name, _clean_text(payer_name),
                 _clean_text(partner_name), percent, status, now, now),
            )
            for order, data in enumerate(components):
                if data.get("status") not in COMPONENT_STATUSES:
                    raise ValidationError("invalid component", {"status": f"must be one of {list(COMPONENT_STATUSES)}"})
                fields = self._normalize_component_input(data, require_value=True)
                component_id = self._assert_label_free(conn, agreement_id, fields["label"])
                conn.execute(
                    "INSERT INTO components (component_key, component_id, agreement_id, label, description, "
                    "amount, percent, percent_base, trigger_condition, vat_status, status, "
                    "origin_event_id, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (uuid.uuid4().hex, component_id, agreement_id, fields["label"], fields.get("description"),
                     fields.get("amount"), fields.get("percent"), fields.get("percent_base"),
                     fields.get("trigger_condition"), fields.get("vat_status"),
                     data["status"], data.get("origin_event_id"), order),
                )
            return self._agreement_dict(conn, agreement_id)

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
        priced: List[Dict[str, Any]] = []
        work_lines: List[Dict[str, Any]] = []
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
