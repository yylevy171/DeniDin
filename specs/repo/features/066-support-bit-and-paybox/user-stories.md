# User Stories: Support Bit, PayBox, Cheques and Cash (Feature 066)

## Story 1 - Bit / PayBox screenshot (P1)
**Given** the admin sends a Bit or PayBox screenshot **When** the bot reads it **Then** a deposit event of that method is recorded with amount, date and sender, the client is resolved as for any slip, and the Feature 064 offer follows. **And** a 320 created from it shows that payment method in Morning.

## Story 2 - Cheque image (P1)
**Given** the admin sends an image of a cheque **When** the bot reads it **Then** a cheque deposit is recorded with amount, payer, cheque number and bank / branch / account, and a 320 created from it shows method cheque in Morning.

## Story 3 - Cash in text (P1)
**Given** the admin writes "קיבלתי 500 במזומן מיוסי" **When** the turn completes **Then** a cash deposit of 500 from Yossi is recorded with no confirmation question, and a 320 created from it shows method cash in Morning.

## Story 4 - Existing bank slips and history (P1)
**Given** the old data model **When** the migration runs and the new release is live **Then** bank slips are still recorded (now as deposit/bank), all history is migrated, and webapp, player and reconciliation keep working.

## Acceptance scenarios (APPROVED 2026-10-09 - see `acceptance-scenarios.md`)
66-1 Bit (expensive) · 66-2 PayBox (expensive) · 66-3 cheque (expensive) · 66-4 cash (billed) - each verified via the document's details fetched from Morning · 66-7 bank-slip regression = existing `test_given_real_bank_deposit_image_then_full_fields_correctly_persisted` (sanity) · 66-9 tracking list of existing tests to adjust. Removed: 66-5, 66-6, 66-8.
