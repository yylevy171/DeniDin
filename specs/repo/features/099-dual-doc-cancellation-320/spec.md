# Feature Specification: Dual-Document Cancellation of a 320

**Feature Branch**: `feature/f64-f66-f71-f99-f100-b72-b73` (bundle)
**Specified**: 2026-10-09
**Status**: Specified (acceptance scenarios approved 2026-10-09) - `speckit.clarify` / `plan` pending
**Dependency**: Feature 063 (Backbone)

## Problem
A 320 (חשבונית מס / קבלה) records both revenue and a cash receipt. Cancelling it today produces only a 330 credit note, which reverses the revenue but leaves the cash side unbalanced.

## Requirements
- **REQ-099-01 (Detect)**: When a full cancellation targets a 320, the bot recognises it.
- **REQ-099-02 (Two documents, in order)**: A 330 matching the 320's lines first, then a 400 receipt with a negative amount: a single line for the total, using the first payment line's method.
- **REQ-099-03 (Two approvals)**: Each document has its own approval step; the 330 is approved before the negative 400 is offered.
- **REQ-099-04 (Linking)**: Both documents reference the original 320, and their descriptions mention its number.
- **REQ-099-05 (Declined 400)**: If the user declines the negative 400, the bot says the cash side is still not reversed.
- **REQ-099-06 (Failure of the 400)**: If the negative 400 fails after the 330 succeeded, the bot says so plainly and offers a retry; nothing is rolled back. (Not covered by a dedicated test - the model's error handling is trusted.)
- **REQ-099-07 (Already cancelled)**: A 320 that already has a 330 against it is refused as already cancelled.
- **REQ-099-08 (Other documents unchanged)**: Cancelling a 305 produces only a 330, as today. Partial credits are unchanged (full cancellation only).
- **REQ-099-09 (Feedback)**: The bot tells the user both documents were created.
- **REQ-099-10 (Ledger)**: The 330 and the 400 are captured as any created document is today.
- **REQ-099-11 (Scope)**: Backbone pipeline only; no feature flag.

## Success criteria
- **SC-001**: After cancelling a 320, the client's books net to zero on both the revenue and the cash side.
- **SC-002**: A user never gets a half-cancelled 320 without being told.

## Open points for planning
Confirm in the Morning sandbox that creating a negative 400 is accepted (Morning's own cancellation documents carry negative amounts - Feature 062 - so likely, but unverified). Note the "first payment's method" rule mis-states a 320 paid by two methods; recorded as decided.
