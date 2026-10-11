# research.md — Phase 0 decisions and rationale

This document resolves the NEEDS CLARIFICATION items from `plan.md` Technical Context for Feature 005 (MCP → Morning Green Receipt integration).

---

## Decision: Language and Runtime
- Decision: Use **Python 3.11** as the runtime for Phase‑1 implementation and packaging.
- Rationale: The existing repository is Python-based and development tooling already aligns with Python; 3.11 offers performance improvements and wide package support.
- Alternatives considered:
  - Python 3.10: compatible but older; less performance for equal code.
  - Python 3.12: newer but adoption & CI images may lag; prefer 3.11 for stability.

## Decision: Web / MCP Framework
- Decision: Use **FastAPI** (ASGI) for the MCP service / HTTP endpoints (if needed).
- Rationale: FastAPI offers first-class Pydantic integration (we plan Pydantic models), async support for concurrent IO (helpful for non-blocking requests to Morning), and excellent testability. It also simplifies generating quick API docs for devs.
- Alternatives considered:
  - Flask (WSGI): simpler but lacks built-in Pydantic/async ergonomics.
  - aiohttp: fully async but less ergonomic for models and typed endpoints.

## Decision: HTTP client strategy and token lifecycle
- Decision: Implement a small synchronous client with `requests` plus `urllib3` `Retry` adapter for idempotent ops; manage tokens centrally with proactive refresh.
- Token policy: Token TTL = 3600s (1 hour). Refresh when remaining TTL <= 300s (5 minutes). Cache token in-memory; optional persistent cache if multi-process deployment required.
- Rationale: `requests` is explicit and well-known; retry adapter handles 429/5xx backoff. Proactive refresh avoids edge-case 401s and simplifies call paths.
- Alternatives considered:
  - Async HTTP with `httpx` + async client: chosen if project moves fully async; start with `requests` to minimize changes.
  - Central token store (Redis) for multi-process deployments: keep optional for Phase‑2 if multi-worker required.

## Decision: Storage & Persistence
- Decision: No database required for Phase‑1; keep integration stateless. Use file-backed SQLite cache only if required for dedup or webhook replay.
- Rationale: MVP operations map 1:1 to Morning API and do not require long-term data storage inside DeniDin. Avoid added operational complexity.
- Alternatives considered:
  - SQLite for local caching/history (low-cost), PostgreSQL for production-level audit logs (deferred to Phase‑2).

## Decision: Testing approach
- Decision: Use `pytest` with `requests-mock` or `respx` for mocking HTTP; write failing tests first per TDD.
- Rationale: Aligns with repo methodology; external calls must be mocked to avoid live requests.

## Decision: Rate limiting and retry
- Decision: Implement client-side rate-limiting (token-bucket) matching Morning recommendation; default to 3 req/s per API key and exponential backoff for 429/5xx.
- Rationale: Reduce API errors and respect provider limits. Tests will include simulated 429 responses to validate retry/backoff behavior.

## Decision: Configuration
- Decision: Store configuration in `config/config.json` (per Constitution). Add required keys:
  - `morning.api_key_id` (string)
  - `morning.api_key_secret` (string)
  - `morning.api_url` (string)
  - `morning.token_ttl_seconds` (number, default 3600)
  - `morning.refresh_before_seconds` (number, default 300)
  - `feature_flags.enable_morning_integration` (bool)
- Rationale: Matches project constitution and existing patterns.

## Decision: Webhooks
- Decision: Support webhook HMAC verification using partner auth token and `X-Data-Signature` header as documented; provide a small webhook handler example in `quickstart.md`.
- Rationale: Required for async operations (file parsing, expense drafts).

## Unresolved / NEEDS CLARIFICATION
Decisions and clarifications (updated):

- **Deployment concurrency model (DECIDED for Phase‑1):** Use a single-process worker model for Phase‑1 (simpler token cache, easier testing). This reduces coordination complexity while we validate tool behavior and tests. For Phase‑2 we will adopt a multi-worker deployment (Gunicorn/uvicorn workers or container instances) and implement a shared token store (Redis) and distributed lock for token refresh.

- **Token store plan (Phase‑2):** Add a design and implementation task to introduce a shared token store using Redis with key TTLs matching provider token TTLs, plus an advisory lock pattern (SETNX with short expiry) to avoid thundering-herd refreshes. See `tasks.md` entries for details.

- **Webhook canonicalization:** See `specs/005-mcp-morning-green-receipt/webhook_canonicalization.md` for the canonicalization algorithm and verification guidance; tests will be added to the TDD tasks (see T024 updates in `tasks.md`).

Open questions (deferred to Phase‑2):
- Should the Phase‑2 deployment use centralized session affinity or a service mesh for token routing? (deferred)
## Next actions (Phase 1 prerequisites)
- Produce `data-model.md` from the spec (entities: Invoice, Client, Payment, ExpenseDraft).
- Generate `contracts/` with OpenAPI snippets or JSON schema for each MCP tool (use inputSchemas in `spec.md` as starting point).
- Create `quickstart.md` showing how to configure `config/config.json` and run the MCP server locally (include webhook verification snippet).
- Add tests skeletons (failing tests) for token lifecycle and basic tool behaviors.


Generated on: 2026-02-03
