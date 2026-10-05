# Implementation Plan: Feature 098 - Mandatory Client ID Above the Allocation Threshold

**Branch**: `feature/098-mandatory-id-above-5000-nis` | **Date**: 2026-10-05 |
**Spec**: [spec.md](spec.md) | **User stories / approved UATs**: [user-stories.md](user-stories.md)

Gate check: acceptance scenarios UAT 1.1-4.2 approved by PM 2026-10-05 ✅

## Summary

Morning-MCP gets a hard, config-driven refusal: a 305/320 whose pre-VAT amount exceeds
`allocation_threshold_nis` (5,000) is never sent to Morning for a client without a
9-digit ID. It also exposes the threshold through a new read-only MCP tool. DeniDin
fetches that value at startup (bounded retry, then background retry), injects it into
its prompt, and a new constitution rule makes the model check the client's ID before
proposing such a document, ask for it if missing, save it via `update_client` (its own
approval), then propose the document (second approval).

## Technical Context

- **Language**: Python 3 (both apps).
- **Dependencies**: existing; **new** `mcp>=1.0.0,<2.0.0` in denidin-app (research R5).
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
| No env vars - all config via config files | ✅ threshold + VAT rate in morning config; DeniDin gets them over MCP |
| No cross-app imports | ✅ DeniDin talks to Morning-MCP only over MCP/HTTP |
| No unverified third-party assumptions | ⚠️ R1 (`GET /clients/{id}`, `taxId` freshness) must be live-verified first - Phase 0 task |
| §XVIII startup handshakes retry | ✅ 2s × 60s, then every 5 min until success (C4) |
| Succeed-or-raise tool contract | ✅ `ClientTaxIdRequiredError` → `isError=True` (R4) |
| Tool boundaries in runtime constitution, both directions | ✅ Phase 3 |
| Feature flags (§VI) | ⚠️ **D-1, pending PM** |
| "Config is code" - config edits need approval | ⚠️ **D-2, pending PM** (VAT 0.17 → 0.18, new threshold field) |
| No bare pytest | ✅ wrappers only |

## Decisions Needed From PM Before Tasks

- **D-1 Feature flag.** Recommend **no flag** (as Feature 092): this is a regulatory
  requirement, a default-off flag would leave the integration tests unable to exercise the
  backstop, and rollback is the previous release.
- **D-2 Config edits.** Approve editing `apps/morning-mcp-app/config/config.{example,dev,prod,test}.json`:
  add `"allocation_threshold_nis": 5000`, change `"default_vat_rate"` 0.17 → 0.18.
- **D-3 Feature 063 order.** Which lands first? (see below)
- **D-4 `mcp` client in denidin-app** (R5) vs. a plain authenticated HTTP route. Recommend
  the MCP tool + client, per your Q3 answer and UAT 4.2.

## Feature 063 Dependency

063 (`origin/feature/063-refactor-oversized-handlers`, 61 commits ahead of master) replaces
`runtime_constitution.md` with `config/prompts/` (backbone + flows + capabilities).
- **098 merges first**: 098 ships the rule in `runtime_constitution.md`; 063 must port it
  into `cap_invoicing_write.md`, `cap_client_write.md` and the flows that issue 305/320
  (`flow_issue_invoice_for_payment_due`, `flow_issue_invoice_receipt_combo`,
  `flow_issue_payment_received_with_reference_doc`, `flow_morning_document_write`) and wire
  the same placeholder substitution into its prompt loader.
- **063 merges first**: 098 rebases and puts the rule straight into those files.
- Either way: the Morning-MCP side (Phases 1-2) is untouched by 063.

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
- New MCP tool (contract C1). Integration test through a real local MCP client.

### Phase 3 - DeniDin (US1-3, REQ-098-03/04/05/06/09/10)
- `requirements.txt`: `mcp` client.
- New `InvoicingRules` holder + startup fetcher service (C4), started from
  `initialize_app`, stopped on shutdown.
- `AIHandler._load_constitution`: placeholder substitution (C5).
- `runtime_constitution.md`: new "Allocation Number (מספר הקצאה)" section - when it
  applies (305/320, pre-VAT > threshold), when it doesn't (300/400/330, at/below
  threshold, client already has a 9-digit ID), the ask → `update_client` approval →
  document approval sequence, 9-digit check, decline handling; cross-references added to
  the Invoice Management, Client Management, Reminder and Ledger sections (METHODOLOGY
  §XXI).
- Tests: unit (substitution, holder, fetcher retry schedule with an injected clock),
  integration (fetcher against a real local FastMCP fixture server - no import of
  morning-mcp-app code).

### Phase 4 - Acceptance (billed, run together once, after everything is GREEN)
- Rebuild/restart dev Morning-MCP with the new image (needs approval).
- morning-mcp-app: UAT 4.1, 4.2.
- denidin-app: UAT 1.1-1.3, 2.1-2.3, 3.1-3.5.

### Phase 5 - 063 port (only if 063 merged first, or as a hand-off note to 063)

## Project Structure

```text
apps/morning-mcp-app/
├── config/config.schema.json, config.{example,dev,prod,test}.json   # D-2
├── src/denidin_mcp_morning/{config,tools,errors,server,morning_client}.py
└── tests/{unit,integration,billed}/test_*allocation*.py

apps/denidin-app/
├── requirements.txt                                   # + mcp
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
| `mcp` client dependency in denidin-app | PM: threshold comes from Morning over MCP (Q3) | HTTP route = second contract for the same value (D-4) |
| Background retry after the 60s poll | §XVIII: never leave a false "unavailable" | One-shot fetch is exactly the 2026-08-25 incident shape |
