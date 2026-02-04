# MERGED CONTENT: files from `specs/005-mcp-morning-green-receipt/`

This file was created to consolidate the original contents of `specs/005-mcp-morning-green-receipt/` into the authoritative `in-definition` folder so nothing is lost and no files are deleted.

---

## specs/005-mcp-morning-green-receipt/spec.md

````markdown
<!-------------------------------------------------------------
  This file was copied from
  specs/in-definition/005-mcp-morning-green-receipt/spec.md
  to satisfy speckit toolchain requirements.
-------------------------------------------------------------->


````markdown
# Feature Spec: MCP Integration with Morning Green Receipt

**Feature ID**: 005-mcp-morning-green-receipt  
**Priority**: P2 (Medium)  
**Status**: Planning  
**Created**: January 17, 2026

# Feature artifacts moved to `specs/in-definition/005-mcp-morning-green-receipt/`

This directory previously contained the canonical feature artifacts for `005-mcp-morning-green-receipt`.

To avoid duplication and keep research artifacts authoritative, all feature documents have been consolidated under:

`specs/in-definition/005-mcp-morning-green-receipt/`

Please edit and review files there. The toolchain (`check-prerequisites.sh`) has been updated to accept `in-definition` as a fallback source for automation.

If you want this directory to be the canonical source instead, we can remove these placeholder files and replace them with symlinks to the in-definition copies.
    "morning": {
        "api_key": "PASTE_YOUR_TEST_API_KEY_HERE",
        "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1/",
        "default_currency": "ILS",
        "default_vat_rate": 0.17,
        "token_ttl_seconds": 3600,
        "refresh_before_seconds": 300
    },
    "feature_flags": {
        "enable_morning_integration": false
    }
}
````

---

## specs/005-mcp-morning-green-receipt/plan.md

``markdown
# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

---

**IMPORTANT**: This plan MUST comply with:
- **CONSTITUTION.md** (§I-III): NO environment variables, UTC timestamps mandatory, Git workflow (feature branches + merge commits)
- **METHODOLOGY.md** (§II, IV, VII): Template structure, Phased planning, Integration Contracts (mandatory for multi-component features)

**Required Sections** (per METHODOLOGY.md):
- ✅ Integration Contracts (§VII) - Document all component interactions with explicit contracts
- ✅ Constitution Check (before Phase 0, after Phase 1)
- ✅ Phased execution (Phase 0-3+) with validation gates

---

This plan was moved to `specs/in-definition/005-mcp-morning-green-receipt/plan.md` when artifacts were consolidated.

Please review and edit the authoritative plan in the `in-definition` folder. The repository's prerequisite checker will read the `in-definition` fallback when canonical files are absent.


```

---

## specs/005-mcp-morning-green-receipt/tasks.md

```markdown
# tasks.md — Implementation tasks for Feature 005 (MCP → Morning)

Phase 1: Setup
- [ ] T001 [P] Create package skeleton `src/denidin_mcp_morning/` with files: `__init__.py`, `server.py`, `tools.py`, `client.py`, `models.py`, `config.py`, `utils.py` (paths: `src/denidin_mcp_morning/`)
- [ ] T002 [P] Add example config file based on schema: `config/config.example.json` (use `specs/in-definition/005-mcp-morning-green-receipt/artifacts/config.schema.json` as source)
- [ ] T003 [P] Add feature README and quickstart: `specs/in-definition/005-mcp-morning-green-receipt/quickstart.md` (create quickstart that documents `config/config.example.json`, running locally, webhook example)
- [ ] T004 [P] Ensure `specs/in-definition/005-mcp-morning-green-receipt/contracts/` contains JSON schemas for all 8 tools (create missing files): path `specs/in-definition/005-mcp-morning-green-receipt/contracts/`

Phase 2: Foundational (blocking prerequisites)
- [ ] T005  Create Pydantic models: `src/denidin_mcp_morning/models.py` (Invoice, Client, Payment, ExpenseDraft) — implement schema fields and validation per `specs/.../data-model.md`
- [ ] T006 [P] [TEST] Write failing unit tests for token lifecycle behavior: `tests/unit/test_token_lifecycle.py` (describe: request token, refresh when TTL<=refresh_before_seconds, handle missing token responses)
- [ ] T007 [P] Implement token manager and HTTP client skeleton in `src/denidin_mcp_morning/client.py` (use `requests`; implement token caching and `get_token()` method) — make tests pass
- [ ] T008  Add rate-limiter utility `src/denidin_mcp_morning/utils.py` (token-bucket with default 3 req/s) and unit tests `tests/unit/test_rate_limiter.py`
- [ ] T009  Add config loader `src/denidin_mcp_morning/config.py` that reads `config/config.json` and validates against `specs/.../artifacts/config.schema.json`

Phase 3: User Stories (priority order)

US1 — Invoice Creation
Independent test criteria: given a valid `create_invoice` input, the MCP tool calls Morning `/documents` and returns the created document JSON (mocked). Files: `src/denidin_mcp_morning/tools.py`, `src/denidin_mcp_morning/client.py`, tests in `tests/unit/test_create_invoice.py`
- [ ] T010 [P] [US1] [TEST] Write failing unit tests for `create_invoice` tool behavior (path: `tests/unit/test_create_invoice.py`)
- [ ] T011 [US1] Implement `create_invoice` tool function in `src/denidin_mcp_morning/tools.py` and wiring in `server.py` to accept tool input

US2 — Invoice Query / List
Independent test criteria: `list_invoices` accepts filters and returns list JSON; pagination handled if present.
- [ ] T012 [P] [US2] [TEST] Write failing unit tests for `list_invoices` (path: `tests/unit/test_list_invoices.py`)
- [ ] T013 [US2] Implement `list_invoices` in `src/denidin_mcp_morning/tools.py` and client mapping in `client.py`

US3 — Payment Tracking / Status
Independent test criteria: `get_invoice_details` returns status and payments; `update_invoice_status` updates status via Morning API.
- [ ] T014 [P] [US3] [TEST] Write failing tests for `get_invoice_details` and `update_invoice_status` (path: `tests/unit/test_invoice_status.py`)
- [ ] T015 [US3] Implement `get_invoice_details` and `update_invoice_status` in `tools.py` and client calls in `client.py`

US4 — Client Management
Independent test criteria: `add_client` creates a client and returns the client object; validation on required fields.
- [ ] T016 [P] [US4] [TEST] Write failing tests for `add_client` tool (path: `tests/unit/test_add_client.py`)
- [ ] T017 [US4] Implement `add_client` in `tools.py` and client call in `client.py`

This tasks document was consolidated into `specs/in-definition/005-mcp-morning-green-receipt/tasks.md`.

Please make edits in the `in-definition` folder; the prerequisite checker will read from `in-definition` when canonical files are not present.
- [ ] T019 [US5] Implement `get_financial_summary` in `tools.py`

```

---

## specs/005-mcp-morning-green-receipt/token_store.md

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

---

## specs/005-mcp-morning-green-receipt/user-stories.md

```markdown
# user-stories.md — Given/When/Then user stories (METHODOLOGY §I requirement)

Each user story below follows Given-When-Then format and includes acceptance criteria and router/dispatcher requirements.

1) Invoice Creation
Given a user sends a natural-language request via MCP (WhatsApp or desktop) to create an invoice
When the NLU extracts a `create_invoice` intent with `client_name`, `amount`, and `description`
Then the MCP server must call the `create_invoice` tool with validated schema and return a human-readable confirmation including invoice number, amount, status and PDF link.

Acceptance criteria:
- Tool input validated against `contracts/create_invoice.json`.
- If multiple clients match `client_name`, respond with a selection prompt listing candidates with IDs.
- On success, respond in Hebrew with invoice number and PDF link.

Router Requirement: `@bot.router.message(intent='create_invoice')` must route to `denidin_mcp_morning.tools.create_invoice`.

2) Invoice Query (List)
Given a user requests invoices for a date range or 'this month' via MCP
When NLU maps the request to `list_invoices` with optional `status`, `from_date`, `to_date`
Then MCP server must call `list_invoices` tool, format results into a readable list (max 10 items, paginated) and include totals.

Acceptance criteria:
- Parameters validated against `contracts/list_invoices.json`.
- Response includes at most 10 items and a continuation token if more results exist.

Router Requirement: `@bot.router.message(intent='list_invoices')` → `denidin_mcp_morning.tools.list_invoices`.

... (truncated for brevity; full content preserved in original file)

```

---

## specs/005-mcp-morning-green-receipt/webhook_canonicalization.md

```markdown
# Webhook Canonicalization and Verification

Purpose: Provide an unambiguous algorithm for verifying incoming webhooks from Morning/GreenInvoice and prevent replay/falsified requests.

## Expected headers
- `X-Data-Signature`: HMAC-SHA256 digest of the canonicalized JSON payload, encoded as **lowercase hex**.
- `X-Data-Timestamp`: UTC ISO8601 timestamp of the event (e.g. `2026-02-03T12:34:56Z`). Required to mitigate replay attacks.

## Canonicalization algorithm (receiver)
1. Parse the incoming request body as JSON.
2. Re-serialize using UTF-8, no extraneous whitespace, `sort_keys=True`, and `separators=(",",":")`.
3. Use the resulting byte sequence as the message for HMAC-SHA256 using the shared `webhook_secret`.
4. Compare the lowercase hex digest with the `X-Data-Signature` header using a constant-time compare.

## Example (Python)

```py
import json, hmac, hashlib
from datetime import datetime, timezone

def canonicalize(body_bytes: bytes) -> bytes:
    obj = json.loads(body_bytes)
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False).encode('utf-8')

def verify_webhook(body_bytes: bytes, signature_header: str, secret: str, timestamp_header: str, window_seconds: int = 300) -> bool:
    # timestamp freshness
    ts = datetime.fromisoformat(timestamp_header.replace('Z', '+00:00'))
    if abs((datetime.now(timezone.utc) - ts).total_seconds()) > window_seconds:
        return False

    canonical = canonicalize(body_bytes)
    mac = hmac.new(secret.encode('utf-8'), canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac.lower(), signature_header.lower())
```

## Signature encoding
- Provider MUST use lowercase hexadecimal encoding for the HMAC digest. The receiver MUST normalize the header to lowercase before comparison.

## Replay protection
- Enforce `X-Data-Timestamp` freshness within 5 minutes by default. Log and reject out-of-window requests.

## Tests (required)
- Unit tests for canonicalization handling: whitespace differences, key order changes.
- Integration tests with recorded example payloads and known secrets to validate end-to-end verification and replay-window enforcement.

## Notes
- If the provider publishes a different canonicalization or includes `signature_version`, implement that version and provide a compatibility adapter. Document any deviations in `webhook_canonicalization.md`.

```
