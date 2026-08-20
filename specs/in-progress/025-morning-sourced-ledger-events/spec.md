# Feature Spec: Morning-Sourced Ledger Events

**Feature ID**: 025-morning-sourced-ledger-events
**Priority**: P2
**Status**: Clarified — ready for `speckit.plan` (see Clarifications, 2026-08-20)
**Created**: July 28, 2026

---

## Problem Statement

Feature 024 (Ledger Event Recognition) captures fee-agreement and bank-deposit events
from conversational text/images via a `capture_ledger_event` function tool, always
attached alongside Morning MCP tools for godfather/admin turns
(`AIHandler._assemble_tools`). Discovered live (2026-07-28, `test_yossi_all_payments_gets_the_complete_picture`):
a real godfather turn asking to "list all payments" for a client triggered
`list_invoices`, and the model then read its own tool output back and mistook
pre-existing Morning documents for new fee-agreement text, calling
`capture_ledger_event` on data that already lives in Morning. Worse, the follow-up
round-trip (`_call_openai_ledger_followup_api`) still had `capture_ledger_event`
available and called it *again* instead of finally answering, so the user got a
completely empty reply despite `list_invoices` having successfully returned the
correct, complete data.

**The underlying insight (user, 2026-07-28) is real and worth building on
purpose**: Morning documents can be created outside DeniDin entirely (directly in
Green Invoice, or by another integration) - `list_invoices`/`get_invoice_details`
are effectively the *only* way DeniDin can ever discover that those events happened.
A document a godfather created by talking to DeniDin already flows into ledger
tracking via the conversational capture path; a document that shows up in Morning
with no matching DeniDin conversation never does, and today has no path into the
ledger at all. This is a real gap, not just a misfire to patch around.

**Immediate mitigation shipped ahead of this spec** (bugfix-adjacent, not a full
fix): `AIHandler._handle_ledger_event_capture` now detects when the same turn's
`response.output` contains a real `mcp_call` item (Morning MCP genuinely produced
this turn's data) and, if so, does not persist any `capture_ledger_event` call(s)
from that turn, and strips `capture_ledger_event` from the follow-up round's tools
so the model can't repeat the same mistake and is forced to produce its actual
text reply. This restores correct behavior (the user gets their real answer) but
throws the Morning-sourced signal away entirely rather than doing anything useful
with it - exactly the gap this spec should close.

## Clarifications

### Session 2026-08-20

- **Q: How should DeniDin track which Morning documents are already known to
  the ledger, to avoid re-capturing the same document on every
  `list_invoices`/`get_invoice_details` call? → A:** Check against the actual
  existing ledger events, not a new separate store and not AHLedger's CSVs.
  Concretely: the "already known" set is derived by scanning already-persisted
  `LedgerEvent` files under `{data_root}/events/*.json` for a non-null
  `morning_document_id` (the field `ledger_event_manager.py` already reserves
  for this — see References). No new storage mechanism.
- **Q: Should capture run only reactively, or also proactively (periodic
  polling)? → A:** Proactive polling.
- **Q: Should Morning-sourced events reuse `capture_ledger_event`'s
  schema/persistence path, or get a dedicated one? → A:** Reuse the same
  `LedgerEvent` persisted-event concept and the same underlying
  `LedgerEventManager.add_ledger_event` persistence path (one JSON file per
  event, same field set), extended with new fields as precisely needed — not
  a parallel storage mechanism. `source_type="חשבונית"` (event letter `"H"`)
  is already reserved and already documented as "never produced by
  `capture_ledger_event`" (i.e. only ever produced by this feature's own
  path). The five fields `ledger_event_manager.py` already reserves —
  `invoice_status`, `invoice_number`, `invoice_type`, `morning_document_id`,
  `invoice_actual_creation_date` — are the intended home for this feature's
  Morning-specific data; any further new fields must be identified precisely
  during `speckit.plan`/`speckit.tasks`, not assumed. **(These five names are
  themselves renamed to `accounting_document_*` in round 2 below —
  `speckit.analyze` flagged this as potentially confusing to a reader who
  stops here; the field *concept*/home decided in this round is unchanged,
  only the literal names.)**
- **Q: Feature-flag gate? → A:** No feature flag. Instead, bump
  `ledger_event_manager.py`'s `CURRENT_SCHEMA_VERSION` from `1` to `2` —
  every event persisted by this feature (and, going forward, by the existing
  `capture_ledger_event` path too, since it's the same schema/file format)
  carries `schema_version: 2`.
- **Q: How does the proactive poll actually call Morning — direct HTTP to
  the MCP server (no AI), or routed through OpenAI/AIHandler? → A:** Routed
  through OpenAI, using the same MCP-tool-attachment access pattern a real
  godfather turn uses (remote MCP tool over the ngrok tunnel) — but this is
  **not** a runtime/conversational turn: it does not use
  `runtime_constitution.md` or any of `AIHandler`'s normal system-prompt
  assembly (memory recall, role context, conversation history). It gets its
  own dedicated, tailored prompt whose job is specifically: list and detail
  every Morning document created since the last poll, then — one at a time —
  call `capture_ledger_event` (extended per above) to persist each as a
  `LedgerEvent`. Same underlying access mechanism (OpenAI Responses API +
  remote Morning MCP tool + the local `capture_ledger_event` function tool),
  materially different flow from any existing user-facing one: no chat
  session, no user message, no reply sent anywhere.
- **Q: Poll scope and cadence? → A:** Company-wide, rolling date window — one
  `list_invoices` sweep per tick with no client filter, bounded by a rolling
  date range, same shape as `reminder_delivery_service.py`'s
  startup-sweep-plus-periodic-tick pattern (see References). Exact window
  sizes and interval to be pinned down in `speckit.plan`/`research.md`.

### Session 2026-08-20 (round 2 — during `speckit.plan`)

- **Q: Vendor-neutral/doc-type-agnostic field naming scheme? → A:** Prefix
  everything with `accounting_document_`: the 5 reserved fields become
  `accounting_document_id` (was `morning_document_id`),
  `accounting_document_number` (was `invoice_number`),
  `accounting_document_type` (was `invoice_type`),
  `accounting_document_status` (was `invoice_status`),
  `accounting_document_creation_date` (was `invoice_actual_creation_date`).
  See `research.md`/`data-model.md` for the full mapping and population
  rules.
- **Q: Keep `source_type="חשבונית"`/letter `"H"`, or a generic
  `"מסמך"`/`"D"`? → A:** Keep `חשבונית`/`"H"` — used as the single bucket for
  every Morning-sourced accounting document regardless of specific type
  (invoice, receipt, credit note, ...), not literally restricted to tax
  invoices. **Flagged as an unverified assumption about the real,
  hand-maintained `Events.csv`'s actual usage of this term** — carried into
  `tasks.md` as a verification step before shipping, per
  `CONSTITUTION.md`'s "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" principle
  (see `research.md`), not treated as fully closed just because it's the
  user's stated preference.
- **Q: Which Morning document types are in scope — invoices only, or all
  types? → A:** All document types. **Finding, not just a decision**: this
  needs NO new `morning-mcp-app` tooling — direct inspection confirmed
  `list_invoices`/`get_invoice_details` already hit Morning's generic
  `/documents/search`/`/documents/{id}` endpoints with no type filter, so
  they already return every document type despite their invoice-specific
  names (`research.md`). This removes what had been flagged as a real
  scope-expansion risk when the question was first asked.
- **Q: Should the poll mechanism bypass OpenAI (direct HTTP to the Morning
  MCP server) or route through it? → A:** Route through OpenAI, using the
  same MCP-tool-attachment access pattern a real turn uses, but with its own
  dedicated non-runtime-constitution prompt (already captured in the first
  session's answer above) — this round confirmed the mechanism stays
  OpenAI-mediated even though it's not a conversational turn.

## Resolved (was "Open Questions") — see `research.md`/`data-model.md`/`contracts/` for detail

- Exact field mapping: **resolved**, see `data-model.md`'s field table.
  `accounting_document_creation_date` maps to `Invoice.issue_date` (`Invoice`
  has no separate system-creation timestamp — confirmed by direct model
  inspection, not assumed) and `accounting_document_type` is decoded from
  `Invoice.type` via Morning's already-elsewhere-confirmed `GET
  /documents/types` lookup.
- Rolling-window/interval sizing: **deferred to `tasks.md`** (a tuning
  decision, not a data-shape one) — the startup/periodic split pattern
  itself (mirroring `reminder_delivery_service.py`) is resolved.
- Code-side duplicate guard: **resolved, yes** — `LedgerEventManager` hard-
  refuses a duplicate `accounting_document_id` inside `add_ledger_event`
  itself; see `contracts/ledger-event-manager-extension.md`.
- Service wiring / failure semantics: **resolved** — new
  `services/accounting_reconciliation_service.py`, started in `__main__`
  only (never `initialize_app()`, mirroring `reminder-delivery.md`'s own
  corrected precedent); a failed tick self-corrects because the watermark
  is derived from what's actually persisted, never a separately-advanced
  counter. See `contracts/accounting-reconciliation-service.md`.
- Document types / naming: **resolved**, see round 2 above.
- **Still genuinely open, carried into `tasks.md`**: (1) verifying
  `source_type="חשבונית"`'s real-`Events.csv` usage (flagged above); (2)
  confirming `event_subtype="הפקה"` (proposed in `data-model.md`, not yet
  independently confirmed) reads correctly as real accounting terminology;
  (3) exact poll interval/lookback numbers; (4) exact reconciliation-prompt
  wording (shape is fixed by `contracts/`, literal text is not).

## Relationship to Feature 024

Direct follow-on. Feature 024 built the capture mechanism and text/image sources;
this spec is about adding Morning MCP tool results as a third source, with real
diffing/dedup logic Feature 024 never needed (conversational text is inherently
"new" each time; Morning tool results are a full history repeated on every call).

## References

- `apps/denidin-app/src/handlers/ai_handler.py` (`_handle_ledger_event_capture`,
  `_call_openai_ledger_followup_api`, `_assemble_tools`) - current suppression logic
  to be replaced/extended by whatever this spec resolves on.
- `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py`
  (`test_yossi_all_payments_gets_the_complete_picture` /
  `test_yossi_explicit_everything_request_gets_the_complete_picture`) - where the
  gap was first observed live.
- `config/runtime_constitution.md`'s "Ledger Event Recognition" section.
- `apps/denidin-app/src/managers/ledger_event_manager.py` — `_LETTER_BY_SOURCE_TYPE`'s
  `"H"`/חשבונית comment, `CURRENT_SCHEMA_VERSION`, and the 5 already-reserved
  `invoice_*`/`morning_document_id` fields on the persisted record — this
  feature's intended landing spot, per the 2026-08-20 clarification session.
- `specs/done/v0.2.0/033-ledger-event-persistence/data-model.md` — historical
  (do not edit) but documents the original Hebrew CSV-column mapping
  (`חשבונית.*`) for those 5 reserved fields.
- `apps/denidin-app/src/services/reminder_delivery_service.py` — the existing
  APScheduler-based background-job pattern (startup sweep + periodic tick,
  wall-clock-aligned `CronTrigger`) this feature's proactive poll should
  mirror structurally.
- `apps/morning-mcp-app/src/denidin_mcp_morning/models.py` (`Invoice`) —
  the structured fields (`id`, `number`, `status`, `type`, `issue_date`,
  `client_name`, `amount`, `linked_documents`, `payments`) available from
  `list_invoices`/`get_invoice_details` to map onto the reserved fields.
