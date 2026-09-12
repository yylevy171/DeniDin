# Tasks: Fee Agreement Document Generation

**Input**: `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
**Acceptance scenarios**: `user-stories.md`'s 4 UAT stages + Test 1.4 (multi-component) - already
drafted as concrete pytest code in `tests/billed/test_fee_agreement_generation_flow.py` (human
review pending per the 2026-09-12 process; alternative_tracks scenario coverage still to be added
to that file, see T014 below).

## Phase 0: Blocking research (resolved)
- [x] T001 Confirm `whatsapp-api-client-python`'s installed `sending` module exposes
  `sendFileByUpload(chatId, path, fileName=None, caption=None, ...)` — CONFIRMED 2026-09-12 by
  inspecting the installed package (`tools/sending.py:142`); signature matches research.md #1's
  assumption. No fallback needed.

## Phase 1: Foundation (models + config)
- [x] T002 `src/models/fee_agreement.py` — `FeeAgreementVariant`, `RepeatingGroup`,
  `GeneratedDocument` dataclasses.
- [x] T003 `src/models/config.py` — add `fee_agreements: Dict` field (templates_dir/tmp_dir),
  gated by `config.feature_flags['fee_agreement_docs']` (default `False`, no dataclass field
  needed — `feature_flags` is already a generic dict).
- [x] T004 Added `fee_agreements` block to `config/config.example.json`, `config/config.test.json`,
  `config/config.dev.json`, `config/config.prod.json`. `feature_flags.fee_agreement_docs` deliberately
  left UNSET (defaults `False` via `.get(..., False)`) everywhere, including `config.test.json` —
  per CLAUDE.md "config is code," flipping a flag is its own explicit human decision, not bundled
  into this task.

## Phase 2: DocTemplateEngine (Task A: tests, Task B: implementation)
- [x] T005 [Task A] `tests/unit/test_doc_template_engine.py` — real `python-docx` calls against
  the 5 real committed templates (no fixture/mock template — CONSTITUTION §I/§V: no mocking of
  internal code, and these templates ARE the production config). Covers: variant listing,
  single-fee generation + verify-clean, missing/extra/empty value rejection, unknown variant
  rejection, `components` supplied for a non-repeating variant rejection, `multi_component_agreement`
  arbitrary-N cloning + validation, `alternative_tracks` arbitrary-N cloning + validation.
- [x] T006 [Task B] `src/managers/doc_template_engine.py` — `DocTemplateEngine.list_variants()`,
  `.generate()`, `.verify()` per `contracts/doc-template-engine.md`. Table-row cloning
  (`multi_component_agreement`) and paragraph-block cloning (`alternative_tracks`) both
  implemented via a shared `_clone_repeating_group()` dispatcher.
- [x] T007 Ran T005 against T006 until green — 16/16 passing (also reconfirmed as part of the full
  1420-test unit suite after Phase 3/4 wiring, see below).

## Phase 3: AI tool wiring — IMPLEMENTED, in a NEW separate file (2026-09-12 user instruction:
  "consider creating a new py file for this... ai_handler.py should be refactored but not now")
- [x] T008-partial [Task A] No dedicated `test_ai_handler_fee_agreement_tools.py` unit test file
  was written this pass — deferred, tracked below as still-outstanding, NOT silently dropped. What
  IS verified so far: the full existing 1420-test unit suite (including
  `test_ai_handler_reminders.py`, `test_ai_handler_retry.py`, `test_ai_handler_zero_execution_detection.py`,
  `test_main_turn_tools.py`) still passes unchanged against the new wiring (no regression), and
  `DocTemplateEngine` itself (the logic `FeeAgreementToolHandler` delegates to) is fully covered by
  T005. `FeeAgreementToolHandler`'s own dispatch logic (proposal validation, approval-details text,
  verify/send bookkeeping) is NOT yet independently unit-tested — this is a real gap, not closed by
  the suite passing, since nothing in the existing suite exercises the new code paths at all yet.
- [x] T009 [Task B] Implemented, split as the user directed:
  - **New file `src/handlers/fee_agreement_tools.py`** (NOT inlined into `ai_handler.py`): tool
    schemas `GENERATE_FEE_AGREEMENT_TOOL`/`VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL`/
    `SEND_FEE_AGREEMENT_DOCUMENT_TOOL`, `FEE_AGREEMENT_AUTHORIZED_ROLES`, and the
    `FeeAgreementToolHandler` class owning ALL DocTemplateEngine-facing logic (proposal validation,
    human-facing approval-details text, turn-scoped `GeneratedDocument` bookkeeping/cleanup).
  - `ai_handler.py` itself only got small, additive hook calls (mirroring the existing
    `_build_reminder_tools`/`_handle_reminder_creation_proposal`/`_resolve_pending_local_tool_approval`
    shape, never duplicating it): `self.doc_template_engine`/`self.fee_agreement_tools` constructed
    in `__init__` (config-driven, DI); `_assemble_tools` appends
    `fee_agreement_tools.build_tools(...)`; a new `_handle_fee_agreement_generation_proposal` (mirrors
    `_handle_reminder_creation_proposal`) wired into `_finalize_response`; a `generate_fee_agreement`
    branch added to `_resolve_pending_local_tool_approval` (own `try/except ValueError`, kept separate
    from the reminder-specific except tuple to protect Feature 054's existing test coverage); and two
    new immediate-dispatch handlers (`_handle_verify_fee_agreement_document`,
    `_handle_send_fee_agreement_document`, mirroring `_handle_list_reminders`) wired into
    `_run_local_tool_dispatch_loop`.
  - Confirmed as originally planned: `generate_fee_agreement` is proposal-only
    (`PendingLocalToolApproval`, values-gated); `verify_fee_agreement_document` dispatches
    immediately, read-only, returns raw facts only — `verified=True` is set (defense-in-depth only,
    per data-model.md) inside `FeeAgreementToolHandler.handle_verify` iff `result["clean"]`;
    `send_fee_agreement_document` (the 3rd tool — see Analysis Findings #1) dispatches immediately,
    refuses as a tool-call-error dict (never a raised exception) unless already verified, calls
    `WhatsAppHandler.send_document_response()`, then deletes the temp file + in-memory entry via
    `FeeAgreementToolHandler._cleanup` regardless of outcome (SC-003).
  - `WhatsAppHandler` needed a new post-construction-injected `green_api_bot` attribute (same DI
    idiom as `denidin_app.green_api_bot`) since `send_document_response` needs the live bot's
    `.api.sending.sendFileByUpload`, unlike `send_response`'s `notification.answer(...)` — wired in
    `denidin.py`'s `__main__` (`ai_handler.whatsapp_handler = whatsapp_handler` too, for the same
    reason, since `AIHandler` didn't hold a `WhatsAppHandler` reference before this feature).

## Phase 4: WhatsApp delivery (`whatsapp_handler.py`) — IMPLEMENTED (Task B only so far)
- [ ] T010 [Task A] `tests/unit/test_whatsapp_handler_document_send.py` — NOT yet written (same
  status as T008-partial above: a real, tracked gap, not silently skipped).
- [x] T011 [Task B] `whatsapp_handler.py`: `send_document_response(generated: GeneratedDocument, chat_id: str, caption: str) -> bool`
  implemented per `contracts/whatsapp-file-delivery.md` — `_send_file_with_retry` (retry-once-on-5xx/
  timeout/connection-error, never-on-4xx, same tenacity pattern as `_send_with_retry`), refuses
  outright (returns `False`, no call attempted) if `generated.verified is not True`, never raises
  (all failure paths return `False`). Temp-file deletion is NOT this method's job — it's
  `FeeAgreementToolHandler._cleanup`'s, called by `ai_handler.py`'s send handler regardless of this
  method's return value (SC-003 still holds, just enforced one layer up).

**Honest status note (2026-09-12): Phase 3/4 code is written and wired end-to-end, and the full
pre-existing 1420-test unit suite passes against it with zero regressions - but T008/T010's OWN
new unit tests do not exist yet.** This is a real, acknowledged gap against this file's original
Task-A-before-Task-B discipline, surfaced explicitly rather than glossed over - not yet re-approved
by the human as an intentional reordering.

## Phase 5: Runtime constitution boundaries (CLAUDE.md-mandated)
- [ ] T012 New "Fee Agreement Generation" section in `config/runtime_constitution.md`: scope (when
  this applies), explicit non-scope (not a general document-editing/DOCX-creation tool; not used
  for invoices/receipts — those stay Morning MCP; not used for reminders), and a restatement that
  ambiguous short replies mid-flow answer the pending clarification in the SAME context.
- [ ] T013 One-line cross-reference added to each of: Reminders, Ledger Event Recognition, Morning
  MCP integration sections — excluding fee-agreement generation from their own scope.

## Phase 6: Acceptance test finalization
- [ ] T014 Extend `tests/billed/test_fee_agreement_generation_flow.py` with an `alternative_tracks`
  scenario (Stage 1 template selection + Stage 2-4 flow), matching the corpus-driven redesign —
  **BLOCKING**: needs human re-approval of the full test file (original approval predates the
  Hebrew/corpus redesign and the 5th variant).
  - [ ] T015 Run the (re-approved) `billed` acceptance tests via `scripts/run_single_test.sh`
  (no per-run approval needed — `billed` tier).
  - [ ] T016 Gate Zero: one real, human-approved live `dev` send exercising
  `sendFileByUpload` end-to-end (per research.md #2) — `expensive`-tier discipline applies
  (fresh approval every time) even though this isn't itself in `tests/expensive/`, since it's a
  real WhatsApp send with a real cost/side-effect profile matching that tier's caution.

## Analysis Findings (speckit.analyze pass, 2026-09-12)

1. **Gap: no tool triggers the actual send.** `contracts/doc-template-engine.md` and
   `contracts/fee-agreement-verification.md` only cover generate+verify; `contracts/
   whatsapp-file-delivery.md` describes `WhatsAppHandler.send_document_response()` but not what
   AI-facing tool calls it. **Resolution (this task pass)**: added `send_fee_agreement_document`
   as a third local tool in T009, RBAC-gated, verified-only. This is a plan-level gap-fill, not a
   requirements change — REQ-083-04/05 already imply a dispatch step must exist between
   verification and delivery; no spec.md edit needed, but `contracts/fee-agreement-verification.md`
   should get a short addendum documenting this tool once T009 lands (tracked, not yet written —
   flagged rather than done, since the contract doc itself is unchanged as of this tasks.md).
2. **Consistency check passed**: `data-model.md`'s `alternative_tracks` section, `manifest.json`'s
   5 variants, and `contracts/doc-template-engine.md`'s generalized `components` field
   description are mutually consistent (all reference the same `{label, terms}` shape and
   `repeating_group.min_items`/`row_placeholders` fields).
3. **No orphaned requirements**: REQ-083-01 through 05 all map to at least one task above.
4. **Feature-flag default**: `plan.md`'s Constitution Check says `fee_agreement_docs` defaults
   `False`. T004 is not yet done, so as of this tasks.md the flag doesn't exist in any config file
   yet — implementing T009 without first landing T004 would mean the tool is permanently absent
   (config.feature_flags.get(...) defaults `False` either way), which is safe but worth doing in
   order.
