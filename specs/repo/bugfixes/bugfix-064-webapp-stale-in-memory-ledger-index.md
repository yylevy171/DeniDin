# Bugfix 064: Stale In-Memory Index in webapp-backend Silently Drops Multi-Process Ledger Events

**Severity**: High (Data Freshness / Operational Blindspot)  
**Components**: `apps/webapp/backend/src/webapp_backend/ledger_reader.py`, `apps/denidin-app/src/managers/ledger_event_manager.py`  
**Affected Service**: `webapp-backend-prod` (Docker container `denidin-prod-webapp-backend-prod-1`)  
**Category**: Capability  

---

## 1. Problem Statement
When new ledger events are captured or reconciled in production by `denidin-app-prod` (or Morning MCP), they are written directly to disk under `{data_root}/events/{event_id}.json`. However, the webapp (`webapp-backend-prod`) NEVER shows any newly written events, regardless of whether the user hard-refreshes the page (`Cmd+Shift+R`), clicks the "רענון" (Refresh) icon, or submits a new search.

The webapp remains completely frozen on the snapshot of events that existed at the exact moment the `webapp-backend-prod` Docker container started up. In production, this caused a 48-hour operational blindspot where all events after 15/09/2026 were completely invisible in the webapp UI.

---

## 2. Architectural Root Cause & Proof
The bug stems from a leaky architectural abstraction between `LedgerEventManager` (designed for a single-process bot daemon) and `LedgerReader` in `webapp-backend` (running as a multi-process, decoupled read-only service).

### A. The One-Time Constructor Load
In `apps/denidin-app/src/managers/ledger_event_manager.py`, `LedgerEventManager` builds its in-memory index only once at construction time:
```python
# ledger_event_manager.py (Line 724)
self._index: List[Dict] = self._load_index()
```
`self._index` is only ever mutated in-process when `add_ledger_event()` is called within that same running Python process.

### B. The Deliberate "No Disk Re-Scan" in `list_events()`
In `apps/denidin-app/src/managers/ledger_event_manager.py`, Feature 068 added `list_events()` for the webapp:
```python
# ledger_event_manager.py (Lines 752-761)
def list_events(self) -> List[Dict]:
    """Feature 068: a shallow copy of every persisted ledger event's record.
    Read-only view over the same in-memory self._index that query_events
    iterates - no disk re-scan, no filtering, no ordering (callers sort/filter).
    """
    return list(self._index)
```
The docstring explicitly specifies: *"no disk re-scan"*.

### C. The Multi-Container Disconnect
In `apps/webapp/backend/src/webapp_backend/ledger_reader.py`:
```python
class LedgerReader:
    def __init__(self, data_root: str) -> None:
        self._manager = LedgerEventManager(str(Path(data_root) / "events"))
    def list_event_rows(self, days_back: int = DEFAULT_DAYS_BACK) -> Dict[str, Any]:
        ...
        for record in self._manager.list_events():  # Calls in-memory list_events()!
            ...
```
1. In production, `denidin-app-prod` is the writer (Container 1).
2. `webapp-backend-prod` is the reader (Container 2).
3. When `denidin-app-prod` writes an event to the shared bind mount (`/mnt/c/Users/Yaron Levi/denidin-prod-data/events`), `webapp-backend-prod` has no IPC or filesystem watcher.
4. When a user clicks "רענון" or changes filters, `GET /api/events` executes `LedgerReader.list_event_rows()`, which queries `self._manager.list_events()`.
5. Because `list_events()` returns `list(self._index)` with no disk re-scan, `webapp-backend-prod` serves the stale in-memory array created when its container booted.

---

## 3. Specification Conflict
In the Feature 068 design document (`specs/done/v0.7.0/068-ledger-ui-and-reports/plan.md` under Data Flow / Filtering Split), the specification promised:
> *"Load / reload (GET /events?days_back=N): server-side filter by trailing window only. This is the only query param that triggers a new read of the underlying data source."*

The spec explicitly intended for `GET /api/events` to trigger a new read of the underlying data source, but the code reused `LedgerEventManager.list_events()` without implementing the disk re-read.

---

## 4. Steps to Reproduce
1. Start `webapp-backend` in container A. It scans 1,000 events on disk into memory.
2. In container B (or via manual file addition), create a new valid ledger event `H99999999999.json` in `{data_root}/events/`.
3. In the webapp browser, click "רענון" or send an HTTP request:
   ```bash
   curl -H "Authorization: Bearer <TOKEN>" "http://localhost:8100/api/events?days_back=7"
   ```
- **Expected Result**: The returned events array includes `H99999999999`.
- **Actual Result**: The returned events array completely ignores the new file and returns only the initial 1,000 events.

---

## 5. Required Fix
In `apps/webapp/backend/src/webapp_backend/ledger_reader.py`: `LedgerReader` must refresh its event list from disk on request.

Specifically:
- Expose a clean `refresh()` or reload mechanism on `LedgerEventManager` or have `LedgerReader.list_event_rows()` re-scan the directory / reload `_index` before filtering by date.
- Re-check directory modification timestamp or reload index upon calling `list_event_rows()`.

---

## 6. User Acceptance Criteria (UAT)
- **UAT-1 (External Event Detection)**: When a new event JSON file is dropped directly into `{data_root}/events/` while `webapp-backend` is already running, the very next `GET /api/events` request immediately includes the new event without restarting the backend container.
- **UAT-2 (UI Refresh Reactivity)**: When the operator clicks the "רענון" button in the webapp UI, the UI displays any events added by `denidin-app` since the initial page load.
