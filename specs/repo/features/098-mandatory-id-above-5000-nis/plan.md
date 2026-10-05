# Implementation Plan: Feature 098 - Mandatory Client ID Above the Allocation Threshold

**Branch**: `feature/098-mandatory-id-above-5000-nis` | **Date**: 2026-10-05 |
**Spec**: [spec.md](spec.md) | **User stories / approved UATs**: [user-stories.md](user-stories.md)

Gate check: acceptance scenarios UAT 1.1-4.2 approved by PM 2026-10-05 ✅

## Summary

Morning-MCP gets a hard, config-driven refusal: a 305/320 whose pre-VAT amount exceeds
`allocation_threshold_nis` (5,000) is never sent to Morning for a client without a
9-digit ID. It also exposes the threshold through a new read-only MCP tool. DeniDin
obtains that value at startup **through OpenAI** (a standalone Responses call with the
Morning MCP tool attached - never a direct call to morning-mcp-app), with bounded retry
then background retry, injects it into its prompt, and a new constitution rule makes the model check the client's ID before
proposing such a document, ask for it if missing, save it via `update_client` (its own
approval), then propose the document (second approval).

## Technical Context

- **Language**: Python 3 (both apps).
- **Dependencies**: existing only. No new packages.
- **Storage**: none new.
- **Testing**: pytest via `scripts/run_unit_integration_tests.sh` /
  `run_single_test.sh` / `run_multiple_billed_tests.sh`; real Morning sandbox; no mocks of
  internal components.
- **Platform**: Docker containers, dev and prod (Windows box).
- **Constraints**: no env vars, Israel-local time, no monkey-patching, `pathlib`, prompt
  caching preserved (constitution stays a stable prefix).

## Constitution Check (pre- and post-design)

| Rule | Status |
|------|--------|
| No env vars - all config via config files | ✅ threshold + VAT rate in morning config; DeniDin gets the threshold via OpenAI → MCP |
| No cross-app imports / no direct calls | ✅ DeniDin reaches Morning-MCP only through OpenAI's remote-MCP tool (PM, D-4) |
| No unverified third-party assumptions | ⚠️ R1 (`GET /clients/{id}`, `taxId` freshness) must be live-verified first - Phase 0 task |
| §XVIII startup handshakes retry | ✅ every 10s for 2 min, then every 10 min until success (C4) |
| Succeed-or-raise tool contract | ✅ `ClientTaxIdRequiredError` → `isError=True` (R4) |
| Tool boundaries in runtime constitution, both directions | ✅ Phase 3 |
| Feature flags (§VI) | ✅ documented exception - **no flag** (PM D-1: mandatory, no going back) |
| "Config is code" - config edits need approval | ✅ approved (PM D-2): VAT 0.17 → 0.18, new threshold field |
| No bare pytest | ✅ wrappers only |

## PM Decisions (2026-10-05)

- **D-1 Feature flag**: none. The feature is mandatory; there is no going back.
- **D-2 Config edits**: approved - `apps/morning-mcp-app/config/config.{example,dev,prod,test}.json`
  get `"allocation_threshold_nis": 5000` and `"default_vat_rate": 0.18` (was 0.17).
- **D-3 Feature 063 order**: 098 goes first; 063 adopts it. See below.
- **D-4 Threshold to DeniDin**: DeniDin never calls morning-mcp-app directly, let alone
  imports it. It gets the value through OpenAI (research R5); the fallback, if that proves
  unreliable, is DeniDin's own config copy.

## Feature 063 Dependency (D-3)

063 (`origin/feature/063-refactor-oversized-handlers`, not merged) replaces
`runtime_constitution.md` with `config/prompts/` (backbone + flows + capabilities).

- **098 merges first and is complete on its own**: Morning-MCP backstop, threshold tool,
  DeniDin startup fetch, placeholder substitution, the `runtime_constitution.md` section,
  and every unit / integration / billed test written.
- **Test running is split**:
  - **Run now**: all unit and integration tests (both apps); Morning-MCP billed UAT 4.1 /
    4.2 (no DeniDin prompts involved); DeniDin's startup-fetch billed test (no prompt
    content involved).
  - **Deferred until 063 merges**: DeniDin billed UATs 1.1-3.5. They test prompt behavior,
    and running them against `runtime_constitution.md` would be thrown away once the
    backbone replaces it. They are run once, on the backbone, after the port.
- **063 adopts** (hand-off checklist, recorded in 063's spec):
  1. Port the "Allocation Number" rule into `cap_invoicing_write.md`, `cap_client_write.md`
     and the flows that issue 305/320 (`flow_issue_invoice_for_payment_due`,
     `flow_issue_invoice_receipt_combo`, `flow_issue_payment_received_with_reference_doc`,
     `flow_morning_document_write`), with the `{{ALLOCATION_THRESHOLD_NIS}}` placeholder.
  2. Move the placeholder substitution to 063's single prompt-assembly point, so it covers
     every dynamically loaded flow/capability file (research R6).
  3. Run DeniDin billed UATs 1.1-3.5 on the backbone.
- Morning-MCP (Phases 1-2) is untouched by 063.

## Phases

### Phase 0 - Live verification (no product code)
- Sandbox: `GET /clients/{id}` returns `taxId`; a just-updated `taxId` is visible on the
  next search/get (R1). Record results in research.md.

### Phase 1 - Morning-MCP hard backstop (US4, REQ-098-01/02/07/08)
- Config: `allocation_threshold_nis` (schema + `MorningMCPConfig` + loader); VAT default 0.18.
- `tools.py`: `InvoicingRules`, `_has_valid_tax_id`, `_pre_vat_amount(payload, vat_rate)`,
  `_enforce_allocation_tax_id(...)`, `ClientTaxIdRequiredError`; call it in the 3 tools
  right before `client.create_invoice`.
- `morning_client.py`: `get_client(client_id)` (as-reference path).
- `errors.py`: verbatim branch for `ClientTaxIdRequiredError`.
- `server.py`: build `InvoicingRules` in `create_server`, inject into the 3 tools.
- Tests: unit (pure helpers, boundary 5,000.00 vs 5,001), integration on the real sandbox
  (the full matrix in user-stories.md "Below the acceptance tier").

### Phase 2 - Morning-MCP `get_invoicing_rules` (REQ-098-03, UAT 4.2)
- New MCP tool (contract C1). Integration test through a real local MCP client (inside
  morning-mcp-app's own tests - this is Morning-MCP testing itself, not DeniDin calling it).

### Phase 3 - DeniDin (US1-3, REQ-098-03/04/05/06/09/10)
- New `InvoicingRules` holder + startup fetcher service (C4): a standalone OpenAI
  Responses call with the Morning MCP tool restricted to `get_invoicing_rules`, value read
  from the `mcp_call` output. Started from `initialize_app`, stopped on shutdown. Same shape
  as `accounting_reconciliation_service.py`.
- `AIHandler._load_constitution`: placeholder substitution (C5).
- `runtime_constitution.md`: new "Allocation Number (מספר הקצאה)" section - when it
  applies (305/320, pre-VAT > threshold), when it doesn't (300/400/330, at/below
  threshold, client already has a 9-digit ID), the ask → `update_client` approval →
  document approval sequence, 9-digit check, decline handling; cross-references added to
  the Invoice Management, Client Management, Reminder and Ledger sections (METHODOLOGY
  §XXI).
- Tests: unit (substitution incl. "unknown" wording, holder, retry schedule with an
  injected clock, parsing an `mcp_call` output item, rejecting a missing/bad value);
  billed (the real startup fetch: real OpenAI → real dev Morning-MCP tunnel → value set).

### Phase 4 - Acceptance (billed)
- **4a, now**: rebuild/restart dev Morning-MCP with the new image (needs approval), then
  morning-mcp-app UAT 4.1 and 4.2, and DeniDin's startup-fetch billed test.
- **4b, written now, run after 063 merges**: DeniDin UAT 1.1-1.3, 2.1-2.3, 3.1-3.5, run on
  the backbone.

### Phase 5 - 063 hand-off
- Add the adoption checklist (above) to 063's spec on its branch, or hand it to whoever
  owns 063.

## Project Structure

```text
apps/morning-mcp-app/
├── config/config.schema.json, config.{example,dev,prod,test}.json   # D-2
├── src/denidin_mcp_morning/{config,tools,errors,server,morning_client}.py
└── tests/{unit,integration,billed}/test_*allocation*.py

apps/denidin-app/
├── config/runtime_constitution.md                     # new section + placeholder
├── denidin.py                                         # start/stop fetcher
├── src/services/invoicing_rules_service.py            # new: holder + fetcher
├── src/handlers/ai_handler.py                         # placeholder substitution
└── tests/{unit,integration,billed}/test_*allocation*.py

specs/repo/features/098-mandatory-id-above-5000-nis/
├── spec.md, user-stories.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/morning-mcp.md
└── checklists/requirements.md
```

## Complexity Tracking

| Item | Why | Simpler alternative rejected because |
|------|-----|--------------------------------------|
| Startup OpenAI call just to read one number | PM: one source of truth, and DeniDin never calls morning-mcp-app directly (D-4) | DeniDin's own config copy = two places to change, silent drift; kept as fallback |
| Background retry after the 2-minute window | §XVIII: never leave a false "unavailable" | One-shot fetch is exactly the 2026-08-25 incident shape |
