# Flow: Fee agreement provided by the user

Goal: the user provided a fee agreement, as text or as an image: make sure its client exists in Morning.

Capabilities: `cap_media_analysis`, `cap_client_read`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. If the agreement came as an image or document, it must have been read with `cap_media_analysis`'s `analyze_media` (load it and read it now if it was not). Use `cap_send_to_user` to report what it contains so the user can see what you understood. If its `missing_required_fields` is not empty, ask the user for exactly those details and wait for them.
2. The client must be resolved by its exact stored name before moving to the next step - either
   from the recent conversation history if it was already resolved there, or, if not, by loading
   `cap_client_read` and resolving it now. Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Recording the agreement itself happens after the turn ends, from what is in the conversation. There is nothing to load or call for it, so do not try. Your job is only to get the client resolved (or created), so the recorded agreement refers to a real client. It can be recorded only once the conversation holds the client and every payment component's amount; if any is missing, ask the user for it. Never tell the user the agreement was or will be recorded while any of it is missing.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_media_analysis`, `cap_client_read` and this flow, keeping any that other work still in progress needs.
