# Implementation Plan: Clients Management UI in Webapp

**Branch**: `feature/087-webapp-clients-mgmt` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/repo/features/087-webapp-clients-mgmt/spec.md`

---

**IMPORTANT**: This plan MUST comply with:
- **CONSTITUTION.md** (§I-III): NO environment variables, Israel local timestamps mandatory, Git workflow (feature branches + merge commits)
- **METHODOLOGY.md** (§II, IV, VII): Template structure, Phased planning, Integration Contracts (mandatory for multi-component features)

---

## Summary

Reshape the webapp frontend from a single Ledger page into two top-level tabs —
"ארועים" (today's Ledger view, relabeled/re-mounted, functionally unchanged here) and
"לקוחות" (new: a productized port of the analyst mapping tool at
`reports/mapping_tool/`). The backend gains a `ClientsService`/`ClientsReader` pair
that ports `generate_client_status.py`'s aggregation/matching/status logic as-is
(including its Hebrew comment-parsing rules and its side-effect writes to
`removed_clients.json`/`new_morning_clients.json`), but swaps its data sources: the
official client list is fetched live from Morning (via the same MCP path
`apps/denidin-app` already uses) on every `GET /api/clients` call instead of a stale
CSV, and ledger-derived amounts (agreements/deposits/invoices) come from the same
environment-scoped `{data_root}/events` source the Events tab already reads — never
the hardcoded sshfs prod path. Operator state (`client_mapping.json`,
`client_comments.json`, `mapping_notes.json`, `removed_clients.json`,
`new_morning_clients.json`) moves to environment-scoped `{data_root}/clients/`.
Visually, Tab 2 adopts the webapp's existing `theme.ts` chrome, but keeps the mapping
tool's distinctive status **text** colors (not its row-background tints).

## Technical Context

**Language/Version**: Python 3.11 (backend, matches `apps/webapp/backend`'s existing
stack) / TypeScript + React Native Web (frontend, matches `apps/webapp/frontend`)
**Primary Dependencies**: Starlette (existing webapp-backend framework — `mapping_server.py`'s
raw `http.server.BaseHTTPRequestHandler` is NOT reused, its logic is rehosted as
Starlette routes/services); existing `apps/webapp/backend`'s established pattern of
importing `apps/denidin-app/src` via direct `importlib` file-loading (`ledger_reader.py`'s
`_load_ledger_event_manager_class()` trick) for `LedgerEventManager` reuse; the official
client list is fetched via a **direct** import of `denidin_mcp_morning.morning_client.MorningClient`
(specifically `search_clients()`) — a plain synchronous HTTPS call straight to the real
Morning (Green Invoice) API using `apps/webapp/backend`'s own Morning API credentials.
No MCP protocol, no AI/OpenAI call, no dependency on `morning-mcp-app`'s container,
ngrok tunnel, or status file being up at all — `apps/webapp/backend` only needs the
client list, nothing else Morning offers, so the AI-tool surface is irrelevant here.
**Storage**: New environment-scoped `{data_root}/clients/` directory (JSON files,
same shape as the analyst tool's current `client_mapping.json`/etc.) — no new
database
**Testing**: `pytest` in `apps/webapp/backend/tests/` (Starlette `TestClient`,
`integration` marker, no mocking of internal components per CONSTITUTION §I/§V —
Morning calls in tests hit the real sandbox); Playwright in `apps/webapp/e2e/` for
the tab-switch/comment-edit/mapping UX flows
**Target Platform**: Linux container (Docker), same as the rest of `apps/webapp`
today; also runnable via `run_webapp.sh host` for local dev
**Project Type**: Existing three-app repo — this feature touches `apps/webapp/backend`
and `apps/webapp/frontend` only; it adds a new cross-app **code import** dependency
from `apps/webapp/backend` to `apps/morning-mcp-app`'s `denidin_mcp_morning` package
(the `MorningClient` class specifically) — a second, deliberate exception to "apps
reach each other only over HTTP," parallel to the webapp's existing exception for
reading `denidin-app`'s data directly. `apps/webapp/backend` needs its own Morning
API credentials in its own config; it never talks to the `morning-mcp-app` service/
container/tunnel at all.
**Performance Goals**: Client list + status table renders within the same
perceived-latency budget as today's Ledger tab load; the Morning client-list fetch is
the dominant new cost (one HTTP round-trip per `GET /api/clients`, no local caching
per the clarified decision)
**Constraints**: Preserve `generate_client_status.py`'s status/aggregation logic and
side effects byte-for-byte per Clarifications; environment-scoped storage (dev/prod
never share `{data_root}/clients/`); auth-gated identically to the Ledger tab (no new
auth mechanism); Hebrew RTL text rendering must match the existing Ledger tab's
handling
**Scale/Scope**: Small client roster (same scale as `generate_client_status.py`
already handles today — tens to low hundreds of clients), no pagination/sharding
concerns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|---|---|---|
| §I No env vars, config-driven | PASS | New config fields (Morning MCP status-file path for webapp-backend, `{data_root}/clients` root) live in `apps/webapp/backend`'s existing `AppConfig`/`config.*.json` pattern — no env vars. |
| §II Israel local time | PASS | Any new timestamps (e.g. `latest_activity`, comment-edit timestamps) use `now_local()`, matching `denidin-app`'s convention (ported via the same import path already used for `LedgerEventManager`). |
| §III Git workflow | PASS | Working on `feature/087-webapp-clients-mgmt`, not `master`. |
| Zero Mocking Policy / §V | PASS | Backend integration tests hit real ledger data files and the real Morning sandbox (dev config) over the real MCP tunnel — no `unittest.mock` for internal components or the Morning call. |
| §VI Feature flags | N/A | This is a new UI surface (a tab), not a behavior change to an existing default path — no flag needed; the Events tab's existing behavior is unchanged except for bugfix-064's own fix (tracked separately). |
| §XVII No monkey-patching | PASS | New `ClientsReader`/`ClientsService` classes, constructed in `build_app()` exactly like `LedgerReader` today — no runtime patching. |
| §XVIII Startup handshake retry | N/A | No tunnel/ngrok/status-file handshake involved — `MorningClient` talks straight to Morning's own HTTPS API using `requests` + urllib3 `Retry` (already built into `MorningClient`'s session, per `morning_client.py:23`'s `_build_session`), which already satisfies the retry-on-5xx/timeout policy. |
| CLAUDE.md webapp exception ("apps talk only over HTTP, except webapp reads denidin-app data directly") | NOTED, widened | This feature adds a **second** deliberate cross-app code-import exception — `apps/webapp/backend` importing `denidin_mcp_morning.MorningClient` directly — alongside the existing `denidin-app`-data-reading one. Documented explicitly here and in `apps/webapp/CLAUDE.md`'s app description (tasks.md should include a doc-update task) so it isn't mistaken for an accidental violation later. `morning-mcp-app`'s own service/container/tunnel remains untouched and uninvolved. |
| METHODOLOGY §VI.a acceptance-scenario approval gate | PASS | UAT-1/2/3 in spec.md + User Stories 1-3 already exist and are being carried forward; Clarifications session 2026-09-17 resolved the open data-source/behavior questions before this plan. |
| METHODOLOGY §VII Integration Contracts | PASS | contracts/clients-api-contract.md (Phase 1) documents the new `/api/clients*` routes and the webapp-backend ↔ morning-mcp-app HTTP contract. |
| CLAUDE.md "AI Agents: tool-bearing feature needs constitution boundaries" | N/A | No AI/model-facing tool is added — this is a human-operator web UI, not a WhatsApp-bot capability. `runtime_constitution.md` is untouched. |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/repo/features/087-webapp-clients-mgmt/
├── spec.md                        # Feature spec (clarified)
├── user-stories.md                # Acceptance scenarios
├── plan.md                        # This file
├── research.md                    # Phase 0 output
├── data-model.md                  # Phase 1 output
├── contracts/
│   └── clients-api-contract.md    # Phase 1 output
├── quickstart.md                  # Phase 1 output
└── tasks.md                       # Phase 2 output (speckit.tasks — not created here)
```

### Source Code (repository root)

```text
apps/webapp/backend/src/webapp_backend/
├── clients_reader.py       # NEW — ClientsReader: ports generate_client_status.py's
│                            #   get_report_data() as an importable function; reads
│                            #   ledger events via the existing LedgerEventManager
│                            #   loader trick, reads/writes {data_root}/clients/*.json
├── morning_client_source.py # NEW — thin wrapper around a directly-imported
│                            #   denidin_mcp_morning.morning_client.MorningClient;
│                            #   calls search_clients(), no MCP/AI/tunnel involved
├── config.py                # MODIFIED — new fields: clients data root, this app's
│                            #   own Morning API credentials (api_key_id/secret/url)
└── server.py                # MODIFIED — new /api/clients* routes, wires
                             #   ClientsReader + morning_client_source in build_app()

apps/webapp/frontend/src/
├── App.tsx                  # MODIFIED — introduces top-level tab state (ארועים /
│                            #   לקוחות), moves existing body into EventsView
├── EventsView.tsx           # NEW — today's Ledger UI, extracted unchanged from App.tsx
├── ClientsView.tsx          # NEW — Clients tab: table, filters, comment editor,
│                            #   alias-mapping UI
├── clientsTheme.ts          # NEW — the preserved mapping-tool status TEXT colors,
│                            #   layered as constants over theme.ts's base tokens
└── ui.tsx                   # MODIFIED (maybe) — reuse existing Button/Field/
                             #   MultiSelect; add only what's genuinely missing

apps/webapp/backend/tests/integration/
└── test_clients_api.py      # NEW

apps/webapp/e2e/
└── clients.spec.ts          # NEW — Playwright: tab switch, comment edit, alias mapping
```

**Structure Decision**: Additive within the existing `apps/webapp` structure — no new
app, no new top-level directory. Mirrors the established `LedgerReader`/`ledger_reader.py`
pattern for the new `ClientsReader`, and the established `App.tsx`-owns-everything
frontend pattern extended with a thin tab layer.

## Complexity Tracking

*No Constitution Check violations — table not needed.*
