# Flow: Invoicing query

Goal: read a client's documents or a document's status from the invoicing system (Morning), for the client the user means.

Capabilities: `cap_client_read`, `cap_invoicing_read`.

Follow these steps in order, to the letter.

1. Look at the conversation window first. If a **prior** turn in this SAME conversation already resolved this exact client — a `resolve_client_name`/`get_client_details` result, or a match you already confirmed with the user — treat that stored name as still resolved, even if that turn already ended and even if `cap_client_read` is no longer loaded. Do **not** re-resolve or re-verify it again "just to be sure" — skip straight to step 3 with it. The same applies to a document id you already hold. Only go to step 2 when the user names a client (or document) you have no such record of in the window, or names a different one.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   - An exact stored name: copy it character for character from the `resolve_client_name` result, never retyped (see `cap_client_read`).
   - A single close match: use `cap_send_to_user` to confirm it with the user before going on.
   - Several candidates: use `cap_send_to_user` to list them and ask which one is meant. Never pick one silently.
   - No match: use `cap_send_to_user` to say the client was not found and stop. Looking something up never creates a client.
3. Load `cap_invoicing_read` and read what was asked, giving it the exact stored client name you resolved (or the document id you hold).
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Hand the result to whoever asked: a flow that loaded this one continues with it; a question from the user is answered with `cap_send_to_user`. Then unload `cap_client_read`, `cap_invoicing_read` and this flow, keeping any that other work still in progress needs.
