# Implementation Plan: Fuzzy Client Lookup by Name — Feature 031

**Feature**: 031-fuzzy-client-lookup-by-name
**Branch**: `031-fuzzy-client-lookup-by-name`
**Spec**: `./spec.md` · **Research**: `./research.md`
**Status**: Ready for Task Generation
**Updated**: July 30, 2026

**Compliance**: CONSTITUTION.md (§I no env vars — N/A, no config touched; §II UTC — N/A, no
timestamps added; §III git workflow; §V real-sandbox integration tests / zero mocking of external
services — the one new test hits the real Morning sandbox, no mocks) and METHODOLOGY.md (§I
spec-first, §VI TDD). No new feature flag: this is a test-only addition confirming already-correct
production behavior, not a behavior change.

---

## Summary

Phase 0 research (see `research.md` Decision 1) resolved this spec's only open question with a
live sandbox investigation: Morning's real `/documents/search` `clientName` param already does
case-insensitive full-text substring matching across the whole client name (confirmed via six
probes against a real seeded invoice — first word, a non-prefix middle word, a suffix word, and a
lowercase variant all matched; an unrelated random string correctly found nothing). This is *more*
permissive than the spec's original concern (a plain "Yossi" query against a client filed as
"Yossi Cohen Ltd" already works today, with no code change).

**Deliverable**: a single new permanent regression test asserting a non-prefix substring match on
`list_invoices`, so a future change in Morning's own matching behavior would be caught rather than
silently assumed. **No production code changes** to `apps/morning-mcp-app` or `apps/denidin-app`
are required — `list_invoices`/`_map_list_invoices_filters` (`tools.py:354-371`) is already
correct as built, and the existing prompt-level fuzzy-matching guidance
(`runtime_constitution.md:364-371`, predates this spec) already tells the model not to require an
exact match.

## Technical Context

- **Language/Version**: Python 3.11 (unchanged).
- **Primary Dependencies**: none new — reuses existing `pytest` + the real `MorningClient`
  sandbox-test pattern already established by `test_morning_sandbox_list_invoices_tool.py`.
- **Storage**: N/A.
- **Testing**: one new real-Morning-sandbox integration test in
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_list_invoices_tool.py` (no mocks —
  CONSTITUTION §V), mirroring the existing `test_list_invoices_tool_finds_seeded_invoice_by_client_name`
  structure and its up-to-18s indexing-wait poll loop.
- **Target Platform**: N/A — no runtime/container change.
- **Constraints**: none beyond the existing sandbox test conventions (unique marker per run, no
  cleanup needed per existing pattern, real network call to the sandbox each time this test runs).
- **Scale/Scope**: single test file, single new test function.

## Constitution Check (pre-Phase 0)

- **No env vars** — PASS: no new config.
- **UTC** — N/A: no new timestamp handling.
- **Feature branch** — PASS: `031-fuzzy-client-lookup-by-name`.
- **Feature flags** — N/A: no behavior change to gate: production code is unchanged, only test
  coverage is added.
- **Real-sandbox tests / ZERO-MOCKING** — PASS (by construction): the new test hits the real
  Morning sandbox exactly like its sibling tests in the same file; no `unittest.mock`.
- **No monkey-patching** — N/A: no new production code.
- **Test immutability (§VIII)** — PASS: this only *adds* a new test function; no existing test is
  modified or rewritten.
- **Friendly errors (§X)** — N/A: no new error path introduced.

*Re-checked post-Phase-0 research: unchanged — the research finding narrowed the deliverable to
test-only, which if anything reduces Constitution Check surface area versus what the spec
originally anticipated (a possible `list_invoices` code change routing through `search_clients`).*

## Integration Contracts (METHODOLOGY §VII)

No new component boundary is introduced or changed — this feature adds test coverage against the
existing, unchanged `list_invoices` ↔ `MorningClient.list_invoices` ↔ `/documents/search` contract.
Documenting the **confirmed** (not just assumed) contract for the record:

**`/documents/search`'s `clientName` query param** (Morning API, confirmed live 2026-07-30):
- Case-insensitive, full-text substring match against the stored client name — matches any word or
  substring position (start, middle, end), not prefix-only.
- An unrelated string that doesn't appear anywhere in any client name returns zero results (not a
  match-everything no-op) — confirmed by the pre-existing
  `test_list_invoices_tool_returns_readable_string_for_no_matches` test.
- This is more permissive than `POST /clients/search`'s `name` param (Feature 026, confirmed
  token-**prefix**-only) — the two Morning endpoints do not share matching semantics, and
  `list_invoices` should keep passing `client_name` straight through to `/documents/search` rather
  than routing it through `search_clients` first (which would make matching *stricter*, not more
  permissive, for this specific tool).

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/031-fuzzy-client-lookup-by-name/
├── spec.md         # done — Problem Statement, Clarifications (2026-07-30), resolved Open Questions
├── research.md     # done — Phase 0 output, Decision 1 (live sandbox finding)
├── plan.md         # this file
└── tasks.md        # Phase 2 output — /speckit.tasks, not produced by this command
```
(No `data-model.md`, `contracts/`, or `quickstart.md` — this feature adds no new entities, no new
MCP tool contracts, and no new user-facing setup steps; those Phase 1 artifacts would be pure
boilerplate for a test-only change and are intentionally omitted.)

### Source Code

```text
apps/morning-mcp-app/tests/integration/test_morning_sandbox_list_invoices_tool.py
  # + one new test: a non-prefix substring client_name query against a seeded invoice,
  #   mirroring test_list_invoices_tool_finds_seeded_invoice_by_client_name's structure
  #   (unique marker, up-to-18s indexing-wait poll loop)
```

**Structure Decision**: no new modules; single test-file addition in `apps/morning-mcp-app`, the
app that owns the Morning integration. No `apps/denidin-app` changes — its existing prompt-level
fuzzy-matching guidance (`runtime_constitution.md:364-371`) already covers the model-facing side
and needs no update given how permissive Morning's actual behavior turned out to be.

## Phased Execution

### Phase 0 — Research (complete, see research.md)
Live sandbox investigation of `/documents/search`'s `clientName` matching semantics. **Checkpoint**:
resolved — substring match confirmed, no code change needed, scope narrowed to test-only.

### Phase 1 — Regression test (TDD)
Add the one new sandbox test per METHODOLOGY §VI (test written and run against the real sandbox;
since no production code changes, there is no RED→GREEN transition in the usual sense — the
test should pass immediately given already-correct production behavior, serving as a **regression
lock**, not a bug-driving test). **Checkpoint**: new test passes against the real sandbox.

### Phase 2 — Close out
Update this spec's `Status` to reflect completion and move it to `specs/done/` per the folder
movement rules once the test is merged.

## Complexity Tracking

No Constitution Check violations requiring justification — this feature adds one test function and
no production code, dependencies, or infrastructure.
