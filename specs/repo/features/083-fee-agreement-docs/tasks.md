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
- [ ] T004 Add `fee_agreements` block + `feature_flags.fee_agreement_docs: false` to
  `config/config.example.json`, `config/config.test.json`, `config/config.dev.json`,
  `config/config.prod.json` (per CLAUDE.md "config is code" — dev/prod values need explicit
  human sign-off before being flipped `true`; `config.test.json` can default `true` since tests
  are isolated).

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
- [ ] T007 Run T005 against T006 until green (`./venv/bin/python3 -m pytest tests/unit/test_doc_template_engine.py -v`).

## Phase 3: AI tool wiring (`ai_handler.py`) — NOT YET IMPLEMENTED
- [ ] T008 [Task A] `tests/unit/test_ai_handler_fee_agreement_tools.py` — unit-level coverage of
  the new tool schemas + dispatch logic in isolation (mirrors `test_ai_handler_approval_gate.py`'s
  pattern for `create_reminder`): `generate_fee_agreement` function-call → creates a
  `PendingLocalToolApproval` (never dispatches immediately) with the full `variant_id`/`values`/
  `components` payload; approval (typed reply or button tap) → calls
  `DocTemplateEngine.generate()` → success path stores the resulting `GeneratedDocument` for the
  same turn's subsequent `verify_fee_agreement_document` call; `verify_fee_agreement_document`
  dispatches immediately (read-only, no approval per contract) and returns the `verify()` result
  to the model; a `verify_fee_agreement_document` call with a stale/unknown `document_id` is a
  tool-call error (mirrors bugfix-038's "always re-fetch fresh, same-turn state" principle).
- [ ] T009 [Task B] `ai_handler.py`:
  - New tool schemas `GENERATE_FEE_AGREEMENT_TOOL` / `VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL` (JSON
    per `contracts/doc-template-engine.md` / `contracts/fee-agreement-verification.md`),
    RBAC-attached (GODFATHER/ADMIN only) alongside reminder/ledger tools, gated additionally by
    `config.feature_flags['fee_agreement_docs']`.
  - `self.doc_template_engine = DocTemplateEngine(...)` constructed in `AIHandler.__init__`
    (config-driven paths, DI — no monkey-patching), analogous to `self.reminder_manager`.
  - A `generate_fee_agreement` function-call branch (near `create_reminder`'s, ~line 2434-2490)
    that validates via `DocTemplateEngine._validate_values`/`_validate_components` (surfacing a
    `ValueError` as a tool-call error string, not a raised exception) and, on success, creates a
    `PendingLocalToolApproval` carrying the full payload — same shape/flow as `create_reminder`.
  - The approval-resolution branch (near line 3886-3997) gets a `generate_fee_agreement` case:
    calls `DocTemplateEngine.generate()`, stores the `GeneratedDocument` keyed by `document_id`
    in a small per-chat in-memory dict (`self._pending_generated_documents: Dict[str, GeneratedDocument]`
    — turn-scoped, not persisted; see data-model.md "not a database row" note) for the immediately
    following `verify_fee_agreement_document` call to retrieve.
  - `verify_fee_agreement_document` dispatches immediately (no `PendingLocalToolApproval`, read-only
    per contract) — looks up the `GeneratedDocument` by `document_id`, calls
    `DocTemplateEngine.verify()`, sets `GeneratedDocument.verified = True` iff the model's
    OWN subsequent judgment (not this tool) accepts it — actually: this tool merely returns the
    facts; `verified` is set immutably `True` only inside the SAME tool call when `result["clean"]`
    is `True` (defense-in-depth per data-model.md — `send_document_response()` still independently
    refuses an unverified document, so this is belt-and-suspenders, not the sole gate).
  - A third local tool, `send_fee_agreement_document` (NOT in the original contracts — added here
    because `verify_fee_agreement_document` is read-only per contract and something must trigger
    the actual WhatsApp send; mirrors how `create_reminder`'s dispatch and delivery are separate
    concerns) — dispatches immediately, RBAC-gated, refuses (tool-call error) unless
    `GeneratedDocument.verified is True`, calls `WhatsAppHandler.send_document_response()`, then
    deletes the temp file and the in-memory `GeneratedDocument` entry regardless of send outcome.
    **NEEDS CLARIFICATION (flagged for `speckit.analyze`, resolved below in Analysis Findings)**:
    this tool wasn't named in `spec.md`/`contracts/` — see Analysis Findings #1.

## Phase 4: WhatsApp delivery (`whatsapp_handler.py`) — NOT YET IMPLEMENTED
- [ ] T010 [Task A] `tests/unit/test_whatsapp_handler_document_send.py` — extends the existing
  `WhatsAppHandler` unit test file's pattern: `send_document_response()` calls
  `bot.api.sending.sendFileByUpload(chatId=..., path=..., fileName=..., caption=...)` exactly
  once on success; retries once on a 5xx/timeout-shaped failure (CONSTITUTION retry policy),
  never retries a 4xx-shaped one; deletes the temp file in both the success path and the
  retry-exhausted failure path (SC-003); raises/returns a friendly error (no raw exception text)
  on final failure; refuses outright (no call attempted) if `GeneratedDocument.verified is not True`.
- [ ] T011 [Task B] `whatsapp_handler.py`: `send_document_response(generated: GeneratedDocument, chat_id: str, caption: str) -> bool`
  per `contracts/whatsapp-file-delivery.md`.

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
