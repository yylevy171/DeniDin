# Feature Specification: Support Bit, PayBox, Cheques and Cash

**Feature Branch**: `feature/f64-f66-f71-f99-f100-b72-b73` (bundle with 064, 071, 099)
**Created**: 2026-08-30 · **Specified**: 2026-10-09
**Status**: Specified (acceptance scenarios approved 2026-10-09) - `speckit.clarify` / `plan` pending
**Dependency**: Feature 063 (Backbone)
**Input**: Support images of Bit, PayBox and cheques (flow identical to bank-transfer images) and cash reported in text; the ledger and Morning documents must carry the real payment method.

## Problem
Only bank transfers are understood today (ledger `type="bank", subtype="deposit"`). Bit, PayBox and cheque images are missed or mis-read, and Morning documents default to "bank transfer".

## Terminology
- **Deposit**: any incoming funds. New ledger shape: `type="deposit"` (הפקדה) with `subtype` = payment method: `bank` (בנק), `bit` (ביט), `paybox` (פייבוקס), `check` (צ׳ק), `cash` (מזומן).
- **320** = חשבונית מס / קבלה (combo). **400** = קבלה (receipt). (The previous draft had these swapped.)

## Requirements
- **REQ-066-01 (Data model flip)**: Every incoming-funds ledger event has `type="deposit"`; the payment method is the `subtype`.
- **REQ-066-02 (Schema version)**: The ledger schema version is bumped, with its matching history entry in the same commit. The exact number is the human operator's decision, given when tasks are written.
- **REQ-066-03 (Bit / PayBox)**: Bit and PayBox screenshots are recognised and recorded as deposits of that method with amount, date and sender name. Nothing more is extracted.
- **REQ-066-04 (Cheques)**: A cheque image is recognised and recorded with amount, payer name, cheque number, and bank / branch / account. No due date.
- **REQ-066-05 (Cash)**: Natural-language text reporting cash received (e.g. "קיבלתי 500 במזומן מיוסי") is recorded as a cash deposit like any other ledger event, with no extra confirmation step.
- **REQ-066-06 (Same flow as bank images)**: Client resolution, adding a client, and the Feature 064 offer work for these methods exactly as for bank slips (images only; cash is text).
- **REQ-066-07 (Morning documents)**: Document creation for 320 and 400 accepts all five methods and sets the matching Morning payment type, so the document shows the real method rather than bank transfer.
- **REQ-066-08 (Migration)**: A one-off script rewrites all historical `bank`/`deposit` events on production to `deposit`/`bank` with no data loss. The only safety net is a backup of the events folder taken first; the previous release cannot read the new format.
- **REQ-066-09 (Ecosystem)**: The webapp (ledger list and Clients tab) shows the new events like bank deposits with the method as a label; the player (replay) and the accounting reconciliation service handle the new type without errors.
- **REQ-066-10 (Scope)**: Backbone pipeline only; no feature flag.

## Success criteria
- **SC-001**: A Bit / PayBox / cheque image or a cash text produces a correct ledger event, and the Morning document created from it shows the same method, amount and date.
- **SC-002**: 100% of historical bank deposits are migrated with zero data loss.
- **SC-003**: Webapp, player and reconciliation load and run after migration without errors tied to the new type.

## Open points for planning
Which cheque details Morning can store on a document; schema-version number (human); the list of existing tests to adjust (tracked as 66-9).
