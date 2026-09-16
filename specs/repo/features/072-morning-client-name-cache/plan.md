# Implementation Plan: Morning Client-Name Cache

**Branch**: `feature/072-morning-client-name-cache` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/repo/features/072-morning-client-name-cache/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

---

**IMPORTANT**: This plan MUST comply with:
- **CONSTITUTION.md** (§I-III): NO environment variables, Israel local timestamps mandatory, Git workflow (feature branches + merge commits)
- **METHODOLOGY.md** (§II, IV, VII): Template structure, Phased planning, Integration Contracts (mandatory for multi-component features)

**Required Sections** (per METHODOLOGY.md):
- ✅ Integration Contracts (§VII) - Document all component interactions with explicit contracts
- ✅ Constitution Check (before Phase 0, after Phase 1)
- ✅ Phased execution (Phase 0-3+) with validation gates

---

## Summary

A transparent, read-through SQLite cache of Morning client names/ids inside
`apps/morning-mcp-app`, intercepting `resolve_client_name`'s existing exact-match fast
path so a previously-seen client resolves instantly with zero Morning API round-trips.
Event-driven write-through (on `add_client` success and on a Morning-confirmed exact
match) and eviction (on "Invalid Client ID" write errors) keep it fresh moment-to-moment;
a periodic TTL sweep against `list_clients` catches renames/deletes made directly in
Morning outside DeniDin. Feature-flagged (`morning_cache_enabled`, default `false`),
byte-identical to today when off. `apps/denidin-app` is entirely unmodified — the cache
is invisible to every existing caller, including Feature 069's recognition call.

## Technical Context

**Language/Version**: Python 3.11 (matches `apps/morning-mcp-app`'s existing stack)
**Primary Dependencies**: stdlib `sqlite3` (no new dependency — matches `reminders.db`'s
approach in `denidin-app`); `APScheduler` (already a `morning-mcp-app` transitive concern
via the established `BackgroundScheduler` pattern used elsewhere in this project — confirm
at tasks time whether it's already a `morning-mcp-app` dependency or needs adding to
`requirements.txt`)
**Storage**: New SQLite file, `apps/morning-mcp-app/data/client_cache.db` (one table,
see data-model.md)
**Testing**: `pytest` — new `apps/morning-mcp-app/tests/integration/` cache tests
(real Morning sandbox, no mocking), a new `apps/denidin-app/tests/billed/` full-cycle
latency test, plus one new `apps/morning-mcp-app` sanity test wired into the existing
sanity suite
**Target Platform**: Linux container (Docker), same as both apps today
**Project Type**: Existing two-app repo — this feature touches `apps/morning-mcp-app`
only (internal cache) plus one new `apps/denidin-app/tests/billed/` acceptance test file
(test-only; no `denidin-app` production code changes)
**Performance Goals**: >=85% cache hit rate against realistic sanity-suite usage
(Phase 3); a measurable (not merely non-negative) latency reduction at both the MCP layer
(Phase 1.a) and the full AI-turn layer (Phase 1.b)
**Constraints**: Feature-flag default `false`, byte-identical disabled path
(CONSTITUTION §VI); dev/prod cache files fully separate (separate Morning accounts,
2026-08-03 asymmetry decision); no change to any MCP tool's external contract/schema
**Scale/Scope**: A small, slowly-changing client roster (the spec's own framing — "a
small, slowly changing client roster"), so a single unindexed-by-volume SQLite table is
more than sufficient; no pagination/sharding concerns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|---|---|---|
| §I No env vars, config-driven | PASS | New `morning_cache_enabled` flag + sweep interval live in `config/config.schema.json`'s existing `feature_flags` object, loaded via `AppConfiguration`-equivalent (`MorningMCPConfig`) — no env vars. |
| §II Israel local time | PASS | `updated_at` uses `now_local()`/`local_isoformat()` (data-model.md), matching `status_writer.py`'s existing pattern in this same app. |
| §III Git workflow | PASS | Working on `feature/072-morning-client-name-cache`, not `master`. |
| Zero Mocking Policy / §V | PASS | Phase 1.a/Phase 2/Phase 3 tests all hit the real Morning sandbox; Phase 1.b is a real billed AI call. No `unittest.mock` planned anywhere in this feature's tests. |
| §VI Feature flags | PASS | `morning_cache_enabled` defaults `false`; disabled path is unmodified `resolve_client_name`/`add_client` code (contracts/cache-contract.md). |
| §XVII No monkey-patching | PASS | New `ClientCache` class, constructed and passed in — no runtime patching of `tools.py`'s existing functions. |
| §XVIII Startup handshake retry | N/A | No new external network handshake at startup — the cache is local SQLite; the periodic sweep already has bounded, repeating retries by construction (it just runs again next interval on failure), not a one-shot give-up. |
| METHODOLOGY §VI.a acceptance-scenario approval gate | PASS | Scenarios drafted, revised per operator direction, and explicitly approved 2026-09-15 (see user-stories.md, commit `dbd91da`) before this plan was started. |
| METHODOLOGY §VII Integration Contracts | PASS | contracts/cache-contract.md documents the `ClientCache` module contract and every modified call site. |
| "AI Agents: tool-bearing feature needs constitution boundaries" (CLAUDE.md) | N/A | This feature adds no new AI-facing tool and changes no tool's schema — it is entirely transparent to the model, per the architecture decision. No `runtime_constitution.md` change is needed. |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/repo/features/072-morning-client-name-cache/
├── spec.md               # Feature spec (clarified)
├── user-stories.md       # Acceptance scenarios (approved 2026-09-15)
├── plan.md               # This file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── contracts/
│   └── cache-contract.md # Phase 1 output
├── quickstart.md         # Phase 1 output
└── tasks.md              # Phase 2 output (speckit.tasks — not created here)
```

### Source Code (repository root)

```text
apps/morning-mcp-app/
├── src/denidin_mcp_morning/
│   ├── client_cache.py       # NEW — ClientCache class (contracts/cache-contract.md)
│   ├── tools.py               # MODIFIED — resolve_client_name, add_client, write
│   │                           #   tools' "Invalid Client ID" handling, all flag-gated
│   ├── cache_sweep_service.py # NEW — periodic reconcile() job (BackgroundScheduler)
│   ├── config.py              # MODIFIED — new feature_flags/interval fields
│   └── server.py              # MODIFIED — wires ClientCache + sweep at startup
├── config/
│   ├── config.schema.json     # MODIFIED — morning_cache_enabled + sweep-interval fields
│   ├── config.example.json    # MODIFIED — documents the new fields
│   └── config.{dev,prod,test}.json  # MODIFIED — flag set per environment (human decision
│                                      #   at rollout time, defaults false until then)
├── data/                       # NEW dir — client_cache.db lives here (gitignored, like
│                                #   denidin-app's data/dev_data)
└── tests/
    ├── integration/
    │   └── test_client_cache_*.py   # NEW — Phase 1.a, Phase 2 candidates
    └── unit/
        └── test_client_cache.py     # NEW — ClientCache module unit tests (no Morning)

apps/denidin-app/
└── tests/billed/
    └── test_client_cache_full_cycle.py  # NEW — Phase 1.b only; no production code changes

docker/
├── docker-compose.dev.yml    # MODIFIED — add data volume mount for morning-mcp-app-dev
└── docker-compose.prod.yml   # MODIFIED — same, prod

(every clone's own docker-compose.{dev,prod}.local.yml override — gitignored, hand-edited
per CLAUDE.md's existing multi-clone data-singleton convention, not part of this feature's
diff)
```

**Structure Decision**: Single-project-per-app structure, unchanged from the existing
repo layout — this feature is additive within `apps/morning-mcp-app` (new module + new
data dir) plus one new test-only file in `apps/denidin-app`. No new top-level app, no
change to either app's existing directory conventions.

## Complexity Tracking

*No Constitution Check violations — table not needed.*
