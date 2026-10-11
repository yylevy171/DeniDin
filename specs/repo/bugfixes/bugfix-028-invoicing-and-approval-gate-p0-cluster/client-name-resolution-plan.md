# Implementation Plan: Client-name resolution architecture fix

**Parent**: `bugfix-028-invoicing-and-approval-gate-p0-cluster.md` (this is a scoped sub-piece, not a
re-scoping of the parent bug — see "Scope boundary" below)
**Branch**: `bugfix/028-invoicing-and-approval-gate-p0-cluster` (unchanged — explicit user decision,
2026-08-12, not to open a new numbered feature branch for this)
**Date**: 2026-08-12
**Input**: This document itself is the spec for this scoped piece — the architecture decision was
reached directly in conversation with the user (see "Decision history" below), not via a separate
`speckit.specify`/`user-stories.md` pass. Given-When-Then user stories are in
`client-name-resolution-quickstart.md` instead of a separate `user-stories.md` file, adapted to this
bugfix-track scope per explicit user instruction ("author whatever file you need").

**Note**: This repo's real `speckit.plan` tooling (`.specify/scripts/bash/setup-plan.sh`) requires a
`###-feature-name` branch and a pre-existing `spec.md` — neither applies to a bugfix branch. This
document is hand-authored to match `plan-template.md`'s section structure and intent, per explicit
user decision (2026-08-12) to keep everything under this scoped bugfix-028 sub-folder rather than
open a new feature track.

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III, §V, §XVII): no environment variables, Israel-local timestamps, feature
  branch workflow (already on one), real-sandbox testing (no mocking of Morning/OpenAI), no
  monkey-patching.
- **CONSTITUTION.md** ("NO UNVERIFIED THIRD-PARTY ASSUMPTIONS"): the constitution-text rewrite (Step
  7) must be verified against a real live turn before being treated as final, not just written and
  assumed correct.
- **METHODOLOGY.md** (§VII, Bug-Driven Development): each of the 8 implementation phases below gets
  its own test-first → human-approval → implement → verify loop, mirroring §VII's root-cause →
  approval → test-gap → tests → approval → fix → verify sequence, applied per-phase rather than once
  for the whole change (justified by the size/blast-radius of this change — see "Complexity Tracking").

---

## Summary

Six MCP tools in `apps/morning-mcp-app` (`create_invoice`, `create_transaction_account`,
`create_combo_document`, `update_client`, `get_client_details`, `list_invoices`) each independently run
a fuzzy/word-growth client-name-matching algorithm (`resolve_client_by_name`, bugfix-039) and can each
come back with their own "did you mean X?" disambiguation. This is architecturally wrong: resolution
should happen exactly once, orchestrated by the model, via one dedicated read-only tool
(`resolve_client_name`) — before any other tool is ever called. The six tools above become "dumb":
they require a `name_resolved: bool` flag asserting the caller already resolved the name, do only a
direct exact lookup, and fail plainly if the flag isn't set or the name doesn't match exactly.

## Technical Context

**Language/Version**: Python 3.11 (both apps, per existing `.pylintrc`/`mypy.ini`)
**Primary Dependencies**: FastMCP (`morning-mcp-app`'s `server.py`), OpenAI Responses API + MCP remote
tool attachment (`denidin-app`'s `ai_handler.py`) — both unchanged by this work, only the tool
inventory/contracts they carry change.
**Storage**: N/A — `morning-mcp-app` is stateless (confirmed: no cache/session store anywhere in
`src/denidin_mcp_morning/`); this is the deciding fact behind the boolean-not-token design decision
(see research.md).
**Testing**: `pytest`, three tiers per app (`unit`/`integration`/`billed`, plus `expensive` in
denidin-app) — all four tiers are affected by this change, see "Test impact" in
`client-name-resolution-data-model.md`.
**Target Platform**: unchanged — both apps run containerized (dev/prod), this change ships through the
normal `cut_release.sh`/`deploy_release.sh` path once merged, not part of this plan.
**Project Type**: two-app monorepo, cross-app change (`apps/morning-mcp-app` tool contracts +
`apps/denidin-app`'s `ai_handler.py` approval-gate list + `runtime_constitution.md`).
**Performance Goals**: N/A — no new performance requirement; `resolve_client_name` reuses the existing
`resolve_client_by_name` engine's real Morning API call volume, unchanged.
**Constraints**: REQ-CLIENT-018 (feature 026) — the real Morning `client_id` must never be exposed to
the model, in any tool parameter or return value. This is the reason resolution stays name-based
end-to-end (no id/token handed back to the model) — see research.md's boolean-vs-token discussion.
**Scale/Scope**: 6 tool signatures changed, 1 new tool, ~2 formatters added, 1 constitution section
rewritten, 1 approval-gate list entry added, dozens of existing tests across 3 test tiers in 2 apps
updated (full enumeration in data-model.md).

## Constitution Check

*Gate: must pass before Phase 0 research below, re-checked after Phase 1 design.*

- ✅ No environment variables introduced.
- ✅ Israel-local timestamps: unaffected (no new datetime handling).
- ✅ Git workflow: staying on the existing feature branch, no direct-to-master work.
- ✅ No mocking of Morning/OpenAI in integration/billed tests — the new `resolve_client_name` tool and
  the six migrated tools are tested the same way everything else in this app is (real sandbox
  integration tests, real conversational billed tests).
- ✅ No monkey-patching — the shared gate (`_require_resolved_client`) is a plain function, dependency-
  injected like every other helper in `tools.py`.
- ✅ REQ-CLIENT-018 preserved — `resolve_client_name` returns a name, never a `client_id`; the
  `name_resolved` flag is a plain boolean assertion, not a token/id smuggled through.
- ⚠️ **Test Immutability (CONSTITUTION §VIII)**: this change modifies/relocates a substantial number of
  already-approved tests (see data-model.md's enumeration). Each relocation/rewrite is itself part of
  this plan's explicit, gated scope — the human-approval gate at each implementation phase (see
  METHODOLOGY §VII) is how §VIII's "explicit human approval before test changes" requirement is
  satisfied here, phase by phase, not a blanket exemption.

*Re-check after Phase 1 (data-model.md/quickstart.md): no new violations introduced — confirmed during
authoring, since the design deliberately reuses existing formatters/patterns (see research.md) rather
than introducing new mechanisms.*

## Project Structure

### Documentation (this scoped piece)

```text
specs/in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster/
├── bugfix-028-invoicing-and-approval-gate-p0-cluster.md   # parent bug spec (unchanged)
├── bugfix-028-HANDOFF.md                                   # parent bug handoff (unchanged)
├── client-name-resolution-plan.md          # this file
├── client-name-resolution-research.md      # Phase 0 output
├── client-name-resolution-data-model.md    # Phase 1 output (tool/formatter contracts + full test-impact list)
├── client-name-resolution-quickstart.md    # Phase 1 output (Given-When-Then scenarios)
└── client-name-resolution-tasks.md         # Phase 2 output (/speckit.tasks equivalent)
```

### Source code (repository root)

Two-app monorepo, existing structure unchanged — no new directories:

```text
apps/morning-mcp-app/src/denidin_mcp_morning/
├── tools.py          # resolve_client_name (new), _require_resolved_client/_resolve_exact_client_name/
│                      # ResolvedClient (new, shared gate), 6 existing tool signatures gain
│                      # name_resolved, _resolve_client_for_document_creation/ClientResolution deleted
├── formatters.py      # format_client_name_resolved, format_name_not_resolved (new)
└── server.py           # new @mcp.tool() wrapper + name_resolved threaded into 6 existing wrappers

apps/morning-mcp-app/tests/{unit,integration}/   # see data-model.md's full enumeration

apps/denidin-app/src/handlers/ai_handler.py       # NO_APPROVAL_MCP_TOOLS gains "resolve_client_name"
apps/denidin-app/config/runtime_constitution.md   # Invoice Management section rewrite
apps/denidin-app/tests/{billed,expensive}/         # see data-model.md's full enumeration
```

**Structure Decision**: no new projects/packages — this is a contract change within
`morning-mcp-app`'s existing single tools/server/formatters modules, plus the two small
`denidin-app`-side companion changes (approval-gate list, constitution text) required for the new
contract to actually work end-to-end.

## Integration Contracts (METHODOLOGY §VII — mandatory, multi-component change)

**Component A (`apps/morning-mcp-app`) ↔ Component B (`apps/denidin-app`)**, over the existing MCP
remote-tool boundary (ngrok tunnel, bearer auth — transport unchanged):

- **New contract**: `resolve_client_name(name: str) -> str`, no approval required. Component B's
  `ai_handler.py` must list it in `NO_APPROVAL_MCP_TOOLS` (confirmed empirically, 2026-07-23, that an
  unlisted tool does NOT default to no-approval) — without this one-line change, the whole redesign
  silently breaks (every resolution call would incorrectly generate a pending-approval prompt).
- **Changed contract**: `get_client_details`, `list_invoices`, `create_invoice`,
  `create_transaction_account`, `create_combo_document`, `update_client` each gain a `name_resolved:
  bool = False` parameter, appended last (never inserted mid-signature, so no existing caller's
  positional arguments silently shift). Approval-gate membership for the mutating four
  (`APPROVAL_REQUIRED_MCP_TOOLS`) is unchanged — `name_resolved` does not affect approval-gating, it
  only affects what the tool does with the name once called.
- **Behavioral contract**: on `name_resolved` not `True`, every one of the six tools returns an
  ordinary string (`format_name_not_resolved()`) — never raises — so Component B/OpenAI always sees a
  plain, actionable response, consistent with every other non-exact/ambiguous case these tools already
  handle this way.

## Complexity Tracking

*Filled in because this touches 6+ existing tool contracts and dozens of existing tests — the
"Simpler Alternative Rejected" column documents why a smaller-blast-radius approach wasn't chosen.*

| Violation / Size driver | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| 6 existing tool signatures changed simultaneously (in the design, though phased incrementally in execution — see Step 2) | The whole point is a single, consistent contract across every client-name-consuming tool — partial adoption would leave exactly the "10 ways to do something" problem that prompted this change | Doing only the mutating 4 (leaving `get_client_details`/`list_invoices` on the old fuzzy-internal pattern) was explicitly rejected by the user during design — the trigger for resolution is "the user referenced a client by name," not "the tool happens to mutate" |
| Boolean `name_resolved` flag, not a stronger (token-based) enforcement mechanism | Matches the user's own "a boolean, or discuss better options" framing | A token-based mechanism was evaluated and rejected on its merits (see research.md) — it would introduce this stateless server's first stateful component with no clean scoping key available today, for marginal additional protection against a non-adversarial failure mode |
