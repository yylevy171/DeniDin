# Contract: Client-Name Cache (internal to `apps/morning-mcp-app`)

No new MCP tool, no new HTTP endpoint — this feature adds no external contract at all
(that's the point of a transparent cache). What follows is the internal module contract
between `tools.py` and the new cache module, so the interaction is still explicit per
METHODOLOGY.md §VII (Integration Contracts).

**Revised 2026-09-15 (operator design review, post-implementation)** — this whole contract
section was rewritten after the original name+id-only, always-live-on-write design was
reviewed against real usage and found to under-deliver: writes gained nothing (they still
always re-verified live), `get_client_details` could never benefit (it needs fields the
cache never stored), and `add_client`'s "already exists" failure silently discarded
information that could have populated the cache. The corrected design below is what's
actually implemented.

## Module: `src/denidin_mcp_morning/client_cache.py`

```python
class ClientCache:
    def __init__(self, db_path: Path) -> None: ...

    def lookup_exact(self, name: str) -> Optional[Client]:
        """Normalize `name` the same way `_bag_equal_words` does; return the
        FULL cached client record (name/email/phone/tax_id/address) on a
        hit, None on a miss (including an ambiguous multi-row match).
        Read-only, never touches Morning."""

    def write_through(self, client: Client) -> None:
        """Upsert one resolved client's FULL record (from add_client
        success, a live exact-match resolution, a successful update_client,
        or a TTL sweep row)."""

    def evict(self, client_id: str) -> None:
        """Remove one client_id row directly (used by `reconcile`'s
        delete-missing pass, and by write-tool stale-id recovery)."""

    def evict_by_name(self, name: str) -> None:
        """Normalize `name` and remove whatever row matches it, if any
        (no-op on a miss)."""

    def reconcile(self, clients: List[Client]) -> None:
        """Full upsert-or-delete sync against a fresh `fetch_all_clients`
        result — the periodic TTL sweep's only entry point."""
```

There is no separate `CachedClient` type — `lookup_exact` returns the app's own `Client`
model directly, since the cache now stores everything that model can hold. Storing the
full record costs zero extra Morning calls: every write path already has the full
`Client` in hand (Morning's `search_clients` — which both a live exact-match resolution
and the sweep's `fetch_all_clients` are built on — already returns full records; the
original design was simply discarding everything but name/id).

## `trust_cache`: which callers are cache-first vs always-live

`_resolve_exact_client_name`/`_require_resolved_client` (`tools.py`) — the shared gate
every client-name-consuming tool goes through — takes a `trust_cache: bool = True`
parameter:

- **`trust_cache=True` (the default)** — `resolve_client_name`, `create_invoice`,
  `create_transaction_account`, `create_combo_document`, `create_receipt`,
  `list_invoices`'s client_name resolve step, `update_client`, `get_client_details`. On a
  cache hit, the cached `Client` is returned immediately — zero Morning calls. On a miss,
  falls through to the existing live search unchanged, and a confirmed live match is
  written through (so a live-verified result still populates/refreshes the cache).
- No caller currently sets `trust_cache=False` — both tools originally carved out for
  always-live behavior (`update_client`, `get_client_details`) were brought into the
  cache-first design once the cache started storing full records (see below), so the
  parameter exists for a future caller that might need it but nothing uses it today.

### Why `update_client` and `get_client_details` are cache-first too

- **`update_client`**: the actual Morning mutation (`client.update_client(client_id,
  payload)`) is id-based, not name-based, so trusting a cached id costs nothing
  mechanically. On success, it write-throughs the FULL merged record (new fields
  overlaid on whatever the resolved client — itself possibly cache-sourced — already
  had), so a rename/detail-change done through this app is reflected immediately.
- **`get_client_details`**: this app's Morning client has no "get client by id" endpoint
  — `search_clients` is the only way to fetch a full record, and it already returns
  everything in one call. Once the cache stores full records, a cache hit here is a
  genuine, complete answer with zero Morning calls — the entire reason to expand the
  schema past name+id in the first place.

## `add_client`'s already-exists recovery

Verified live against the real sandbox, 2026-09-15: `POST /clients` on a duplicate fails
with HTTP 400, `{"errorCode": 1010, "errorMessage": "<existing client_id>"}` — Morning
hands back the existing client's own id directly. `add_client` catches this, fetches the
real existing record via `search_clients({"id": ...})` (also verified live to work),
write-throughs it, and returns the same success-shaped result the caller would have
gotten from a real creation — rather than raising and leaving the cache a permanent miss
for that client until the next sweep.

## The one new failure mode cache-first writes introduce

Under the old always-live design, a write tool's identify step always re-verified before
any mutation, so a stale identity could never reach the actual write call. Trusting a
cache hit removes that pre-check, which means the *write call itself* can now fail
because the cached `client_id` no longer exists in Morning (deleted since the cache last
saw it — a rename does NOT trigger this, since document creation is id-based, not
name-based).

Verified live against the real sandbox, 2026-09-15: `POST /documents` with a nonexistent
`client.id` fails with HTTP 400, `{"errorCode": 2411, "errorMessage": "לקוח לא קיים"}`.
`_create_document_with_stale_client_recovery` (`tools.py`) wraps `client.create_invoice`
for every id-based document-creation call site, catches exactly this error code, evicts
the stale row, and raises the existing `ClientNotFoundError` — the same recovery
instruction every other resolution failure already gives ("call resolve_client_name and
retry"). Any other Morning failure propagates unchanged.

A cache MISS is fully transparent either way, for every caller — falls through to the
same live resolution this codebase has always done.

## Background sweep: `run_cache_sweep` (`cache_sweep_service.py`, wired at server startup)

A scheduled job (APScheduler `BackgroundScheduler` + `IntervalTrigger`, matching the
established pattern `reminder_delivery_service.py`/`accounting_reconciliation_service.py`
already use in `denidin-app`) that calls `fetch_all_clients` then `cache.reconcile(...)`
on a config-driven interval (`client_cache_sweep_interval_minutes`, default 60). Only
starts when `morning_cache_enabled` is true; also runs once synchronously at startup as a
catch-up. This is the ONLY mechanism that catches a rename done entirely outside this
app (bypassing every write-through hook) — a `get_client_details`/`resolve_client_name`
read of the old name is served stale (the accepted trade-off of being cache-first) until
a sweep reconciles it. `run_cache_sweep` has no internal retry/backoff of its own: if
`fetch_all_clients` fails, `reconcile` is simply never called that tick and the cache is
left exactly as it was after the last successful sweep — not emptied — with the next
scheduled tick trying again.
