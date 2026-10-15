# bugfix-077: progress updates went quiet after 067; typing dots appear after the last message

**Status**: Done - PR pending (number filled in after the PR exists). Prompts/tool descriptions rewritten as guidelines, completed-write-is-final guidance added, typing dots fixed (option 1). Not verified against the real model or live on dev.
**Found by**: PM, live in dev/prod on 0.8.3.

## Problem 1 - far fewer progress updates (reactions unchanged, out of scope)

Feature 067 (no-turn redesign) merged "interim" and "final" into one concept. Commit `b24109c2` and the
prompt work around it changed what the MODEL reads:

- `cap_send_progress_update.md` kept 0.8.2's "call this every single time you interact with any tool" but
  067 added "It sends exactly like `send_to_user`" - the two tools now look identical to the model.
  (Correction 2026-10-15: an earlier version of this spec wrongly said 067 removed the "every single
  time" line; it did not - the 0.8.3 prompt still has it.)
- `cap_send_to_user.md` / `backbone.md` gained "send the answer once, never send a follow-up
  wrap-up or status message" and "progress updates say what is being done for the user" - all of it
  discourages interim messages.
- The progress tool's own JSON-schema description (unchanged since Feature 080) CONTRADICTS the capability prompt above - it says "use ONLY on a turn
  you already know will take a while ... never on an ordinary fast turn" and "you MUST still produce a real
  final answer" - a restraint, and it mentions a concept (final answer) the progress tool should not know.

## Decided behavior (PM, 2026-10-15)

1. **Progress updates** are sent when a flow has more steps ahead. They describe, in words the user
   understands, what the model plans to do next.
2. **`send_to_user`** is the official summary of what was done, or the answer to a user question (or a
   question to the user). It is not about progress at all.
3. The two are **distinct and unaware of each other**: neither prompt (nor tool description) mentions the other.
4. **The backbone** defines when to use which. **Every flow** says at its top that progress updates can be
   sent between its steps, so the user understands what is going on.
5. Reactions: unchanged.

## Problem 2 - typing dots after the last message

Each `sendTyping` ping is a 20-second, non-cancellable indicator (Green API holds the HTTP call for the
whole `typingTime`). After the last message is sent the backbone makes one more model call (the one that
ends with no tool call); typing is switched on for it, so a fresh ping starts after the reply and the dots
linger up to ~20s. The keep-alive jobs themselves are removed on time (verified in the dev container log).
**Whether a call is the last one cannot be known before making it.** No delay before the first ping
(PM: rejected). Remaining option: shorter pings. DECISION PENDING.

## Acceptance (user terms - draft, needs PM approval before any billed run)

- A multi-step request (e.g. "issue a tax invoice/receipt for X ..." needing client lookup and more) -> the
  user receives at least one plain-Hebrew progress message BEFORE the first long step, and the closing
  summary arrives separately and is not itself a progress message.
- A simple question -> one answer, no progress message.


## Addendum 2026-10-15 - a completed write is never repeated

A failed reaction (every reaction fails in tests) once made the model redo a flow that had already created a
Morning tax document. Duplicate tax documents have legal consequences. The reaction failure is not the bug; the model
treating an unrelated error as a reason to repeat an irreversible write is.
Decision (PM): guidance only, no code. The backbone ("Behavioral Guidelines"), `cap_invoicing_write.md` ("A document
that was created is final") and the top of all eight document-writing flows now say that a successful create/cancel
cannot be undone and is never repeated because of anything that follows; when unsure, check Morning, then ask.
The tool result for a failed reaction is deliberately unchanged (hiding the error was rejected). Not added: a
morning-mcp-app duplicate-document backstop (offered, declined).
Tests: `tests/unit/test_created_documents_are_final_077.py` (structure only).


## Addendum 2026-10-15 - typing dots decision (PM approved option 1)

No delay and no change to the ping length. The model call that follows a round whose only tool call was
`send_to_user`, with no waiting user message, runs without the typing indicator (`src/backbone/typing_policy.py`,
wired in `Backbone._run_conversation`/`_call_model`). Every other call keeps it. Known cost: if the model sends a
message and then keeps working, there are no dots during that one thinking gap; they return with the next real
tool call. Not done: a Green API way to clear typing early (none known), a model-set "more coming" flag (would
bring back an end-of-turn signal). Tests: `tests/unit/test_typing_after_last_message_077.py`.
Not verified live: needs a look at a real chat on dev.
