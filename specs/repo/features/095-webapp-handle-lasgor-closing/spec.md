# Feature 095: Webapp - Handle "לסגור" (Close) command securely

## Overview
Currently, when the rule sees "לסגור" in the comments, it adds money to the agreement so the line can become "green". This is misleading since the agreement did not actually change.

## Requirements
- Add a proper "Agreement Status" (pre-feature 89) to represent a "Completed" state.
- When handling "לסגור" (for clients that paid some amount > 0, but no invoices went out, etc.), simply mark the agreement as closed/"green".
- Do NOT artificially add to the money paid or change the agreement amounts. 
- This effectively sets the agreement status to "Completed" regardless of the amounts in the agreement versus paid.
