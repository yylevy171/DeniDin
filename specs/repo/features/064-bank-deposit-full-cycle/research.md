# Research: Feature 064

- **Decision**: reuse `approval_with_yes_no_buttons`. **Rationale**: it is stateless and domain-agnostic (`resolution_tools.py`); the Backbone sets `offer_approval_buttons` on the response when it is called (`backbone.py` `_run_resolution_calls`, `_finalize_response`), so WhatsApp renders real buttons and button taps arrive as ordinary turns. **Alternatives**: a new local tool / pending-offer manager (rejected: state, code, no benefit).
- **Verified (grep)**: no Python code depends on the literal `לאישור — כן/לא?`; it is a prompt-level convention only, so the offer may use a different closing question.
- **Verified**: client resolution already ends the turn with questions when ambiguous; the flow's final step is where the offer belongs ("after the last of the resolutions").
- **Open for implementation**: confirm via the Backbone capability registry that the flow is reachable only for roles with Morning tools (RBAC) - the stated reason no offer reaches regular clients.
