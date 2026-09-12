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
- [x] T008 [Task A/B done together, human-approved reordering 2026-09-12] `tests/unit/test_ai_handler_fee_agreement_tools.py`
  written (19 tests) covering: tool attachment (RBAC + feature flag, 4 tests), the
  `generate_fee_agreement` proposal path (valid/missing-values/unknown-variant, 4 tests), the
  approval-resolution path (approve → real `DocTemplateEngine.generate()` → followup text; decline;
  TOCTOU re-validation, 3 tests), and the immediate-dispatch verify/send handlers (clean verify sets
  `verified=True`; stale `document_id` is a tool-call error not a crash; send refused when
  unverified; send success cleans up the document + temp file; send with no chat_id/no
  whatsapp_handler is a tool-call error, 8 tests). Real `DocTemplateEngine` throughout (no mocking
  of internal code) — only the OpenAI client is a stand-in, same discipline as
  `test_ai_handler_reminders.py`.
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
- [x] T010 [Task A/B done together] `tests/unit/test_whatsapp_handler_document_send.py` written
  (8 tests): sends exactly once on success with the exact expected `sendFileByUpload` args; refuses
  outright when unverified (no call attempted); returns `False` when no bot is injected; retries
  once on a 5xx then succeeds; never retries a 4xx; returns `False` after retry exhausted; never
  raises on a connection error; never deletes the temp file itself (that's
  `FeeAgreementToolHandler._cleanup`'s job). Fixing this test surfaced and fixed a real bug in the
  first retry-predicate implementation (see note below).
- [x] T011 [Task B] `whatsapp_handler.py`: `send_document_response(generated: GeneratedDocument, chat_id: str, caption: str) -> bool`
  implemented per `contracts/whatsapp-file-delivery.md` — `_send_file_with_retry` (retry-once-on-5xx/
  timeout/connection-error, never-on-4xx), refuses outright (returns `False`, no call attempted) if
  `generated.verified is not True`, never raises (all failure paths return `False`). Temp-file
  deletion is NOT this method's job — it's `FeeAgreementToolHandler._cleanup`'s, called by
  `ai_handler.py`'s send handler regardless of this method's return value (SC-003 still holds, just
  enforced one layer up).

**Bug caught by T010's own test (2026-09-12, worth recording)**: the first `_send_file_with_retry`
implementation used `retry_if_exception_type((Timeout, ConnectionError, HTTPError))` with an inner
`except HTTPError: if 4xx: log "not retrying"; raise` — but tenacity's retry predicate evaluates the
exception the DECORATED function raises, regardless of what happened inside it; re-raising an
`HTTPError` from inside the function body doesn't stop tenacity from matching `HTTPError` and
retrying anyway, so a 4xx was actually being retried once despite the log line claiming otherwise.
Fixed by switching to `retry_if_exception` with an explicit status-code-aware predicate
(`_is_retryable_send_error`). `test_never_retries_a_4xx_error` failed against the buggy version and
passed once fixed — a real regression this task's own Task-A-first discipline caught before it
shipped.

**Status (2026-09-12): Phase 3 and Phase 4 are both fully implemented AND unit-tested — T008/T010
were done as Task A/B together (reordered from the file's original A-then-B split), which the human
explicitly approved when asked how to close this gap** (see the exchange right after this file's
prior revision). Full unit suite: 1447/1447 passing (1420 pre-existing + 27 new, zero regressions).

## Phase 5: Runtime constitution boundaries (CLAUDE.md-mandated) — DONE
- [x] T012 New "Fee Agreement Document Generation" section added to `config/runtime_constitution.md`:
  scope (explicit request for the actual document, not just discussing/agreeing terms), the
  mandatory 3-step generate→verify→send flow (never skip/reorder), explicit non-scope (not
  invoices/receipts — Morning MCP; not reminders; not merely discussing/recording an agreement —
  that's Ledger Event Recognition, automatic, no tool call), and the standard ambiguous-short-reply
  restatement (answers the pending question in the SAME context, never a trigger to switch tool
  families).
- [x] T013 Cross-references added to each of: Reminder Management (its own scope-separation
  paragraph now lists this feature too), Ledger Event Recognition ("How recording works" paragraph
  now clarifies recording ≠ producing a document), Ledger Event Querying ("When this tool does NOT
  apply" bullet now lists this feature alongside Invoice Management/Reminder Management), and
  Invoice Management Context (its opening scope paragraph now lists this feature too) —
  bidirectional, matching the existing cross-reference pattern exactly.

## Phase 6: Acceptance test finalization
- [x] T014 Extended `tests/billed/test_fee_agreement_generation_flow.py`:
  - Added `test_alternative_tracks_selected_and_generated` — asserts variant selection picks
    `alternative_tracks` (not `multi_component_agreement`) for a mutually-exclusive-choice
    request, asserts the required `SHARED_ADDON_TERMS` scalar is never omitted, and runs the
    full generate→approve→verify→send flow end-to-end for the 5th variant.
  - **Also fixed real API mismatches** the draft had predating implementation:
    `pending_local_tool_approval_manager.get_pending()` → `.get()` (the manager's actual method
    name); `send_document_response`/`_send_file_with_retry` mock `call_args` index fixes (patched
    at the class level, so `self` is never in `call_args.args` — the draft assumed it was);
    `_call_send_file_by_upload` (never existed) → `_send_file_with_retry` (the real private
    method); added `fee_agreements` to the test fixture's `config_dict`.
  - **STILL BLOCKING on fresh human re-approval of the WHOLE file** before T015 runs — the
    original approval predates the Hebrew/corpus redesign, the alternative_tracks variant, AND
    now these API-correctness fixes. The file's own docstring states this blocking status.
- [ ] T015 Run the (re-approved) `billed` acceptance tests via `scripts/run_single_test.sh`
  (no per-run approval needed — `billed` tier — but the file-level re-approval above is a
  separate, prior gate that must clear first).
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
