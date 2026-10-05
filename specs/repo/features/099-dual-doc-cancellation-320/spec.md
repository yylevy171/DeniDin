# Feature 099: Dual-Document Generation for 320 Cancellations

**Feature Branch**: `feature/099-dual-doc-cancellation-320`
**Status**: Backlog

## 1. Business & Architectural Goals

A `320` document (חשבונית מס קבלה - Tax Invoice Receipt) represents two distinct accounting events:
1. Recognizing revenue (Invoice).
2. Recognizing a cash inflow (Receipt).

Currently, when a user asks DeniDin to "cancel" a 320, we generate a `330` (חשבונית זיכוי - Credit Note). This properly reverses the *revenue* aspect, but leaves the *cash inflow* aspect unbalanced in the ledger. 
To fully and correctly cancel a 320, we must issue TWO documents: a `330` (Credit Note for the invoice portion) and a `Negative 400` (Negative Receipt to refund the cash portion).

## 2. PM Requirements (Functional)

- **REQ-099-01 (Detection)**: When the user requests a cancellation, the system must detect if the target document being cancelled is a `320`.
- **REQ-099-02 (Dual Generation)**: If cancelling a 320, the system must automatically execute two Morning API calls in sequence:
  1. Generate a `330` (Credit Note) matching the original `320` line items.
  2. Generate a `400` (Receipt) with a negative amount matching the original payment method/amount of the `320`.
- **REQ-099-03 (Atomicity/Linking)**: Both documents should ideally reference the original 320 in their comments/descriptions (e.g., "ביטול לחשבונית מס קבלה X").
- **REQ-099-04 (User Feedback)**: The AI must inform the user that *both* a credit note and a negative receipt were generated to properly balance the books.

## 3. User Acceptance Tests (UAT)

- **UAT-1 (Standard Cancellation)**:
  - *Given* a 320 document exists for 1,000 NIS paid via Bit,
  - *When* the user says "Cancel the last invoice",
  - *Then* the system generates a 330 for 1,000 NIS AND a 400 for -1,000 NIS (Bit), and links them to the client.
- **UAT-2 (Edge Case - Cancellation of purely 300)**:
  - *Given* a 300 document (חשבונית מס),
  - *When* the user cancels it,
  - *Then* the system ONLY generates a 330, as there was no cash receipt to reverse.

## 4. Complexity & Open Questions

- Does the Morning API allow creating a `400` with a strictly negative amount? Sometimes accounting systems use a specific "Refund Receipt" document type instead. (Dev must verify the Morning API payload for reversing a receipt).
- What if one API call succeeds (the 330) but the negative 400 fails? We need error handling to ensure we don't end up in a partially-cancelled state without alerting the user.
