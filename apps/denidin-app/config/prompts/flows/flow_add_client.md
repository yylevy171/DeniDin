# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave, with `resolve_client_name` - it also finds similar names (other spellings), which an exact search such as `list_clients` misses.
2. Handle what you find:
   - A clean exact match (`resolve_client_name` returned an exact match for that very name): use `cap_send_to_user` to tell the user plainly that the client already exists. Do not modify it and do not offer to. The flow is complete.
   - Anything other than a clean exact match - one candidate or several, however close the spelling: these are similar clients, not the same one. Use `cap_send_to_user` to list each similar client by name, spelled exactly as Morning returned it, and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
