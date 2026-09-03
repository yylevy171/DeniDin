# `ledger_069/` — Feature 069 acceptance fixtures + ground-truth manifests

**Feature**: 069-mandatory-client-resolution-before-ledger-event
**Contract**: [`contracts/payload-fidelity-manifest.md`](../../../../../specs/in-progress/069-mandatory-client-resolution-before-ledger-event/contracts/payload-fidelity-manifest.md) (C9)
**Requirements**: FR-069-005, FR-069-022, SC-004

Every Feature 069 acceptance scenario that ends in a persisted `LedgerEvent` must prove
**bidirectionally** that the resolution detour lost nothing:

1. **No silent drop** — every field present in the source message/image/document appears in
   the persisted event.
2. **No hallucination** — every non-null, non-provenance field on the persisted event traces
   back to the source (or to the resolved Morning client name).

## File convention

Each `הסכם` / `בנק` fixture ships a committed sibling manifest:

```
<name>.<ext>            the source artifact (.txt | .png | .docx)
<name>.manifest.json    its ground-truth manifest
```

**Authored 2026-09-04** (Phase 11), alongside the shared helper
`tests/billed/_ledger_069_acceptance.py` (`assert_event_matches_manifest`,
`assert_event_matches_manifest_two_hop`). Status:

| Fixture | Manifest | Source artifact | Notes |
|---|---|---|---|
| `agreement_new_client` | ✅ | ✅ `.txt` | US4 + US8 store-anyway |
| `agreement_ambiguous` | ✅ | ✅ `.txt` | US5 — test seeds the 2 partial-match clients |
| `agreement_doc_multi` | ✅ | ✅ `.docx` (`build_agreement_doc_multi.py`) | US10 |
| `agreement_photo_multi` | ✅ | ↔ reuses `media/ledger_events/agreement_idan_shabtai.jpg` | US9 |
| `deposit_exact_match` | ✅ | ↔ reuses `media/ledger_events/Bank-test-image.jpg` | US7d |
| `deposit_zero_matches` | ✅ | ↔ reuses `media/ledger_events/bank_deposit_kehilat_tzair.jpg` | US7a |
| `deposit_one_partial` | ✅ | ↔ reuses `media/ledger_events/bank_transfer_grinfeld.jpg` (payer גרינפלד אורלי, 800 ₪, 23/08/2026) | US7b — test seeds 1 non-exact partial |
| `deposit_two_plus` | ✅ | ↔ reuses `media/ledger_events/bank_transfer_grinfeld.jpg` | US7c — test seeds 2 partials; shares the image with US7b (candidate count not asserted) |

Manifests key against the **English snake_case** persisted-`record` field names (below); the
helper normalises `"4000"`↔`4000` and `DD/MM/YYYY`↔`YYYY-MM-DD`, so a manifest may state
either form.

Planned fixture set (per C9):

| Fixture | Ext | Tier | Story |
|---|---|---|---|
| `agreement_new_client` | `.txt` | billed | US4 (+ store-anyway variant US8) |
| `agreement_ambiguous` | `.txt` | billed | US5 (5a/5b) |
| `agreement_doc_multi` | `.docx` | billed | US10 |
| `agreement_photo_multi` | `.png` | expensive | US9 |
| `deposit_zero_matches` | `.png` | expensive | US7a |
| `deposit_one_partial` | `.png` | expensive | US7b |
| `deposit_two_plus` | `.png` | expensive | US7c |
| `deposit_exact_match` | `.png` | expensive | US7d (exact Morning match — no question, no new client) |

## Manifest shape

```json
{
  "source_kind": "image" | "text" | "document",
  "expected_event": {
    "source_type": "בנק",
    "event_subtype": "הפקדה",
    "amount": "6200",
    "txn_date": "2026-08-14",
    "bank_number": "12",
    "bank_branch": "645",
    "bank_account": "418302",
    "reference": "88213347",
    "payer_name": "רונית בר"
  },
  "client_resolution": {
    "scenario": "exact_match | one_partial_then_new | two_plus_then_pick | new_client | store_anyway",
    "morning_name_after_resolution": "רונית בר-כוכבא",
    "expects_marker_in_description": false
  }
}
```

For a `הסכם` fixture (text, photo, or `docx`), `expected_event` also lists **every fee
component as its own entry** under a `components` list, each
`{kind: "fixed" | "percent", value, description}` — `agreement_photo_multi` and
`agreement_doc_multi` each carry a fixed retainer + a success percentage + a per-hearing
fee at minimum, so drop-detection is not weak.

## Persisted `LedgerEvent` field names — pinned

Manifests key against the **English snake_case** names written by
`src/managers/ledger_event_manager.py` into its persisted `record` dict (currently
`ledger_event_manager.py` ~lines 1079–1145). **Never** key a manifest against a Hebrew
stash label or the `capture_ledger_event` tool-argument name if it differs.

`schema_version` stays **2** for this feature — no `LedgerEvent` field is added, and **no
test asserts `schema_version`'s value** (CLAUDE.md — ledger schema is human-only).

### Fields a Feature 069 manifest asserts on (`expected_event`)

| Persisted key | Notes |
|---|---|
| `source_type` | `"בנק"` \| `"הסכם"` (Feature 069 never touches `"חשבונית"`) |
| `event_subtype` | e.g. `"יצירה"` (`הסכם`), `"הפקדה"` (`בנק`) — value as the model/extractor emits it |
| `client_name` | the **exact resolved Morning name** (checked separately via `client_resolution.morning_name_after_resolution`); for `store_anyway`, the operator-stated name instead |
| `payer_name` | `הסכם`-only; forced `None` for `בנק` / `חשבונית`. For `בנק`, if `client_name` is empty but `payer_name` is given, the manager rescues `payer_name` into `client_name` |
| `description` | free text; for `store_anyway` must contain the marker phrase `[לקוח לא אומת במורנינג]`, otherwise must **not** contain it |
| `amount` | stored as string |
| `reference` | |
| `agreement_id` | where the fixture supplies one |
| `component_id`, `component_label` | per-component (`הסכם`); forced `None` for `בנק` |
| `trigger_condition` | `הסכם`-only; `None` for `בנק` |
| `percent`, `percent_base` | per-component (`הסכם`) |
| `hours`, `hourly_rate` | per-component (`הסכם`) |
| `txn_date` | hours-worked date (`הסכם`) or transaction date (`בנק`) |
| `vat_status` | unconditionally `"כולל"` for `בנק` |
| `bank_number`, `bank_branch`, `bank_account` | **the `בנק` banking triplet — these exact keys.** Populated only for `source_type in ("בנק", "חשבונית")`, else forced `None`. A manifest must never use a Hebrew label (`בנק`, `סניף`, `חשבון`) for these. |

### Provenance / bookkeeping fields — never asserted by a manifest

`event_id`, `event_datetime`, `captured_at`, `session_id`, `message_id`, `schema_version`,
`reference_hint` (the C9 `PROVENANCE_IGNORE` set). The backward "no hallucination" check
skips these; `client_name` and `description` have their own dedicated checks.

### `בנק`-only forced values (assert these hold, don't let a manifest contradict them)

- `vat_status` == `"כולל"` always.
- `payer_name`, `percent`, `percent_base`, `hours`, `hourly_rate`, `trigger_condition`,
  `component_label` → `None`.
- `bank_number` / `bank_branch` / `bank_account` → populated from the slip.
