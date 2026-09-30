# Flow: Modify reminder

Goal: change or cancel an existing reminder, on the exact one the user means.

Capabilities: `cap_reminders_read`, `cap_reminders_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_reminders_read` and list the user's active reminders. Work out which one the user's wording points to (its text, or its time). Never guess a reminder.
   - Exactly one plausible match: use `cap_send_to_user` to confirm it with the user if there is any doubt.
   - Several: use `cap_send_to_user` to show the candidates and ask which one.
   - None: use `cap_send_to_user` to say so. The flow is complete.
2. If the reminder repeats, find out whether the user means the whole series or a single occurrence; ask with `cap_send_to_user` if it is not clear.
3. Load `cap_reminders_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Changing or cancelling a reminder MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, make the change or cancel. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_reminders_read`, `cap_reminders_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
