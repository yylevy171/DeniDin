# Bugfix 072: Bank Deposit Missing txn_date

**Bugfix Branch**: `bugfix/072-bank-deposit-missing-txn-date`
**Status**: Backlog

## 1. Description & Business Impact

During the recent Feature 063 (Backbone Refactor) testing, it was discovered that `txn_date` is not being properly stored when processing bank deposit images. 

**Business Impact**: 
- The ledger remains incomplete/inaccurate because the date of the cash inflow is missing.
- When generating Morning documents (e.g., a 400 receipt or a 320 tax invoice receipt) based on these bank deposit images, the documents might be generated with an incorrect or missing date (defaulting to today rather than the actual deposit date).

## 2. PM Requirements & Fix Criteria

- **REQ-072-01 (Extraction)**: The media analysis capability (vision extractor) MUST correctly extract the `txn_date` from bank deposit images.
- **REQ-072-02 (Ledger Storage)**: The extracted `txn_date` MUST be properly propagated and persisted into the local SQLite ledger.
- **REQ-072-03 (Morning Integration)**: When a Morning document (such as a 320 or 400) is generated based on a bank deposit image, it MUST use the correct extracted `txn_date` for the payment/receipt date, rather than defaulting to the current date.

## 3. User Acceptance Tests (UAT)

- **UAT-1 (Extraction & Storage)**:
  - *Given* a user uploads a photo of a bank deposit slip dated "01/10/2026",
  - *When* the AI processes the image,
  - *Then* the ledger record is created with `txn_date = "2026-10-01"`.

- **UAT-2 (Morning Generation)**:
  - *Given* the user has uploaded the deposit slip from UAT-1,
  - *When* the user requests to generate a receipt (400) for that deposit,
  - *Then* the Morning API call includes the date "2026-10-01" for the payment, and the resulting document reflects the correct historical date, not today's date.
