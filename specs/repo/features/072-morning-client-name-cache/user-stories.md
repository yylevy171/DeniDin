# User Stories: Morning Client-Name Cache

## Business Goal
Reduce perceived AI latency by bypassing the 3-5 second overhead associated with querying the external Morning API for known, recurring clients. The MVP target is an **85% cache hit rate** for daily operations.

---

## Stories & Acceptance Criteria

### User Story 1 - The "Cache Hit" Fast Path (Priority: P1)
**Given** the user mentions a client that exists in the local cache (e.g., a recently added or frequently used client like "Yossi")
**When** the AI attempts to resolve the client name
**Then** the system MUST resolve the exact name instantaneously against the local cache, completely avoiding any external HTTP calls to the Morning API.
**And** the user receives their final answer 3-5 seconds faster than the baseline.

### User Story 2 - The "Cache Miss" Fallback (Priority: P1)
**Given** the user mentions a brand new client or a name not currently in the local cache
**When** the AI fails to find an exact match locally
**Then** the AI MUST gracefully fall back to querying the live Morning API via the standard `resolve_client_name` flow.
**And** once the new client is found or created, they MUST be injected into the cache so the next request results in a Cache Hit.

### User Story 3 - Cache Updates / Sync (Priority: P2)
**Given** a new client is added to Morning outside of DeniDin (e.g., via the Morning web interface), OR added via DeniDin's `add_client` tool
**When** the system runs its sync lifecycle or the tool returns success
**Then** the cache MUST be updated without requiring manual developer intervention. (The engineers must define a TTL, webhook, or sync strategy that maintains the 85% minimum hit rate).

---

## User-Facing Testing (Billed & Expensive E2E Suites)

To definitively **PROVE** the speed gains and the 85% hit rate requirement, the engineering team MUST implement the following in the user-facing test suites (`tests/billed/` and/or `tests/expensive/`). Unit and integration tests do not qualify as proof.

### Test 1: Quantifiable Speed Gain Proof (`tests/expensive/` or `tests/billed/`)
**Goal**: Prove the cache successfully eliminates the Morning API overhead on repeated lookups, saving 3-5 seconds.
- **Scenario**: The test script simulates a user sending two consecutive queries about the same client (e.g., *"Did Avi Levi pay?"* followed by *"Send Avi Levi a new invoice for 500 NIS"*).
- **Hard Assertions**:
  1. The telemetry for the **first turn** MUST show a `morning_api_request_times_ms` entry for `resolve_client` (Cache Miss).
  2. The telemetry for the **second turn** MUST show **NO** `resolve_client` network call in `morning_api_request_times_ms` (Cache Hit).
  3. The test runner MUST measure the raw execution time of both turns and explicitly assert that Turn 2's total processing time is significantly faster (at least 2-3 seconds faster) than Turn 1, proving the perceived speed gain for the user.

### Test 2: 85% Hit Rate Target Proof (`tests/billed/`)
**Goal**: Prove the caching implementation achieves the 85% minimum hit rate under a realistic usage distribution.
- **Scenario**: Create a new user-facing test (e.g., `test_cache_hit_rate_simulation_billed.py`) that feeds a simulated batch of 20 user requests into the AI (e.g., 17 requests for existing frequent clients, 3 for new/unknown clients).
- **Hard Assertions**:
  1. The test MUST assert that the final calculated Cache Hit rate across the batch is **>= 85%**.
  2. The test output MUST log the total cumulative time saved across the batch (e.g., "Total time saved by cache hits: 45.2 seconds").
