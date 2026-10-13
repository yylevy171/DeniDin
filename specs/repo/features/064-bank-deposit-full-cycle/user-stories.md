# User Stories: Bank Deposit Full Cycle (Feature 064)

## Story 1 - Offered the 320 after a slip (P1)
**Given** the admin sends a bank-deposit slip image for a client that exists in Morning
**When** the bot has read and recorded it
**Then** it asks, with yes/no buttons, whether to create a חשבונית מס / קבלה, naming no amounts
**And** on yes the 320 flow starts and shows its own approval message with the slip's client, amount and date; on no the bot acknowledges briefly and creates nothing.

## Story 2 - New client first (P2)
**Given** the slip's payer is not in Morning
**When** the bot completes the existing add-client flow
**Then** the offer is made after the client exists; and if the admin declines to add the client, no offer is made.

## Story 3 - Doing something else (P3)
**Given** an offer is pending
**When** the admin writes a different request instead of tapping
**Then** the offer counts as declined and the request is handled normally.

## Acceptance scenarios (APPROVED 2026-10-09 - see `acceptance-scenarios.md`)
64-1 (expensive, **sanity**) yes path · 64-2 (expensive) no path · 64-4 (expensive) new client.
Removed: 64-3, 64-5, 64-6. Overlap: client-resolution paths already covered by `test_e2e_media_client_resolution.py`.
