# Feature Specification: Bank Deposit Full Cycle (offer a 320 after bank evidence)

**Feature Branch**: `feature/f64-f66-f71-f99-f100-b72-b73` (bundle with 066, 071, 099 - see `bundle-064-066-071-099/`)
**Created**: 2026-08-27 · **Specified**: 2026-10-09
**Status**: Specified (acceptance scenarios approved 2026-10-09) - `speckit.clarify` / `plan` pending
**Dependency**: Feature 063 (Backbone). Bit / PayBox / cheque images join the trigger once Feature 066 ships.
**Input**: "After the bot has read and recorded a bank payment image, offer to create the חשבונית מס / קבלה that follows it almost every time - instead of waiting for the user to ask."

## Problem
Today: the user uploads a bank slip image -> the bot extracts and classifies it -> ledger capture records it (resolving the client, adding one if needed) -> the user then, almost every time, asks for a 320 -> the 320 flow runs, resolving everything again. The follow-up request is nearly always the same, so the bot should offer it.

## Terminology
- **Bank evidence image**: an image classified as proof of money received (a bank deposit slip today; Bit, PayBox, cheque images after Feature 066).
- **320**: Morning "חשבונית מס / קבלה" (combined tax invoice + receipt).
- **The offer**: one closed yes/no question asking whether to create that document from this evidence.

## Requirements
- **REQ-064-01 (Unchanged flow)**: Extraction, classification, ledger capture, client resolution and adding a new client behave exactly as today. This feature only adds the offer at the end.
- **REQ-064-02 (When)**: The offer is made once all resolutions of the turn are complete - at the point where the ledger recording is due - and only if the client is resolved. Client resolution may take several turns; the offer waits for the last one.
- **REQ-064-03 (No offer)**: No offer when the client remains unresolved (ambiguous, or the user declined to add them), when the sender is not godfather/admin, or when the file is not an image.
- **REQ-064-04 (Offer content)**: A model-written message asking whether to create the 320 from this evidence. It carries no amounts, names or dates - those appear later in the 320 flow's own approval. It is sent with yes/no interactive buttons; a typed yes/no is also accepted (same behaviour as the Feature 047 approval buttons).
- **REQ-064-05 (Yes)**: Yes starts the existing 320 flow with the evidence's details; that flow's own approval message is still shown and nothing is created before it is approved.
- **REQ-064-06 (No)**: No gets a short acknowledgement (wording is the model's choice). No document is created; the ledger recording is unaffected.
- **REQ-064-07 (Anything else)**: If the user ignores the buttons and asks for something else, the offer counts as declined and the new request is handled normally; a typed yes still counts as yes.
- **REQ-064-08 (Always offer)**: The offer is made every time the conditions hold, with no duplicate detection (the user decides).
- **REQ-064-09 (Who)**: Godfather/admin in 1:1 chats and in groups (a group turn uses the group's most-permissive member role).
- **REQ-064-11 (User wins)**: Any explicit instruction from the user that conflicts with the offer (e.g. "don't create a document") takes precedence over it.
- **REQ-064-10 (Scope)**: Backbone pipeline only; no feature flag (rollback = previous release).

## Edge cases
- The user's caption already asks for something: the bot does what the user asks AND the whole of this feature as well, including the offer. If the caption already asks for the 320, that only reinforces the offer (no special case). If the user explicitly says NOT to create a document, the user wins and no offer is made (human decision, 2026-10-09).
- Two slips in a row: the newer offer supersedes the older; a tap on the older one is ignored by the existing stale-tap guard (assumption).
- The user taps a button after the offer was superseded or answered: ignored silently (existing guard).

## Success criteria
- **SC-001**: After a slip for a known client, the admin gets the 320 approval message with the slip's details in two taps/messages (yes, then approve), without typing a request.
- **SC-002**: Declining costs the admin one tap and produces no document.
- **SC-003**: No offer is ever made for an unresolved client.

## Assumptions
Edge-case assumptions above; the offer's tone is left to the model. Whether the interactive-buttons plumbing is reused as-is or extended is a planning matter.
