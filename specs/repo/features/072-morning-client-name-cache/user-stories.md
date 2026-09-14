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

### Phase 1: Statistical Proof of Value (Development Phase)
**Goal**: We need concrete, statistically valid proof that the Morning cache actually saves significant time. The cache only eliminates the MCP-to-Morning link, so we must prove that this specific link is slow enough to warrant caching.
- **Methodology**: The engineers MUST write a dedicated benchmarking script (e.g., `scripts/benchmark_morning_cache.py`) used during development.
- **Scenario**: 
  1. The script modifies `config.json` to toggle a feature flag (e.g., `"morning_cache_enabled": false`).
  2. It runs a batch of **50 resolution requests** and calculates the average `tool_total_execution_time_ms` (which includes the MCP network overhead + Morning API latency).
  3. It toggles `config.json` to `"morning_cache_enabled": true`.
  4. It runs the same **50 requests** and calculates the average `tool_total_execution_time_ms` (which now only includes the MCP network overhead).
- **Proof Required**: The script must output the exact average time saved per tool call. The engineering team must present these numbers. If the average time saved is negligible (e.g., < 0.5 seconds), we re-evaluate the feature's value.

### Phase 2: No-Regression Sanity Test (CI/CD Phase)
**Goal**: Ensure that over time, the cache continues to function and provide a speed benefit without regressing.
- **New Test File**: The engineers MUST add a new test to the sanity suite (e.g., `test_cache_regression_sanity.py`).
- **Methodology**: The test executes a longer, multi-turn user conversation (e.g., 5 messages resolving various clients).
- **Hard Assertions**:
  1. The test runs the conversation with the `config.json` cache flag OFF, recording total execution time.
  2. The test runs the identical conversation with the cache flag ON.
  3. The test asserts that the total execution time for the Flag ON run is consistently and measurably faster than the Flag OFF run, explicitly catching any future performance regressions.

### Phase 3: 85% Hit Rate Target Proof (`tests/billed/`)
**Goal**: Prove the caching implementation achieves the 85% minimum hit rate under a realistic usage distribution.
- **Batch Definition**: A test (`test_cache_hit_rate_simulation_billed.py`) executes a deterministic batch of **20 sequential user messages** against a fresh conversation state.
  - **Distribution**: 17 messages will refer to 3-4 recurring "known" clients (simulating heavy daily use). 3 messages will refer to entirely new/unknown clients (simulating the ~15% miss rate).
- **Measurement & Assertions**:
  1. The test asserts that exactly >= 85% (17/20) of the `resolve_client` tool invocations resulted in a Cache Hit (i.e., `morning_api_request_times_ms` was NULL/empty).
