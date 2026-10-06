# Flow: Create reminder

Goal: create a new reminder (one-time or recurring) for the user, exactly as they asked.

Capabilities: `cap_reminders_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_reminders_write`.
2. Work out what to remind about and when (a one-time moment, or a recurring cadence), resolving relative wording against the current date and time. Anything you don't have from the user, ask for with `cap_send_to_user`, one question at a time; never guess or invent a value.
3. Approval: creating a reminder MUST be approved by the user BEFORE it is created. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Do NOT call `create_reminder` in this step or before a clear yes. On a no, do nothing, and ask with `cap_send_to_user` what to change.
4. Only after a clear yes: call `create_reminder`. If it fails, tell the user plainly what happened; retry once only if the reason is fixable, otherwise stop.
5. If the user drops the request or changes the subject at any point, do nothing further; the flow is complete.
6. End: report the outcome with `cap_send_to_user`, then unload `cap_reminders_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
