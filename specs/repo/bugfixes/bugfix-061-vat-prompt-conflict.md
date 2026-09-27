# Bugfix 061: Constitution Disambiguation - VAT Prompt Conflict on Deposits

## Problem
Despite the constitution defining that deposit screenshots and bank transfers (320 document types) default to VAT included (`vat_included = true`), the model frequently interrupts the invoicing flow to ask the operator if the amount includes VAT. 

This occurs due to a direct contradiction in the `runtime_constitution.md` where a global safety rule overrides a tool-specific default:
1. **Tool-specific default (under `create_combo_document`):** "vat_included defaults to true for deposit screenshots... only the user explicitly saying the opposite overrides this default."
2. **Global negative constraint (under Missing Fields):** "A missing VAT treatment, purpose, transaction date or client is not something to fill in with a plausible guess — ask, then call the tool once you have the answer."

Large language models prioritize absolute negative constraints over conditional defaults buried in tool parameter descriptions. Thus, the model prioritizes safety and strictly interrogates the operator.

## Production Sighting
**Date:** 2026-09-16
**Session:** `12e158e2-114d-4533-8945-51b17c42562b`

The operator uploaded a deposit screenshot for an 8,500 ₪ transfer. The extracted text clearly indicated a bank transfer:
```
העברה מעבר חשבון
20-577-0000-000512512 תומר
ענבר
₪8,500.00
```
Instead of defaulting VAT to true and proceeding, the model halted and replied:
> "כדי להפיק חשבונית מס/קבלה עבור תומר ענבר על 8,500 ₪, חסרים שני פרטים:
> 1. עבור מה התשלום?
> 2. האם הסכום כולל מע״מ או לפני מע״מ?"

## Solution
Add a top-level exception placed directly in the "Missing Fields" section of the constitution, explicitly stating that creating 320 documents from deposit screenshots is exempt from the VAT interrogation rule and must unconditionally default to true unless manually overridden by the user.

## Status
**Fixed** (2026-09-27, `fix(bugfix-061)`). The originally-described 320/deposit-screenshot
exception described above was already in place in `runtime_constitution.md` by the time a full
categorization of every VAT-related test in the suite was done (see
`bugfix-061-vat-test-categorization.md`, same directory) — but that categorization surfaced a
second, previously-unnoticed gap with the same root shape: `create_invoice` (type 305, an
ordinary tax invoice) had **zero** VAT guidance at all, so the model silently assumed VAT-included
instead of asking, exactly the mirror-image failure of the original bug. Fixed by giving
`create_invoice` the same mandatory-ask rule `create_transaction_account` (300) already had (no
deposit-reference exception applies there, since a 305 by definition covers money not yet
received). See PR for this branch for the full diff, the test categorization, and added tests.
