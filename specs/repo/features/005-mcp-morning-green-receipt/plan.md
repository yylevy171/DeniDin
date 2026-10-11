# Implementation Plan: MCP Server for Morning (Green Invoice) — Invoice Management

**Feature**: 005-mcp-morning-green-receipt
**Branch**: `feature/005-morning-mcp-server` (create when implementation begins)
**Spec**: `./spec.md`
**Status**: Ready for Implementation
**Estimated Duration**: 5–8 days
**Updated**: July 8, 2026

**Compliance**: This plan complies with CONSTITUTION.md (§I no env vars, §II UTC, §III git
workflow, §V integration tests, §XVII no monkey-patching) and METHODOLOGY.md (§IV phased
execution, §VI TDD, §VII integration contracts, §IX technology choices).

---

## Summary

Build a standalone MCP server in `apps/morning-mcp-app/` exposing **7 invoice-management
tools** over the Morning (Green Invoice) REST API, consumable by OpenAI models as a remote
MCP tool. Authentication and a partial HTTP client already exist (`MorningAuth`,
`MorningClient` with 3 of the needed operations, plus real-sandbox integration tests). This
plan adds the config loader, Pydantic models, response formatters, the remaining 5 client
operations, the 8 MCP tools (`tools.py`), and the FastMCP server (`server.py`) over
streamable-HTTP — all under the project's TDD-with-real-sandbox-tests discipline.

## Technical Context

- **Language/Version**: Python 3.9+ (match `apps/morning-mcp-app/Dockerfile`; `python:3.9-slim`).
- **Primary Dependencies**: `mcp` (FastMCP server SDK), `pydantic`, `requests`, `urllib3`
  (existing), `pytest`, `pytest-cov` (existing). Add `mcp` and `pydantic` to
  `apps/morning-mcp-app/requirements.txt`.
- **Server/Transport**: FastMCP over **streamable-HTTP** (see spec §Technology Choice) so
  OpenAI's remote-MCP connector can reach it; runs locally with one command.
- **Storage**: **None** (resolved — previously NEEDS CLARIFICATION). The feature is a
  stateless integration; tools map 1:1 to Morning API responses. No DB/SQLite.
- **Testing**: **real Morning-sandbox integration tests only** (no mocks), following the
  existing `tests/integration/test_morning_sandbox_*.py` pattern. TDD: real-sandbox test
  fails before implementation.
- **Target Platform**: Linux container (own `Dockerfile`); dev on macOS.
- **Performance/Scale**: low-throughput control plane, single sandbox tenant (resolved —
  previously NEEDS CLARIFICATION). Client-side rate-limit ~3 req/s to avoid 429. Multi-tenant
  scale is deferred (spec §Scope).
- **Constraints**: no env vars (flat `config/config.json`); UTC timestamps; new behavior
  gated behind `feature_flags.enable_mcp_server` (default false); `pathlib.Path` for files.

## Constitution Check (pre-Phase 0)

- **No environment variables** — PASS: flat `config/config.json` validated against
  `artifacts/config.schema.json`; loaded via a `config.py` loader by dependency injection.
- **UTC timestamps** — PASS: models/formatters use `datetime.now(timezone.utc)`; a small
  UTC helper in `utils`.
- **Feature branch** — PASS: implementation runs on `feature/005-morning-mcp-server` (this
  spec-cleanup work is on `docs/005-morning-mcp-spec-ready`).
- **Feature flag** — PASS: `feature_flags.enable_mcp_server` gates server startup; when
  false, the existing client library + integration tests are byte-for-byte unaffected.
- **TDD / real-sandbox tests** — MUST ADHERE: every new tool gets a failing real-sandbox
  test approved before implementation (METHODOLOGY §VI).
- **No monkey-patching** — PASS: tools receive a `MorningClient` via dependency injection.

No blocking violations. Any future need for env vars/DB must be justified in Complexity
Tracking.

## Post-Design Constitution Check (after Phase 1 artifacts)

- **Config location** — PASS: flat schema in `artifacts/config.schema.json` matches the
  real `config.example.json`/`config.test.json`; existing tests still read flat keys.
- **UTC** — PASS: `data-model.md` marks datetimes UTC.
- **Feature flag** — PASS: present in schema + spec.
- **TDD** — NOTE: tests must be written and approved (RED) before each tool's implementation.

## Integration Contracts (METHODOLOGY §VII)

### `tools.py` ↔ `MorningClient`
- **tools.py MUST**: validate tool input against `contracts/<tool>.json` (and Pydantic
  models) before calling the client; pass a fully-formed Morning payload; never construct
  raw HTTP.
- **MorningClient PROVIDES**: one method per operation returning parsed JSON (`dict`);
  raises `requests.HTTPError` on non-2xx (after urllib3 retry on 429/5xx); JWT handled
  internally via `MorningAuth`.
- **MorningClient EXPECTS**: `invoice_id` a non-empty Morning `documentId` string; payloads
  matching Morning's document/client shapes (see `data-model.md`).

### MCP client ↔ FastMCP server (`server.py`)
- **server.py MUST**: register all 7 tools with `@mcp.tool()`; expose them over
  streamable-HTTP on the configured host/port; start only when
  `feature_flags.enable_mcp_server` is true.
- **server PROVIDES**: MCP tool discovery + dispatch; each tool returns a human-readable
  (Hebrew-by-default) string/structured result; errors surfaced as friendly messages
  (spec §Error Handling), technical detail logged.
- **server EXPECTS**: a validated config object and an injected `MorningClient` (no globals,
  no monkey-patching).

## Project Structure

### Documentation (this feature)
```text
specs/in-definition/005-mcp-morning-green-receipt/
├── spec.md
├── plan.md              # this file
├── research.md
├── data-model.md
├── user-stories.md
├── quickstart.md
├── endpoints.md
├── contracts/           # 7 invoice tools + morning_token_exchange
├── artifacts/           # config.schema.json (flat), mcp_tools_schema.json, error_codes.json
└── checklists/comprehensive.md
```

### Source code (the app)
```text
apps/morning-mcp-app/
├── requirements.txt                 # + mcp, pydantic
├── config/
│   ├── config.example.json          # flat; add optional fields + mcp/feature_flags blocks
│   ├── config.test.json             # flat (unchanged; used by existing tests)
│   └── config.json                  # gitignored real secrets
├── src/denidin_mcp_morning/
│   ├── __init__.py
│   ├── auth.py                      # EXISTS — MorningAuth (JWT)
│   ├── morning_client.py            # EXISTS — extend with 5 more operations
│   ├── config.py                    # NEW — load+validate flat config
│   ├── models.py                    # NEW — Pydantic models
│   ├── formatters.py                # NEW — Hebrew/₪/VAT/date formatting
│   ├── tools.py                     # NEW — 8 MCP tools
│   └── server.py                    # NEW — FastMCP server (streamable-http)
└── tests/integration/
    ├── test_morning_sandbox_invoices_crud.py     # EXISTS
    ├── test_morning_sandbox_list_invoices.py     # EXISTS
    └── test_morning_sandbox_<tool>.py            # NEW per tool (real sandbox, no mocks)
```

**Structure Decision**: single package `apps/morning-mcp-app/src/denidin_mcp_morning/`,
extending the existing client rather than introducing a parallel structure. Keeps the app
self-contained and Dockerizable.

## Phased Execution

### Phase 0 — Research (DONE)
Morning REST API, `/account/token` JWT auth, sandbox/prod URLs, ~3 req/s rate limit, and the
real `/documents` payload shape are confirmed (see `research.md`, `endpoints.md`, and the
passing `test_morning_sandbox_invoices_crud.py`). **Checkpoint**: API validated; foundational
`MorningAuth` + `MorningClient` (3 ops) implemented and green against the sandbox.

### Phase 1 — Foundation (config, models, formatters)
Add `mcp`/`pydantic` deps; `config.py` (flat load+validate); `models.py`; `formatters.py`.
**Checkpoint**: config loads & validates against the flat schema; models validate the real
document shape; existing integration tests still pass.

### Phase 2 — Client extension + MCP tools (per user story, TDD)
For each of US1–US8 (spec §MCP Tools / user-stories.md), in priority order: write the
failing real-sandbox integration test (Task A) → human approval → implement the client
method (if needed) + the `@mcp.tool()` wrapper (Task B) → green. **Checkpoint**: each tool
callable end-to-end against the sandbox.

### Phase 3 — Server + E2E dispatch
`server.py` FastMCP over streamable-HTTP registering all 7 tools, gated by the feature flag.
Add the E2E test that starts the server and invokes a tool via an MCP client (proves
registration/dispatch — §V routing). **Checkpoint**: OpenAI-style remote MCP client can
discover and call the tools locally.

### Phase 4 — Polish
Structured logging + error-code mapping (`artifacts/error_codes.json`), Hebrew i18n
finalization, `quickstart.md`, README, `config.example.json` fields, Dockerfile `CMD` swap
to run the server. **Checkpoint**: quickstart reproduces a working local server.

## Complexity Tracking

No constitutional deviations. (No env vars, no DB, no mocks, no monkey-patching.)
