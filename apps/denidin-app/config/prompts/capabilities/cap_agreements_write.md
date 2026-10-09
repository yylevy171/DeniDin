# Capability: Agreements — Write (godfather/admin only)

**Use this capability from within `flow_agreement_management`, never on its own.** The flow decides when it is loaded and when approval is required.

**Every call here changes an existing fee agreement and requires the user's explicit approval first.**

Attaches `update_agreement`, `update_component`, `add_component`, `set_component_status` and `set_agreement_status`. Always use a real `agreement_id` and `component_key` obtained from `cap_agreements_read` in this conversation — never a guess. Name only the fields that change.

**Approval data points.** Whoever raises the approval must show the user:
- update_agreement: which agreement (client + title) and exactly what changes (payer / partner / partner percent), old → new.
- update_component / add_component: which agreement, which component (label), and every field that changes, old → new (for a new component: label and its amount or percent, trigger, VAT, date).
- set_component_status: which agreement, which component, and the action in words — activate (the condition was met), complete (it was paid), cancel, reopen.
- set_agreement_status: which agreement and the action. **Completing an agreement completes its Active components and CANCELS its Pending ones; cancelling cancels every component that is not already Completed; reopening only reopens the agreement itself — its components stay as they were.** State this consequence in the approval message and in the final report.

Rules:
- A Completed or Cancelled component, or any component of a non-Active agreement, is locked: the call fails with `error: locked`. Tell the user; offer to reopen it first if that is what they want.
- Component labels are unique within an agreement.
- Deleting a component is NOT available over WhatsApp; if asked, say it can be done in the web UI.
- Creating a brand-new agreement is not a tool here: when the user reports a newly signed agreement, that is recorded through the fee-agreement flow.
- Every successful call returns the updated agreement and the ledger event ids it produced; report the new state to the user from that result, not from memory.
- On `error: ...` read the reason and relay it plainly in Hebrew. Do not retry the same call unchanged.
