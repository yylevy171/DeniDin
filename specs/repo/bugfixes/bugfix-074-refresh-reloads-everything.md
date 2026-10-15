# Bugfix 074: Any Refresh Reloads Everything

**Bugfix Branch**: `bugfix/074-refresh-reloads-everything`
**Status**: Done (2026-10-15) - PR #724. Fix lands on master; reaches prod with the next release.

## 1. Description & Business Impact

The webapp had two independent refreshes. The Events tab's button re-read the ledger event files; the Clients
tab's button only re-fetched the Morning client list and recomputed the report from the event index it already
held. A page reload re-read nothing at all, because the backend answered from memory.

Found in prod on 2026-10-15: a client created from WhatsApp (Morning client plus a `הסכם` ledger event) showed in
the Clients tab's gray "past" section, which has no buttons, and pressing the Clients refresh did not fix it. The
Morning list had the new client, but the event index predated his event, so he had no activity and was routed to
"past".

## 2. PM Requirements

- **REQ-074-01**: Every refresh reloads everything - ledger events, cached conversations, the Morning client list and
  the clients report - whichever way it is triggered:
  - a browser reload (F5 / soft refresh);
  - Ctrl+Shift+R;
  - the refresh button in any tab.
- **REQ-074-02**: After a refresh button is pressed, every tab that has been opened shows the freshly loaded data,
  not just the tab whose button was pressed.

## 3. Fix

- Backend: one `refresh_all()` (reload the ledger index, reset and re-warm the conversation cache, drop the Morning
  list and report caches). `/api/events?refresh=1` and `/api/clients?refresh=1` both call it; new `POST /api/refresh`
  (204, auth-guarded) calls only it.
- Frontend: every page load calls `POST /api/refresh` once before any view fetches; every refresh button calls it,
  then all mounted views re-read.

## 4. Tests

`backend/tests/integration/test_refresh_reloads_everything.py` (Starlette app via `TestClient`, real files on disk):
the Clients refresh reloads the ledger, the Events refresh reloads the clients, and `POST /api/refresh` does both.

## 5. Frontend / e2e notes

- The view tabs mount only after the page-load refresh completes (a "…טוען" placeholder shows meanwhile), and both
  views start with `loading = true`, so there is no moment with neither a placeholder nor a loading indicator.
- e2e: `10-clients.spec.ts` "the refresh button reloads everything" now expects `POST /api/refresh` then a plain
  `GET /api/clients`; "switching tabs never refetches" waits for the page-load requests to settle before counting.
  Main suite 257 passed, clients 16, agreements 29 (2026-10-15).
