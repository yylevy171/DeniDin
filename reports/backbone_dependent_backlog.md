# Backbone-Dependent Backlog Shortlist

This shortlist prioritizes features and bugfixes that were blocked by or directly depend on the recently completed Backbone Refactor (Feature 063). With the new prompt architecture, conversational memory, and robust tool-calling in place, these items can now be picked up.

## Features
1. **Feature 064: Bank Deposit Full Cycle**
   - **Why:** End-to-end automation of client creation and 300+320 combo generation from a bank deposit image. Extremely high UX value.

2. **Feature 066: Support Bit, PayBox, Checks, and Cash**
   - **Why:** Maximum business value for product-market fit. Re-architects the ledger around a unified "deposit" type to natively handle all alternative payment forms.

3. **Feature 067: Realistic Message Handling (Burst Messages)**
   - **Why:** Replaces the strict "1 message = 1 turn" limit. Buffers rapid-fire user messages so the AI processes them coherently in one batch. Massive UX win for natural texting.

4. **Feature 071: Single-Call PDF Extraction**
   - **Why:** Reads multi-page PDFs in a single API call instead of rasterizing page-by-page. Drastically cuts token costs and stops the system from dropping ledger events on PDF fee agreements.

5. **Feature 072: Morning Client-Name Cache**
   - **Why:** Cuts response latency in half for repeat clients by checking a local cache instead of waiting 3-5 seconds for the live Morning API. Pairs well with the Feature 100 context cache.

6. **Feature 099: Dual-Document Cancellation for 320s**
   - **Why:** Properly reverses both the revenue (via a 330 Credit Note) and cash flow (via a Negative 400 Receipt) when cancelling a 320, ensuring our ledger stays perfectly balanced. Both docs will accurately reference the original doc ID in the API payload.

7. **Feature 100: Client Resolution Caching**
   - **Why:** A major performance optimization. It allows the AI to skip redundant client resolution checks over the tunnel if it already verified the client recently. Highly synergistic with the Backbone.

## Bugfixes
1. **Bugfix 072: Bank Deposit Missing txn_date**
   - **Why:** The AI is successfully recognizing bank deposit images, but it's failing to extract and store the actual deposit date (`txn_date`). This causes the ledger to be inaccurate, and any Morning documents generated from these deposits end up with today's date instead of the actual transaction date.

2. **Bugfix 073: Client Resolution Robustness (Levenshtein Rescue Hatch)**
   - **Why:** Fixes an issue where slight typos (e.g., "מור פלומבו" instead of "מור פלימבו") cause perfectly good client candidates to be dropped by the strict filter. By adding a Levenshtein distance check, we rescue extremely relevant matches and surface them to the user.


