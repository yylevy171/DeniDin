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

## User Acceptance Testing (UAT)

To ensure we actually achieved the speedups and hit the 85% KPI, developers must verify the following scenarios:

### UAT-A: Cache Hit Speed Verification
1. Ensure "Avi Levi" is in the local cache.
2. Ask the bot: *"Did Avi Levi pay his invoice?"*
3. **Verification**: 
   - Check the telemetry logs for `morning_api_request_times_ms`. 
   - There MUST be NO recorded call to `resolve_client_name` or `list_clients`.
   - Total latency must be noticeably faster (measuring just LLM inference time).

### UAT-B: Cache Miss Fallback
1. Clear the cache or ask about a brand new client: *"Did NewCorp pay?"*
2. **Verification**:
   - The bot falls back to the Morning API.
   - Telemetry logs show `morning_api_request_times_ms` captured for the resolution call.
   - A subsequent ask about "NewCorp" must now register as a Cache Hit (UAT-A).
