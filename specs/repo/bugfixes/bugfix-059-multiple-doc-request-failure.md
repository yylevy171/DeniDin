# Bugfix 059: Request requiring multiple documents failed

## Problem
When a request demands the generation of multiple documents simultaneously (e.g., creating 4 receipts sequentially for a single user request), it triggers an unhandled exception or 500 internal server error during the `create_combo_document` processing loop. This leads to a total crash and fallback.

## Solution
Investigate the multi-document generation loop. Identify why concurrent or rapid sequential calls to the document generation service are failing, and implement robust error handling or batched processing so the request completes successfully for all requested documents.
