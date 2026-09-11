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
| `deposit_zero_matches` | ✅ | ↔ reuses `media/ledger_events/Deposit_Kehunai.jpg` | US7a — payer name is a compound/unclear joint holder, deliberately not the client (see `resolution.mode: new_client_distinct_payer`) |
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

## Manifest shape (normalised 2026-09-10 — ONE schema for every manifest)

A test's **name is the only key**: `Test X → load_manifest("X")`. Once loaded, the
whole seed / drive / assert mechanism is common to every scenario.

```json
{
  "source_kind": "text" | "image" | "document" | "morning_create",
  "story": "one-line human description",
  "source_file": "agreement_new_client.txt",          // optional; the source artifact
  "seed_clients": [                                     // optional; seed_scenario() seeds each
    {"id_prefix": "F069_US1", "name": "…", "phone": "…", "ensure_exists": true}
  ],
  "resolution": { "mode": "…", … },                    // THE one scenario-specific knob
  "files": "single" | "per_component",
  "shared_fields":  { "<persisted_field>": <rule>, … },// identical on every persisted file
  "components":     [ { "<persisted_field>": <rule>, … }, … ]   // per_component only
}
```

`shared_fields` + the union of `components` keys must classify **every**
`LEDGER_EVENT_FIELDS` entry exactly once. Each `<rule>` is one of
`{"tested": <v>}` (`"$client"` = the resolved client name), `{"generated": "<kind>"}`,
`{"null": true}`, `{"free_text": true}`.

### `resolution.mode` — drives the answer bank (in `drive_capture`) and `$client` (in the asserter)

| mode | params | flow the driver answers | `$client` resolves to |
|---|---|---|---|
| `exact` | `name` | none — asserts NO detour happened | `name` |
| `pick_existing` | `stated`, `resolves_to` | "yes, the existing client `resolves_to`" | `resolves_to` |
| `new_client` | `name`, `email`, `phone` | supplies full name + email + phone → `add_client` | `name` |
| `new_client_distinct_payer` | `name`, `email`, `phone` | rejects the source's own payer name as the client ("that's only who paid"), states an unrelated new client → `add_client`; `payer_name` is asserted non-null (verbatim from the source) instead of null | `name` |
| `store_as_stated` | `name` | "store it as-stated, don't verify in Morning" | `name` |
| `none` | `name` | no client detour (only e.g. US2's approval gate) | `name` |

`name` / `email` may be the sentinel `"$unique"` / `"$email"` — bound **once per
test** to a freshly-minted real client name / ASCII email (`load_manifest`
memoises; the autouse fixture clears it). One `$unique` value is shared by
`resolution.*` and every `seed_clients` entry.

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
