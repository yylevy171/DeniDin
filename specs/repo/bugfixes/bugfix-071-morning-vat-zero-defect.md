# Bugfix 071: Morning Documents Created with VAT = 0 Instead of VAT Included

**Status**: Open — Root cause isolated, production scope quantified, awaiting human approval / handoff to engineering.
**Severity**: P0 / Critical (Compliance & Tax Under-reporting)
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

The fix is in `morning-mcp-app` only. It reaches dev/prod only via a new cut release + deploy
(human decisions, every time); merging alone changes nothing on running containers.
