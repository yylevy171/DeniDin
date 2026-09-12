# Implementation Plan: WhatsApp Reactions

**Branch**: `feature/084-whatsapp-reactions-impl` | **Date**: 2026-09-12 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/in-progress/084-whatsapp-reactions/spec.md`

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I, §V, §XI, §XVII, NO UNVERIFIED THIRD-PARTY ASSUMPTIONS): No env vars
  (nothing new is configurable per-environment beyond the existing config file), no mocking of
  internal components, the CONSTITUTION §XI retry policy (retry once on 5xx/timeout after 1s,
  never retry 4xx) applied explicitly to the new Green API call, no monkey-patching of the vendored
  `whatsapp_api_client_python` SDK, and — because this feature introduces a brand-new, never-before-
  exercised third-party integration (Green API's reaction endpoint) — a mandatory, blocking,
  human-approved Gate Zero live verification before that endpoint's shape is trusted.
- **METHODOLOGY.md** (§II, IV, VII): Integration Contracts written (`contracts/*.md`).

---

## Summary

Add native WhatsApp emoji reactions at two points in the message pipeline: (1) a fast, heuristic,
non-LLM "in-flight" reaction dispatched from `denidin.py`'s webhook dispatch path within the
spec's <1000ms budget, giving the user immediate visual feedback that a document or action request
is being processed; and (2) a model-driven `react_to_message` AI tool the LLM can call during its
own reasoning to set a reaction on the current turn, or to flip a reaction set earlier in the same
multi-turn workflow (e.g. flipping a document's in-flight 👀 to a final ✅/❌ once ledger capture
resolves). Green API's reaction endpoint has no existing wrapper anywhere in this codebase's
vendored SDK, so a new thin helper is added using the SDK's own `bot.api.request()` wrapper (the
same mechanism every existing Green API call in this codebase already uses) against the
live-confirmed `sendReaction` endpoint, rather than hand-rolled HTTP or a patch into third-party
source. Group
chats only ever react to messages DeniDin actually engages with (reusing the existing addressed-to-
bot check, never duplicating it); 1:1 discretion and creative/conversational reactions are governed
by a new `runtime_constitution.md` section, not code. Reaction failures are isolated entirely inside
the new helper — logged at WARNING, never propagated into the core conversational turn or any
ledger/document transaction.

## Technical Context

**Language/Version**: Python 3.9+ (existing project floor, `apps/denidin-app`)
**Primary Dependencies (new)**: none — no new pip packages. The implementation relies entirely on
the SDK's own `bot.api.request()` wrapper (already vendored in `whatsapp-api-client-python`,
used internally by every existing `Sending` method) against the live-confirmed `sendReaction`
endpoint (`research.md` R1, Gate Zero closed 2026-09-12).
**Storage**: no new persistent storage / no new SQLite table. Reactions are stateless, fire-and-
forget side effects on Green API's side; the only new state is two lightweight in-process fields
(see `data-model.md`) threaded through existing `Message`/`Session` objects.
**Testing**: `tests/unit/` covers the new `send_reaction()` helper (retry-once/never-retry-4xx
policy, WARNING logging, never-raises contract, against a stubbed `bot.api.request`) and the
fast-path heuristic's classification logic in isolation. `tests/integration/` covers real router
dispatch through `bot.router` for the fast-path hook (verifying group ambient messages produce zero
reaction calls, and that addressed messages do). `tests/billed/` covers the `react_to_message` tool
being offered/called correctly during a real conversational turn. No `tests/expensive/` — nothing
here calls vision.
**Target Platform**: N/A beyond the code change itself — no container/runtime change, no
`requirements.txt` update (existing rebuild-on-merge process applies once merged).
**Performance Goals**: fast-path reaction dispatched and Green API request issued within the
spec's <1000ms budget from webhook arrival (SC-001) — achievable synchronously (plain HTTP, no LLM
call) but flagged in `quickstart.md` as an item to time-verify against the real environment, not
just assumed from the absence of an LLM call.
**Constraints**: reaction calls must never block or fail the core conversational turn or a ledger/
document transaction (REQ-084-007); group ambient messages must produce literally zero reaction
webhooks (SC-003), enforced by the same addressed-to-bot predicate the existing group-etiquette
logic already uses, never a second, independently-drifting check.
**Scale/Scope**: one new Green API helper (`send_reaction`); one new AI tool (`react_to_message`,
dispatched immediately, no approval gate); one new fast-path pre-dispatch hook in `denidin.py`
(not a new `HANDLER_REGISTRY` entry — that table's exact 8-key shape is locked by an existing test);
two new optional fields threaded through existing `Message`/`Session` objects; one new
`runtime_constitution.md` section plus cross-reference edits to every other tool-bearing section.

## Constitution Check

*GATE: Must pass before Phase 0 research is closed. Re-checked after Phase 1 design (this
document).*

- ✅ **§I No env vars**: nothing new is configurable; no config file changes are needed at all for
  this feature (the fast-path emoji/keyword tables are code constants, not config).
- ✅ **§V no mocking of internal components**: `tests/integration/` exercises real router dispatch
  (a real notification through `bot.router`), real internal objects throughout. The one genuinely
  new third-party dependency this feature introduces — Green API's reaction endpoint — is mocked
  only at the unit tier (permitted; unit tests may stub `bot.api.request`). `research.md`'s Gate
  Zero has already closed at the integration/live tier (2026-09-12) — no mock ever substituted for
  actually confirming Green API's real behavior before implementation proceeds.
- ✅ **§XI retry policy**: `send_reaction()` applies the retry-once-on-5xx/timeout-after-1s /
  never-retry-4xx policy explicitly and locally (there is no shared retry decorator for Green API
  calls elsewhere in this codebase to reuse — `mark_message_read`/`send_proactive_message` each
  handle their own failure paths locally too, so this is consistent with the existing idiom, not a
  new one).
- ✅ **§XVII No monkey-patching**: `send_reaction()` is a new, plain function in `green_api_bot.py`
  calling the SDK's own already-public `request()` method — no patching of
  `whatsapp_api_client_python`'s classes, no dynamic attribute injection.
- ✅ **NO UNVERIFIED THIRD-PARTY ASSUMPTIONS**: the exact reaction endpoint path/payload/response
  shape, and the flip-not-stack (empty string clears, new emoji replaces) semantics the spec's own
  glossary asserts, were confirmed live via a real, human-approved Gate Zero call (`research.md`
  R1, closed 2026-09-12) — two pre-verification assumptions (the endpoint path and the payload key
  name) turned out wrong and were corrected from the real, observed behavior, not merely inferred
  from documentation.
- **No feature-flag deviation, confirmed by human decision (2026-09-12)**: this feature ships
  without a `config.feature_flags` gate, same as Feature 054 — a wrong reaction is cosmetic, not a
  data-integrity or financial concern, and nothing existing is being altered, only a new, additive
  side effect.

## Integration Contracts

Per METHODOLOGY §VII (multi-component feature: `denidin.py`, `green_api_bot.py`, `ai_handler.py`,
`session_manager.py`, and `runtime_constitution.md` all gain new responsibilities). Full contracts
in `contracts/`:

1. **`contracts/green-api-reaction-client.md`** — `send_reaction()`'s signature, retry policy,
   logging contract, and its Gate Zero dependency.
2. **`contracts/react-to-message-tool-schema.md`** — the `react_to_message` tool schema, its
   no-approval-gate dispatch, and its `message_id` resolution fallback chain.
3. **`contracts/fast-path-reaction-heuristic.md`** — the pre-dispatch hook's exact placement in
   `dispatch_notification()`, its media/action-request classification tables, and its shared
   flip-not-stack contract with the AI tool.
4. **`contracts/group-discretion-gating.md`** — the fast-path classification-as-gate design
   (corrected 2026-09-12: no separate addressed-to-bot predicate exists to extract) and the new
   `runtime_constitution.md` section (including the classics list) plus required cross-references.
5. **`contracts/reaction-judgment-tuning.md`** — the scenario pool, capture-stub mechanism,
   rotation harness, and the AI-run iterative tuning loop that replaces fixed acceptance scenarios
   for judgment quality (human decision, 2026-09-12).

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/084-whatsapp-reactions/
├── spec.md                # done — approved 2026-09-12
├── user-stories.md        # done — 5 prioritized stories
├── plan.md                # this file
├── research.md            # this phase's output — Gate Zero OPEN/blocking
├── data-model.md          # this phase's output
├── quickstart.md          # this phase's output
├── contracts/
│   ├── green-api-reaction-client.md      # this phase's output
│   ├── react-to-message-tool-schema.md   # this phase's output
│   ├── fast-path-reaction-heuristic.md   # this phase's output
│   ├── group-discretion-gating.md        # this phase's output
│   └── reaction-judgment-tuning.md       # this phase's output
└── tasks.md                # NOT yet run (/speckit.tasks)
```

### Source Code (repository root, single project — `apps/denidin-app/`)

```text
apps/denidin-app/
├── denidin.py                              # MODIFIED — new _dispatch_fast_path_reaction() call
│                                            #   inside dispatch_notification(), after the dedup
│                                            #   check and before HANDLER_REGISTRY.get(...); never
│                                            #   touches HANDLER_REGISTRY's own shape.
├── src/
│   ├── managers/
│   │   └── session_manager.py              # MODIFIED — Message gains whatsapp_id_message
│   │                                        #   (Optional[str]); Session gains
│   │                                        #   active_document_message_id (Optional[str]).
│   ├── utils/
│   │   └── green_api_bot.py                # MODIFIED — + send_reaction().
│   └── handlers/
│       └── ai_handler.py                   # MODIFIED — new REACT_TO_MESSAGE_TOOL schema,
│                                            #   attached unconditionally (no RBAC gate), dispatched
│                                            #   immediately (no PendingLocalToolApprovalManager
│                                            #   involvement) via the existing local-tool dispatch
│                                            #   loop.
├── config/
│   └── runtime_constitution.md             # MODIFIED — new `## Reaction Management` section
│                                            #   (with the classics list) + cross-reference edits to
│                                            #   every other tool-bearing section (Reminder
│                                            #   Management, Ledger Event Querying, Morning MCP
│                                            #   sections).
├── scripts/
│   └── run_reaction_tuning.sh              # NEW — rotation/state harness for the reaction
│                                            #   judgment tuning loop (see
│                                            #   contracts/reaction-judgment-tuning.md)
└── tests/
    ├── unit/
    │   ├── test_green_api_bot.py                       # MODIFIED (already exists) — +
    │   │                                                #   send_reaction tests (retry/never-raise/
    │   │                                                #   WARNING-log contract, stubbed
    │   │                                                #   bot.api.request)
    │   ├── test_fast_path_reaction_heuristic.py         # NEW — media/action-request
    │   │                                                 #   classification, addressed-to-bot
    │   │                                                 #   gating, no LLM call involved
    │   └── test_reaction_tuning_harness.py              # NEW — rotation-state selection, the
    │                                                     #   capture-stub's interception/logging
    │                                                     #   shape (plumbing only, not judgment)
    ├── integration/
    │   └── test_reaction_dispatch_routing.py            # NEW — real notification through
    │                                                     #   bot.router; addressed group message
    │                                                     #   produces a reaction call, ambient
    │                                                     #   group message produces zero
    ├── billed/
    │   └── reaction_judgment_pool.py                    # NEW — see
    │                                                     #   contracts/reaction-judgment-tuning.md
    └── expensive/
        └── reaction_judgment_pool.py                    # NEW — same, vision-based scenarios
```

**Structure Decision**: Single project, following the exact placement convention already used for
`mark_message_read`/`send_proactive_message` (`utils/green_api_bot.py`) and the reminder/ledger
local-tool pattern (`handlers/ai_handler.py`) — no new top-level module, every new piece lands
where its closest analog already lives.

## Phased Implementation Order

1. **Phase 0 — Research**: ✅ done. `research.md`'s non-live decisions (fast-path emoji/keyword
   tables) are resolved, and Gate Zero R1 (live Green API reaction call) has closed (2026-09-12) —
   the confirmed endpoint/mechanism/payload shape below are live-verified, not assumed.
2. **Phase 1 — `send_reaction()` helper**: `green_api_bot.py`, fully unit-testable in isolation
   against a stubbed `bot.api.request` — lowest-risk, foundational, build first.
3. **Phase 2 — Data model additions**: `Message.whatsapp_id_message`, `Session.active_document_message_id`
   in `session_manager.py`, plus the capture point (inbound webhook parsing already extracts
   `idMessage` for read-receipt purposes — reuse that extraction, do not re-derive it).
4. **Phase 3 — Fast-path hook**: `denidin.py`'s pre-dispatch hook, whose own classification is the
   entire gate (corrected 2026-09-12 — no separate addressed-to-bot predicate exists to extract,
   see `contracts/group-discretion-gating.md`'s Correction).
5. **Phase 4 — `react_to_message` AI tool**: schema + immediate-dispatch wiring in `ai_handler.py`,
   depends on Phases 1-2 for the resolution fallback chain to have real fields to read.
6. **Phase 5 — `runtime_constitution.md`**: new `## Reaction Management` section (with the classics
   list) + cross-reference edits, reviewed the same way Feature 054's reminder section was.
7. **Phase 6 — Reaction judgment tuning**: build the scenario pool, capture stub, and
   `scripts/run_reaction_tuning.sh` rotation harness (`contracts/reaction-judgment-tuning.md`), then
   run the iterative tuning loop (AI-run, billed rounds first, expensive rounds once billed judgment
   looks stable) until judgment is consistently sound across rotated subsets.
8. **Phase 7 — `quickstart.md` manual verification**: the handful of items the tuning harness
   deliberately doesn't cover (see Testing Strategy below).

## Testing Strategy

**Human decision (2026-09-12)**: this feature does NOT use fixed `billed`/`expensive` acceptance
scenarios asserting a specific expected emoji — see `user-stories.md`'s "Acceptance Approach"
section and `contracts/reaction-judgment-tuning.md` for the full reasoning and replacement
mechanism.

**Unit** (`tests/unit/`, no network): `test_green_api_bot.py` additions (never-raises contract,
retry-once-on-5xx-never-on-4xx, WARNING logging, correct payload construction — all against a
stubbed `bot.api.request`, permitted at the unit tier), `test_fast_path_reaction_heuristic.py`
(media vs. action-request classification, addressed-to-bot gating producing zero calls for
un-addressed group messages, rapid-burst "primary message only" logic), and unit tests for the
tuning harness's own plumbing (rotation-state selection, the capture-stub's interception/logging
shape — not the judgment content it captures).

**Integration** (`tests/integration/`, real router dispatch, no mocking of internal components):
a real notification through `bot.router` confirming an addressed group/1:1 message triggers a
(stubbed-at-the-Green-API-boundary-only) reaction call and an ambient, unaddressed group message
does not.

**Reaction judgment tuning** (`tests/billed/reaction_judgment_pool.py` +
`tests/expensive/reaction_judgment_pool.py`, run via `scripts/run_reaction_tuning.sh`, AI-run and
AI-reviewed, not a fixed pass/fail acceptance gate): see `contracts/reaction-judgment-tuning.md` in
full — hard assertions only on deterministic plumbing within these scenarios (zero calls for
ambient group scenarios, correct flip targeting), never on emoji choice itself.

**Manual/`quickstart.md`-only**: the <1000ms fast-path timing check against a real dev environment;
the deleted-message-before-reaction edge case (already resolved as a silent no-op per Gate Zero,
but worth a real confirmation once implemented).

## Complexity Tracking

No Constitution Check violations requiring justification. The no-feature-flag decision above is
settled by explicit human confirmation (2026-09-12).
