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

Build a **new, fully parallel** implementation of DeniDin's turn-handling: a thin **Backbone
orchestrator kernel** (static behavioral constants only — persona, boundaries, always-on UX) that
drives a plan-execution loop through 2 **meta-capabilities** (Intent Identification, Planning —
themselves real capabilities with their own prompts, not routing logic baked into the Backbone)
and 7 **domain capabilities** (Invoicing Write/Read, Ledger Events Capture/Query, Reminders
Write/Read, and **Media Analysis** — image/PDF/DOCX extraction, newly folded into this same
capability model instead of living outside it). Every message — text or media — enters through
this one orchestrator; there is no separate deterministic media pre-route. Each step of a plan is
its own OpenAI call carrying Backbone + exactly one active capability's prompt+tools, reusing the
existing followup-call pattern `ai_handler.py` already implements for reminders/ledger-query/etc.

This is selected at startup via `config.feature_flags.enable_capability_backbone` (default
`false`) — **not** a conditional inside the existing handler, and not a default for new work in
general (CONSTITUTION.md §VI now requires asking before adding a flag; this feature keeps one
because it was explicitly requested for this specific large refactor). With the flag off,
`denidin.py` constructs the existing, completely untouched `AIHandler`, reading the existing,
completely untouched `runtime_constitution.md`, `config/ledger_recognition_prompt.md`, and
`prompts/*.txt` (REQ-063-07) — `ai_handler.py` and the extractor classes are never modified by
this feature. The two domains with real local storage (Ledger Events, Reminders) and Media
Analysis's extraction code all stay exactly where they are, imported unmodified by the new
orchestrator's capability handlers — everything else in the new path is independent, new code
under a new `config/prompts/` folder. No new persisted data shape, no new user-facing behavior, no
new acceptance scenarios (human-approved decision, 2026-09-14) — the pre-existing
`billed`/`expensive` test suite, run against both implementations, is the acceptance gate.

## Technical Context

**Language/Version**: Python 3.11 (existing `apps/denidin-app` venv/Dockerfile, unchanged)
**Primary Dependencies**: `openai` SDK (Responses API, already in use), existing internal
`AppConfiguration`/`SessionManager`/domain managers — no new third-party dependency introduced.
**Storage**: N/A for new data — `ledger_event_manager.py`/`reminder_manager.py`'s SQLite/iCalendar
persistence and `handlers/extractors/*.py`'s extraction logic stay exactly where they are,
imported unmodified by both implementations; no data reshaping.
**Testing**: `pytest` — existing `unit`/`integration`/`billed`/`expensive`/`sanity` tiers,
unchanged tooling (`scripts/run_single_test.sh` etc.). `ai_handler.py`'s existing unit tests are
untouched (the file itself doesn't change); the new orchestrator gets its own new, standalone unit
tests. `billed`/`expensive`/`sanity` suites run unmodified, against both implementations.
**Target Platform**: Docker containers, `dev`/`prod`, unchanged (019-env-separation).
**Project Type**: Single backend application (`apps/denidin-app`), no new project/service.
**Performance Goals**: SC-004 — measurable per-turn input token reduction, text AND media turns
alike (media vision calls today unconditionally prepend the full constitution), via the plan
execution loop attaching only one capability's content per call instead of everything up front —
net latency/cost tradeoff (more, smaller calls vs. one large call) instrumented per research.md R6,
not assumed.
**Constraints**: REQ-063-06 — Backbone+single-capability prefix must remain OpenAI's byte-stable
cached prefix per call; REQ-063-07 — `ai_handler.py`, `runtime_constitution.md`,
`config/ledger_recognition_prompt.md`, `prompts/*.txt`, and `handlers/extractors/*.py` must remain
byte-for-byte untouched while the flag exists; zero observable behavior change with the flag on
(REQ-063-05); Planning failure must fail open, never silently drop a needed capability
(data-model.md).
**Scale/Scope**: 1 new `src/backbone/` package (orchestrator + 2 meta-capabilities) + 4 new domain
capability packages under `src/capabilities/` (9 new prompt files total: 2 meta + 7 domain,
consolidating what's currently split across `runtime_constitution.md`,
`ledger_recognition_prompt.md`, and 2 standalone `.txt` files) built alongside (not replacing) the
existing 4,859-line `ai_handler.py`; the 3 named oversized managers plus the 3 extractor classes
all stay exactly where they are, imported unmodified by the new capability handlers.

## Constitution Check

*GATE: Must pass before Phase 0 research (done above) and re-checked after Phase 1 design (this
section, post-design).*

| Gate | Status | Notes |
|---|---|---|
| No environment variables (CONSTITUTION §II) | ✅ Pass | New `backbone_config`/`enable_capability_backbone` are `config.json` fields, loaded via `AppConfiguration`, exactly like every other config value. |
| Israel-local timestamps (CONSTITUTION §III) | ✅ Pass | No new timestamp logic introduced; existing `now_local()` usage untouched. |
| Feature flags: ask before adding, don't default to one (CONSTITUTION §VI, revised 2026-09-14) | ✅ Pass | Explicitly discussed with and requested by the human for this feature (large structural change, real regression risk) — not unilaterally added. `enable_capability_backbone` default `false`; flag-off path is the literal untouched `AIHandler`/`runtime_constitution.md`, not a conditional branch (research.md R1). |
| No monkey-patching (CONSTITUTION §XVII) | ✅ Pass | Capability/plan loading is plain conditional dispatch + dependency injection (config-driven file paths), no runtime method replacement. |
| `pathlib.Path`, not string concatenation | ✅ Pass | New `_load_capability_prompt` follows `_load_constitution`'s existing `Path(base_dir) / ...` pattern. |
| Integration tests as real entry points, zero internal mocking (CONSTITUTION §I/§V) | ✅ Pass | No new integration tests planned beyond what `speckit.tasks` derives per-capability; existing integration suite untouched. |
| Retry policy (retry once on 5xx/timeout, never 4xx) | ✅ Pass | Every orchestration-loop step (Intent Identification, Planning, each domain capability call) reuses `_timed_llm_call`'s existing retry policy, reimplemented in the new module (research.md R2), no new policy. |
| Version/release decisions human-only | ✅ N/A at plan stage | No release cut as part of this plan; flag-default-flip and eventual legacy-path deletion are explicitly out of scope, deferred to a later human decision. |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/repo/features/063-refactor-oversized-handlers/
├── spec.md                          # updated across 2 clarify + 2 plan-phase revision passes (2026-09-14)
├── user-stories.md                  # UAT + §VI.a decision (no new acceptance scenarios)
├── plan.md                          # this file
├── research.md                      # Phase 0 output (R1-R6, R2a, R2b)
├── data-model.md                    # Phase 1 output
├── quickstart.md                    # Phase 1 output
├── contracts/
│   ├── orchestration-loop.md         # supersedes the retired pre-classifier.md
│   └── prompt-assembly.md            # renamed from constitution-assembly.md
└── tasks.md                         # Phase 2 output (speckit.tasks — not created here)
```

### Source Code (repository root)

```text
apps/denidin-app/
├── config/
│   ├── runtime_constitution.md                   # UNTOUCHED — still used verbatim by legacy AIHandler (flag off)
│   ├── ledger_recognition_prompt.md               # UNTOUCHED — still used verbatim by legacy AIHandler
│   └── prompts/                                   # NEW — used only by the new orchestrator (flag on)
│       ├── backbone.md
│       └── capabilities/
│           ├── intent_identification.md           # meta
│           ├── planning.md                        # meta
│           ├── invoicing_write.md
│           ├── invoicing_read.md
│           ├── ledger_capture.md                   # includes domain rules split out of
│           │                                        #   ledger_recognition_prompt.md (backbone gets the
│           │                                        #   generic recognition-step mechanism instead)
│           ├── ledger_query.md
│           ├── reminders_write.md
│           ├── reminders_read.md
│           └── media_analysis.md                   # consolidates prompts/image_analysis.txt + docx_analysis.txt
├── prompts/                                        # UNTOUCHED — image_analysis.txt/docx_analysis.txt,
│                                                     #   still used verbatim by the legacy extractors
├── src/
│   ├── handlers/
│   │   ├── ai_handler.py                         # UNTOUCHED — legacy path, byte-for-byte (REQ-063-07)
│   │   └── extractors/                            # UNTOUCHED — image/pdf/docx_extractor.py, byte-for-byte
│   ├── backbone/                                  # NEW package — the orchestrator kernel (flag on)
│   │   ├── orchestrator.py                        # new get_response/resolve_button_tap equivalent — the
│   │   │                                            #   plan-execution loop (contracts/orchestration-loop.md)
│   │   ├── intent_identification.py                # meta-capability
│   │   └── planning.py                             # meta-capability
│   ├── capabilities/                              # NEW package — 4 domain subpackages (write/read stays a
│   │   │                                            #   prompt/tool distinction, not a Python file split)
│   │   ├── invoicing/
│   │   │   └── handler.py                        # NEW code (not extracted — parallel to ai_handler.py's logic)
│   │   ├── ledger_events/
│   │   │   └── handler.py                        # NEW code (capture + query)
│   │   ├── reminders/
│   │   │   └── handler.py                        # NEW code (write + read)
│   │   └── media_analysis/
│   │       └── handler.py                        # NEW code — wraps the unmodified extractor classes
│   ├── managers/                                    # ALL UNTOUCHED — ai_handler.py's imports don't change
│   │   ├── ledger_event_manager.py                # imported by both ai_handler.py (unchanged) and the new
│   │   │                                            #   capabilities/ledger_events/handler.py (new import, new file)
│   │   ├── reminder_manager.py                     # same sharing pattern
│   │   └── session_manager.py                      # Backbone-layer infra, used unmodified by both implementations
│   └── denidin.py (repo root of the app)          # initialize_app: constructs AIHandler XOR the new orchestrator;
│                                                     #   when flag on, ALSO routes media dispatch into the new
│                                                     #   orchestrator instead of WhatsAppHandler.handle_media_message
│                                                     #   directly (R2a) — flag-off dispatch is fully unchanged
└── tests/
    ├── unit/
    │   ├── test_ai_handler_*.py                    # UNTOUCHED — ai_handler.py didn't change
    │   └── test_backbone_*.py, test_capabilities_*  # NEW — standalone unit tests for the new orchestrator/capabilities
    ├── billed/  , tests/expensive/                # UNCHANGED — the actual regression gate (REQ-063-05), run
                                                      #   against both implementations
```

**Structure Decision**: Single-project structure (Option 1 from the template), scoped entirely to
`apps/denidin-app` — no new app, no frontend/backend split. `src/backbone/` (orchestrator + 2
meta-capabilities) and `src/capabilities/` (4 domain subpackages) are new top-level packages,
fully additive alongside the existing (untouched) `src/handlers/ai_handler.py` and
`src/handlers/extractors/`. Write/read stays a prompt/tool-attachment distinction (R3) rather than
a Python package split, per research.md R5's rationale. The domains with real local
storage/extraction logic (`managers/ledger_event_manager.py`, `managers/reminder_manager.py`,
`handlers/extractors/*.py`) all stay exactly where they are and are imported, unmodified, by both
the legacy path (unchanged, as today) and the new capability handlers — zero changes to any
legacy file, including imports; everything else in the new path is independent new code, selected
at startup per REQ-063-07.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
