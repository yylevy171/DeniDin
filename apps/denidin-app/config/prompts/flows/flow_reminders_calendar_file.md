# Flow: Reminders calendar file

Goal: give the user a calendar (.ics) file of reminders they already have, when they ask for it or accept the offer.

Capabilities: `cap_reminders_read`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_reminders_read` and list the user's active reminders. Answer the user's question about them, if they asked one.
2. If the user already asked for a calendar file, go to step 4 with the reminders they named (or all of them if they said "all"). If it is unclear which reminders they mean, use `cap_send_to_user` to ask which; never guess.
3. Offer: load `cap_approval_with_buttons` and ask `לייצא את התזכורות שלך לקובץ יומן (ics)?`. Send nothing until the user answers. On a no, or no answer, do nothing more; the flow is complete.
4. On a yes (or an explicit request): call `send_reminders_calendar_file` with the `reminder_id` of every reminder to include. If it fails, tell the user plainly with `cap_send_to_user`; retry once only if the reason is fixable.
5. End: unload `cap_reminders_read`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.

This flow never creates, changes or deletes a reminder, and calendar files for anything other than reminders are out of scope.
