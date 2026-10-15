# bugfix-077: progress updates went quiet after 067; typing dots appear after the last message

**Status**: In progress - root causes found 2026-10-15, fix directions decided by the PM (below). Typing item awaiting a decision.
**Found by**: PM, live in dev/prod on 0.8.3.

## Problem 1 - far fewer progress updates (reactions unchanged, out of scope)

Feature 067 (no-turn redesign) merged "interim" and "final" into one concept. Commit `b24109c2` and the
prompt work around it changed what the MODEL reads:

- `cap_send_progress_update.md` was rewritten to say it "sends exactly like `send_to_user`", and
  lost "before your final reply" / the "every single time you interact with any tool" push - the two
  tools now look identical to the model, so it uses the main one.
- `cap_send_to_user.md` / `backbone.md` gained "send the answer once, never send a follow-up
  wrap-up or status message" and "progress updates say what is being done for the user" - all of it
  discourages interim messages.
- The progress tool's own JSON-schema description (unchanged since Feature 080) says "use ONLY on a turn
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
