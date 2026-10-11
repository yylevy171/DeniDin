# Implementation Plan: Feature 098 - Mandatory Client ID Above the Allocation Threshold

**Branch**: `feature/098-mandatory-id-above-5000-nis` | **Date**: 2026-10-05 |
**Spec**: [spec.md](spec.md) | **User stories / approved UATs**: [user-stories.md](user-stories.md)

Gate check: acceptance scenarios UAT 1.1-4.1 approved by PM 2026-10-05 ✅ (4.2 dropped with D-4)

## Summary

Morning-MCP gets a hard, config-driven refusal: a 305/320 whose pre-VAT amount exceeds
`allocation_threshold_nis` (5,000) is never sent to Morning for a client without a
9-digit ID. DeniDin keeps its own copy of the threshold in its config (PM decision -
speed over a single source of truth), fills it into its prompt, and a new constitution rule makes the model check the client's ID before
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
| No env vars - all config via config files | ✅ threshold + VAT rate in morning config; threshold copy in DeniDin config |
| No cross-app imports / no direct calls | ✅ DeniDin never reads morning's config or calls it (PM, D-4) |
| No unverified third-party assumptions | ⚠️ R1 (`GET /clients/{id}`, `taxId` freshness) must be live-verified first - Phase 0 task |
| §XVIII startup handshakes retry | ✅ n/a - no startup handshake added |
| Succeed-or-raise tool contract | ✅ `ClientTaxIdRequiredError` → `isError=True` (R4) |
| Tool boundaries in runtime constitution, both directions | ✅ Phase 2 |
| Feature flags (§VI) | ✅ documented exception - **no flag** (PM D-1: mandatory, no going back) |
| "Config is code" - config edits need approval | ✅ approved (PM D-2, D-4): morning VAT 0.17 → 0.18 + threshold field; DeniDin threshold field |
| No bare pytest | ✅ wrappers only |

## PM Decisions (2026-10-05)

- **D-1 Feature flag**: none. The feature is mandatory; there is no going back.
- **D-2 Config edits**: approved - `apps/morning-mcp-app/config/config.{example,dev,prod,test}.json`
  get `"allocation_threshold_nis": 5000` and `"default_vat_rate": 0.18` (was 0.17).
- **D-3 Feature 063 order**: 098 goes first; 063 adopts it. See below.
- **D-4 Threshold to DeniDin**: DeniDin never calls morning-mcp-app directly, let alone
  imports it. **It keeps its own copy** in `apps/denidin-app/config/config.{example,dev,prod,test}.json`
  (`allocation_threshold_nis: 5000`) - easy to implement, speed is of the essence. The two
  copies must be changed together; nothing detects drift (research R5).

## Feature 063 Dependency (D-3)

063 (`origin/feature/063-refactor-oversized-handlers`, not merged) replaces
`runtime_constitution.md` with `config/prompts/` (backbone + flows + capabilities).

- **098 merges first and is complete on its own**: Morning-MCP backstop, DeniDin config
  copy, placeholder substitution, the `runtime_constitution.md` section,
  and every unit / integration / billed test written.
- **Test running is split**:
  - **Run now**: all unit and integration tests (both apps); Morning-MCP billed UAT 4.1
    (no DeniDin prompts involved).
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
  4. `denidin.py`'s `__main__` `config_dict` must keep its `allocation_threshold_nis` entry
     (added by 098), or the configured value is silently ignored.
  5. Cross-references: every other tool-bearing prompt file in the backbone keeps a 9-digit
     reply to the pending ID question out of its scope (098 added these to the Reminder,
     Ledger Event Recognition, Ledger Event Querying and Fee Agreement sections).
- Morning-MCP (Phase 1) is untouched by 063.

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

### Phase 2 - DeniDin (US1-3, REQ-098-03/04/05/06/09/10)
- Config: `allocation_threshold_nis` in `AppConfiguration` (+ defaults, validation:
  number > 0) and in `config.{example,dev,prod,test}.json` (D-4).
- `AIHandler._load_constitution`: placeholder substitution from config (C5).
- `runtime_constitution.md`: new "Allocation Number (מספר הקצאה)" section - when it
  applies (305/320, pre-VAT > threshold), when it doesn't (300/400/330, at/below
  threshold, client already has a 9-digit ID), the ask → `update_client` approval →
  document approval sequence, 9-digit check, decline handling; cross-references added to
  the Invoice Management, Client Management, Reminder and Ledger sections (METHODOLOGY
  §XXI).
- Tests: unit (config field + validation, substitution, no placeholder left in any final
  `instructions`). No integration/billed test for the config copy itself.

### Phase 3 - Acceptance (billed)
- **4a, now**: rebuild/restart dev Morning-MCP with the new image (needs approval), then
  morning-mcp-app UAT 4.1.
- **4b, written now, run after 063 merges**: DeniDin UAT 1.1-1.3, 2.1-2.3, 3.1-3.5, run on
  the backbone.

### Phase 4 - 063 hand-off
- Add the adoption checklist (above) to 063's spec on its branch, or hand it to whoever
  owns 063.
- **Status (2026-10-05)**: checklist above is final. Reported to PM; 063's branch was not
  edited from this clone.

### Phase 5 - adopt the backbone (063 merged to master first, 2026-10-06)

D-3 assumed 098 would merge first and 063 would adopt it. 063 merged first instead
(PR #699), and the backbone flag (`enable_capability_backbone`) is ON from now on, so 098
adopts the backbone itself. Master was merged into this branch (504c3a5).

**Impact assessment**

| Area | Impact |
|---|---|
| morning-mcp-app (Phase 1) | None. 063 changed only `create_receipt` (payment method / bank details); 098's three tools, `get_client`, config and refusal are intact. Unit: 422 pass. |
| DeniDin prompt rule | **Not in effect.** The backbone builds its prompt from `config/prompts/` (backbone + capabilities + flows) and never reads `runtime_constitution.md`, so 098's "Allocation Number" section and its `{{ALLOCATION_THRESHOLD_NIS}}` fill reach only the legacy (flag-off) path. |
| Approvals | The backbone has no pending-approval state: `approval_with_yes_no_buttons` ends the turn with buttons, the model reads the next turn's yes/no, and runs the write itself (`require_approval: never`). The two-approval chain becomes: yes-turn runs `update_client`, then the same turn raises the document's approval. `_apply_write_guards` counts the `update_client` run, so no "not performed" note. |
| DeniDin config | Unaffected. `allocation_threshold_nis` kept in `AppConfiguration` and in `startup_config`'s `config_dict` (conflict resolved). |
| 098 unit tests | `test_constitution_allocation_threshold.py` (5): fail - `AIHandler` is now built from the `DeniDin` instance. `test_config_allocation_threshold.py`: pass. |
| 098 integration test | `test_allocation_tax_id_approval_routing.py` (3): error - `DeniDin` has no `ai_handler`, and it tests the legacy pending-approval chain the backbone doesn't use. |
| 098 billed tests | Use `ai_handler.pending_approval_manager` and `ai_handler.last_response`; 063's helpers moved to `approval_buttons_on_screen(chat)` and `denidin_app.last_response`, and added `assert_no_errors_sent_to_user`. |
| Rest of DeniDin suite | 1922 run: only 098's 8 above, plus `test_player_replay_offline.py::test_player_replays_through_the_real_pipeline`, which also fails on master's own code (`_finalize_response`: `response.usage` is None). |
| morning-mcp-app suite | `test_logger_retention.py::test_concurrent_emit_across_rotations_loses_nothing` fails about 1 run in 3 (also before the merge). |

**Plan**

1. Prompts (`config/prompts/`):
   - `cap_invoicing_write.md`: a new "Allocation number" section - the rule (305/320,
     pre-VAT above `{{ALLOCATION_THRESHOLD_NIS}}` ₪, divide by 1.18; a 300 is closed for its
     total including VAT), check the ID with `get_client_details`, never issue without it,
     what to do if Morning still refuses.
   - The three issuing flows (`flow_issue_invoice_for_payment_due`,
     `flow_issue_invoice_receipt_combo`, `flow_issue_payment_received_with_reference_doc`):
     a step after the client is resolved and the amount known - no 9-digit ID: ask in plain
     text (`cap_send_to_user`); a valid reply: save it with its own approval, then go straight
     on to the document's approval; wrong format: ask again; a decline: confirm nothing was
     issued. An ID given in the request goes straight to the save approval. (Mechanism: see
     question 1.)
   - `cap_client_write.md`: the `tax_id` field (9 digits) and that saving it is its own
     approval.
2. Placeholder fill in the backbone: substitute `{{ALLOCATION_THRESHOLD_NIS}}` once, on the
   assembled `build_instructions` output, so every capability/flow file is covered. The
   value is constant, so the cached prefix is unchanged. Legacy `_load_constitution` keeps
   its own fill.
3. Tests (unit/integration, free to change):
   - `test_constitution_allocation_threshold.py`: adapt to the new `AIHandler` construction
     (legacy) and add backbone cases (placeholder filled in `build_instructions`; no
     placeholder left in any `config/prompts/` file after assembly).
   - Replace `test_allocation_tax_id_approval_routing.py` with a backbone integration test,
     in the style of `test_backbone_capability_resolution.py`: the yes-turn that runs
     `update_client` and raises the document approval is sent with buttons and gets no
     write-guard note; a typed yes and a tap both work; declining the document creates
     nothing.
4. Billed tests: adapt the 13 DeniDin tests to 063's helpers (`approval_buttons_on_screen`,
   `denidin_app.last_response`, `assert_no_errors_sent_to_user`, the backbone chat cleanup).
   Assertions unchanged. Run T1, then T3, with the backbone on (question 3).
5. Docs: CLAUDE.md's Feature 098 paragraph names the backbone prompt files; acceptance-tests.md
   records the backbone as the target.

**PM decisions (2026-10-06)**: Q1 (a) reuse `flow_modify_client`; Q2 keep the legacy
section and its existing tests (not newly tested); Q3 flag on in
`config.example.json` and the local `config.test.json` (copied from teammate1); dev/prod set
by hand.

**Open questions (PM, as asked)**

1. ID-save mechanism on the backbone: (a) the issuing flow loads `flow_modify_client` for the
   save, then continues - reuses the existing flow and approval wording; or (b) a new small
   `flow_save_client_tax_id` used by the three issuing flows - narrower, but a new flow
   tag. Recommendation: (a).
2. Legacy path: keep 098's `runtime_constitution.md` section, its fill, and legacy test
   coverage (as a fallback if the flag is ever turned off), or remove them?
   Recommendation: keep; adapt the unit tests; drop the legacy integration test.
3. "Flag ON from now on": flip `feature_flags.enable_capability_backbone` to `true` in
   `config.example.json` and the local dev/prod/test configs (config is code - needs
   approval), or only run tests with `--enable_capability_backbone=true`?
4. The two failures 098 didn't cause (`test_player_replay_offline`, the flaky logger
   rotation test): fix on this branch, or as a separate bugfix?

## Project Structure

```text
apps/morning-mcp-app/
├── config/config.schema.json, config.{example,dev,prod,test}.json   # D-2
├── src/denidin_mcp_morning/{config,tools,errors,server,morning_client}.py
└── tests/{unit,integration,billed}/test_*allocation*.py

apps/denidin-app/
├── config/runtime_constitution.md                     # new section + placeholder
├── config/config.{example,dev,prod,test}.json         # + allocation_threshold_nis
├── src/models/config.py                               # + allocation_threshold_nis
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
| Threshold duplicated in two configs | PM D-4: speed; DeniDin never calls morning-mcp-app | Startup fetch via OpenAI: billed call per start + retry machinery |
