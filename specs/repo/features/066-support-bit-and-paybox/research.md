# Research: Feature 066

## Verified live against the Morning sandbox (2026-10-09, probe scripts in session scratchpad)
- Cheque payment line (type 2): `chequeNum`, `bankName`, `bankBranch`, `bankAccount` persist and render ("מס' צ'ק … / בנק … / סניף … / חשבון …"). `dueDate` and `transactionId` are silently dropped.
- Bit / PayBox (type 10): `appType` 1 = bit, 3 = PayBox, `transactionId` persists; rendered "bit" / "PayBox".
- Existing MCP builder already maps `bit`, `paybox`, `cash`, `cheque`, `bank_transfer`; only cheque number was missing.

## Decisions
- Ledger shape: `source_type="הפקדה"`, `event_subtype` = method (human-approved). Event-ID letter stays `B` (human-approved). Bank subtype label `בנק` (human-approved).
- Duplicate-detection fingerprint (existing rule: same content on the same calendar day = duplicate) gains the subtype so a cash and a bank deposit of the same amount/day don't collide. Cash with no `txn_date` follows the same rule, and is NOT flagged incomplete for the missing date (human: a cash deposit without a date is fine). Consequence: two genuine same-day same-amount cash deposits from one client collapse into one, exactly as two identical bank slips do today.
- Migration is a file-level rewrite with backup (human-approved: backup only, no reverse script).
