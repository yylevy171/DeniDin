# Feature 086: Support closing multiple transaction accounts (300's) with a single combo doc (320)

## Overview
We need to support closing multiple transaction accounts (300 series) using a single combo document (type 320). Currently, the system lacks the ability to handle multiple 300 accounts seamlessly in a single combo transaction.

## Requirements
- Ability to select and group multiple 300 accounts when generating a 320 combo document.
- The system should allocate the totals appropriately across the grouped transaction accounts.
- AI handler and constitution must be updated to process this combined request.
