# Bugfix 071: Morning Documents Created with VAT = 0 Instead of VAT Included

**Status**: Done (2026-10-06) — fix merged via PR #TBD; verified by 27/27 billed/expensive tests on the Feature 063 backbone (§7). Not yet released or deployed (human decision). Production remediation of the already-issued documents (§3, §5) is a separate accounting task.
**Priority**: P0
**Severity**: P0 / Critical (Compliance & Tax Under-reporting)
**Branch**: `bugfix/071-morning-vat-zero-defect`
**Components**: `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (`_build_combo_document_payload`, `create_combo_document`, `_build_create_invoice_payload`)
**Found via**: Operational audit requested by CEO (2026-10-05)

---

## 1. Problem Statement

Morning documents that were intended to be issued with VAT included (`vat_included = True`) have been generated in production with `VAT = 0%` (exempt / פטור ממע"מ).

In an official Israeli tax invoice/receipt (`חשבונית מס / קבלה` - Type 320), issuing legal services with zero VAT constitutes a severe tax reporting discrepancy. Corporate clients cannot deduct input tax, and the firm’s periodic VAT returns under-report collected output tax.

### Quantitative Scope in Production (01/07/2026 – 05/10/2026)
A live audit of the production Morning Green-Invoice API across all combo tax invoices (Type 320) revealed:
* **Total Type 320 Documents Issued:** 107 documents
* **Defective (Issued with VAT = 0%):** **37 documents** (100% of DeniDin automated combo creations)
* **Total Gross Billed Volume:** **₪280,918.00**
* **Under-reported VAT Exposure (18% inclusive):** **₪42,851.92**
* **Clean Invoices with Full VAT (≥ 05/08/2026):** Exactly 15 documents (₪102,578.10 gross), all created manually by staff directly in the Morning UI.
* **Pre-Go-Live Baseline (< 05/08/2026):** Exactly 55 documents, 100% manual, zero zero-VAT defects.

---

## 2. Root Cause Analysis

> **Superseded (2026-10-05).** The `vatRate: 0` analysis below, as originally filed, was
> disproven by the VAT matrix (§2a): `vatRate` is ignored by Morning in every probed shape.
> Kept for history. The approved root cause is §2a.


In `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`:

```python
def _build_combo_document_payload(..., vat_included: bool, ...):
    vat_type = 1 if vat_included else 0
    payload = {
        "type": 320,
        "vatType": vat_type,
        ...,
        "income": [
            {
                "price": amount,
                "vatRate": 0,       # <-- ROOT CAUSE: Explicitly sending vatRate: 0
                "vatType": vat_type # <-- ROOT CAUSE: Passing vatType: 1 at line item level
            }
        ]
    }
```

### Morning API Tax Engine Mechanics:
Comparing a valid document (#112346) against a defective document (#112347) in the live production payload:
1. **Valid Document:**
   * Document-level: `vatType: 0`, `vatRate: 0.18`, `vat: 228.81`.
   * Income line-level: `vatType: 1` (Taxable standard), `vatRate: 0.18`, `vat: 228.81`.
2. **Defective Document:**
   * Document-level: `vatType: 1`, `vatRate: 0`, `vat: 0`.
   * Income line-level: `vatType: 2` (Exempt / פטור ממע"מ), `vatRate: 0`, `vat: 0`.

When DeniDin explicitly passed `"vatRate": 0` in the `income` dictionary, Morning treated the line as **tax-exempt income (`vatType: 2`)** and overrode the document calculation to zero VAT.

---

## 2a. Approved Root Cause (human-approved 2026-10-05)

Source: Morning's official OpenAPI spec (`developers.morning.co/docs/openapi.bundled.json`,
v2.0.0). `vatType` is **two different enums** sharing one field name:

- `DocumentVatType` (`CreateDocumentRequest.vatType`): `0` Default (based on business type),
  `1` **Exempt (VAT-free)**, `2` Mixed.
- `ItemVatType` (`IncomeRowRequest.vatType`): `0` Default (VAT added based on business type),
  `1` **Included (VAT included in price)**, `2` Exempt.

Every payload builder in `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` computes ONE value
(`vat_type = 1 if vat_included else 0`) and writes it to BOTH levels. "VAT included" therefore
sends document-level `1` = Exempt; Morning exempts the whole document (rewrites the row to
`vatType: 2`, `vat: 0`). "VAT excluded" sends `0`/`0`, which is correct. Affected builders: 305
(`_build_create_invoice_payload`), 300 (`_build_transaction_account_payload`), 320
(`_build_combo_document_core_payload`, fresh and closing-a-300), 330 (`_build_cancellation_payload`,
which mirrors the original's DOCUMENT-level `vatType` onto the ROW and falls back to `1`).

Why it shipped: the code was never checked against Morning's published enums. bugfix-028's live
probe (2026-08-09) observed "11 stays 11" with `vatType: 1` and recorded it as "price includes
VAT" (`tools.py:380-383`) - it was Morning's exemption. Unit tests then pinned the conflated payload.

Separate defect found alongside (bugfix-028 A2 implemented only halfway): `create_invoice` (305) and
`create_combo_document_as_reference` still default `vat_included=True` in their MCP schema, so a VAT
treatment the model never established silently becomes "included" - and, via this root cause, exempt.

Reproduction: `apps/morning-mcp-app/tests/integration/test_morning_sandbox_vat_matrix.py` (17 cells,
real MCP server + real sandbox): 10 failed / 7 passed on current code.

## 2b. Sandbox Research (2026-10-05)

Raw payloads to the sandbox, each read back via `GET /documents/{id}`. Business settings
(`GET /documents/info?type=305`): `vatRate: 0.18`, `documentVatType: 0`, `rowVatType: 0`,
`mixedVatEnabled: false`.

| Probe | Sent (doc / row / vatRate / price / payment) | Stored (vat / amount / net) |
|---|---|---|
| 305, 300, 320 VAT included | 0 / 1 / omitted, 0.18 or 0 / 118 / (320: 118) | 18 / 118 / 100 ✅ all 9 |
| 305, 300, 320 VAT excluded | 0 / 0 / omitted or 0 / 100 / (320: 118) | 18 / 118 / 100 ✅ all 6 |
| 330 full, against correct 305 (incl. or excl.) | 0 / 1 / omitted / 118 | 18 / 118 / 100 ✅ |
| 330 partial, against correct 305 | 0 / 1 / omitted / 59 | 9 / 59 / 50 ✅ |
| 330 as the CURRENT builder would send it against a correct original (mirror doc 0 onto row) | 0 / 0 / 0 / 118 | **21.24 / 139.24 / 118 ❌ over-credits 18%** |
| 320 closing a 300 (incl. or excl.), price = the 300's stored total | 0 / 1 / omitted / 118 / 118 | 18 / 118 / 100 ✅ |

Findings: (1) document-level `vatType: 0` + row-level `vatType` 1/0 is correct for every taxable
type; (2) row `vatRate` has no effect (omitted, `0.18` and `0` all stored 18%) - Morning applies the
business rate; (3) a 320 with VAT excluded is accepted when the payment line carries the gross; (4) a
330 must NOT mirror the original's document-level `vatType` onto its row - against a correctly-issued
original that over-credits by 18%.

## 2c. Approved User-Level VAT Matrix (human-approved 2026-10-05)

From the user's perspective there is one VAT: the VAT inside the amount paid / to be paid. X = what the
user said.

| Document | User says "VAT included" | User says "VAT not included" | User says nothing |
|---|---|---|---|
| 305 tax invoice | total = X (VAT inside) | total = X + VAT | refuse - ask |
| 300 transaction account | total = X (VAT inside) | total = X + VAT | refuse - ask |
| 320 standalone | ignored (VAT inside X) | conflict - refuse, ask | total paid = X, VAT inside |
| 320 closing a 300 | ignored | conflict - refuse, ask | amount paid (300's total or partial), VAT inside |
| 400 standalone | ignored | conflict - refuse, ask | receipt = X, no VAT on the receipt |
| 400 against a 305 | ignored | conflict - refuse, ask | 305's total or the partial paid |
| 330 against a taxable original (305/320) | ignored | conflict - refuse, ask | mirrors the original (VAT inside) |
| 330 against an exempt original | conflict - refuse, ask | conflict - refuse, ask | mirrors the original (no VAT) |

A 300 is not a tax document - its total always includes VAT whichever way it was created (100 incl. -> 100;
100 excl. -> 118); the 320 that closes it is the tax document, and the amount paid always includes VAT.

Refusal = MCP `isError` via the existing error boundary (`errors.py`), nothing created in Morning, any
referenced original untouched. Successful results stay on the existing JSON-only contract (2026-09-04) -
no new prose.

Sandbox-confirmed payload translation (§2b + 2026-10-05 gap probes G1-G4): document-level `vatType` 0
(Default) everywhere except a 330 against an exempt original (mirrors the original's 1); row `vatType` 1 for
every VAT-inside amount, 0 only for an explicit "not included" on 305/300; no `vatRate` sent; a 320's payment
line = the amount paid.

### Out of scope (human decision, 2026-10-05): amounts relative to the original

Sandbox probe (2026-10-05) found Morning itself enforces NO amount limits on referencing documents: a
receipt of 150 against a 100 tax invoice, a credit note of 150 against 100 (original `amountOpened` -50),
a 320 of 150 closing a 100 transaction account, cumulative partials exceeding the total, and a "full"
close after a partial (our tools use the original's TOTAL, not its open balance `amountOpened`, so 40 +
100 = 140 paid against 100) were all accepted. This is a separate defect (no amount validation against the
original's open balance) and is NOT addressed by bugfix-071; the VAT matrix varies VAT only, at full
amounts, and existing amount tests are left as they are and are not used as evidence here.

## 3. Complete List of Impacted Documents

### A. Type 320 Invoices Issued with VAT = 0 (37 Documents)

| # | Doc # | Date | Client | Gross (₪) | Expected VAT (18%) | Description |
|:---:|:---:|:---:|:---|:---:|:---:|:---|
| 1 | 112347 | 2026-10-05 | עדו דניאל | ₪10,000.00 | ₪1,525.42 | שכר טרחה עבור כתב הגנה בתביעת לשון הרע |
| 2 | 112345 | 2026-09-28 | דודו טאטי | ₪3,000.00 | ₪457.63 | שכר טרחה עבור הסכם פשרה |
| 3 | 112344 | 2026-09-25 | רחמים אורי אהרון | ₪5,000.00 | ₪762.71 | שכר טירחה עבור עריכת הסכם |
| 4 | 112343 | 2026-09-25 | שי עמנואלי | ₪8,000.00 | ₪1,220.34 | שכר טרחה עבור יצוג משפטי |
| 5 | 112342 | 2026-09-24 | הסתדרות כללית חדשה | ₪47,200.00 | ₪7,200.00 | שכר טרחה חודש אוגוסט 2026 |
| 6 | 112340 | 2026-09-23 | דודו טאטי | ₪3,000.00 | ₪457.63 | שכר טרחה עבור הסכם פשרה |
| 7 | 112339 | 2026-09-18 | יניב גרין | ₪5,000.00 | ₪762.71 | שכר טרחה עבור טיפול משפטי |
| 8 | 112338 | 2026-09-17 | כמיל משג׳ראוי | ₪4,000.00 | ₪610.17 | שכר טרחה |
| 9 | 112336 | 2026-09-16 | תומר ענבר | ₪8,500.00 | ₪1,296.61 | שכר טרחה |
| 10 | 112335 | 2026-09-16 | ארז ברויר | ₪3,000.00 | ₪457.63 | שכר טרחה עבור ייעוץ משפטי |
| 11 | 112334 | 2026-09-16 | ליטל תורגמן | ₪2,500.00 | ₪381.36 | שכר טרחה |
| 12 | 112332 | 2026-09-15 | רבאב חביבאללה | ₪3,000.00 | ₪457.63 | שכר טרחה |
| 13 | 112331 | 2026-09-14 | עו״ד יועז יובל | ₪24,000.00 | ₪3,661.02 | שכר טרחה |
| 14 | 112330 | 2026-09-11 | שי עמנואלי | ₪8,000.00 | ₪1,220.34 | שכר טרחה עבור יצוג משפטי |
| 15 | 112329 | 2026-09-11 | יוגב חבאני | ₪5,000.00 | ₪762.71 | שכר טרחה |
| 16 | 112327 | 2026-09-10 | דודי אדלר | ₪5,000.00 | ₪762.71 | שכר טרחה עבור ייעוץ |
| 17 | 112326 | 2026-09-10 | אחמד עאבד | ₪7,138.00 | ₪1,088.85 | שכר טרחה |
| 18 | 112325 | 2026-09-08 | אתי אסולין | ₪10,000.00 | ₪1,525.42 | שכר טרחה עבור ייצוג משפטי |
| 19 | 112321 | 2026-09-06 | אודי הניס | ₪3,000.00 | ₪457.63 | שכר טרחה |
| 20 | 112320 | 2026-09-04 | שלמה נזרי | ₪3,000.00 | ₪457.63 | שכר טרחה |
| 21 | 112319 | 2026-09-04 | רוני גרינבוים זיו | ₪1,362.00 | ₪207.76 | שכר טרחה |
| 22 | 112318 | 2026-09-01 | ד״ר דוד אדלמן | ₪7,000.00 | ₪1,067.80 | שכר טרחה |
| 23 | 112316 | 2026-08-31 | מור פלימבו | ₪3,750.00 | ₪572.03 | שכר טרחה |
| 24 | 112315 | 2026-08-28 | ל.מ פאות קאולה 2022 בעמ | ₪6,500.00 | ₪991.53 | שכר טרחה עבור טיפול משפטי |
| 25 | 112314 | 2026-08-27 | ל.מ פאות קאולה 2022 בעמ | ₪6,000.00 | ₪915.25 | שכר טרחה עבור טיפול משפטי |
| 26 | 112313 | 2026-08-27 | יעל לוריא | ₪1,500.00 | ₪228.81 | שכר טרחה עבור טיפול משפטי |
| 27 | 112312 | 2026-08-25 | גלית סיטבון | ₪6,500.00 | ₪991.53 | שכר טרחה עבור ייצוג משפטי |
| 28 | 112311 | 2026-08-24 | אורלי גרינפלד | ₪800.00 | ₪122.03 | שכר טרחה עבור ייעוץ |
| 29 | 112310 | 2026-08-23 | גדי רוזן | ₪20,000.00 | ₪3,050.85 | שכר טרחה |
| 30 | 112309 | 2026-08-23 | מקורות | ₪12,272.00 | ₪1,872.00 | שכר טרחה |
| 31 | 112308 | 2026-08-19 | רומן אלטשולר | ₪3,000.00 | ₪457.63 | שכר טרחה |
| 32 | 112307 | 2026-08-19 | רומן ציקל | ₪3,000.00 | ₪457.63 | שכר טרחה |
| 33 | 112306 | 2026-08-19 | ליאור חכם | ₪5,000.00 | ₪762.71 | שכר טרחה עבור ייצוג משפטי |
| 34 | 112305 | 2026-08-17 | שי עמנואלי | ₪20,000.00 | ₪3,050.85 | שכר טרחה עבור ייצוג משפטי |
| 35 | 112303 | 2026-08-11 | אביתר כהן | ₪2,500.00 | ₪381.36 | שכר טרחה עבור ייעוץ משפטי |
| 36 | 112297 | 2026-08-06 | רונית יעקובסון | ₪3,776.00 | ₪576.00 | שכר טרחה עבור ייצוג |
| 37 | 112296 | 2026-08-06 | מתנס שורק | ₪10,620.00 | ₪1,620.00 | שכר טרחה עבור ייצוג משפטי |

---

## 4. Required Engineering Fix

> Superseded by the approved VAT matrix (§2c) and the fix as built (§7). Kept as originally written.

1. In `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`:
   - Adjust `_build_combo_document_payload` and `_build_create_invoice_payload`.
   - When `vat_included=True`, pass the proper taxable VAT parameters required by Morning:
     - Document-level: `vatType: 0` (price includes VAT).
     - Income line: omit explicit `"vatRate": 0` so Morning computes standard VAT, or pass `"vatType": 1` (*Taxable standard* with default rate).
2. Add comprehensive automated integration tests against the Morning sandbox verifying that a created 320 document returns `vat > 0` and `vatRate == 0.18`.

---

## 5. Operations & Accounting Remediation Plan

1. **Accounting Review:** Consult the firm’s CPA to decide between:
   * **Remediation Option A:** Generating cancellation credit notes (`חשבונית זיכוי` 330) for the 37 documents and reissuing proper 320 documents.
   * **Remediation Option B:** Reporting the ₪42,851.92 VAT discrepancy directly as an adjustment on the upcoming periodic VAT return (`דו״ח מע״מ תקופתי`).
2. **Client Communications:** Institutional clients (הסתדרות, מקורות, עיריית רמת השרון) should be re-issued valid tax invoices to allow input VAT recovery.

---

## 6. Addendum (2026-10-05) - sandbox trace evidence; root cause narrowed

Found independently on 2026-10-04 while auditing Feature 063 E2E traces
(`apps/denidin-app/debug_traces/031026/`, Morning **sandbox**, 26 `create_*` calls, 2026-10-03/04).

### 6.1 Every VAT-included document type is affected, not only 305/320

What the model sent vs. what Morning stored (the `create_*` tool result):

| `vat_included` sent | Calls | Document types | Morning stored |
|---|---|---|---|
| `true` | 15 | 305, 300, 320, 320-by-reference | **`vat_rate: 0.0`, `vat_amount: 0`, `amount_excl_vat` = full amount** - 15 of 15 |
| `false` | 4 | 305 | `vat_rate: 0.18`, VAT added on top - correct, 4 of 4 |

Example (`ST12.md`, invoice 52580): `create_invoice {"amount": 16, "vat_included": true, ...}` ->
`{"amount": 16.0, "amount_excl_vat": 16.0, "vat_amount": 0.0, "vat_rate": 0.0}`. Expected 13.56 + 2.44.

The model passed the right flag every time; the defect is entirely in `morning-mcp-app`'s payloads.

### 6.2 `"vatRate": 0` alone does not explain it - the document-level `vatType: 1` does

§2 attributes the defect to the income line's `"vatRate": 0`. The **type-300 builder
(`_build_transaction_account_payload`, `tools.py:357-415`) sends no `vatRate` at all**, yet all four
VAT-included 300s in the traces were stored at 0% too. What every defective payload shares is
`"vatType": 1` at **document** level whenever `vat_included=True` - and §2's own production
comparison shows exactly that: valid #112346 has document `vatType: 0` + line `vatType: 1`;
defective #112347 has document `vatType: 1` (+ Morning rewrote the line to `vatType: 2`, exempt).

Working hypothesis (to verify with a sandbox probe **before** fixing): document-level `vatType`
means 0 = regular / 1 = exempt / 2 = mixed, while line-level `vatType` means 0 = price excludes VAT /
1 = price includes VAT / 2 = exempt. DeniDin reuses one `vat_type` value (1 when included) at **both**
levels, so a VAT-included document is declared exempt. The `vat_included=false` path is correct only
by coincidence (0 means "regular" at document level and "excludes" at line level).

The misreading is recorded in `_build_transaction_account_payload`'s docstring (`tools.py:376-383`):
the 2026-08-09 live probe checked only that "`vatType: 1` stores 11 as 11" - the total - never the
VAT split. That comment must be corrected with the fix.

### 6.3 Every site that needs the fix (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`)

| Builder | Document type(s) | Document-level `vatType` | Line-level `vatType` / `vatRate` |
|---|---|---|---|
| `_build_create_invoice_payload` | 305 | :112 | :130 / `vatRate: 0` :129 |
| `_build_transaction_account_payload` | 300 | :392 | :409 / (none) |
| `_build_combo_document_core_payload` (used by `create_combo_document` and the by-reference closing path) | 320 | :540 | :558 / `vatRate: 0` :557 |
| `_build_cancellation_payload` | 330 credit note | :1073 `original.get("vatType", 1)` | :1092 same / `vatRate: 0` :1091 |

The 330 builder copies the original document's `vatType` and **defaults to 1** - so a credit note
against a correct (VAT-bearing) document can also come out exempt; its mapping needs the same
document/line split. (A credit note cancelling one of the defective 0%-VAT documents should reverse it
exactly as issued - relevant to remediation Option A.)

### 6.4 Section 3.B (type 400 receipts) is a separate question, not this code defect

A receipt (`קבלה`, 400) never carries VAT in Morning by design - VAT belongs on the tax invoice.
The 16 standalone receipts come from Feature 056's standalone-receipt path (deposits / refunds,
`create_receipt` with no linked invoice). Whether those payments also needed a tax invoice is an
accounting decision for the CPA, not something the `vatType` fix changes; keep their ₪2,117.44 out
of the code-defect total and track them separately.

### 6.5 Test gap and required tests

- **Why nothing caught it:** no test asserts the stored VAT split. The billed E2E tests check only
  that `create_*` ran without error and that the reply/approval text says `כולל מע"מ`; the sandbox
  integration tests check totals. The VAT-zero result is visible in every trace and was never asserted.
- **Integration (morning-mcp-app, real sandbox):** one test per builder - 305, 300, 320, 320
  by-reference, 330 against a VAT-bearing 305 - creating 118 ₪ with `vat_included=True` and asserting
  Morning stores `vatRate 0.18`, VAT 18.00, before-VAT 100.00; plus the `vat_included=False` case
  (100 ₪ -> VAT 18.00 on top, total 118.00), unchanged.
- **Billed E2E (denidin-app):** at least one VAT-included creation test should assert the
  `create_*` result's `vat_rate == 0.18` and `vat_amount > 0` (operator sign-off needed - billed test
  change).

### 6.6 Rollout

The fix touches both `morning-mcp-app` (payloads, conflict refusal) and `denidin-app` (prompts and
approval text, §7). It reaches dev/prod only via a new cut release + deploy of both apps (human
decisions, every time); merging alone changes nothing on running containers.

---

## 7. Resolution (2026-10-06)

Implements the approved matrix (§2c). Amounts relative to the original stay out of scope (§2c).

### 7.1 `morning-mcp-app` (`tools.py`, `server.py`, `errors.py`)

- **Payloads:** document-level and row-level `vatType` are now separate values, the root cause (§6.2).
  - Document `vatType` is always 0 (Default). A 330 mirrors its original's document `vatType`.
  - Row `vatType` is 1 (VAT inside) for every VAT-inside amount, and 0 (VAT added) only for an
    explicit "not included" on a 305/300.
  - `vatRate` is never sent.
- **305/300:** `vat_included` is required, with no default.
- **320, 400 and 330:** `vat_included` is optional.
- **Conflicts are refused:** a "not included" that contradicts the document type raises
  `VatConflictError` before anything reaches Morning. That covers a 320 or 400 (money already
  paid), any referencing document, and any VAT statement on a credit note against an exempt
  original. The error surfaces as an MCP `isError`, so nothing is created.
- **Bank details:** `create_receipt` keeps Feature 063's bank fields alongside `vat_included`.

### 7.2 `denidin-app`

- **Backbone prompts** (Feature 063; the flag is on for this work):
  - `cap_invoicing_write.md` has a "VAT — one rule per document type" section.
  - Every document approval must carry two lines, `סוג מסמך: <type>` and `מע״מ: <label>`.
  - The label is one of `כולל מע״מ`, `לא כולל מע״מ` (305/300 only) or `לפי המסמך המקורי`.
  - `cap_approval_with_buttons.md` and `flow_issue_invoice_receipt_combo.md` point to the same
    lines.
- **Legacy path** (flag off): `runtime_constitution.md` follows the same rules, and the code-built
  approval in `ai_handler.py` states the VAT label.

### 7.3 Tests (closing the gap from §6.5)

- **Approvals:** every billed/expensive conversation that reaches a document approval asserts it
  states VAT (`tests/e2e_helpers.py::assert_document_approval_states_vat`).
  - A missing line fails.
  - An unknown label fails.
  - So does "not included" on anything but a 305/300.
- **Stored figures:** created documents are checked against Morning's stored split
  (`assert_stored_vat` / `assert_stored_receipt`), not only the totals.
- **New tests:**
  - `apps/morning-mcp-app/tests/integration/test_morning_sandbox_vat_matrix.py` — the matrix,
    against the real sandbox.
  - `apps/denidin-app/tests/unit/test_ai_handler_approval_vat_label_071.py`.
  - `apps/denidin-app/tests/billed/test_bugfix_071_vat_rules_billed.py` — the 9 approved
    scenarios.
- **Rewritten, approved 2026-10-06:**
  - The old `test_receipt_request_with_exact_invoice_amount_resolves_correctly` became
    `test_receipt_for_the_net_amount_of_a_vat_added_invoice_is_flagged`.
  - Paying the net amount against a VAT-added 305 must be flagged: no receipt, no approval, and
    the reply states the gross total or the VAT gap.
- **Run on the backbone, 2026-10-06** (tracker:
  `apps/denidin-app/logs/test_logs/bugfix-071-test-tracker.md`, gitignored):

| Batch | Result |
|---|---|
| P1: sanity | 8/8 (7 billed + 1 expensive) |
| P2: other affected tests | 10/10 (9 billed + 1 expensive) |
| P3: new scenarios | 9/9 |

  - Two P3 tests first failed because of a test bug: a Hebrew prefix letter was glued onto a random
    client name (`מ`/`ל` + name), so the bot asked which client was meant. Fixed with
    `ללקוח`/`מהלקוח`, and both passed on re-run.
  - The production defect itself is reproduced: a ₪554 bank-transfer slip now becomes a 320
    stored as 469.49 + VAT 84.51.

