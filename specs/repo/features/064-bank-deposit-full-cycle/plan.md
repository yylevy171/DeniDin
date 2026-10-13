# Implementation Plan: Bank Deposit Full Cycle (Feature 064)

**Spec**: `spec.md` · **Stories/scenarios**: `user-stories.md`, `acceptance-scenarios.md` (approved 2026-10-09) · **Design approved**: 2026-10-09 (separate messages for report and offer)

## Technical context
Backbone pipeline (Feature 063). Behaviour lives in prompt files under `apps/denidin-app/config/prompts/` (baked into the image). No Python change is expected. Offer = the existing stateless `approval_with_yes_no_buttons` tool; cross-turn memory = the existing `record_planning_status` note.

## Constitution check
No env vars, no mocking, no new feature flag (human decision), config-as-code respected, no schema change. The "tool-bearing features need explicit boundaries" rule: the offer is scoped inside `flow_deposit_provided_by_user` only, and the flow states a bare yes/no outside that context never triggers it (see Design §4).

## Design
1. `flow_deposit_provided_by_user.md` - restructure the end of the flow:
   - Step 3 (documents): if the user (caption or message) asks for a Morning document, load `flow_morning_document_write` and do it - **and the offer below still applies**, unless the user explicitly said not to create a document (user wins).
   - New step "Offer" (after resolution is complete, only when the deposit came as an **image**, the client is resolved, and the user did not say not to create a document): first `cap_send_progress_update` sends the outcome report as its own message (`send_to_user` ends the turn - `backbone.py` `_run_resolution_loop` returns on it - so it cannot precede a second message in the same turn); then, **as a separate final message**, `approval_with_yes_no_buttons` carries a short model-written question asking whether to create a חשבונית מס / קבלה (320) from this evidence. No amounts, names or dates. Closing question is NOT the reserved `לאישור — כן/לא?` (that string means "approve a write"). Record "offered a 320, awaiting yes/no" with `cap_record_planning_status`.
   - Reply handling (next turn): yes -> load `flow_morning_document_write` (320, details from the evidence) - its own approval still follows; no -> short acknowledgement, nothing created; anything else -> offer dropped, new request handled normally (existing "drops the request / changes subject" step).
   - End step: unload as today, but keep nothing pending once answered.
2. `cap_approval_with_buttons.md` - note that a plain offer (not a write approval) uses a different closing question than `לאישור — כן/לא?`.
3. `backbone.md` - one line: a bare yes/no answers the most recent pending question in the same context (already stated in Contexts of Operation in the legacy constitution; mirror for Backbone if absent).
4. Boundaries: the offer applies only inside this flow, only to image evidence, never to PDF/DOCX/text deposits; the offer is out of scope for every other flow.

## Out of scope
Duplicate detection, groups-specific logic (RBAC already gates Morning tools by role), PDF slips, a code-level pending-offer state.

## Tests
- Acceptance (approved): 64-1 (sanity), 64-2, 64-4 - `expensive`, written last, run jointly.
- Unit: prompt-assembly test that loading `flow_deposit_provided_by_user` yields the offer step and that the reserved approval string is not used for the offer (cheap guard on the contract).

## Project structure (touched)
`apps/denidin-app/config/prompts/flows/flow_deposit_provided_by_user.md`, `.../capabilities/cap_approval_with_buttons.md`, `.../backbone.md`; `apps/denidin-app/tests/unit/test_flow_deposit_offer_064.py` (new).
