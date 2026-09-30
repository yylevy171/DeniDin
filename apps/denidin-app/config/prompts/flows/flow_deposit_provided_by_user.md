# Flow: Deposit provided by the user

Goal: a bank deposit was provided by the user: make sure the payer exists in Morning as a client.

Capabilities: `cap_client_read`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
2. Recording the deposit itself is automatic after the turn ends. There is nothing to load or call for it, so do not try. Your job is only to get the payer resolved (or created).
3. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
4. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read` and this flow, keeping any that other work still in progress needs.
