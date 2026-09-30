# Flow: Modify client

Goal: change an existing client's own details in Morning, on the one client the user really means.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   - An exact stored name: use it verbatim.
   - A confirmation question: use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: use `cap_send_to_user` to say so. The flow is complete. Creating a new client is a different request, so only offer it.
2. Load `cap_client_write` and prepare the change from what the user gave. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
3. Changing a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
4. On a yes, make the change. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
