"""Transparent SQLite cache of Morning client names/ids (Feature 072).

See specs/repo/features/072-morning-client-name-cache/{data-model.md,
contracts/cache-contract.md} for the full design. One table, `clients`,
keyed by Morning's own `client_id`, with a unique index on a normalized
name for exact-match lookup. Not a source of truth - Morning always is;
this table only ever mirrors it (spec, "Proposed Direction & Architecture").

Name normalization here deliberately mirrors tools.py's
`_normalize_hebrew_geresh`/`_bag_equal_words` exactly (bag-of-words,
casefolded, geresh-normalized) - duplicated rather than imported to avoid a
tools.py <-> client_cache.py import cycle (tools.py is the one that will
import THIS module). Any future change to that normalization in tools.py
must be mirrored here, or an exact-match cache hit could stop matching
what resolve_client_by_name's own Step 0 would consider exact.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .models import Client
from .utils.time_utils import local_isoformat, now_local

_APOSTROPHE_VARIANTS = ("'", "’", "ʼ")
_HEBREW_GERESH = "׳"


def _normalize_hebrew_geresh(name: str) -> str:
    for variant in _APOSTROPHE_VARIANTS:
        name = name.replace(variant, _HEBREW_GERESH)
    return name


def _normalized_bag_key(name: str) -> str:
    """Bag-of-words, casefolded, geresh-normalized - order/case-independent
    cache key, matching resolve_client_by_name's own exactness criterion."""
    words = sorted(_normalize_hebrew_geresh(w.strip().casefold()) for w in name.split() if w)
    return " ".join(words)


@dataclass(frozen=True)
class CachedClient:
    """One cached client, as returned by `lookup_exact` — never exposes
    anything a caller couldn't already learn from a live resolution."""

    client_id: str
    name: str


class ClientCache:
    """Read-through cache over Morning client identities. Every method here
    is local SQLite only - it never itself calls Morning."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    client_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    name_normalized TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # Deliberately NOT unique (found live, 2026-09-15, against the real
            # sandbox's accumulated test data): Morning does not enforce unique
            # client names - two different real client_ids can legitimately
            # share the same stored name. `lookup_exact` below treats more than
            # one match for the same normalized name as an ambiguous miss
            # (falls through to live resolution), mirroring
            # resolve_client_by_name's own Step 0 exact-match discipline
            # (exactly one candidate, or it isn't a safe exact match).
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_clients_name_normalized "
                "ON clients(name_normalized)"
            )

    def lookup_exact(self, name: str) -> Optional[CachedClient]:
        """Read-only exact-match lookup. None on a miss - either no cached
        client has this normalized name, or more than one does (ambiguous -
        the cache has no authority to pick one, same as a live Morning
        search returning multiple candidates). Either way the caller falls
        through to the existing live Morning resolution unchanged."""
        key = _normalized_bag_key(name)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT client_id, name FROM clients WHERE name_normalized = ?",
                (key,),
            ).fetchall()
        if len(rows) != 1:
            return None
        return CachedClient(client_id=rows[0][0], name=rows[0][1])

    def write_through(self, client: Client) -> None:
        """Upsert one resolved client - called on add_client success or a
        live Step-0 exact Morning match (resolve_client_name's miss branch,
        so the *next* lookup for that name is a hit)."""
        if not client.id:
            raise ValueError("write_through requires a client with a real id")
        key = _normalized_bag_key(client.name)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO clients (client_id, name, name_normalized, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    name=excluded.name,
                    name_normalized=excluded.name_normalized,
                    updated_at=excluded.updated_at
                """,
                (client.id, client.name, key, local_isoformat(now_local())),
            )

    def evict(self, client_id: str) -> None:
        """Remove one row by client_id (used by `reconcile`'s delete pass).
        A no-op if the id isn't cached."""
        with self._connect() as conn:
            conn.execute("DELETE FROM clients WHERE client_id = ?", (client_id,))

    def evict_by_name(self, name: str) -> None:
        """Remove whatever row matches `name`'s normalized key, if any - the
        eviction hook used from _resolve_exact_client_name when a cached
        name fails live re-resolution (see the corrected call-site contract
        in contracts/cache-contract.md). A no-op on a miss."""
        key = _normalized_bag_key(name)
        with self._connect() as conn:
            conn.execute("DELETE FROM clients WHERE name_normalized = ?", (key,))

    def reconcile(self, clients: List[Client]) -> None:
        """Full upsert-or-delete sync against a fresh `list_clients` result
        - the periodic TTL sweep's only entry point. Clients not present in
        `clients` are deleted; clients present are upserted (catching
        renames done directly in Morning, outside DeniDin)."""
        live_ids = {c.id for c in clients if c.id}
        with self._connect() as conn:
            cached_ids = {row[0] for row in conn.execute("SELECT client_id FROM clients")}
            stale_ids = cached_ids - live_ids
            if stale_ids:
                conn.executemany(
                    "DELETE FROM clients WHERE client_id = ?",
                    [(cid,) for cid in stale_ids],
                )
            timestamp = local_isoformat(now_local())
            conn.executemany(
                """
                INSERT INTO clients (client_id, name, name_normalized, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    name=excluded.name,
                    name_normalized=excluded.name_normalized,
                    updated_at=excluded.updated_at
                """,
                [
                    (c.id, c.name, _normalized_bag_key(c.name), timestamp)
                    for c in clients
                    if c.id
                ],
            )
