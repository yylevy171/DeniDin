# User Stories: Dual-Document Cancellation of a 320 (Feature 099)

## Story 1 - Cancel a 320 fully (P1)
**Given** a 320 for 1,000 paid by bank transfer **When** the admin says "בטל את החשבונית האחרונה" **Then** the bot asks approval for a 330, then for a negative 400; after both approvals both exist in Morning, linked to the original, and the bot says both were created.

## Story 2 - Decline the cash reversal (P2)
**Given** the same 320 **When** the admin approves the 330 but declines the negative 400 **Then** the bot says the cash side is still not reversed.

## Story 3 - Already cancelled (P2)
**Given** a 320 that already has a 330 **When** the admin asks to cancel it **Then** the bot refuses as already cancelled.

## Story 4 - Cancelling a 305 (P3)
**Given** a 305 **When** the admin cancels it **Then** only a 330 is created.

## Acceptance scenarios (APPROVED 2026-10-09 - see `acceptance-scenarios.md`)
99-1 (billed, **sanity**) · 99-2 · 99-3 · 99-4 (all billed). Removed: 99-5 (two payment lines), 99-6 (failure of the 400). Precondition: negative 400 accepted by the sandbox.
