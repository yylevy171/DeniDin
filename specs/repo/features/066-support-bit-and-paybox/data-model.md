# Data model: Feature 066 (LedgerEvent deposit shape)

| Field | Before | After |
|---|---|---|
| `source_type` | `בנק` for bank deposits | `הפקדה` for every incoming-funds event |
| `event_subtype` | `הפקדה` (a filler) | method: `בנק`, `ביט`, `פייבוקס`, `צ׳ק`, `מזומן` |
| `check_number` | - | new, optional; cheques only |
| `bank_number/branch/account` | bank only | bank and cheque |
| `txn_date` | optional | the evidence's date; null only for cash with none |
| `vat_status` | forced `כולל` for בנק | forced `כולל` for every `הפקדה` |
| `schema_version` | 2 | new number supplied by the human |
| `event_id` | letter `B` for בנק | letter `B` for `הפקדה` (unchanged for old events; filenames never change) |

Migration invariant: for every old `בנק` event only `source_type`, `event_subtype` (and `schema_version`) change; every other field is byte-identical.
