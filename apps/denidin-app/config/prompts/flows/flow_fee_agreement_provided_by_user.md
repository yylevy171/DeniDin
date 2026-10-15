# Flow: Fee agreement provided by the user

Goal: the user provided a fee agreement, as text or as an image, or logged hours worked for a client (e.g. "רן אורפני 4 שעות על היום"): make sure its client exists in Morning. Logged hours are a work-log entry under the client's fee arrangement, recorded like an agreement - not a reminder request.

Capabilities: `cap_media_analysis`, `cap_client_read`, `cap_ledger_query`, `cap_ledger_capture`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

Progress updates (`cap_send_progress_update`) can be sent between the steps, in plain words, so the user understands what is going on.

1. If the agreement came as an image or document, it must have been read with `cap_media_analysis`'s `analyze_media` (load it and read it now if it was not). If its `missing_required_fields` is not empty, ask the user for exactly those details in the same reply as step 2.
2. The client must be resolved by its exact stored name before moving to the next step.
   - **Agreement given as an image or document:** 🚨 resolve it before you reply at all. Load `cap_client_read` and call `resolve_client_name` with the client name the user gave. If the user gave none, use the client name `analyze_media` extracted from the agreement, **copied verbatim, character for character, letter for letter, exactly as extracted**: never corrected, completed, or swapped for a similar name or a client from earlier in the conversation. Then send one reply (`cap_send_to_user`) that reports what the agreement contains and handles what you found.
   - **Agreement or logged hours given as text:** resolve it from the recent conversation history if it was already resolved there for this same client, or else load `cap_client_read` and resolve it now.

   Handle what you find:
   - An exact stored name: copy it character for character from the `resolve_client_name` result from here on - in the approval text and in every tool call, never retyped (see `cap_client_read`).
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Proceed with whichever they choose.
   - Several candidates: use `cap_send_to_user` to list each of them by name and ask the user to specify, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Never pick one yourself.
   - No such client, or the user chose to create a new one: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. **Record the agreement in the ledger - only once it is complete, and only once.** It is complete when its client is resolved (or created) and every payment component's amount is in the conversation - or, for logged hours, the number of hours. If any is missing, ask the user for it and wait (never tell the user the agreement was or will be recorded while any of it is missing). When it is complete, load `cap_ledger_query` and `cap_ledger_capture` if not loaded, follow `cap_ledger_capture` exactly (look up the client's ledger history first, then call `report_ledger_recognition` with `verdict` `complete`), and report it that way. A correction, an addition or a cancellation of an agreement already recorded is reported the same way, as `cap_ledger_capture` describes. If the recording fails, tell the user so; if it succeeds, say it was recorded.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_media_analysis`, `cap_client_read`, `cap_ledger_query`, `cap_ledger_capture` and this flow, keeping any that other work still in progress needs.
