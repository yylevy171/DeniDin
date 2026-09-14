# Implementation Plan: The Dynamic Capability Backbone (063 + 073 + 085)

**Branch**: `feature/063-refactor-oversized-handlers` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/repo/features/063-refactor-oversized-handlers/spec.md`

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III, VI): no environment variables, Israel-local timestamps, git
  workflow (feature branch + PR/merge), feature-flag-gated rollout for safe deployment.
- **METHODOLOGY.md** (§II, IV, VI.a/VI.b, VII): spec-first, acceptance scenarios defined+approved
  before this plan (satisfied — see `user-stories.md`'s "no new scenarios" decision, approved
  2026-09-14), phased planning, per-story unit/integration TDD discipline in `speckit.tasks`.

---

## Summary

Build a **new, fully parallel** implementation of DeniDin's turn-handling — a **Backbone**
(always-loaded core persona/boundaries/always-on UX + a pre-classifier routing step) plus **6
gated Capability Plugins** (Invoicing Write/Read, Ledger Events Capture/Query, Reminders
Write/Read), each pairing new handler code with a new constitution markdown file, loaded only
when a cheap pre-classifier LLM call determines the turn needs it. This is selected at startup via
`config.feature_flags.enable_capability_backbone` (default `false`) — **not** a conditional inside
the existing handler. With the flag off, `denidin.py` constructs the existing, completely
untouched `AIHandler`, reading the existing, completely untouched `runtime_constitution.md`
(REQ-063-07). `ai_handler.py` is never modified by this feature. Only the two domains with real
local storage (Ledger Events, Reminders) share their SQLite/iCalendar persistence code between
implementations — everything else in the new path is independent, new code. No new persisted data
shape, no new user-facing behavior, no new acceptance scenarios (human-approved decision,
2026-09-14) — the pre-existing `billed`/`expensive` test suite, run against both implementations,
is the acceptance gate.

## Technical Context

**Language/Version**: Python 3.11 (existing `apps/denidin-app` venv/Dockerfile, unchanged)
**Primary Dependencies**: `openai` SDK (Responses API, already in use), existing internal
`AppConfiguration`/`SessionManager`/domain managers — no new third-party dependency introduced.
**Storage**: N/A for new data — the SQLite/iCalendar persistence internals of
`ledger_event_manager.py` / `reminder_manager.py` are extracted into a shared location imported
by *both* implementations (unchanged schema/behavior); no data reshaping.
**Testing**: `pytest` — existing `unit`/`integration`/`billed`/`expensive`/`sanity` tiers,
unchanged tooling (`scripts/run_single_test.sh` etc.). `ai_handler.py`'s existing unit tests are
untouched (the file itself doesn't change); the new orchestrator gets its own new, standalone unit
tests. `billed`/`expensive`/`sanity` suites run unmodified, against both implementations.
**Target Platform**: Docker containers, `dev`/`prod`, unchanged (019-env-separation).
**Project Type**: Single backend application (`apps/denidin-app`), no new project/service.
**Performance Goals**: SC-004 — measurable per-turn input token reduction on turns matching few/no
capability plugins, via the new pre-classifier (adds one small call, trades against the token
savings on the main call — net latency/cost tradeoff instrumented per research.md R6, not assumed).
**Constraints**: REQ-063-06 — Backbone must remain OpenAI's byte-stable cached prefix; REQ-063-07 —
`ai_handler.py`/`runtime_constitution.md` must remain byte-for-byte untouched while the flag
exists; zero observable behavior change with the flag on (REQ-063-05); classifier failure must
fail open, never silently drop a needed capability (data-model.md).
**Scale/Scope**: 1 new Backbone-layer orchestrator module + 3 new domain capability packages (6
new plugin prompt files) built alongside (not replacing) the existing 4,859-line `ai_handler.py`;
1 new Backbone file + 6 new plugin files built alongside the existing 1,879-line
`runtime_constitution.md`; 2 of the 3 named oversized managers
(`ledger_event_manager.py`, `reminder_manager.py`) have their storage internals shared between
both implementations, `session_manager.py` stays untouched Backbone-layer infrastructure used by
both.

## Constitution Check

*GATE: Must pass before Phase 0 research (done above) and re-checked after Phase 1 design (this
section, post-design).*

| Gate | Status | Notes |
|---|---|---|
| No environment variables (CONSTITUTION §II) | ✅ Pass | New `capabilities_dir`/`enable_capability_backbone` are `config.json` fields, loaded via `AppConfiguration`, exactly like every other config value. |
| Israel-local timestamps (CONSTITUTION §III) | ✅ Pass | No new timestamp logic introduced; existing `now_local()` usage untouched. |
| Feature flags: ask before adding, don't default to one (CONSTITUTION §VI, revised 2026-09-14) | ✅ Pass | Explicitly discussed with and requested by the human for this feature (large structural change, real regression risk) — not unilaterally added. `enable_capability_backbone` default `false`; flag-off path is the literal untouched `AIHandler`/`runtime_constitution.md`, not a conditional branch (research.md R1). |
| No monkey-patching (CONSTITUTION §XVII) | ✅ Pass | Plugin loading is plain conditional dispatch + dependency injection (config-driven file paths), no runtime method replacement. |
| `pathlib.Path`, not string concatenation | ✅ Pass | New `_load_capability_plugin` follows `_load_constitution`'s existing `Path(base_dir) / ...` pattern. |
| Integration tests as real entry points, zero internal mocking (CONSTITUTION §I/§V) | ✅ Pass | No new integration tests planned beyond what `speckit.tasks` derives per-plugin extraction; existing integration suite untouched. |
| Retry policy (retry once on 5xx/timeout, never 4xx) | ✅ Pass | Pre-classifier call reuses `_timed_llm_call`'s existing retry wrapper, no new policy. |
| Version/release decisions human-only | ✅ N/A at plan stage | No release cut as part of this plan; flag-default-flip and eventual legacy-path deletion are explicitly out of scope, deferred to a later human decision. |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/repo/features/063-refactor-oversized-handlers/
├── spec.md                          # updated by speckit.clarify (2026-09-14)
├── user-stories.md                  # UAT + §VI.a decision (no new acceptance scenarios)
├── plan.md                          # this file
├── research.md                      # Phase 0 output
├── data-model.md                    # Phase 1 output
├── quickstart.md                    # Phase 1 output
├── contracts/
│   ├── pre-classifier.md
│   └── constitution-assembly.md
└── tasks.md                         # Phase 2 output (speckit.tasks — not created here)
```

### Source Code (repository root)

```text
apps/denidin-app/
├── config/
│   ├── runtime_constitution.md                   # UNTOUCHED — still used verbatim by legacy AIHandler (flag off)
│   ├── backbone.md                                # NEW — used only by the new orchestrator (flag on)
│   └── capabilities/                              # NEW
│       ├── invoicing_write.md
│       ├── invoicing_read.md
│       ├── ledger_capture.md
│       ├── ledger_query.md
│       ├── reminders_write.md
│       └── reminders_read.md
├── src/
│   ├── handlers/
│   │   └── ai_handler.py                         # UNTOUCHED — legacy path, byte-for-byte (REQ-063-07)
│   ├── backbone/                                  # NEW package — the new orchestrator (flag on)
│   │   ├── orchestrator.py                        # new AIHandler-equivalent: get_response/resolve_button_tap/etc.
│   │   └── pre_classifier.py                      # new — the routing call (contracts/pre-classifier.md)
│   ├── capabilities/                              # NEW package
│   │   ├── invoicing/
│   │   │   └── handler.py                        # NEW code (not extracted — parallel to ai_handler.py's logic)
│   │   ├── ledger_events/
│   │   │   └── handler.py                        # NEW code (capture + query)
│   │   └── reminders/
│   │       └── handler.py                        # NEW code (write + read)
│   ├── managers/                                    # ALL UNTOUCHED — ai_handler.py's imports don't change
│   │   ├── ledger_event_manager.py                # imported by both ai_handler.py (unchanged) and the new
│   │   │                                            #   capabilities/ledger_events/handler.py (new import, new file)
│   │   ├── reminder_manager.py                     # same sharing pattern
│   │   └── session_manager.py                      # Backbone-layer infra, used unmodified by both implementations
│   └── denidin.py (repo root of the app)          # initialize_app: constructs AIHandler XOR the new orchestrator,
│                                                     #   based on config.feature_flags.enable_capability_backbone
└── tests/
    ├── unit/
    │   ├── test_ai_handler_*.py                    # UNTOUCHED — ai_handler.py didn't change
    │   └── test_backbone_*.py, test_capabilities_*  # NEW — standalone unit tests for the new orchestrator/plugins
    ├── billed/  , tests/expensive/                # UNCHANGED — the actual regression gate (REQ-063-05), run
                                                      #   against both implementations
```

**Structure Decision**: Single-project structure (Option 1 from the template), scoped entirely to
`apps/denidin-app` — no new app, no frontend/backend split. `src/backbone/` and
`src/capabilities/` are new top-level packages, fully additive alongside the existing (untouched)
`src/handlers/ai_handler.py`. `src/capabilities/` is organized by domain (3 packages) rather than
by the 6-way write/read plugin split, per research.md R5's rationale (the write/read distinction
lives at the constitution-file and classification-tag level, not as separate Python packages). The
two domains with real local storage (`managers/ledger_event_manager.py`,
`managers/reminder_manager.py`) stay exactly where they are and are imported, unmodified, by both
`ai_handler.py` (unchanged, as today) and the new capability handlers — zero changes to
`ai_handler.py`, including its imports; everything else in the new path is independent new code,
selected at startup per REQ-063-07.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
