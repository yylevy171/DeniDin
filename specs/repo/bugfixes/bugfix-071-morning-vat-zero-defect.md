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
A live audit of the production Morning Green-Invoice API across all documents issued since July 1st, 2026 revealed:
* **Total Audited Documents (Types 320 & 400):** 123 documents
* **Type 320 (`חשבונית מס / קבלה`):** 107 documents total.
  * **Defective (Issued with VAT = 0):** **37 documents** (34.6% of all Type-320 combo invoices).
  * **Gross Billed via Defective 320 Invoices:** **₪280,918.00**
  * **Under-reported VAT Exposure (at 18% inclusive):** **₪42,851.92**
* **Type 400 (`קבלה` - Standalone Receipts):** **16 documents** total.
  * All 16 are standalone receipts with zero VAT, with **zero associated Type-305 tax invoices** linked in Morning.
  * **Gross Volume on Standalone Receipts:** **₪13,881.00**
  * **Associated Expected VAT (if services rendered without separate tax invoice):** **₪2,117.44**
* **Combined Financial Exposure:** **53 documents | ₪294,799.00 Gross Volume | ₪44,969.36 VAT**

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

### B. Type 400 Standalone Receipts with No 305 Invoice (16 Documents)

| # | Doc # | Date | Client | Gross (₪) | Expected VAT (18%) | Notes |
|:---:|:---:|:---:|:---|:---:|:---:|:---|
| 1 | 130127 | 2026-10-02 | ירין ביטון | ₪-1,500.00 | ₪-228.81 | החזר / קבלה שלילית |
| 2 | 130126 | 2026-09-28 | דודי אדלר | ₪3,000.00 | ₪457.63 | קבלה ללא חשבונית 305 מקושרת |
| 3 | 130125 | 2026-09-14 | עו"ד שרון כהן | ₪500.00 | ₪76.27 | קבלה ללא חשבונית 305 מקושרת |
| 4 | 130124 | 2026-08-28 | רמי בן חמו | ₪4,500.00 | ₪686.44 | קבלה ללא חשבונית 305 מקושרת |
| 5 | 130123 | 2026-08-27 | דודי אדלר | ₪210.00 | ₪32.03 | קבלה ללא חשבונית 305 מקושרת |
| 6 | 130122 | 2026-08-23 | אתי אסולין | ₪1,071.00 | ₪163.37 | קבלה ללא חשבונית 305 מקושרת |
| 7 | 130121 | 2026-08-17 | מירה אבוראס תלי | ₪2,800.00 | ₪427.12 | קבלה ללא חשבונית 305 מקושרת |
| 8 | 130120 | 2026-08-09 | רלי אוחנה | ₪1,500.00 | ₪228.81 | קבלה ללא חשבונית 305 מקושרת |
| 9 | 130119 | 2026-08-09 | שלמה נזרי | ₪2,000.00 | ₪305.08 | קבלה ללא חשבונית 305 מקושרת |
| 10 | 130118 | 2026-08-09 | עדו דניאל | ₪3,000.00 | ₪457.63 | קבלה ללא חשבונית 305 מקושרת |
| 11 | 130117 | 2026-08-09 | טלאל קרעאן | ₪2,300.00 | ₪350.85 | קבלה ללא חשבונית 305 מקושרת |
| 12 | 130116 | 2026-07-31 | יחיאל אוהב עמי | ₪3,000.00 | ₪457.63 | קבלה ללא חשבונית 305 מקושרת |
| 13 | 130115 | 2026-07-22 | מירה אבוראס תלי | ₪-7,000.00 | ₪-1,067.80 | החזר / ביטול קבלה |
| 14 | 130114 | 2026-07-21 | חברת אוריון משני | ₪-532.00 | ₪-81.15 | החזר / ביטול קבלה |
| 15 | 130113 | 2026-07-21 | חברת אוריון משני | ₪532.00 | ₪81.15 | קבלה ללא חשבונית 305 מקושרת |
| 16 | 130112 | 2026-07-21 | רועי עטיה | ₪-1,500.00 | ₪-228.81 | החזר / ביטול קבלה |

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
