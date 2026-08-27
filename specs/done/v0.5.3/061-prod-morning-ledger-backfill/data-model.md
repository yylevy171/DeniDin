# Data Model: Prod Morning Ledger Backfill

**Feature**: 061-prod-morning-ledger-backfill

**Revised 2026-08-25 (round 4)** for the five-phase architecture (Download → Method Selection →
Transform → **Validate** → Load). Still no *new persisted domain schema* — `LedgerEvent` (Phase
3's output) is reused completely unchanged. New this round: Phase 3.5's validation report entity.

## Entities

### 1. Raw downloaded document (Phase 1's output)

One local file per Morning document, holding Morning's own raw API response verbatim — no
reshaping, no field renaming. Written by Phase 1, read by Phase 3 and by Phase 3.5 (never
re-fetched from Morning during either).

- **Location**: an operator-designated local directory, stable and reused across runs (dedup, R8).
- **Filename**: keyed on the document's own Morning id (e.g. `{morning_document_id}.json`) — stable
  across re-runs, so a second Phase-1 run over an overlapping window overwrites byte-identically
  rather than creating a duplicate file under a different name (cross-cutting re-run-safety
  requirement).
- **Content**: exactly `MorningClient.get_invoice(invoice_id)`'s return value — a plain dict,
  serialized as-is. No fields added, removed, or renamed by Phase 1.
- **Not validated/typed further at this stage** — Phase 1's job is faithful capture, not
  interpretation; interpretation is Phase 3's job, and checking that interpretation is correct is
  Phase 3.5's job.

### 2. `LedgerEvent` (REUSED, unchanged — Phase 3's output)

Written one-per-document to a local output directory, in the exact same shape Feature 025's live
sweep already produces: `schema_version=2`, `source_type="חשבונית"`, `event_subtype` = Morning's
own document-type label (e.g. "חשבונית מס" — this is what carries the document-type info; there is
no separate `accounting_document_type` field), plus `accounting_document_display_number`,
`accounting_document_status`/`_status_code`/`_status_label`, `accounting_document_creation_date`
(not `_creation_timestamp`), `accounting_document_payment_method`, `client_name` (not
`accounting_document_client_name`), `description`, `amount`, `txn_date`, `bank_number`/`_branch`/
`_account`, `vat_status`, `event_id` in the existing letter+`DDMMYY`+`HHMM`+sequence-digit format
(`ledger_event_manager.py`'s `_next_seq`, scoped to whichever `storage_dir` the `LedgerEventManager`
instance was constructed with — Phase 3's own local output directory throughout Phases 1-3.5;
prod's real `{data_root}/events/` only once Phase 4 lands the files there). **Field list corrected
2026-08-25** against the real source (`apps/denidin-app/src/managers/ledger_event_manager.py`'s
`_expand_accounting_document_json`, read directly) — an earlier draft of this entity cited
`accounting_document_type`/`accounting_document_client_name`/`accounting_document_creation_timestamp`,
none of which exist in the real schema. See
`specs/done/025-morning-sourced-ledger-events/data-model.md` for the full field list — not
restated here.

### 3. Method-selection manifests + comparison report (Phase 2's output, one-time artifact)

**Redesigned 2026-08-26** (`research.md` R7): three related, plain local JSON files, not a
runtime data model — evidence for *which method Phase 3 is built with*, not consumed by any later
phase at runtime, not regenerated on every real run.

- **Method A's manifest** (`generate_method_a_manifest`'s `output_dir/manifest.json`): `{raw
  document id: sha256 hash}`, one entry per one of the ~20 sandbox documents, hashed over each
  document's CANONICAL JSON (`format_invoice_json`'s output — Stage 1+2 only, NOT the final
  `LedgerEvent`). Each document's canonical JSON is also written alongside the manifest, as its
  own file, for inspection.
- **Method B's manifest**: identical shape, generated via a real live-MCP relay through an actual
  AI call — fully implemented 2026-08-26 (see contracts/cli-contract.md); actually *running* it
  still needs a live dev/sandbox `morning-mcp-app` server (its own environment-start approval,
  not yet given).
- **Comparison report** (`compare_manifests`'s output, written by `--compare`): `{count_a,
  count_b, only_in_a: [ids], only_in_b: [ids], mismatched_hashes: [ids], identical: bool}` — no
  field-level content, purely a hash diff. `only_in_a`/`only_in_b` name a document present on one
  side only; `mismatched_hashes` names a document present on both sides whose canonical JSON
  hashed differently.

### 4. Validation report (NEW — Phase 3.5's output, one per backfill window)

A plain local file (JSON or Markdown, implementer's choice) produced fresh for every real Phase-1
→ Phase-3 run over a given window. Content (per REQ-BACKFILL-010):

- **Document-count reconciliation**: total raw documents in Phase 1's `--output-dir` for this
  window vs. total `LedgerEvent` files Phase 3 produced, with every discrepancy either explained
  (a documented, intentional skip reason — e.g. a document type outside the ledger's scope) or
  flagged as unexplained.
- **Surfaced anomalies**: every anomaly outcome `LedgerEventManager.add_ledger_event` returned
  during this Phase-3 run (R5) — listed explicitly, never silently absorbed into a "success" count.
- **Sampled field-level comparison**: for a sample of the window's documents, the raw source
  document's relevant fields next to the transformed `LedgerEvent`'s corresponding fields, so a
  systematic mapping bug (which a count-only check wouldn't reveal) is visible.
- **Sign-off field**: initially empty/unsigned; a human operator marks it signed (mechanism —
  editing the file, a separate small `--approve` flag, or similar — decided at implementation time)
  before Phase 4 is allowed to run for this window. Phase 4 MUST check this before writing anything
  (REQ-BACKFILL-010).

This report is per-window, not reused across windows or re-runs — a fresh window or a re-run gets
its own fresh report and its own fresh sign-off (`spec.md` Assumptions: "Phase 3.5 is a gate, not a
formality").

### 5. `backfill_prod_creds.local.json` (not a schema — a small gitignored credentials file)

See `contracts/backfill-creds-file.md` for the exact shape. Holds only the raw Green Invoice API
credentials Phase 1 (and eventually Phase 4, if it needs its own Morning access) requires.

## Relationships

```
Phase 1        Phase 2 (once)     Phase 3            Phase 3.5           Phase 4
Download   ──►  Method Selection   Transform     ──►  Validate       ──►  Load
(MorningClient   Experiment         (LedgerEvent-      (report +           (mechanism: TBD,
 → raw doc       (sandbox only,     Manager dedup       human sign-off      writes into prod's
 files, local,   decides HOW        + persist,           per window,         real
 keyed on doc    Phase 3 is         local output)        REQ-BACKFILL-010)   {data_root}/events/)
 id)             built)
```

Phase 2's diff report (entity 3) and Phase 3.5's validation report (entity 4) are structurally
similar (both are field-by-field diff/comparison artifacts) but serve different purposes: Phase
2's report is produced once, before Phase 3 is built at all, to decide *how* it's implemented;
Phase 3.5's report is produced on *every real run*, after Phase 3 has already run for that window,
to decide *whether that run's specific output* is trustworthy enough to load.

## No new entities beyond the above

No new dataclass is added to `apps/denidin-app/src/models/`. `LedgerEvent`'s schema is unchanged.
The raw-document file and both report types are plain files with documented shapes, not typed
Python models — consistent with this feature being a set of standalone scripts, not a change to
either existing app's own runtime code.
