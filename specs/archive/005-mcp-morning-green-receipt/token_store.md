```markdown
# Token store design (Phase‑2)

Purpose: design a shared token store for multi-worker deployments so all workers can reuse tokens and avoid thundering-herd token refreshes.

Requirements
- Store provider access tokens with expiry metadata.
- Provide atomic refresh coordination so only one worker refreshes a token when expired.
- Fast reads (in-memory-like latency) and optional persistence for observability.

Proposed implementation (Redis)
- Use Redis keys: `morning:token:<business_id>` with value JSON: `{ "token": "...", "expires_at": "2026-02-03T12:34:56Z" }`.
- TTL: set Redis key TTL to match `expires_at` - small drift acceptable. Store `refresh_before_seconds` in config to trigger early refresh.
- Coordination: use advisory lock pattern via `SET key_lock value NX PX 10000` (SETNX with expiry). Worker that obtains lock performs token refresh and writes new key. Other workers will wait or use stale token for a short grace period if allowed.
- Fallback: if Redis unavailable, fall back to local in-process cache (best-effort) and mark telemetry/event for degraded mode.

Testing
- Unit: mock Redis to ensure SETNX flow triggers only one refresh.
- Integration: deploy two worker processes in test harness and assert single refresh on token expiry.

Operational notes
- Secure Redis with TLS and access controls; limit access to worker pool.
- Rotate secrets per organization policy; do not store API keys in Redis — only store tokens issued by provider.

Next steps
- Implement adapter `src/denidin_mcp_morning/token_store/redis_adapter.py` and tests `tests/unit/test_token_store_redis.py` (see T029 in `tasks.md`).

```
