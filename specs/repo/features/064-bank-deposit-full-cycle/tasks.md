# Tasks: Feature 064
Order in bundle: 1st. (A = tests first; B = implementation.)
- T064-A1 Unit test (new `tests/unit/test_flow_deposit_offer_064.py`): the assembled `flow_deposit_provided_by_user` text contains the offer step, uses `approval_with_yes_no_buttons` as a separate message after the report, never uses the reserved string `לאישור — כן/לא?` for the offer, scopes the offer to images, and states user-wins / yes-no-in-context.
- T064-B1 Edit `flow_deposit_provided_by_user.md` (steps 3, offer, reply handling, end); `cap_approval_with_buttons.md` note; `backbone.md` line if absent.
- T064-B2 Verify RBAC reachability of the flow (capability registry) - read-only check, noted in research.
- T064-C Acceptance: write `tests/expensive/test_deposit_offer_064_e2e.py` for 64-1 (sanity mark + add to `run_sanity.sh` arrays; run `verify_sanity_lists.sh`), 64-2, 64-4 - written last, run jointly later (each expensive run needs human approval).
