# Bugfix Spec: Model treats a truncated nickname of its own name as a different named person, wrongly emitting `[[NO_REPLY]]`

## Bug ID
bugfix-025-nickname-not-recognized-as-self-address

## Title
In a WhatsApp group turn, the model received "דני, מה החשבונית האחרונה במערכת?" ("Dani, what's
the latest invoice in the system?") - a message clearly in DeniDin's own domain (invoices) -
and responded with the literal `[[NO_REPLY]]` sentinel instead of answering or asking a
clarifying question, even though it had introduced itself as "דנידין" two turns earlier in
the same session.

## Priority
P1 - not a crash, not data loss, but a real, reproducible-shaped false negative in the core
group-addressing logic (Feature 039) that silently drops a message a human godfather clearly
intended for the bot, with zero visible feedback (no reply, no error, nothing) - the worst
failure mode for an addressing decision, since the user has no signal anything went wrong at
all.

## Status
Open - root cause investigated live during manual dev-environment testing (2026-08-05); no
fix has been designed or implemented yet. Per Bug-Driven Development (METHODOLOGY.md SVII),
next step is human review/approval of the root cause below before any test-gap analysis or
fix design begins.

## Date Opened
2026-08-05

## Reported By
yaronlev171 (found during manual dev-environment testing in a real WhatsApp group, chat
`120363410226011645@g.us`, godfather role)

## Affected Area
- `apps/denidin-app/config/runtime_constitution.md` - "Group Conversation Etiquette" section,
  specifically rule **1** ("The message names a specific person"), which frames the
  DeniDin-name-match as "a simple, mechanical check, not a judgment call" and gives no
  guidance for the case where the name in the message is *both* a plausible truncation/
  nickname of DeniDin's own name *and* a plausible independent Hebrew given name.
- `apps/denidin-app/src/handlers/ai_handler.py` - `_finalize_response` / the
  `[[NO_REPLY]]` → `should_reply=False` wiring (working as designed; not itself suspected of
  a bug - the sentinel was emitted deliberately by the model, not misparsed by the app).

## Description
Live sequence observed in `denidin-app-dev` logs (chat `120363410226011645@g.us`, real
WhatsApp group, godfather role, session `86d351d6-7679-434c-a87c-56c1deffbc70`):

1. `09:29:23` - User: "ומי אתה?" ("and who are you?") → model answered normally: **"אני
   דנידין — עוזר AI של משרדך בוואטסאפ..."** ("I am DeniDin - your office's WhatsApp AI
   assistant..."). Correct, no ambiguity, self-introduced by full name.
2. `09:30:03` - User: "@972506205541 מה יש לך להגיד בנושא?" (an explicit `@`-mention of
   another participant's phone number, "what do you have to say on the matter?") → model
   correctly returned `[[NO_REPLY]]`. Correct - unambiguously addressed to someone else by
   phone-number mention.
3. `09:31:15` - User: **"דני, מה החשבונית האחרונה במערכת?"** ("Dani, what's the latest
   invoice in the system?") → model again returned `[[NO_REPLY]]`. **This is the bug.** The
   message: (a) opens with "דני" - a common truncation/nickname of "דנידין," the name the
   bot itself used one turn earlier in the same session (msg 1 above, still in the 12-message
   history window passed to this call per the log's "Retrieved 12 messages from session
   history"); (b) asks a question squarely inside DeniDin's own stated domain (invoices,
   explicitly called out in the constitution's "Invoice Management Context" section); (c) has
   no `@`-mention and no full name of any other participant, unlike message 2. By the
   constitution's own rule **3** ("something else about the phrasing still makes it genuinely
   unclear who it's for... ask a short, natural Hebrew clarifying question"), the *minimum*
   correct behavior even in the worst case would have been a clarifying question - not
   silence.

No error, exception, or RBAC block anywhere in the logs for this turn; the OpenAI call
completed normally (`resp_07d549efda16ee88...`, 16559 tokens) and the model's own output text
was exactly `[[NO_REPLY]]` - i.e. the app behaved exactly as designed given what the model
returned. The bug is in the model's addressing *decision*, not in how the app handled it.

## Root Cause (proposed - pending human approval)

Rule **1** in "Group Conversation Etiquette" instructs the model to treat the name-match as
"a simple, mechanical check, not a judgment call," and its worked examples ("רותי", "דוד")
are all names with **no** textual overlap with "DeniDin" at all - the rule never contemplates
a name that is a genuine substring/truncation of the bot's own name. "דני" is:
- a real, common, standalone Israeli given name (so it plausibly names a third person), AND
- the literal first syllable of "דנידין," which the bot had used to introduce itself just one
  turn earlier in the very same session/history window.

Given the rule's "mechanical, not a judgment call" framing, the model appears to have resolved
this by literal-ish string comparison against "is this DeniDin or a close variant" and judged
"דני" insufficiently close - without weighing the strong contextual signal that its own name
had just been spoken in full two turns prior, or that the message content itself was squarely
in-domain. That combination (recency of self-naming + domain fit) is exactly the kind of
holistic, cross-turn reasoning the rule's black-and-white framing discourages the model from
doing for step 1, and the rule gives no fallback to step 3 ("genuinely unclear... ask") for a
name match that is itself ambiguous rather than clearly-absent.

This is a **prompt/constitution-design gap**, not an app-logic bug: `ai_handler.py` passed the
full, correct history (12 messages, including the self-introduction) into the call; nothing
was dropped or mis-assembled on the app side. The fix, if approved, likely belongs in
`runtime_constitution.md` rule 1/3 wording (e.g. explicitly: if the named token is a
recognizable truncation/nickname of DeniDin's own name, treat as case 1's "IS DeniDin" branch,
or route to case 3 if genuinely unsure) rather than in `ai_handler.py`.

### Why did *you* (the assistant reading these logs) catch this immediately, when gpt-5.6-luna
### (the configured `ai_model`, see `config/config.dev.json`) didn't, in the same conversation?

Not because one model is unconditionally "smarter" at Hebrew or at reasoning in general - a
few concrete, narrower differences most likely explain it:

1. **I read the transcript after the fact, with the outcome already visible and nothing else
   to do.** I had your explicit question as a prompt to specifically go looking for why the
   name didn't match, plus unlimited time/no latency budget to line up "דני" against the
   "אני דנידין" reply two lines above it. The production model gets one real-time turn, no
   step back, and (per the constitution's own framing) an instruction to treat the name check
   as fast and mechanical rather than deliberative - i.e. the system prompt is actively
   steering it away from the slower, connect-the-dots reading that solved it for me.
2. **The rule text itself, as currently written, doesn't ask the model to check "is this name
   a truncation of my own name," only "is this name DeniDin or a close variant."** "דני" vs.
   "דנידין" is arguably a close variant, but the examples given (fully distinct names like
   "רותי"/"דוד") anchor the model toward a stricter string-similarity reading than the intent
   behind the rule.
3. **This is not guaranteed-reproducible model behavior.** Re-running the identical prompt
   could plausibly get a different answer next time (correct or not) - LLM output for a
   borderline case like this is not deterministic, which is itself part of why this is being
   filed as a bug against the *rule wording* (the one thing that's actually fixable and
   testable) rather than treated as a one-off fluke.

In short: this isn't evidence AI "doesn't understand" Hebrew or context in general - it's a
specific instruction-following gap where the constitution tells the model to be mechanical
exactly where mechanical judgment breaks down, and I had the unfair advantages of hindsight,
your explicit question, and no such instruction constraining me.

## Next Step
Per BDD, awaiting your explicit approval of the root cause above before any test-gap analysis
or fix design begins.
