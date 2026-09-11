# Right-Panel Field Manifests (Component 4.3), per event type/subtype

Display rules, per field: **ALWAYS** (shown even if empty/null/None), **IF-EXISTS** (shown only
when non-empty/non-null), or **NEVER** (not shown at all, regardless of value). Every field
needs a Hebrew display label. Internal/bookkeeping fields (`event_id`, `agreement_id`,
`component_id`, `session_id`, `message_id`, `captured_at`, `schema_version`) are never shown in
the detail panel at all — not even as NEVER-labeled rows, simply absent from the manifest
entirely.

## Common fields (every event type, ALWAYS shown)

| Field | Hebrew label |
|---|---|
| `event_datetime` | תאריך אירוע |
| `source_type` | סוג אירוע |
| `event_subtype` | תת-סוג |
| `client_name` | שם לקוח |
| `description` | תיאור |
| `amount` | סכום |
| `txn_date` | תאריך תנועה |

## הסכם (Agreement)

| Field | Hebrew label | Rule |
|---|---|---|
| `component_label` | תווית רכיב | IF-EXISTS |
| `trigger_condition` | תנאי הפעלה | IF-EXISTS |
| `percent` | אחוז | IF-EXISTS |
| `percent_base` | בסיס אחוז | IF-EXISTS |
| `hours` | שעות | IF-EXISTS |
| `hourly_rate` | תעריף שעתי | IF-EXISTS |
| `split_partner` | שותף לפיצול | IF-EXISTS |
| `split_percent` | אחוז פיצול | IF-EXISTS |
| `vat_status` | סטטוס מע"מ | IF-EXISTS |
| `payer_name` | שם משלם | IF-EXISTS |
| `reference` | אסמכתא | **ALWAYS if `event_subtype != "יצירה"`; otherwise IF-EXISTS** |
| `reference_hint` | רמז אסמכתא | **ALWAYS if `event_subtype != "יצירה"`; otherwise IF-EXISTS** |

## בנק (Bank deposit)

| Field | Hebrew label | Rule |
|---|---|---|
| `bank_number` | מספר בנק | **ALWAYS if `event_subtype == "הפקדה"`; otherwise IF-EXISTS** |
| `bank_branch` | מספר סניף | **ALWAYS if `event_subtype == "הפקדה"`; otherwise IF-EXISTS** |
| `bank_account` | מספר חשבון | **ALWAYS if `event_subtype == "הפקדה"`; otherwise IF-EXISTS** |
| `vat_status` | סטטוס מע"מ | **ALWAYS if `event_subtype == "הפקדה"`; otherwise IF-EXISTS** |
| `payer_name` | שם משלם | IF-EXISTS |
| `split_partner` | שותף לפיצול | **NEVER** |
| `split_percent` | אחוז פיצול | **NEVER** |

## חשבונית (Accounting document)

Known `event_subtype` labels and their Morning numeric type (for reference only — the numeric
code is not a stored field, matching is by label):
- `320` = "חשבונית מס קבלה"
- `330` = "חשבונית זיכוי"
- `400` = "קבלה"
- `305` = "חשבונית מס"
- `300` = "חשבון עיסקה"

| Field | Hebrew label | Rule |
|---|---|---|
| `accounting_document_display_number` | מספר מסמך | **ALWAYS** |
| `accounting_document_status_label` | סטטוס | **ALWAYS** |
| `vat_status` | סטטוס מע"מ | **ALWAYS** |
| `accounting_document_status` | — | **NEVER** |
| `accounting_document_status_code` | — | **NEVER** |
| `accounting_document_payment_method` | אמצעי תשלום | IF-EXISTS |
| `bank_number` | מספר בנק | **ALWAYS, but only when `event_subtype` is "חשבונית מס קבלה" (320) or "קבלה" (400) AND `accounting_document_payment_method == "העברה בנקאית"`; otherwise not part of this type's manifest at all** |
| `bank_branch` | מספר סניף | same condition as `bank_number` |
| `bank_account` | מספר חשבון | same condition as `bank_number` |
| `reference` | אסמכתא | **ALWAYS if `event_subtype == "חשבונית זיכוי"` (330); otherwise IF-EXISTS** |
| `reference_hint` | רמז אסמכתא | **ALWAYS if `event_subtype == "חשבונית זיכוי"` (330); otherwise IF-EXISTS** |

`component_label`/`trigger_condition`/`percent`/`percent_base`/`hours`/`hourly_rate`/
`split_partner`/`split_percent` are agreement-only — not part of the חשבונית manifest at all
(they will always be null/absent on a real accounting-document record regardless).

## Unknown/unsupported source_type (defensive, 2026-09-05)

If a record ever has a `source_type` outside `הסכם`/`בנק`/`חשבונית` (shouldn't happen today),
the right panel shows an explicit **"unrecognized event type" / unsupported message** instead
of any fields — makes the gap loudly visible rather than silently degrading to a generic view.

## Confirmed (2026-09-05)

When the bank-transfer condition does not hold (wrong subtype, or payment method isn't
"העברה בנקאית"), `bank_number`/`bank_branch`/`bank_account` are **completely absent** from the
manifest for that record — not IF-EXISTS, not shown under any circumstance. This is now locked
in, not an open item.
