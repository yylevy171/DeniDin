# Feature Spec: Morning-Sourced Ledger Events

**Feature ID**: 025-morning-sourced-ledger-events
**Priority**: P2
**Status**: Implemented and accepted (see Clarifications rounds 1-6) — all 9 `billed` acceptance tests (all 5 user stories) passing against the real `dev` Morning sandbox + real OpenAI, 2026-08-23. `accounting_ledger_update_freq` is `0` in `prod` (deliberately, pending the T032 backfill) and `60` in `dev`/`test`. Phase 9b (widening `format="json"` to the remaining Morning MCP read tools) is explicit, tracked future work, deliberately out of scope for this feature — see `tasks.md`.
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

### Session 2026-08-21 (round 3 — mid-`speckit.implement`, before Phase 2 code was written)

- **Q: How is the poll interval configured? → A:** A new DeniDin (not
  Morning-specific) config field, `config.accounting_ledger_update_freq`
  (top-level, minutes, int). `0` means the feature is inactive — the
  scheduler never starts at all. No nesting, no `config.feature_flags` gate
  (unchanged from round 1 — schema-version bump still covers the
  no-flag decision).
- **Q: What happens when a sweep's gap since the watermark exceeds a safety
  cap? → A:** A hard cap of **5 days OR 100 documents**, whichever binds
  first, measured from the derived watermark. If exceeded, the sweep
  **skips the entire tick** (captures nothing, does not advance the
  watermark) rather than attempting a partial catch-up or a full backfill —
  explicitly NOT a backfill mechanism. Logged at ERROR only; no WhatsApp
  alert (this stays a silent background mechanism, consistent with the
  original "no confirmation reply sent anywhere" contract). The cap check
  itself is done by the **service directly** (a plain, non-AI-mediated
  `list_invoices(from_date=since)` call solely to count/date-check before
  ever invoking OpenAI) — never trusted to the model's own scoping, matching
  this codebase's existing "never trust the AI's own math/scoping"
  philosophy (`_normalize_amount`, `vat_status` forcing, etc. in
  `ledger_event_manager.py`).
- **Q: Should a duplicate `accounting_document_display_number` hard-refuse
  the second write (round-1's original design)? → A: No — replaced
  entirely.** The user directive: *"I don't like the hard refusal... this
  raises a question of how to reconcile when there are clarifications
  required... The 'since when' mechanism SHOULD NOT RELY ON A REFUSAL
  MECHANISM."* New tri-state design (`data-model.md`/
  `contracts/ledger-event-manager-extension.md`):
  - Same display number + same creation timestamp seen before → **true
    duplicate**, silently discarded (no new file).
  - Same display number + a **different** creation timestamp than any
    previously seen → **anomaly** (should never happen for a real Morning
    document) → persisted as a **new** `LedgerEvent` (its own new
    `event_id`, since the differing timestamp changes it) **and** logged
    **and** appended to a new persisted `pending_review.json` tracker. No
    WhatsApp.
  - Not seen before → ordinary new capture.
  This decision explicitly lives inside `LedgerEventManager` (a ledger
  concern), **not** in the new `ai_handler.py` handler — user directive:
  *"it's clearly a ledger requirement regardless of ai."*
- **Q: Where does the "known documents" tracking data live — a new
  persisted state file, or derived by re-scanning every tick? → A:**
  Neither, exactly as originally proposed. **In-memory only**, built via
  **one** disk scan at first use per process (lazy, via the existing
  `scan_accounting_documents`), then mutated in-process — appended to on
  each new capture, pruned each tick — never re-scanned from disk again
  during that process's lifetime. User directive: *"ideally no reading and
  parsing of the ledger events is required per tick... one-time built on
  startup."* Pruning rule: an entry can be dropped once it's older than the
  5-day cap plus a small safety margin (7 days total) before "now," since
  the forward-only watermark can never legitimately cause it to be
  re-queried again — **flagged for live confirmation** of Morning's
  `from_date` filter semantics (folded into the live-verification task,
  `tasks.md`).
- **Q: Is `accounting_document_id` (Morning's opaque internal id) or
  `accounting_document_number` (the human-visible number) the right dedup
  key / persisted identity field? → A: Neither name as originally
  proposed — collapsed into one field, `accounting_document_display_number`.**
  User directive: *"document id... is the USER FACING display number - NOT
  the morning internal id... rename it everywhere to
  document_display_number."* The internal Morning id (`Invoice.id`) is used
  only transiently within a sweep tick (to call `get_invoice_details`) and
  is never persisted or exposed as its own field. The field count drops
  from 5 to **4**: `accounting_document_display_number` (was the planned
  `accounting_document_id`/`accounting_document_number` pair, now merged),
  `accounting_document_type`, `accounting_document_status`,
  `accounting_document_creation_date`.
- **Q: Does every Morning document really have a full-precision creation
  time and a non-null display number, or was round 2's `documentDate`
  (date-only) really the best available? → A: Live-verified, real gap
  found.** A real, read-only probe against the actual Morning **dev**
  sandbox (25 real documents, 6 distinct document types: 300/305/320/330/
  400) confirmed: **every** document carries a non-null `number` (the
  display number) AND a full-precision `creationDate` (a real Unix epoch
  integer, not just a date — e.g. `1787241168` → `2026-08-20 18:52:48`
  Israel local). **But** `apps/morning-mcp-app`'s `Invoice` Pydantic model
  currently maps neither field — it only maps `documentDate` (date-only).
  This is a real, material scope addition (not present in round 1/2's
  plan): Feature 025 now includes a small `morning-mcp-app` change — map
  `creationDate` into a new `Invoice` field and expose it through
  `get_invoice_details`'s tool output — landed as part of **this** feature
  (per user decision) rather than spun off separately. Once mapped,
  `accounting_document_creation_date` sources from `creationDate` (full
  precision), not `documentDate` — which also resolves the
  `event_id`-HHMM-portion question from round 1: it uses the document's own
  real creation time directly, no midnight-fallback placeholder needed.

### Session 2026-08-21 (round 4 — during `speckit.implement`, T011 planning)

- **Q: The 100-document safety-cap check was designed as a direct, non-AI
  `list_invoices` call before ever invoking OpenAI — but no direct MCP-client
  mechanism (raw HTTP/JSON-RPC to the Morning MCP server, bypassing OpenAI's
  `type: "mcp"` attachment) exists anywhere in `denidin-app` today, and
  building one from scratch is real new infrastructure. How should this
  actually work? → A: Post-hoc, not pre-hoc.** One OpenAI+MCP call as
  already planned (the model lists/details/captures in one turn) — no new
  client needed. **After** it completes, the service inspects the real
  `list_invoices` `mcp_call` item's own `output` text (already embedded in
  `response.output`, per the existing `mcp_calls` extraction pattern
  `ai_handler.py` already uses elsewhere) for the true total count —
  `morning-mcp-app`'s own `format_invoice_list`/`format_too_many_invoices_message`
  always states the real total in one of a few fixed Hebrew phrasings
  ("נמצאו {N} חשבוניות...", "מוצגות {shown} מתוך {N}...", "לא נמצאו
  חשבוניות..."). If that parsed total exceeds 100, the **entire turn's
  captures are discarded** (never call `_handle_accounting_reconciliation_capture`
  at all) — same "never trust the AI's own scoping" guarantee (the code
  reads the tool's real structured-ish output, never the AI's prose), just
  checked after the one call instead of before. The **5-day** half of the
  cap stays a genuine pre-check (pure local computation from the cache
  watermark, no call needed either way). User directive: *"should use
  'list'. verify that the total number of items is returned in the list
  object returned to ai"* — confirmed live-in-code (not merely assumed):
  `formatters.py`'s `format_invoice_list`/`format_too_many_invoices_message`
  do state the real total, unconditionally, in every response shape.

### Session 2026-08-22 (round 5 — during `speckit.implement`, after live dev testing)

- **Q: Is `get_invoice_details` required at all, or is `list_invoices`
  sufficient? → A: `list_invoices` alone is sufficient.** Measured
  directly against the real dev sandbox: `get_invoice_details`' response
  adds exactly **two** fields over a `/documents/search` item —
  `linkedDocuments` and `userName` — and nothing else. The search response
  is already a complete document object (including `creationDate` and the
  top-level `description`); `morning-mcp-app`'s formatter was simply
  dropping most of it before the model ever saw it. The entire round-3/4
  two-call design (list → details×N → capture×N) was therefore solving a
  problem that did not exist. **The shipped flow is one `list_invoices`
  call, then one `capture_ledger_event` per document** — verified live:
  zero `get_invoice_details` calls, 18/18 documents fully correct across 3
  consecutive playground trials plus the deployed sweep.
- **Q: Why did the model refuse to call `get_invoice_details` even when the
  prompt demanded it? → A: its own tool description outranked the
  prompt.** `get_invoice_details`' registered description scopes it to
  status-change flows ("mark as paid", "cancel it"). Across 6 live trials
  it was never called once, regardless of how forcefully the user-message
  prompt demanded it. **General lesson for this codebase**: a tool's own
  `description` is a stronger signal than any per-turn instruction — when a
  background flow needs a tool used outside its documented purpose, fix the
  data/tooling so the tool isn't needed, or change the tool's description;
  do not try to out-argue it in a prompt.
- **Q: `list_invoices` truncated at 2500 tokens (8 of 18 real documents) —
  raise it? → A: yes, 20000.** Also found: **no** config file
  (`dev`/`test`/`prod`) had `list_invoices_token_budget` set at all, so
  every environment was silently running the 2500 code default. Now set
  explicitly in `dev`/`test`/`example`; `prod` deliberately left untouched
  (it does not run this feature yet).
- **Q: Credit notes (`חשבונית זיכוי`) know which invoice they cancel, but
  only as free text in `description` — capture that linkage structurally
  in `reference`/`reference_hint`? → A: leave as-is for now (deferred, user
  decision).** The structured linkage lives in `linkedDocuments`, which is
  one of the only two fields `list_invoices` does not carry — capturing it
  would mean reintroducing per-document `get_invoice_details` calls for the
  documents that have links. Deferred deliberately rather than forgotten:
  the linkage remains visible in `description` text, and Feature 033's
  existing `reference`/`REFERENCE_PLACEHOLDER` mechanism was always designed
  for a later human/script resolution pass. Revisit as its own scoped
  change if/when the ledger needs it structurally.

### Session 2026-08-23 (round 6 — Phase 9, full document capture, implemented)

Design decisions taken with the user, then what actually happened when built.

- **Q: Scope? → A:** Full document capture **extends Feature 025** (not a separate
  Feature 026) — 025 does not ship until it lands.
- **Q: Transport? → A:** MCP read tools gain a `format="json"` parameter; the
  **default stays Hebrew prose**, so conversational output is byte-for-byte
  unchanged. The model copies one JSON blob verbatim;
  `LedgerEventManager` maps and derives everything in code. Scoped to the 2
  sweep tools now, with **all read tools committed as a follow-up phase**
  (`tasks.md` Phase 9b) — *"I want uniformity for the whole mcp server."*
- **Q: Line items? → A:** Use only the **first** `income[]` entry; log a WARNING
  naming how many were dropped, so a multi-line document is never silently
  half-captured.
- **Q: Which fields? → A:** All 13 candidates reviewed individually; **8
  skipped** (derivable, constant, volatile or redundant). Two genuinely new
  fields survived, plus three mapped onto fields that already existed — see
  `tasks.md` Phase 9 for the table and the per-field reasoning.
- **Q: Bank details? → A:** Lift the `בנק`-only force-null and **reuse**
  `bank_number`/`bank_branch`/`bank_account`.
- **User corrections that removed proposed fields** (both caught by the user,
  not by the implementer — the same class of mistake twice):
  - `payment[].date` is **`txn_date`**, a field that already means "the
    transaction/value date", not a new `accounting_document_payment_date`.
  - `linkedDocuments` maps onto the existing **`reference`/`reference_hint`**
    mechanism, whose own docstring names the case ("the real prior event id
    this event relates to (replaces, **cancels**, or otherwise references)") —
    not new `linked_number`/`linked_type` fields.

- **Q: What gates the expensive per-document fan-out? → A: the caller's
  CONTEXT, not the output format** (user catch, 2026-08-23). The first
  implementation gated on `output_format="json"`, which silently coupled two
  orthogonal concerns — presentation vs cost. Since Phase 9b makes JSON the
  format for *every* read tool, that gate would have made every ordinary
  conversational `list_invoices` explode into N per-document GETs. Now gated
  on **`include_full_details`**, independent of format.
  **Refined same day:** this is a *capability*, not a context lock —
  conversations may opt in too, whenever a question genuinely needs bank
  details or linked documents ("which account was I paid into?"). *"There is
  no expense in making api calls, only a bit of latency and that is
  acceptable."* It is simply not the default, because most questions do not
  need it; the sweep always does.

- **Q: How do Morning's document types map into the ledger's own taxonomy?
  → A: the document type IS the `event_subtype`** (user decision,
  2026-08-23), using **Morning's own retrieved label**, never a hand-written
  string: `300 חשבון עסקה`, `305 חשבונית מס`, `320 חשבונית מס / קבלה`,
  `330 חשבונית זיכוי`, `400 קבלה`. This replaces the original flat mapping,
  where all five types collapsed to `event_subtype="הפקה"` and the real type
  survived only in a separate descriptive field — which made a credit note
  (a cancellation) and a receipt (a payment) indistinguishable from an
  invoice issuance in the ledger's own vocabulary. **`accounting_document_type`
  is therefore removed**: the type is now persisted in `event_subtype`, and
  storing it twice would be redundant. `הסכם`/`בנק` keep their existing
  `יצירה`/`הפקדה` vocabulary untouched.

**What building it actually proved:**

1. **The N+1 fan-out cannot be delegated to the model — and the prompt is not
   the lever.** Structured bank details and `linkedDocuments` exist ONLY on the
   single-document GET. `get_invoice_details`' own description was first fixed
   (it scoped itself to status-change flows, which outranked every
   instruction). Even then, asked to chain the calls, the model called
   `list_invoices`, emitted two captures and **stopped — never once calling
   `get_invoice_details`**. Resolution: the fan-out moved **server-side** into
   `morning-mcp-app`, where it is deterministic code. One model call in,
   complete documents out. *Generalisable lesson: when a flow needs N reliable
   tool calls, put the loop in code, not in the prompt.*
2. **A silent 17% data-loss bug.** One run persisted 15 of 18 documents with no
   error: the model re-emitted the payload with **literal newlines** where
   `json.dumps` had written `\n`, so `json.loads` rejected it. The source is
   always valid and the content intact, so parsing now uses `strict=False`
   (tolerating mangled whitespace escaping) while genuinely malformed JSON is
   still rejected loudly.
3. **Two more pre-existing dropped mappings**, both silently affecting every
   caller, not just this feature: `Invoice.payments` was always `[]` (raw key
   `payment`, no mapping — so `get_invoice_details`' "תשלומים:" block was dead
   code that had never rendered for anyone), and `vat_amount` was mapped only
   from `vatAmount` when real responses spell it `vat`.

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
- Code-side duplicate/mismatch handling: **resolved, revised in round 3** —
  no hard refusal. `LedgerEventManager` maintains an in-process (not
  disk-persisted) known-documents cache, lazily built once via one disk
  scan, and applies the tri-state duplicate/anomaly/new logic described in
  round 3 above. See `contracts/ledger-event-manager-extension.md`.
- Service wiring / failure semantics: **resolved** — new
  `services/accounting_reconciliation_service.py`, started in `__main__`
  only (never `initialize_app()`, mirroring `reminder-delivery.md`'s own
  corrected precedent); a failed/capped tick self-corrects because the
  watermark is derived from the in-process cache, never a separately-
  advanced counter. See `contracts/accounting-reconciliation-service.md`.
- Document types / naming: **resolved**, see round 2 above; field-naming
  (`accounting_document_display_number`, 4 fields not 5) and the
  `creationDate`-mapping gap further resolved in round 3.
- Poll interval/config: **resolved, round 3** —
  `config.accounting_ledger_update_freq`, no longer deferred.
- Safety cap on catch-up scope: **resolved, round 3** — 5 days / 100 docs,
  whichever binds first; skip-entire-tick on breach.
- **Still genuinely open, carried into `tasks.md`**: (1) verifying
  `source_type="חשבונית"`'s real-`Events.csv` usage (flagged above); (2)
  confirming `event_subtype="הפקה"` (proposed in `data-model.md`, not yet
  independently confirmed) reads correctly as real accounting terminology;
  (3) live-confirming Morning's `from_date` filter semantics (drives the
  known-documents pruning rule's safety margin, round 3); (4) exact
  reconciliation-prompt wording (shape is fixed by `contracts/`, literal
  text is not); (5) whether `number`/`creationDate` are guaranteed non-null
  for every document type across Morning's full type set, not just the 6
  types sampled live in round 3.

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
