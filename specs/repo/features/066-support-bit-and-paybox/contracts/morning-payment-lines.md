# Contract: Morning payment lines (Feature 066)
`_build_payment_line(amount, payment_date, payment_method, bank_number, bank_branch, bank_account, transaction_reference, cheque_number)`
- `bank_transfer` -> type 4 + bankName/bankBranch/bankAccount.
- `cheque` -> type 2 + bankName/bankBranch/bankAccount + `chequeNum` (new).
- `bit` / `paybox` -> type 10 + appType 1 / 3 (+ transactionId if given).
- `cash` -> type 1, date and price only.
Deposit subtype -> `payment_method`: `בנק`=bank_transfer, `ביט`=bit, `פייבוקס`=paybox, `צ׳ק`=cheque, `מזומן`=cash.
