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

**Revised and approved 2026-09-15, per operator direction** — Phase 1 splits into a no-AI
integration measurement (1.a) and a real end-to-end billed measurement (1.b); Phase 3 drops
the deterministic 17/3 batch in favor of an organic sanity sweep run with the cache flag ON.

### Phase 1.a: MCP-Layer Latency Proof (`apps/morning-mcp-app` integration tests, no AI)
**Goal**: Prove the transparent cache actually eliminates the Morning API round-trip at the
MCP layer, in isolation — no OpenAI call needed, since the thing being measured is purely
`resolve_client_name`'s own execution time.
- **Methodology**: A dedicated integration test (or benchmark script invoked by one) in
  `apps/morning-mcp-app/tests/integration/`, calling `resolve_client_name` directly against
  the real Morning sandbox (constitution: no mocking).
- **Scenario**:
  1. With `morning_cache_enabled: false`, call `resolve_client_name` for the same known
     client **50 times**, recording each call's wall-clock time.
  2. With `morning_cache_enabled: true`, repeat the same 50 calls (cache warmed on the
     first call).
  3. Compute and assert the average time for the flag-ON run is measurably lower than the
     flag-OFF run.
- **Proof Required**: The test prints/logs the exact average time saved per call. If the
  average saved is negligible (e.g., < 0.5s), that's a real finding to surface, not a
  reason to weaken the assertion.

### Phase 1.b: Full-Cycle Latency Proof (`tests/billed/`, denidin-app, real AI in the loop)
**Goal**: Prove the cache's MCP-layer saving (1.a) actually translates into a faster
end-to-end user-facing reply — the AI call, tool round-trip, and reply generation together.
- **Methodology**: A `tests/billed/` test in `apps/denidin-app` that sends the same
  client-resolution request through the full `AIHandler`/Morning-MCP pipeline twice.
- **Scenario**:
  1. With `morning_cache_enabled: false`, send a message that requires resolving a known
     client; record total turn time (request in → reply out).
  2. With `morning_cache_enabled: true` (cache pre-warmed for that client), send the
     equivalent message again; record total turn time.
  3. Assert the flag-ON turn is measurably faster than the flag-OFF turn.

### Phase 2: No-Regression Sanity Test (CI/CD Phase)
**Goal**: Ensure that over time, the cache continues to function and provide a speed benefit without regressing.
- **New Test File**: The engineers MUST add a new test to the sanity suite (e.g., `test_cache_regression_sanity.py`).
- **Methodology**: The test executes a longer, multi-turn user conversation (e.g., 5 messages resolving various clients).
- **Hard Assertions**:
  1. The test runs the conversation with the `config.json` cache flag OFF, recording total execution time.
  2. The test runs the identical conversation with the cache flag ON.
  3. The test asserts that the total execution time for the Flag ON run is consistently and measurably faster than the Flag OFF run, explicitly catching any future performance regressions.

### Phase 3: 85% Hit Rate Target Proof (sanity suite, cache flag ON)
**Goal**: Prove the caching implementation achieves the 85% minimum hit rate under realistic,
organic usage — not a hand-tuned distribution.
- **Methodology**: Run a random sweep of **~20 existing `@pytest.mark.sanity` tests**
  (`./scripts/run_sanity.sh` or `run_sanity_parallel.sh`'s existing billed subset — no new
  bespoke test file, no fixed message script) with `morning_cache_enabled: true` for the
  whole run, since counting hits only makes sense with the cache actually on.
- **Measurement & Assertions**:
  1. Across every `resolve_client_name` invocation made during that sweep, assert
     >= 85% resulted in a Cache Hit (i.e., no live Morning API round-trip was made).
  2. Since this rides real sanity tests rather than a scripted client-name distribution,
     the hit-rate measurement is a reported/logged outcome checked against the 85%
     threshold, not a hand-picked-to-pass fixture.
