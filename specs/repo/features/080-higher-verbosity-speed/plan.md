# Implementation Plan: Higher Verbosity, Active Feedback, and Latency Telemetry

**Branch**: `feature/080-higher-verbosity-speed` | **Date**: 2026-09-12 | **Spec**: `spec.md`
**Input**: Feature specification from `specs/repo/features/080-higher-verbosity-speed/spec.md`

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III): no environment variables, `now_local()` (Israel local time, not
  UTC — CONSTITUTION.md's UTC-everywhere rule was superseded by bugfix-037), feature-branch git
  workflow, no monkey-patching.
- **METHODOLOGY.md** (§II, IV, VII): phased planning, Integration Contracts for the
  multi-component pieces below (keep-alive ↔ Green API, telemetry ↔ every internal component
  that spends time).

---

## Summary

Three related but separable changes, one feature: (1) a keep-alive mechanism so the WhatsApp
"typing…" indicator survives turns longer than ~20s; (2) a `runtime_constitution.md` directive
telling the AI to proactively narrate progress on slow/multi-step turns; (3) a structured
per-request telemetry record (LLM time, tool time, per-tool/per-Morning-endpoint breakdown,
token counts) persisted for later analysis. REQ-080-03 (no artificial chunking of the final
reply) is a **non-goal confirmation** — `WhatsAppHandler.send_response()` already sends the
final text as one message (only truncating at >4000 chars); this feature does not change that
behavior, it just states explicitly that nothing here should introduce chunking.

## Technical Context

**Language/Version**: Python 3.11 (existing `apps/denidin-app` codebase)
**Primary Dependencies**: `whatsapp-chatbot-python`/`whatsapp_api_client_python` (Green API
client, already a dependency — `bot.api.serviceMethods.sendTyping`), `APScheduler`
(`BackgroundScheduler`, already used by `reminder_delivery_service.py` and
`accounting_reconciliation_service.py` — reused here for the keep-alive renewal, see Research),
OpenAI Responses API client (`self.client.responses.create`, already used throughout
`ai_handler.py`).
**Storage**: New — a queryable telemetry store. See Research for the storage-technology
decision (candidates: SQLite table under `{data_root}/telemetry/`, mirroring
`roll_markers.db`'s and `reminders.db`'s existing SQLite pattern, vs. structured JSON-lines log
file).
**Testing**: `pytest` — unit tests for the telemetry recorder and keep-alive renewal logic
(mocking only the external Green API/OpenAI calls, per CONSTITUTION §I/§V); the Acceptance-phase
`billed`/`expensive` scenarios are **approved** (`user-stories.md`, 2026-09-12) as: extend 5
existing `billed` tests + 2 existing `expensive` tests (bank-deposit-image and multi-component
agreement-image ledger-capture flows) with progress-update-sent + telemetry-row-written
assertions, rather than writing new dedicated tests. **Critical scope addition (operator
2026-09-12)**: because REQ-080-02 breaks the single-deterministic-reply-per-turn assumption most
existing multi-tool-call `billed`/`expensive` tests rely on, a full sweep of `tests/billed/` and
`tests/expensive/` in both apps to adapt turn-driving helpers/assertions is now required
`tasks.md` scope, completed before the 5+2 acceptance tests are trusted — see
`user-stories.md`'s "Cross-Cutting Risk" section. Manual UAT per `user-stories.md`'s Scenarios
A/B/C remains required for the end-to-end timing behavior itself (WhatsApp on-device rendering
is not something a test can assert on — same precedent as feature 048).
**Target Platform**: Existing `denidin-app` Docker container (dev/prod), no new deployable.
**Project Type**: Single project — all changes are inside `apps/denidin-app/`.
**Performance Goals**: Typing indicator must not lapse for turns up to ~180s (mirrors feature
048's original cap); telemetry recording must add negligible overhead to the request path
(target: <10ms of the request's own wall-clock time for the write itself).
**Constraints**: No blocking of the main request-handling thread by telemetry writes; keep-alive
renewal must not reintroduce feature 048's unresolved ~20s first-call scheduling delay (see
Research — root-caused before implementation, since it directly blocks REQ-080-01, even though
the user has directed "proceed as spec'd" rather than block on prior history — the root cause
is investigated as ordinary Phase 0 research, not treated as a blocking gate).
**Scale/Scope**: Every inbound message DeniDin processes (conversational + media), one telemetry
record each; keep-alive applies to every turn already covered by feature 048's typing indicator
(conversational + media, not while DeniDin is waiting on the user).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **No env vars**: telemetry storage path/enable-flag comes from `AppConfiguration`
  (`config.telemetry` block), not env vars. ✅ planned.
- **Israel local time**: every telemetry timestamp uses `now_local()` — no bare
  `datetime.now()`/`datetime.now(timezone.utc)`. ✅ planned.
- **No monkey-patching**: keep-alive renewal and telemetry recording are both implemented as
  explicit calls at existing boundary-crossing sites (mirroring feature 048's
  `send_typing_indicator` call sites and `whatsapp_audit_log.py`'s inbound/outbound logging
  sites), not via method replacement. ✅ planned.
- **`pathlib.Path`**: any new file/DB path uses `Path`. ✅ planned.
- **Feature flag**: new behavior (keep-alive renewal, telemetry recording, constitution
  progress-update directive) gated under `config.feature_flags`, default `false`, byte-identical
  path when disabled. ✅ planned — see data-model.md / contracts.
- **Integration Contracts (METHODOLOGY §VII)**: this is multi-component (WhatsApp/Green API ↔
  keep-alive renewer; every tool-call/LLM-call site ↔ telemetry recorder ↔ storage). See
  `contracts/` for the explicit interfaces.

No violations requiring Complexity Tracking at this stage.

## Project Structure

### Documentation (this feature)

```text
specs/repo/features/080-higher-verbosity-speed/
├── plan.md              # This file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   ├── keep-alive-renewal.md
│   └── telemetry-recorder.md
└── tasks.md              # Phase 2 output (speckit.tasks — not this command)
```

### Source Code (repository root)

```text
apps/denidin-app/
├── src/
│   ├── utils/
│   │   ├── green_api_bot.py          # send_typing_indicator() gains an optional
│   │   │                              # renewal loop (feature-flagged); reuses
│   │   │                              # APScheduler pattern instead of feature 048's
│   │   │                              # reverted raw-thread renewer
│   │   └── time_utils.py             # now_local() — reused, unchanged
│   ├── managers/
│   │   └── telemetry_manager.py      # NEW — records/persists RequestTelemetry
│   ├── handlers/
│   │   ├── ai_handler.py             # instruments LLM call time, tool call time/name,
│   │   │                              # token counts; emits one RequestTelemetry per turn
│   │   └── whatsapp_handler.py       # wires request_id / timestamp_received at webhook
│   │                                  # receipt, keep-alive start/stop around processing
│   └── models/
│       └── telemetry.py              # NEW — RequestTelemetry dataclass
├── config/
│   └── runtime_constitution.md       # NEW section: proactive progress-update directive
│                                      # (REQ-080-02), with explicit scope/cross-references
│                                      # per CLAUDE.md's "every tool-bearing feature needs
│                                      # explicit constitution boundaries" rule
└── tests/
    ├── unit/
    │   ├── test_telemetry_manager.py       # NEW
    │   └── test_green_api_bot.py           # extended for renewal behavior
    └── billed/
        └── test_progress_update_behavior.py  # NEW — Acceptance-phase only, per
                                                 # METHODOLOGY §VI TDD redefinition
```

**Structure Decision**: Single project, all within `apps/denidin-app/`. No changes to
`apps/morning-mcp-app/` are required for this feature — Morning-endpoint latency breakdown
(`morning_api_request_times_ms`) is captured from the *caller* side (denidin-app's MCP tool-call
result handling), not inside the Morning server itself, since that server already logs its own
timings independently (bugfix-036/037 audit logging) and duplicating instrumentation there is
out of scope.

## Complexity Tracking

*No Constitution Check violations at this stage — table intentionally empty.*
