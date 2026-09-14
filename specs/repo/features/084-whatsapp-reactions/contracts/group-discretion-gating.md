# Contract: Group discretion gating + `runtime_constitution.md` boundaries

## Correction (2026-09-12, discovered during implementation)

The original plan assumed an existing `is_message_addressed_to_bot()`-style predicate could be
extracted from `whatsapp_handler.py`'s group-gating logic and shared with the fast-path hook.
**No such predicate exists.** Feature 039 removed group mention-gating entirely — DeniDin
processes every group message by default (same as 1:1), and the `[[NO_REPLY]]` sentinel is the
model's own *after-the-fact* judgment on whether to reply substantively, not a pre-dispatch gate
anything else can consult. There is nothing to extract.

**Revised design**: the fast-path hook's own classification IS the gate, for both group and 1:1
traffic alike — no separate "addressed to bot" check exists or is added. A message only produces a
fast-path reaction if it matches the media-type check (`imageMessage`/`documentMessage`) or the
action-verb keyword check (`contracts/fast-path-reaction-heuristic.md`, `research.md` R2). Ambient
group banter (two humans chatting, no action verbs, no media) simply never matches either check —
REQ-084-005/SC-003's "zero reactions for ambient group chatter" falls out of the classification
itself, not a dedicated addressing predicate. This is a deliberately narrower, cheaper guarantee
than "detect whether DeniDin is truly being addressed" — it's "detect whether this specific message
looks actionable," which is all the fast-path ever needed and matches what the classification
already had to do regardless of group/1:1.

**What this means for group-chat reactions beyond the fast-path**: the model's own
`react_to_message` tool calls (flips, conversational reactions) are governed entirely by
constitution guidance below — same discretion as any other tool call, no code-level "is this
message addressed to me" gate exists for those either, consistent with how the reply pipeline
itself works (Feature 039: the model decides `[[NO_REPLY]]` on its own for replies; the model
decides whether/how to react on its own for reactions, guided by the same "favor silence in
groups" framing).

**Human review flag**: this is a smaller, more mechanical claim than the original plan assumed
(classification-as-gate rather than a shared, extracted predicate) — worth a quick sanity check
during review that ambient group scenarios in the reaction-judgment pool actually produce zero
fast-path calls, since there is no longer a dedicated, separately-named guard to point to.

## New `runtime_constitution.md` section: `## Reaction Management`

Proposed placement: alongside `## Reminder Management` and `## Ledger Event Querying`, following
their exact when-applies / when-does-NOT-apply / ambiguity-resolution structure.

Draft content (wording refined iteratively via `contracts/reaction-judgment-tuning.md`'s harness,
not settled in a single pass):

```markdown
## Reaction Management — all roles

A native WhatsApp emoji reaction (via the `react_to_message` tool) is a lightweight, reversible
signal — never a substitute for a substantive reply, and never something to reach for out of
uncertainty about what else to do.

### The classics — reach for one of these first, in the large majority of cases
| Emoji | Use it for |
|---|---|
| 👍 | Simple acknowledgment, low-stakes |
| 🫡 | An action command received — "on it" |
| 👀 | A document/media being looked into |
| ✅ | Clean, successful resolution |
| 🎉 | A resolution worth celebrating (a larger win, a milestone) |
| ⚠️ | Resolved, but something needs attention |
| ❌ | Failed or explicitly declined |
| ❓ | Outcome unresolved, needs clarification |
| 🙏 | Reciprocating thanks/gratitude |
| ❤️ | Warmth stronger than a simple thanks warrants |

Reach for one of these ten first. Depart from the list only when a specific occasion makes a
more precise emoji unambiguous (a holiday, a birthday) — if you have to stop and think about
whether the reader will actually recognize it, use a classic instead. Novelty is not the goal;
being understood instantly is.

### When this applies
- A document or media message that starts a multi-step workflow (e.g. a fee agreement upload) —
  an in-flight 👀/🔍/⏳ may already be present from the fast-path; flip it to a terminal ✅/⚠️/❌
  once that workflow actually resolves (ledger capture succeeds, is rejected, or the user
  abandons it).
- An explicit action command (e.g. "create an invoice for...") — flip any in-flight receipt
  reaction to reflect the real outcome (✅/🎉 on success, ⚠️/❓ on validation failure or a blocked
  action) alongside your explanatory reply, never as a replacement for it.
- Warm, personal, non-transactional messages (holiday greetings, thanks, birthdays) — an
  expressive, context-appropriate emoji is a nice, human touch. This is a SHOULD, not a MUST:
  skipping it is never wrong.

### When this does NOT apply — do not call this tool
- Ambient group banter not concerning DeniDin at all (unrelated small talk between other
  participants). There is no code-level filter hiding these from you the way there is for the
  fast-path's own classification — this is your own judgment call, same discretion as deciding
  whether a reply is warranted.
- Trivial 1:1 acknowledgments, routine small talk, or any turn where a reaction would feel forced
  or generic. Favor silence — no reaction is often the more polite choice, exactly as choosing not
  to reply substantively can be. Do not react "just in case" or because a tool happens to be
  available.
- Any other tool-bearing feature's own domain (reminders, ledger events, Morning invoicing) is
  unaffected by this section — reacting to a message is never a substitute for, or a step within,
  those tools' own approval/dispatch flows.

### Resolving ambiguity
Same rule as every other tool-bearing section (see "Contexts of Operation"): when unsure whether a
reaction fits, don't send one — there is no ambiguity-resolution question here that reaching for
this tool answers better than staying silent.
```

## Required cross-references in other sections

Per the CLAUDE.md "every new tool-bearing feature needs explicit constitution boundaries,
cross-referenced everywhere" rule, add a one-line note to each existing tool-bearing section
(`## Reminder Management`, `## Ledger Event Querying`, the Morning MCP sections) stating that
reacting to a message is a separate, independent action from that section's own tools and never a
substitute for them — mirroring the existing "an Invoice Management action is automatically
'Neither'" cross-reference pattern already used elsewhere.

## Testing

No hard-assertion test can verify prose guidance/emoji taste directly — by explicit human decision
(2026-09-12), this feature does NOT use fixed `billed`/`expensive` acceptance scenarios asserting a
specific expected emoji. The fast-path classification's unit/integration tests still hard-assert on
the zero-tolerance group-ambient-silence requirement for the fast-path specifically (that's
deterministic plumbing, not judgment) — there is no separate predicate to test on its own, since
classification IS the gate (see the Correction above). Reaction *quality*, and the model's own
tool-driven reaction/silence decisions in groups, are instead tuned iteratively via
`contracts/reaction-judgment-tuning.md`'s rotating capture harness — see that contract for the
full mechanism.
