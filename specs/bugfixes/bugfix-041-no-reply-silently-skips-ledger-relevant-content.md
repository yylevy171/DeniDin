# Bugfix Spec: `[[NO_REPLY]]` silently skips genuine billable-hours/ledger content in a group chat, with no clarifying question and no capture attempt

## Bug ID
bugfix-041-no-reply-silently-skips-ledger-relevant-content

## Title
In a real WhatsApp group turn, a message stating real billable hours for a named client and
matter ("אורית בנימין / מקורות / שעתיים" - client, legal matter, hours worked, no date) was
answered with the literal `[[NO_REPLY]]` sentinel (Feature 039's group-addressing mechanism)
instead of a clarifying question or a `capture_ledger_event` call. The information was silently
dropped - not flagged, not asked about, not stored anywhere but raw session history text -
until an unrelated message the *next day* incidentally caused the model to recall it and
capture it under the wrong date.

## Priority
P1 - not a crash, but a real, reproducible-shaped false negative at the intersection of two
features (Feature 039's group no-reply etiquette and Feature 033's ledger event capture) that
silently drops genuine billable/financial information with zero visible feedback to the user -
same failure class and severity as bugfix-025 (see "Related Work"), but for ledger-relevant
content specifically, which carries real financial consequences (unbilled hours) rather than
just a missed conversational reply.

## Status
Open - root cause investigated during a manual `needs_clarification.jsonl` review pass over a
real production data replay (2026-08-23, item 9/86 of that review). No fix has been designed
or implemented yet. Per Bug-Driven Development (METHODOLOGY.md §VII), next step is human
review/approval of the root cause below before any test-gap analysis or fix design begins.

## Date Opened
2026-08-23

## Reported By
yaronlev171, during the interactive ledger-event review of the AHLedger production player
replay (Feature 043).

## Affected Area
- `apps/denidin-app/config/runtime_constitution.md` - "Group Conversation Etiquette" section
  (the `[[NO_REPLY]]` decision rule) has no carve-out at all for messages that are plainly
  ledger-relevant (client name + matter + amount/hours) even when not explicitly addressed to
  DeniDin by name - the etiquette rule and the ledger-capture rule currently operate as if
  fully independent, with no cross-reference in either direction (the same structural gap
  category CLAUDE.md's "EVERY NEW TOOL-BEARING FEATURE NEEDS EXPLICIT CONSTITUTION BOUNDARIES"
  banner calls out for reminders/Feature 054 - this is the same class of gap, just discovered
  the other way around: content that SHOULD trigger a tool got skipped instead of content that
  shouldn't have triggered one firing anyway).
- `src/handlers/ai_handler.py` - `_finalize_response` / `[[NO_REPLY]]` → `should_reply=False`
  wiring itself is working as designed (the sentinel was deliberately emitted by the model, not
  misparsed by the app) - not itself suspected of a bug.

## Description

Real sequence, found via the player replay's `run_log_20260701_20260819.txt`
(`apps/denidin-app/player_data/`), chat `120363210094632983@g.us` (godfather role), session
`7749c2c1-c330-4514-a6af-76af46770832`:

1. Real export line 1917, `8/2/26, 21:23` - message from אילה 🐣: **"אורית בנימין\nמקורות\nשעתיים"**
   ("Orit Binyamin / Mekorot / two hours") - a plain, unambiguous billable-hours report: client
   name, legal matter, hours worked. No date given, no `@`-mention of anyone else, nothing that
   marks it as addressed to a different person.
2. Dispatched (`[46/569] line=1917 ... status=dispatched, 0 ledger event(s)`) - the model's real
   response was the literal `[[NO_REPLY]]` sentinel:
   ```
   19:10:08 ... _finalize_response: ... output_text='[[NO_REPLY]]'
   19:10:08 ... Stored user message (no-reply sentinel, no assistant message stored) in session ...
   19:10:08 ... No reply sent (should_reply=False, no-reply sentinel)
   ```
   No clarifying question. No `capture_ledger_event` call. No ledger event. The message text
   *was* still persisted into session history (as any user message is), but with no assistant
   turn attached to it at all - functionally invisible to anything downstream that isn't
   re-reading raw session history.
3. The *next day*, `8/3/26, 14:41` - an unrelated image batch (5 photos) arrived. Processing
   that batch, the model - reading back through session history - recalled the prior "שעתיים"
   mention and *this time* attempted to capture it, but with no date attached to either
   message, defaulted `txn_date`/`event_datetime` to the *current* message's date (8/3) rather
   than the date the actual hours claim was made (8/2) - producing `A03082614410` with an
   incorrect date, only caught and corrected by hand during the manual review (see that item's
   entry in `player_data/_review_decisions.jsonl`, item 9/86).

**Two distinct, stacked problems, not one:**
- (a) A message with real ledger-relevant content, addressed to nobody in particular, produced
  neither a clarifying question nor a capture attempt - it was dropped as if the etiquette rule
  and the ledger-capture rule never talk to each other.
- (b) Because the content only got noticed a day later via incidental recall, the resulting
  event's date defaulted to the wrong day - a downstream symptom of (a), not a separate root
  cause.

This is a genuine information-loss risk in a real, financially-consequential path: unlike a
missed conversational reply (bugfix-025's shape), a silently-skipped billable-hours report
means real unbilled work, discoverable only by manual review of raw session history (exactly
how this instance was found) - there's no user-visible signal anything was missed at all.

## Related Work
- `specs/bugfixes/bugfix-025-nickname-not-recognized-as-self-address.md` - same general area
  (Feature 039's `[[NO_REPLY]]` group-addressing mechanism producing a false negative), same
  Open/root-cause-only status, but a different specific trigger (name-nickname ambiguity vs.
  no addressing signal at all for genuinely ledger-relevant content). Worth resolving together
  or at least cross-referencing constitution fixes, since both point at the same underlying
  gap: the etiquette rule has no awareness of what content downstream features actually care
  about.
- CLAUDE.md's "EVERY NEW TOOL-BEARING FEATURE NEEDS EXPLICIT CONSTITUTION BOUNDARIES" banner -
  same structural category of gap (missing cross-reference between a tool-bearing feature and
  another piece of the constitution that can pre-empt it), directionally inverted here (a tool
  that SHOULD have fired didn't, rather than one that shouldn't have fired did).
- `player_data/_review_decisions.jsonl` (item 9/86) and `player_data/events/_originals/
  A03082614410.json` - the real data trail this bug was found from; the date-correction applied
  to `A03082614410` as a result is tracked there, separately from this spec.

## Next Steps (per Bug-Driven Development, METHODOLOGY.md §VII)
1. Human approval of this root cause (this document).
2. Test-gap analysis - what test, if any, currently exercises `[[NO_REPLY]]` against
   ledger-relevant-but-unaddressed content; almost certainly none, given this was found via
   manual data review rather than a failing test.
3. Design a fix - open question, not yet decided: should the etiquette rule gain an explicit
   ledger-relevance carve-out (e.g. "content that states a client/matter/amount is never
   silently no-replied, even if not explicitly addressed - ask instead"), should
   `capture_ledger_event`'s own tool description/constitution section state it applies
   regardless of addressing, or something else. Needs a human design decision, not assumed here.
4. Failing test written, approved, minimal fix implemented, verified.
