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
**Goal**: Prove the cache successfully eliminates the Morning API network overhead when the AI invokes the resolution tool for a known client.
- **Scenario**: A user-facing test script sends two consecutive queries about the same client (e.g., *"Did Avi Levi pay?"* followed by *"Send Avi Levi a new invoice"*).
- **Assumed Architecture**: The AI still invokes the `resolve_client` tool on both turns, but the tool acts as a passthrough.
- **Hard Assertions**:
  1. **Cache Miss (Turn 1)**: The telemetry MUST show a `morning_api_request_times_ms` entry for `resolve_client`, and `tool_total_execution_time_ms` will reflect the network latency (typically >1000ms).
  2. **Cache Hit (Turn 2)**: The telemetry MUST show **NO** network call in `morning_api_request_times_ms`. 
  3. **Speed Proof**: The test MUST explicitly assert that the `tool_total_execution_time_ms` for the cache hit is near-instantaneous (e.g., < 100ms), proving the network hop was eliminated.

### Test 2: 85% Hit Rate Target Proof (`tests/billed/`)
**Goal**: Prove the caching implementation achieves the 85% minimum hit rate under a realistic usage distribution, and calculate total time saved.
- **New Test File**: The engineers MUST create a new test (e.g., `test_cache_hit_rate_simulation_billed.py`).
- **Batch Definition**: The test will execute a deterministic batch of **20 sequential user messages** against a fresh conversation state.
  - **Distribution**: 17 messages will refer to 3-4 recurring "known" clients (simulating heavy daily use). 3 messages will refer to entirely new/unknown clients (simulating the ~15% miss rate).
- **Measurement & Assertions**:
  1. The test tracks every invocation of the `resolve_client` tool.
  2. **Hit Rate**: It asserts that at least 85% (17/20) of those tool invocations resulted in a Cache Hit (i.e., `morning_api_request_times_ms` was NULL/empty).
  3. **Time Saved**: It calculates the difference in `tool_total_execution_time_ms` between the misses (average network time) and the hits (local cache time), and logs the cumulative "Total Time Saved" to the CI output.
