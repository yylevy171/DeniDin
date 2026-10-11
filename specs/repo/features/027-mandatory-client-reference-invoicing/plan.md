# Implementation Plan: Mandatory Reference to an Existing Client for Invoice Creation — Feature 027

**Feature**: 027-mandatory-client-reference-invoicing
**Branch**: `feature/027-mandatory-client-reference-invoicing`
**Spec**: `./spec.md` · **User stories**: `./user-stories.md`
**Status**: Ready for Task Generation
**Updated**: August 6, 2026

**Compliance**: CONSTITUTION.md (§I no env vars, §II UTC N/A — no new timestamp handling, §III git
workflow, §V real-sandbox integration tests / zero mocking of external services, §X friendly
errors, §XVII no monkey-patching, "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" — satisfied by this
feature's own live sandbox confirmation, see research.md Decision 1) and METHODOLOGY.md (§I
spec-first, §VI TDD, §VII integration contracts). No feature flag: this is a pure correctness fix
to existing tools' payload construction, not new user-facing behavior requiring staged rollout —
mirrors how Feature 026 shipped its `add_client` approval-gate reversal directly, spec-approved,
no toggle.

---

## Summary

Fix 6 existing Morning MCP document-creation tools, in two groups, to stop attaching documents to
a bare client-name string and instead attach them to a real Morning client record:

- **Group A** (`create_invoice`, `create_transaction_account`, `create_combo_document`): resolve
  their `client_name` argument via Feature 026's existing `_resolve_client_by_name` helper before
  building the `/documents` payload — attach by real `client_id` on exactly one match (disclosing
  non-exact matches), refuse with a friendly message on zero or multiple matches. No new tool, no
  new parameter, no new approval-gate logic — `client_name: str` stays the only client-identifying
  input, and the existing per-tool MCP approval gate (`AIHandler.APPROVAL_REQUIRED_MCP_TOOLS`)
  needs no change at all.
- **Group B** (`create_credit_note`, `create_receipt`, `close_transaction_account`): stop
  discarding the real `client.id` that's already present on their fetched linked original document
  — use it when present; refuse (create nothing) when absent (a pre-feature, bare-name-only
  original). No search/resolution logic needed here at all — simpler than Group A.

Both groups' fixes are confined entirely to `apps/morning-mcp-app` — no `apps/denidin-app` change,
since every one of these 6 tools is already individually listed in
`AIHandler.APPROVAL_REQUIRED_MCP_TOOLS` today.

## Technical Context

- **Language/Version**: Python 3.11 (unchanged).
- **Primary Dependencies**: none new. Reuses existing `requests`/`urllib3` (`MorningClient`),
  `mcp` (FastMCP), and Feature 026's `_resolve_client_by_name`/`_is_exact_name_match`/
  `format_client_not_found`/`format_ambiguous_clients_message`.
- **Storage**: none new. Morning remains the sole source of truth (no local mirror, unchanged).
- **Testing**: real-Morning-sandbox integration tests (`apps/morning-mcp-app/tests/integration/`,
  no mocks — CONSTITUTION §V) for all 6 tools' new client-attachment behavior; real-API E2E tests
  (`apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py`, `@pytest.mark.expensive`)
  for the full WhatsApp-turn flows (US1-US6), reusing existing `e2e_helpers.py` infrastructure.
  **All client names in any automated test MUST use the existing `_unique_marker(label)` →
  `f"Test Client {marker}"` mechanism** (research.md Decision 8) — never the illustrative persona
  names ("Danny Cohen" etc.) from `user-stories.md`/`quickstart.md`, which are narrative-only.
- **Target Platform**: existing containerized runtime, unchanged (Docker, `run_morning_mcp.sh`).
- **Constraints**: no env vars; UTC N/A (no new timestamps); `pathlib.Path` N/A (no new file I/O);
  no monkey-patching; friendly (Hebrew) errors for Group B's refusal path; tests immutable once
  approved (no existing test is expected to need rewriting — this is new behavior on top of
  currently-passing tests that never asserted the old bare-name shape as a requirement, only as an
  incidental fact).

## Constitution Check (pre-Phase 0)

- **No env vars** — PASS: no new config keys.
- **UTC** — N/A: no new timestamp handling.
- **Feature branch** — PASS: `feature/027-mandatory-client-reference-invoicing`.
- **Feature flags** — N/A, deliberate: this is a correctness fix (documents were never supposed to
  be bare-name-only; that was always the bug this feature exists to close), not new opt-in
  behavior — mirrors Feature 026's direct, unflagged `add_client` behavior change.
- **Real-sandbox tests / ZERO-MOCKING** — MUST ADHERE: every story (US1-US6) gets a failing
  real-sandbox test before implementation; no `unittest.mock` of the Green Invoice API or the
  OpenAI Responses API.
- **No monkey-patching** — PASS: all changes are plain function-body edits to existing
  `tools.py` functions (payload builders + their callers) using existing dependency-injected
  `MorningClient` instances — no globals, no runtime attribute replacement.
- **No unverified third-party assumptions** — PASS, explicitly: the core API-behavior question
  (does `/documents` accept `client.id`?) was answered via a real, live sandbox call before this
  plan was written (research.md Decision 1), not assumed from documentation.
- **Friendly errors (§X)** — Group B's new refusal path (REQ-INV-013) needs a **new** formatter
  (`format_original_not_linked_to_client()` or similar) — the existing generic
  `friendly_error_message` mapping (for exceptions) doesn't fit here since this is a normal,
  non-exceptional return value (mirrors how `format_client_not_found()` is a normal return, not an
  exception path), matching the "[emoji] [what happened]. [what to do next]." shape.

## Integration Contracts (METHODOLOGY §VII)

### `apps/morning-mcp-app` tools.py — Group A payload builders

**`_build_create_invoice_payload`/`_build_transaction_account_payload`/`_build_combo_document_payload`
MUST**:
- No longer take a bare `client_name: str` and blindly embed it. Each builder's **caller**
  (`create_invoice`/`create_transaction_account`/`create_combo_document`) MUST first call
  `_resolve_client_by_name(client, client_name)` and branch:
  - 0 matches → return `format_client_not_found()` immediately; never call the builder or
    `client.create_invoice` (REQ-INV-003).
  - >1 matches → return `format_ambiguous_clients_message(candidates)` immediately; never call the
    builder (REQ-INV-005).
  - Exactly 1 match → call the builder with the **resolved `client_id`** instead of the raw
    `client_name` string; the builder emits `"client": {"self": False, "id": client_id}` (no
    `name` field) (REQ-INV-002). If `_is_exact_name_match(resolved.name, client_name)` is `False`,
    the caller prepends a disclosure line to the confirmation reply before returning it
    (REQ-INV-011) — this is call-site text composition, not a `formatters.py` change (research.md
    Decision 5).

**`_resolve_client_by_name`/`_is_exact_name_match`/`format_client_not_found`/
`format_ambiguous_clients_message` PROVIDE**: unchanged (Feature 026) — reused verbatim, zero
modification.

### `apps/morning-mcp-app` tools.py — Group B payload builders

**`_build_cancellation_payload`/`_build_payment_receipt_payload`/`_build_combo_closing_payload`
MUST**:
- Change their `client` object construction from
  `{"self": False, "name": client_info.get("name")}` to checking `client_info.get("id")` first:
  present → `{"self": False, "id": client_info["id"]}` (REQ-INV-012).
- The **calling** tool function (`create_credit_note`/`create_receipt`/
  `close_transaction_account`) MUST check `original.get("client", {}).get("id")` **before**
  calling the builder or `client.create_invoice` — if absent, return the new
  `format_original_not_linked_to_client()`-style message immediately, calling nothing further
  (REQ-INV-013). This check happens right after the existing `original = client.get_invoice(...)`
  call each of these functions already makes — no new network round-trip.

**`formatters.py` MUST** gain one new formatter for the Group B refusal message (research.md
Decision 7) — no existing formatter's wording fits this specific situation.

**`MorningClient` PROVIDES**: unchanged — `get_invoice`, `create_invoice` (generic `POST
/documents` wrapper, accepts whatever payload `dict` it's given, per Feature 005/018/021).

### `AIHandler` / `runtime_constitution.md` — no code change, one guidance addition

**AIHandler**: **no change** — every one of the 6 target tools is already individually listed in
`APPROVAL_REQUIRED_MCP_TOOLS` (confirmed by reading `ai_handler.py` directly during
`/speckit.specify`). This feature adds no new tool name to gate.

**`runtime_constitution.md` MUST** gain guidance for REQ-INV-004's model-driven flow (Group A,
US2): on seeing a "client not found" reply from any Group A tool, ask the godfather for
phone/email and call `add_client`, then retry the original request — mirrors the existing pattern
already taught for invoice_id resolution (Feature 026's own constitution addition). No guidance
change needed for Group B (US6) — refusal there has no inline-fixable follow-up the model should
attempt (there is no remediation path, per Clarifications), so the constitution should say nothing
that implies one exists.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/027-mandatory-client-reference-invoicing/
├── spec.md                          # done, corrected for Group A/B 2026-08-06
├── user-stories.md                  # done, corrected for Group A/B 2026-08-06 (US1-US6)
├── checklists/requirements.md
├── plan.md                          # this file
├── research.md                      # Phase 0 output
├── data-model.md                    # Phase 1 output
├── contracts/                       # Phase 1 output
│   ├── create_invoice.json          # Group A
│   ├── create_transaction_account.json   # Group A
│   ├── create_combo_document.json   # Group A
│   ├── create_credit_note.json      # Group B
│   ├── create_receipt.json          # Group B
│   └── close_transaction_account.json    # Group B
└── quickstart.md                    # Phase 1 output
```
(`tasks.md` is Phase 2 output — `/speckit.tasks`, not produced by this command.)

### Source Code

```text
apps/morning-mcp-app/src/denidin_mcp_morning/
├── tools.py
│   # Group A (changed): create_invoice, create_transaction_account, create_combo_document
│   #   + their _build_*_payload helpers - add resolve/attach/refuse/disclose logic
│   # Group B (changed): create_credit_note, create_receipt, close_transaction_account
│   #   + _build_cancellation_payload, _build_payment_receipt_payload,
│   #   _build_combo_closing_payload - preserve client.id or refuse
├── formatters.py
│   # + one new formatter for Group B's refusal message (REQ-INV-013)
└── server.py                        # unchanged - no tool signature changes on either group

apps/morning-mcp-app/tests/integration/
├── test_morning_sandbox_invoices_crud.py           # (changed) add client-attachment assertions
├── test_morning_sandbox_create_invoice_client_resolution.py   # NEW (Group A: found/not-found/ambiguous/non-exact)
├── test_morning_sandbox_group_a_uniformity.py      # NEW (create_transaction_account/create_combo_document, US4)
└── test_morning_sandbox_group_b_client_preservation.py        # NEW (US6: preserve-or-refuse, all 3 Group B tools)

apps/denidin-app/config/runtime_constitution.md
  # add guidance for the "client not found -> ask for details -> add_client -> retry" flow (Group A only)

apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py
  # (changed) new E2E scenarios for US1-US6 (real WhatsApp-turn flows through the real webhook router)
```

**Structure Decision**: All new logic lives in `apps/morning-mcp-app` (tools + formatters + tests),
consistent with Feature 026/021 — the Morning integration lives entirely there.
`apps/denidin-app` gets only a `runtime_constitution.md` prompt addition (mounted config, hot-reloaded
by mtime — no rebuild needed) plus new E2E test scenarios; no source code change.

## Phased Execution

### Phase 0 — Research (this plan's Phase 0, see research.md)
Already complete before this plan was drafted: the live `client.id`-attachment confirmation
(Decision 1), the Group A/B code-reading discovery (Decision 2), the preservation mechanism
(Decision 3), the backward-compat refuse decision (Decision 4, user-confirmed), and the two
formatter decisions (5, 7). **No unknowns remain that block implementation.**

### Phase 1 — Group A: resolve/attach/refuse/disclose (TDD)
`create_invoice` first (most-used tool, already has the richest existing test coverage to extend),
then `create_transaction_account`/`create_combo_document` reusing the same helper logic — each
preceded by a real-sandbox test per CONSTITUTION §V, following METHODOLOGY §VI's
EXPLAIN → RED → GREEN → REFACTOR gates. Covers US1-US4.

### Phase 2 — Group B: preserve-or-refuse (TDD)
`create_credit_note`, `create_receipt`, `close_transaction_account` — simpler than Phase 1, no
search/disambiguation involved. New formatter for the refusal message. Covers US6. Needs the
raw-`MorningClient`-seeded "no `id`" fixture noted in research.md's Outstanding item.

### Phase 3 — denidin-app constitution guidance + E2E verification
`runtime_constitution.md` addition for Group A's "not found → ask → add_client → retry" flow; new
`@pytest.mark.expensive` E2E scenarios for US1-US6 through the real webhook router. Covers US5
(RBAC, likely already passing unchanged — verify, don't assume).

### Phase 4 — Cross-cutting verification
Full spec-to-test traceability pass (every REQ-INV-* and every SC-* has at least one asserting
test) before `/speckit.analyze`.

## Complexity Tracking

No Constitution Check violations requiring justification. Group B's fix is strictly simpler than
originally scoped (no resolution logic needed, just stop discarding a value already in hand); the
scope grew from 5 to 6 tools (adding `close_transaction_account`) for consistency, not complexity.
