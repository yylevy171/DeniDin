# Flow: Agreement management

Goal: answer questions about, or change, an EXISTING fee agreement of a client, exactly as the user asked.

Capabilities: `cap_agreements_read`, `cap_agreements_write` (only when a change is requested), `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_agreements_read`. Work out which client the user means; if the exact stored name is unclear, resolve it first, never guess.
2. Call `find_agreements`. If there is more than one agreement and the user didn't say which, ask with `cap_send_to_user` which one (name them by title). If there is none, say so and stop.
3. If the user only asked a question, answer it from the result with `cap_send_to_user` and go to step 7.
4. The user wants a change. Work out exactly which agreement and which component, and the new values. Anything missing or ambiguous, ask one question at a time; never guess.
5. Approval: every change MUST be approved BEFORE it is made. Load `cap_agreements_write` and `cap_approval_with_buttons`, and ask with a message holding all the data points listed in `cap_agreements_write`, old → new. For completing or cancelling a whole agreement, spell out what happens to each component. Do NOT call any write tool before a clear yes. On a no, do nothing and ask what to change.
6. Only after a clear yes: make the call. If it fails, tell the user the real reason; if it is locked, offer to reopen first; never retry unchanged.
7. End: report the outcome (the new state of what changed) with `cap_send_to_user`, then unload `cap_agreements_write`, `cap_agreements_read`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
