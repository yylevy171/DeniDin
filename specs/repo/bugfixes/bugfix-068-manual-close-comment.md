# Bugfix 068: Prevent "לסגור" Comment from Corrupting Agreement Totals

**Status**: In Progress

## Issue
Currently, when a user types "לסגור" (close) in the free-text comments of the Clients tab, the system applies a hack: it artificially modifies the underlying fee agreement totals so that `agreed_amount == paid_amount`. This forces the UI row to turn green (settled), but it fundamentally corrupts the firm's financial data by faking the agreement values.

## Business Reality
Often, a client pays *some* amount (> 0), but the case ends prematurely. The remaining balance will never be paid, and no invoices will be issued. The user wants to visually mark this client as "done" (green) without pretending the client paid the full original agreement, or without artificially lowering the original agreement to match the paid amount.

## Solution (Pre-Feature 089)
1. **Remove the Hack:** The backend logic that parses "לסגור" MUST stop modifying any `agreed_amount` or `paid_amount` values.
2. **Introduce `force_closed` flag:** The aggregation logic should simply parse the comment for "לסגור". If found, it flags that specific client/agreement as `force_closed = True`.
3. **UI Rendering:** The Webapp UI MUST render any row with `force_closed = True` in the "Green" (Completed) state, completely ignoring the math of `agreed_amount - paid_amount`. 
4. **Financial Integrity:** The actual `agreed_amount` and `paid_amount` shown in the UI and used in reports MUST remain true to reality, even if they don't match.

## User Acceptance Tests (UAT)
1. **UAT 1**: User types "לסגור" in the comments of a client who agreed to 10k but only paid 2k. 
   - **Expectation**: The UI row turns green. The UI still displays Agreed: 10k, Paid: 2k. The firm's total revenue pipeline is NOT artificially inflated or deflated.
