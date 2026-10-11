# Proposal: Full Morning Document Capture into the Ledger

**Feature**: 025-morning-sourced-ledger-events · **Date**: 2026-08-23 · **Status**: RESOLVED and IMPLEMENTED (Phase 9a, 2026-08-23). Every §5 decision was taken
with the user — see `spec.md`'s round-6 Clarifications for the outcomes and for the two
implementation findings that changed the design. `tasks.md` Phase 9 is the live task list.

**Goal (user, 2026-08-23)**: *"the sweep captures as much as possible into the ledger so that
future queries are done against the ledger and not the morning mcp."* The ledger becomes a
faithful local mirror of each Morning document, not a summary of it.

All findings below come from **real calls against the live Morning dev sandbox** (2026-08-22/23),
one representative document of each of the 5 types the sweep actually encountered, plus Morning's
own authoritative lookup endpoints. No assumed field semantics — per CONSTITUTION.md's "NO
UNVERIFIED THIRD-PARTY ASSUMPTIONS".

---

## 1. What each document type actually carries

Meaningful (non-empty) fields per type, measured:

| Field | 300 חשבון עסקה | 305 חשבונית מס | 320 חשבונית מס/קבלה | 330 חשבונית זיכוי | 400 קבלה |
|---|---|---|---|---|---|
| `income[]` (line items) | ✅ | ✅ | ✅ | ✅ | ❌ **none** |
| `payment[]` (how paid) | ❌ | ❌ | ✅ | ❌ | ✅ |
| `linkedDocuments[]` | ❌ | ❌ | ❌ | ✅ | ❌ |
| `vat`/`vatRate` (real VAT) | ✅ 7.92 / 0.18 | 0 | 0 | 0 | — |
| `amountOpened` (still owed) | 0 | **62** | 0 | 0 | 0 |
| `amountExcludeVat` | ✅ | ✅ | ✅ | ✅ | — |
| `cancelType` | — | — | **330** | — | — |
| `status` | 2 | 0 | 1 | 1 | 0 |

**The user's point confirmed**: this is not uniform. A 400 has no line items at all; only 320/400
carry payment details; only 330 carried a real document linkage; only the 300 in this sample had
real VAT.

### Authoritative code tables (fetched live, not guessed)

- **`GET /documents/types`** — 15 types exist. The sweep saw 5. Also real: `10 הצעת מחיר`,
  `20 חשבון/אישור תשלום`, `100 הזמנה`, `200 תעודת משלוח`, `210 תעודת החזרה`, `405 קבלה על תרומה`,
  `410 ביטול תרומה`, `500 הזמנת רכש`, `600 קבלת פיקדון`, `610 משיכת פיקדון`. **`models.py`'s
  `_DOCUMENT_TYPE_NAMES` only lists 5** — an unmapped type renders as a bare number.
- **`GET /documents/statuses`** — `0 מסמך פתוח`, `1 מסמך סגור`, `2 סומן ידנית כסגור`,
  `3 מסמך מבטל`, `4 מסמך שבוטל`.
- **`GET /payments/types`** — `0 ניכוי במקור`, `1 מזומן`, `2 צ'ק`, `3 כרטיס אשראי`,
  `4 העברה בנקאית`, `5 פייפאל`, `10 אפליקציית תשלום`, `11 אחר`.

### ⚠️ Two semantic traps found

1. **`ref[]` is NOT a document reference.** A 305 carried `ref: [200, 300, 400]` and a 400 carried
   `ref: [300, 305]` — these are **document *type* codes** (which follow-on types are permitted),
   not document numbers. Mapping `ref[]` as linkage would silently produce nonsense. The only real
   linkage is `linkedDocuments[]` (carries a real `number` + `id`), and it exists **only** on the
   single-document GET, never on `/documents/search`.
2. **Morning's `status` is open/closed, not paid/unpaid.** `models.py` currently maps
   `1 (מסמך סגור) → "paid"` and `2 (סומן ידנית כסגור) → "paid"`. For a 300 (proforma), "closed"
   plausibly means *converted to an invoice*, not *paid*. Cancellation (3/4) **is** mapped
   correctly. Recommend recording Morning's own literal status alongside the derived
   paid/unpaid interpretation, so the ledger never loses the real value.

---

## 2. What the ledger captures today vs. what's available

Today a `source_type="חשבונית"` event captures **7** real values: display number, type, status,
creation timestamp, client name, description, amount. Everything else on the record is `null`.

**Not captured, though Morning returns it:**

| Category | Available | Why it matters for ledger-only queries |
|---|---|---|
| Money breakdown | `amountExcludeVat`, `vat`, `vatRate`, `vatType`, `amountOpened`, `currency` | "How much VAT did I collect?", "What's still owed?" — `amountOpened` is the open balance |
| Issue date | `documentDate` | The legally meaningful accounting date. **We capture creation time but not this.** |
| Payment | `payment[].name/type/date/amount` | "How was I paid?" |
| Bank | `payment[].bankName/bankBranch/bankAccount` | **Structured only in `get_invoice_details`** — `/documents/search` has them merely concatenated into a Hebrew string |
| Linkage | `linkedDocuments[].number/type/id`, `cancelType` | Which invoice a credit note cancels — the double-counting question |
| Line items | `income[]` (description, quantity, price, vatRate, amount) | Per-line detail; a document may have many |
| Provenance | `userName`, `data.generatedBy`, Morning `id` | Who issued it; drill-back to the source document |
| Client | `client.id`, `client.phone`, `client.emails` | Grouping/matching beyond a display name |

---

## 3. Proposed changes

### 3a. `apps/morning-mcp-app` (required either way)

1. **Fix `Invoice.payments` — pre-existing bug, user approved fixing it here.** Raw key is
   `payment` (singular); model field is `payments` (plural); **no mapping exists**, so it is
   *always* `[]` for every caller. Proven with real data. `Payment` also requires `invoice_id`,
   absent from the raw object, so it would fail validation even if mapped. Consequence:
   `get_invoice_details`' "תשלומים:" block is **dead code today** — it has never rendered for
   anyone, including real godfather conversations. Fix: map `payment` → `payments`, make
   `invoice_id` optional, add `bank_name`/`bank_branch`/`bank_account`/`payment_type`/`status`.
2. **Complete `_DOCUMENT_TYPE_NAMES`** with all 15 real types from `GET /documents/types`.
3. **Expose the new fields in tool output** (both list and details, same shared block that already
   fixed the creation timestamp).

### 3b. Transport: how the data reaches the ledger — **the key decision**

Every field added is a field the model must transcribe correctly. At ~7 fields it works (18/18
proven). At ~25 fields per document, prose transcription becomes the weak link.

- **Option A — labeled Hebrew lines (status quo, extended).** Cheap; consistent with today. Risk
  grows with field count; already observed the model inventing `00:00` when a value was missing.
- **Option B — MCP returns a compact machine-readable JSON block per document**, model transcribes
  it verbatim into one `raw_document` tool argument; **`LedgerEventManager` parses and maps it in
  code**. Model does copying, not interpretation. Code owns every derived value.
  **Recommended** — it matches this codebase's existing "never trust the AI's own math/scoping"
  discipline (`_normalize_amount`, `vat_status` forcing, `payer_name` rescue).
- **Option C — sweep bypasses the model for data**, using it only to enumerate ids. Cleanest in
  principle, but denidin-app has no direct MCP client (rejected earlier as new infrastructure).

### 3c. Ledger schema (`schema_version` 2 → 3)

Proposed new fields, `accounting_document_`-prefixed per the round-3 naming convention, non-null
only for `source_type="חשבונית"`:

```
accounting_document_issue_date        <- documentDate  (the accounting date)
accounting_document_amount_excl_vat   <- amountExcludeVat
accounting_document_vat_amount        <- vat
accounting_document_vat_rate          <- vatRate
accounting_document_amount_open       <- amountOpened   (still owed)
accounting_document_currency          <- currency
accounting_document_status_code       <- status (raw int) + Morning's own literal label
accounting_document_payment_method    <- payment[].name  (העברה בנקאית / מזומן / ...)
accounting_document_payment_date      <- payment[].date
accounting_document_linked_number     <- linkedDocuments[].number
accounting_document_linked_type       <- linkedDocuments[].type
accounting_document_issued_by         <- userName / data.generatedBy
accounting_document_morning_id        <- id  (provenance/drill-back only, never an identity field)
```

**Reused existing fields** (no new field needed): `bank_number`/`bank_branch`/`bank_account` ←
`payment[].bankName/bankBranch/bankAccount` — **requires lifting the current `בנק`-only
force-null** (`ledger_event_manager.py:596-603`); `vat_status` — **derive in code** from
`vat`/`amountExcludeVat`/`amount` rather than asking the model; `due_date` ← `dueDate`;
`reference`/`reference_hint` ← `linkedDocuments` (the deferred credit-note linkage, round 5).

### 3d. Line items (`income[]`) — open question

The ledger already has a **multi-component design** (`components[]`, one persisted event per
component, sharing an `agreement_id`) built for exactly this shape. Mapping `income[]` → one
component per line item would use it as intended, but changes the current 1-document-1-event
model and would need new per-component fields (`quantity`, `unit_price`). A 400 has no `income[]`
at all. **Needs a decision** — see below.

---

## 4. Consequences to accept

- **`get_invoice_details` comes back per document.** Structured bank fields and `linkedDocuments`
  exist *only* there. That reintroduces N+1 calls — the pattern that failed before. **Critically:
  it failed because `get_invoice_details`' own tool description scopes it to status-change flows
  and outranked the prompt** (round 5). This must be fixed at the tool-description level, not by
  prompt wording, or the same failure repeats.
- **Cost/latency**: 18 documents → 19 MCP calls per sweep instead of 1.
- **`schema_version` 2 → 3**; existing v2 events are not migrated (per the established
  never-retro-apply rule).
- **Scope**: this is materially larger than Feature 025's current spec — arguably its own feature.

---

## 5. Decisions needed

1. **Transport** — Option A (labeled lines), **B (JSON blob + code-side mapping, recommended)**,
   or C?
2. **Line items** — map `income[]` to `components[]` (one event per line), or keep one event per
   document with line details summarized?
3. **Field scope** — take the full §3c list, or a subset? (`amountOpened`, `documentDate`,
   payment method, and bank details look highest-value for real queries.)
4. **Feature boundary** — extend Feature 025, or land the current working sweep first and do this
   as Feature 026?
