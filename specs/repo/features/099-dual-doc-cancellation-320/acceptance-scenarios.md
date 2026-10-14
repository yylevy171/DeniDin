# Feature 099 - Acceptance scenarios (DRAFT, approved 2026-10-09 by the human operator, all points settled)

Tier: `billed` (text-only, Morning sandbox). Precondition: confirm in the sandbox that Morning accepts creating a negative 400.

| # | Tier | Scenario |
|---|---|---|
| 99-1 | billed, **sanity** | A 320 for 1,000 **paid by bank transfer** exists. The admin says "בטל את החשבונית האחרונה". The bot asks approval for a 330; the admin approves. The bot then asks approval for a negative 400; the admin approves. Both exist in Morning, linked to the original, and the bot says both were created. |
| 99-2 | billed | Same, but the admin declines the negative 400. The bot says the cash side is still not reversed. |
| 99-3 | billed | The 320 already has a 330 against it. The admin asks to cancel it. The bot refuses, saying it is already cancelled. |
| 99-4 | billed | The admin cancels a **305** (חשבונית מס). Only a 330 is created, as today. |

Removed at approval: 99-5 (two payment lines), 99-6 (Morning failure on the 400 - the model's own error handling is trusted).
Corrected: 99-1 uses bank transfer (not Bit); 99-4 uses a 305 (a 300 is not cancelled in practice).
