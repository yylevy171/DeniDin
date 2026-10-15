# Feature 064 - Acceptance scenarios (DRAFT, approved 2026-10-09 by the human operator)

Tier: `expensive` = sends an image to the vision model (own fresh approval per run). Plain-language, user view - not test code.
Scope: Backbone pipeline, godfather/admin, 1:1 chat. Offer = model-written, yes/no buttons, carries no data.

| # | Tier | Scenario |
|---|---|---|
| 64-1 | expensive, **sanity** | **Yes.** The admin sends a bank-deposit slip image for a client that exists in Morning. The bot reads it and records the deposit, then asks (yes/no buttons) whether to create a חשבונית מס / קבלה. The question names no amount or client. The admin taps yes. The normal 320 flow starts and its approval message shows the client, amount and date from the slip. Nothing is created until the admin approves that message. |
| 64-2 | expensive | **No.** Same slip. The admin taps no. The bot gives a short acknowledgement, creates no document, and the deposit stays in the ledger. |
| 64-4 | expensive | **New client.** The slip's payer is not in Morning. The bot goes through the existing add-client flow first; once the client exists and the turn is complete, the offer appears. If the admin declines to add the client, no offer appears. |

Removed at approval: 64-3 (ignore the buttons), 64-5 (group), 64-6 (not-allowed role).
Existing overlap: client-resolution paths are already covered by `tests/expensive/test_e2e_media_client_resolution.py` (US7a-d); 064's tests cover only the offer.
