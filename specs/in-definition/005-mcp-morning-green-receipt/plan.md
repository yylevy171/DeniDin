````markdown
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

## Summary

This plan implements MCP integration between DeniDin and Morning (Green Invoice) to enable natural-language invoice and receipt operations via WhatsApp and other MCP clients. Phase‑0 research confirmed the Morning REST API, authentication (API key -> /account/token → JWT), sandbox endpoints, rate limits (~3 req/s), and webhook semantics. Phase‑1 will produce data models, API contracts, and a minimal MCP server implementing the eight proposed tools (create/list/get/update invoices, client CRUD, summaries, send/download PDF).

## Technical Context

**Language/Version**: Python 3.11.4 (pinned). Use this exact minor version for development, CI, and packaging to ensure reproducible builds.
**Primary Dependencies**: `requests`, `pydantic`, `pytest`, `fastapi`, `uvicorn` (ASGI server). The chosen ASGI framework is **FastAPI** (pinned). Update `pyproject.toml` / `requirements.txt` accordingly.
**Storage**: None required for core feature (stateless integration); local persistent cache (SQLite) optional for tool caches/history — default: `N/A` (no DB) unless product requires persistence — NEEDS CLARIFICATION.
**Testing**: `pytest` + `requests-mock` for external API mocking; unit tests and integration test plan will be created in Phase‑1.
**Target Platform**: Linux server (containerized), development on macOS — deployment guidelines will target Linux containers. Use `uvicorn` as the production ASGI runner when deploying FastAPI.
**Project Type**: Server-side integration library + small MCP service (single backend project under `src/denidin_mcp_morning/`).
**Performance Goals**: Low-throughput control plane (expected < 10 req/s per tenant). Enforce client-side rate limiting to avoid 429 responses. — NEEDS CLARIFICATION: SLA / expected concurrent tenants.
**Constraints**:
- Must follow `CONSTITUTION.md`: NO environment variables; all config in `config/config.json`.
- Use UTC for timestamps.
- Feature must be gated by a feature flag in `config/config.json`.
**Scale/Scope**: P2 feature; minimal initial footprint supporting one partner sandbox account. Growth planning reserved for Phase‑2.

## Constitution Check

Pre-check (Phase‑0 entry):

- **NO environment variables**: PASS — plan will store config in `config/config.json` (template in `specs/.../artifacts/config.schema.json`). Implementation MUST read from config files only.
- **UTC timestamps**: PASS — all code and tests MUST use UTC; will add a helper util to enforce `datetime.now(timezone.utc)`.
- **Feature branch requirement**: PASS — current branch is `005-mcp-morning-green-receipt` (script output `BRANCH` = `005-mcp-morning-green-receipt`). Continue work on this branch.
- **TDD/Test-first requirement**: MUST ADHERE — Phase‑1 will create failing tests before implementation per `METHODOLOGY.md` §VI.

No constitution violations detected that would block Phase‑0. Any deviations (e.g., using env vars) will be documented in Complexity Tracking and must be justified.

## Post-Design Constitution Check

After Phase‑1 artifacts (data models, contracts, quickstart) were created the following checks were performed:

- **Configuration location**: PASS — quickstart and artifacts reference `config/config.json` and `config.schema.json` artifact exists under `specs/.../artifacts/`.
- **UTC timestamps**: PASS — data-models indicate `datetime (UTC)` and quickstart mentions UTC helper.
- **Feature flags**: PASS — quickstart shows `feature_flags.enable_morning_integration` and plan requires gating behavior.
- **TDD compliance**: NOTE — tests skeletons were planned; Phase‑2 must create failing tests before implementation to satisfy TDD gate.

No blocking constitution violations detected. Any future need to add environment variables (e.g., CI secrets) must be justified and documented in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Chosen structure: single Python package inside `src/denidin_mcp_morning/` to keep integration self-contained.
src/
└── denidin_mcp_morning/
  ├── __init__.py
  ├── server.py          # Lightweight MCP wiring / entrypoint (ASGI or script)
  ├── tools.py           # MCP tool definitions (8 tools)
  ├── client.py          # Thin HTTP client for Morning (token lifecycle handled here)
  ├── models.py          # Pydantic models for request/response
  ├── config.py          # Config loader (reads `config/config.json`)
  ├── utils.py           # helpers (UTC time, rate limiting)
  └── tests/
    ├── unit/
    └── integration/
```

**Structure Decision**: Use the single-package layout above. This keeps the MCP glue isolated under `src/denidin_mcp_morning/` and avoids introducing a new top-level project. It fits repository conventions and makes packaging for deployment straightforward.
|-----------|------------|-------------------------------------|

````