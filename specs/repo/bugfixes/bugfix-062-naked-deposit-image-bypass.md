# Bugfix 062: Naked Deposit Image Bypass

## Root Cause Analysis
Feature 69 (Ledger Recognition) was designed to act as a background safety net, silently recording financial events (like bank deposits) based on the context of the main conversation. A core requirement for recording a bank deposit is that the client must be verified in the Morning system. The Ledger Recognizer relies entirely on the main LLM having called the `resolve_client_name` MCP tool during its turn.

However, the main LLM operates under a strict "Customer Engagement" firewall for images. The `runtime_constitution.md` dictates that when the user uploads an image, the LLM must only extract its metadata ("מטא־נתונים") and must NOT use "Invoice Management" tools.

Because `resolve_client_name` is conceptually misclassified as an "Invoice Management" tool instead of a generic client management capability (despite it interacting with Morning), the LLM refuses to use it when presented with a "naked" deposit image (an image uploaded with no explicit caption or command). 

As a result:
1. The user uploads a deposit image with no caption.
2. The main LLM obediently extracts the metadata and stops, deliberately NOT calling `resolve_client_name`.
3. The Ledger Recognizer (Feature 69) runs post-turn, sees no MCP evidence of a resolved client, and strictly (but correctly, according to its rules) returns `none`.
4. The deposit is silently dropped from the ledger.

## Why the Tests Passed
The expensive acceptance test (`test_given_real_bank_deposit_image_then_full_fields_correctly_persisted`) explicitly simulated a user uploading the image WITH a command caption: `caption="הפקדה שנכנסה, תרשום ביומן"`. This active directive caused the main LLM to break out of the passive "Customer Engagement" image extraction mode, call `resolve_client_name`, and trigger the clarification detour, which gave the Ledger Recognizer the verified client it needed.

## Fix Specification
1. **Reclassify `resolve_client_name`**: The constitution must explicitly decouple `resolve_client_name` (and potentially `add_client`) from the "Invoice Management" rules. It must be framed as a core, universal Client Management capability that is REQUIRED whenever evaluating an economic event, regardless of whether it came from text or a naked image.
2. **Update Image Instructions**: The "Customer Engagement" image rules must explicitly state that if a bank deposit slip is detected, the LLM must proactively resolve the client name, even if no explicit command like "תרשום ביומן" was provided.
3. **Fix the Test**: The `caption` must be removed from `test_given_real_bank_deposit_image_then_full_fields_correctly_persisted` in `test_ledger_event_capture_e2e.py` so that the test accurately reflects the real-world scenario of a naked upload, effectively forcing the test to fail until the prompt architecture is fixed.
