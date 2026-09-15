# Contract: Client-Name Cache (internal to `apps/morning-mcp-app`)

No new MCP tool, no new HTTP endpoint — this feature adds no external contract at all
(that's the point of a transparent cache). What follows is the internal module contract
between `tools.py` and the new cache module, so the interaction is still explicit per
METHODOLOGY.md §VII (Integration Contracts).

## Module: `src/denidin_mcp_morning/client_cache.py` (new)

```python
class ClientCache:
    def __init__(self, db_path: Path) -> None: ...

    def lookup_exact(self, name: str) -> Optional[CachedClient]:
        """Normalize `name` the same way `_bag_equal_words` does; return the
        cached (client_id, name) row on a hit, None on a miss. Read-only,
        never touches Morning."""

    def write_through(self, client: Client) -> None:
        """Upsert one resolved client (from add_client success, a Step-0
        Morning exact match on a miss, or a TTL sweep row)."""

    def evict(self, client_id: str) -> None:
        """Remove one client_id row directly (used by `reconcile`'s
        delete-missing pass)."""

    def evict_by_name(self, name: str) -> None:
        """Normalize `name` and remove whatever row matches it, if any
        (no-op on a miss). Called from `_resolve_exact_client_name` when a
        cached name fails live re-resolution (see the corrected call-site
        contract below) — the caller only ever has the name at that point,
        never a client_id."""

    def reconcile(self, clients: List[Client]) -> None:
        """Full upsert-or-delete sync against a fresh `list_clients` result
        — the periodic TTL sweep's only entry point."""


@dataclass(frozen=True)
class CachedClient:
    client_id: str
    name: str
```

## Call-site contract: `resolve_client_name` (`tools.py`, modified)

```
resolve_client_name(client, name):
    if feature_flags.morning_cache_enabled:
        hit = cache.lookup_exact(name)
        if hit is not None:
            return format_client_name_resolved(hit.name)   # identical shape to a live hit
    # unchanged from here down — existing resolve_client_by_name flow
    resolved, candidates = resolve_client_by_name(client, name)
    if resolved is not None:
        if feature_flags.morning_cache_enabled:
            cache.write_through(resolved)
        return format_client_name_resolved(resolved.name)
    ...
```

- **Output contract unchanged**: a cache hit returns the exact same
  `format_client_name_resolved(...)` string shape a live exact match already returns —
  no caller (including every `denidin-app` MCP consumer) can distinguish a hit from a
  live resolution by the response shape. This is what "transparent" means operationally.
- **Flag off**: code path is byte-for-byte identical to pre-feature behavior (no cache
  object even constructed on the hot path) — CONSTITUTION §VI.

## Call-site contract: `add_client` (`tools.py`, modified)

On success, calls `cache.write_through(new_client)` before returning — flag-gated, same as
above.

## Call-site contract: `_require_resolved_client` / `_resolve_exact_client_name` (`tools.py`, modified)

**Corrected at `speckit.tasks` time (see tasks.md's "Correction" note)**: no write tool in
this codebase ever consumes a cached `client_id` — every write call re-resolves its
`client_name` live, by name, via `_require_resolved_client` (bugfix-028 architecture
fix; REQ-CLIENT-018 also forbids ever disclosing an id to the caller in the first place).
So the real staleness surface is: a name the cache says is valid fails live re-resolution.
That is the correct eviction trigger:

```
_resolve_exact_client_name(client, name):
    resolved = <existing live lookup, unchanged>
    if resolved is None and feature_flags.morning_cache_enabled:
        cache.evict_by_name(name)   # no-op if not cached
    return resolved
```

No new exception type, no change to `_require_resolved_client`'s existing
`ClientNotFoundError` behavior or its user-facing message — eviction is a side effect on
the existing failure path, not a new outcome.

## Background sweep: `periodic_cache_sweep` (new, wired at server startup)

A new scheduled job (APScheduler `BackgroundScheduler`, matching the established pattern
`reminder_delivery_service.py`/`accounting_reconciliation_service.py` already use in
`denidin-app` — no new scheduling mechanism introduced) that calls `list_clients` then
`cache.reconcile(...)` on a config-driven interval (`config.feature_flags`-adjacent numeric
field, exact name/default decided at `speckit.tasks`). Only starts when
`morning_cache_enabled` is true.
