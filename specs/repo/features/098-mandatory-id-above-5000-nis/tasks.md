# Tasks: Feature 098 - Mandatory Client ID Above the Allocation Threshold

**Input**: `plan.md`, `spec.md`, `user-stories.md`, `research.md`, `data-model.md`,
`contracts/morning-mcp.md`, `quickstart.md`
**Branch**: `feature/098-mandatory-id-above-5000-nis`

## Ground rules (apply to every task)

- **Task A / Task B gates (METHODOLOGY §VI.b).** A = tests (RED), B = implementation
  (GREEN). **PM instruction 2026-10-05**: implement straight through, including unit and
  integration tests, and report back only on design questions. The A→B human-approval
  pause is therefore not taken during this run; all new tests are delivered for PM review
  with the implementation, and become immutable once approved.
- **Running tests**: only via `scripts/run_unit_integration_tests.sh` (each app). Never a
  bare `pytest`. Relay each `>>> TEST [k/N]` line live.
- **Billed / expensive**: written now, **not run** in this pass. Morning-MCP UAT 4.1 can
  run after dev Morning-MCP is rebuilt (needs approval). DeniDin UATs 1.1-3.5 are deferred
  until Feature 063 merges, then run on the backbone (plan.md D-3).
- **No mocks of internal components.** Unit tests may use the existing fake `MorningClient`
  (third-party boundary, as `tests/unit/test_tools_document_creation.py` does).
  Integration tests hit the real Morning sandbox.
- **No feature flag** (PM D-1). Path prefixes: `M` = `apps/morning-mcp-app`,
  `D` = `apps/denidin-app`, `S` = `specs/repo/features/098-mandatory-id-above-5000-nis`.

---

## Phase 1: Setup

- [ ] T001 Green baseline: run `M/scripts/run_unit_integration_tests.sh tests/unit/` and `D/scripts/run_unit_integration_tests.sh tests/unit/` on the untouched branch; record pass counts here.

## Phase 2: Foundational - live verification (research R1)

- [ ] T002 Add `MorningClient.get_client(client_id)` (`GET /clients/{id}`) in `M/src/denidin_mcp_morning/morning_client.py`, same `_request`/`raise_for_status` shape as `get_invoice`.
- [ ] T003 `M/tests/integration/test_morning_sandbox_allocation_tax_id.py::test_get_client_by_id_returns_tax_id` - seed a client with ID 308253681 via `add_client`, `get_client(id)` returns `taxId == "308253681"`; then `update_client` a second seeded (ID-less) client with an ID and confirm both `get_client` and `search_clients` show it (polling, as the existing update-client tests do). Record the result in `S/research.md` R1. **If it fails → stop and report (design question).**

---

## Phase 3: US4 - Morning-MCP hard backstop (P1)

**Independent test:** calling the 305/320 creation tools directly for an ID-less client
above the threshold refuses and creates nothing; everything else is unchanged.

### Task A - tests

- [ ] T004 [P] [US4] `M/tests/unit/test_config.py` (append): `allocation_threshold_nis` loads from config, defaults to 5000; `default_vat_rate` defaults to 0.18; schema rejects a non-positive threshold.
- [ ] T005 [P] [US4] `M/tests/unit/test_tools_allocation_tax_id.py` - pure helpers:
  - `_has_valid_tax_id`: `"308253681"` ✓, `" 308253681 "` ✓, `None`/`""`/`"12345678"`/`"30825368a"`/`"308-253-681"` ✗;
  - `_pre_vat_amount`: VAT-inclusive payload 5,900 → 5000.00; VAT-exclusive 5,001 → 5001.00; multi-line income sums `price × quantity`;
  - `_enforce_allocation_tax_id`: refuses only for type 305/320 with pre-VAT **>** threshold and no valid ID; never for 300/330/400; not at exactly the threshold.
- [ ] T006 [P] [US4] Same file - tools with the fake client:
  - `create_invoice` 8,000 excl. VAT, ID-less client → `ClientTaxIdRequiredError`, zero `create_invoice` calls on the fake;
  - `create_combo_document` 12,000 incl. VAT, ID-less → refused, nothing sent;
  - `create_combo_document_as_reference` on a 10,000 type-300 original whose current client (via `get_client`) has no ID → refused, nothing sent; with an ID → created;
  - same tools with a client that has `taxId: "308253681"` → created as today;
  - 4,500 incl. VAT, ID-less → created; custom `InvoicingRules(threshold=10000)` + 7,000 → created.
- [ ] T007 [P] [US4] `M/tests/unit/test_errors.py` (append): `friendly_error_message(ClientTaxIdRequiredError(msg))` returns `msg` verbatim (not the generic `_INVALID_REQUEST`).
- [ ] T008 [US4] `M/tests/integration/test_morning_sandbox_allocation_tax_id.py` - real sandbox matrix:
  - 305 (`create_invoice`), 320 (`create_combo_document`), 320 closing a 300 (`create_combo_document_as_reference`): ID-less client above threshold → refused, no new document for the client, the 300 still open;
  - the same three with an ID on the client → created;
  - below threshold, ID-less → created;
  - 300 (`create_transaction_account`) 12,000, ID-less → created (out of scope).
- [ ] T009 [US4] `M/tests/integration/test_mcp_server_e2e.py`-style check through the real MCP server: the refusal arrives as `isError=True` with the Hebrew message (contract C2). New test in `M/tests/integration/test_morning_sandbox_allocation_tax_id.py` reusing the in-process server pattern from `test_mcp_server_e2e.py`.

### Task B - implementation

- [ ] T010 [US4] Config: `allocation_threshold_nis` in `M/config/config.schema.json`, `MorningMCPConfig`, `load_config` (default 5000); `default_vat_rate` default 0.17 → 0.18 in code and schema.
- [ ] T011 [US4] Config files (PM D-2): `M/config/config.example.json` (tracked) and this clone's gitignored `config.dev.json`, `config.prod.json`, `config.test.json` - add `"allocation_threshold_nis": 5000`, set `"default_vat_rate": 0.18`.
- [ ] T012 [US4] `M/src/denidin_mcp_morning/tools.py`: `InvoicingRules` dataclass + module default (same precedent as `_LIST_INVOICES_TOKEN_BUDGET`), `_has_valid_tax_id`, `_pre_vat_amount`, `ClientTaxIdRequiredError`, `_enforce_allocation_tax_id` (with `log_refusal`).
- [ ] T013 [US4] Wire the check into `create_invoice`, `create_combo_document` (client from `_require_resolved_client`) and `create_combo_document_as_reference` (client via `get_client`, after the idempotent no-op and not-linked checks), right before `client.create_invoice(payload)`. New keyword-only `rules: InvoicingRules = DEFAULT_INVOICING_RULES` parameter.
- [ ] T014 [US4] `M/src/denidin_mcp_morning/server.py`: build `InvoicingRules` from config in `create_server`, pass it to the three tools.
- [ ] T015 [US4] `M/src/denidin_mcp_morning/errors.py`: verbatim branch for `ClientTaxIdRequiredError`.
- [ ] T016 [US4] Run `M` unit + integration suites → GREEN (new and existing).

---

## Phase 4: US1-US3 - DeniDin asks first (P1)

**Independent test:** DeniDin's prompt contains the rule with the configured number and no
leftover placeholder; acceptance tests are the billed UATs (deferred).

### Task A - tests

- [ ] T017 [P] [US1] `D/tests/unit/test_config_allocation_threshold.py`: `AppConfiguration` loads `allocation_threshold_nis`, defaults to 5000, `validate()` rejects ≤ 0.
- [ ] T018 [P] [US1] `D/tests/unit/test_constitution_allocation_threshold.py`: with a tmp constitution containing `{{ALLOCATION_THRESHOLD_NIS}}`, `AIHandler._load_constitution` returns it with `5,000` (and `12,500` for 12500, `5,000.5` for 5000.5); with the real `config/runtime_constitution.md`, the loaded text contains no `{{ALLOCATION_THRESHOLD_NIS}}` and contains the allocation section.

### Task B - implementation

- [ ] T019 [US1] `D/src/models/config.py`: `allocation_threshold_nis` field, default, `from_dict`, `validate`.
- [ ] T020 [US1] `D/config/config.example.json` (tracked) and this clone's gitignored `config.dev.json`, `config.prod.json`, `config.test.json`: add `"allocation_threshold_nis": 5000` (PM D-4).
- [ ] T021 [US1] `D/src/handlers/ai_handler.py` `_load_constitution`: substitute `{{ALLOCATION_THRESHOLD_NIS}}` after the Feature 080 gate, every call (not into the mtime cache).
- [ ] T022 [US1] [US2] [US3] `D/config/runtime_constitution.md`: new "Allocation Number (מספר הקצאה)" section - applies to 305/320 with pre-VAT > `{{ALLOCATION_THRESHOLD_NIS}}` ₪; check `get_client_details` first; if no 9-digit ID ask (plain text, no document proposal); on a 9-digit reply propose `update_client` (approval), then the original document (approval) without the user restating it; not 9 digits → say so, ask again; decline → nothing issued; never 300/330/400; at/below threshold or client already has a 9-digit ID → no question; if Morning still refuses, ask for the ID. Cross-references in the existing invoice, client-management, reminder and ledger sections (METHODOLOGY §XXI).
- [ ] T023 Run `D` unit + integration suites → GREEN.

---

## Phase 5: Acceptance tests - written, not run

- [ ] T024 [P] [US4] `M/tests/billed/test_allocation_tax_id_billed.py::test_openai_create_combo_refused_without_client_id` (UAT 4.1), modeled on `test_openai_invokes_mcp_e2e.py`.
- [ ] T025 [P] [US1] `D/tests/billed/test_allocation_tax_id_billed.py` - UAT 1.1, 1.2, 1.3.
- [ ] T026 [P] [US2] Same file - UAT 2.1, 2.2, 2.3.
- [ ] T027 [P] [US3] Same file - UAT 3.1-3.5.
- [ ] T028 `S/acceptance-tests.md`: list every new billed/expensive test (node id, UAT, tier, run status: deferred / runnable).
- [ ] T029 Collect-only check (`--collect-only` through the wrapper) that the new billed files import and are marked `billed`.

## Phase 6: Polish

- [ ] T030 Docs: CLAUDE.md (morning-mcp-app section: the allocation check; config notes: the threshold lives in both apps' configs, change together), `S/quickstart.md` check.
- [ ] T031 Hand-off note for Feature 063: append the adoption checklist (plan.md "Feature 063 dependency") to `S/plan.md` status and report it to PM - do **not** edit 063's branch.
- [ ] T032 Lint/type-check touched files in both apps (pylint/mypy via each app's config).

## Dependencies

T001 → T002 → T003 (gate) → Phase 3 → Phase 4 → Phase 5 → Phase 6. Phase 4 Task A/B
can start in parallel with Phase 3 once T003 passes (different app).

---

## speckit.analyze findings (2026-10-05) and fixes

| # | Finding | Severity | Fix |
|---|---------|----------|-----|
| A1 | Prod runs on the Windows box with **its own** `config.prod.json` files, not this clone's. Editing this clone's gitignored prod configs (T011/T020) does not reach prod. | Medium | Both loaders default the threshold to 5000 and the VAT rate to 0.18, so prod works with no edit. quickstart.md now says an explicit value on the box is a manual step at deploy time. |
| A2 | Existing billed/expensive tests that issue a 305/320 above 5,000 for an ID-less client would now fail. A text search found none (the 40,000 test is a 300). Image-driven expensive tests can't be fully checked by text search. | Low | Recorded as a residual risk in `acceptance-tests.md`; confirmed only when those tiers next run. |
| A3 | UAT 1.3 / the as-reference path depends on `GET /clients/{id}` (unverified third-party behavior). | Medium | T003 is a hard gate before Phase 3. |
| A4 | `default_vat_rate`'s schema `default` (0.17) is documentation only, but would contradict the code default. | Low | T010 updates both. |
| A5 | `denidin-app/config/config.json` and `config.player_prod.json` (gitignored, not in the D-4 list) won't get the field. | Low | Covered by the 5000 default; not edited (not approved). |
| A6 | spec, user-stories, plan, contracts, data-model agree on: scope 305/320, strictly-greater, pre-VAT, 9 digits, two approvals, no flag, threshold in both configs, no direct DeniDin→Morning call. | - | No change. |
