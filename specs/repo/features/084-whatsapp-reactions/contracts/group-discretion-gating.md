# Contract: Group discretion gating + `runtime_constitution.md` boundaries

## `is_message_addressed_to_bot()` predicate

**Location**: extracted into a small, standalone function (proposed home:
`src/handlers/whatsapp_handler.py`, alongside the existing group-handling logic it's extracted
from), reused by:
1. The fast-path pre-dispatch hook (`contracts/fast-path-reaction-heuristic.md`), to guarantee
   **zero** Green API reaction calls for ambient group messages (REQ-084-005, SC-001).
2. Whatever existing logic already determines group-turn engagement today (Feature 039's
   etiquette model — DeniDin is addressed by default in a group, same as 1:1, and the model's own
   `[[NO_REPLY]]` sentinel judgment governs substantive replies).

**Why extract rather than duplicate**: REQ-084-005 requires the *reaction* gate to precisely match
"messages that are actively processed by DeniDin" — if this were reimplemented as a second,
independent string/heuristic check, the two could silently drift apart over time (a message the
reply-gate would answer but the reaction-gate misses, or vice versa), which is exactly the failure
mode SC-003 ("zero reaction webhooks... for ignored ambient group chat messages") exists to
prevent. A single shared predicate makes drift structurally impossible rather than something to
catch in review.

**Human review flag**: extracting and repurposing existing group-gating logic for a second purpose
is exactly the kind of refactor that deserves explicit human sign-off before being trusted, per this
plan's own "Human decisions flagged for later" — a subtle regression here fails silently (nothing
crashes; SC-003 is just quietly violated) and would only surface as an unwanted reaction in a real
group chat.

**Note**: this predicate answers "is DeniDin engaged with this specific message" — it is
*independent* of whether the model ultimately decides to reply substantively (the `[[NO_REPLY]]`
sentinel) or whether it decides to react at all (User Story 5's 1:1 discretion, governed by
constitution guidance below, not this predicate). The predicate only needs to be correct about
group-addressing; 1:1 discretion is handled entirely downstream, by the model.

## New `runtime_constitution.md` section: `## Reaction Management`

Proposed placement: alongside `## Reminder Management` and `## Ledger Event Querying`, following
their exact when-applies / when-does-NOT-apply / ambiguity-resolution structure.

Draft content (final wording subject to the same human review other tool-bearing sections got):

```markdown
## Reaction Management — all roles

A native WhatsApp emoji reaction (via the `react_to_message` tool) is a lightweight, reversible
signal — never a substitute for a substantive reply, and never something to reach for out of
uncertainty about what else to do.

### When this applies
- A document or media message that starts a multi-step workflow (e.g. a fee agreement upload) —
  an in-flight reaction may already be present from the fast-path; flip it to a terminal ✅/⚠️/❌
  once that workflow actually resolves (ledger capture succeeds, is rejected, or the user
  abandons it).
- An explicit action command (e.g. "create an invoice for...") — flip any in-flight receipt
  reaction to reflect the real outcome (✅ on success, ⚠️/❓ on validation failure or a blocked
  action) alongside your explanatory reply, never as a replacement for it.
- Warm, personal, non-transactional messages (holiday greetings, thanks, birthdays) — an
  expressive, context-appropriate emoji is a nice, human touch. This is a SHOULD, not a MUST:
  skipping it is never wrong.

### When this does NOT apply — do not call this tool
- Any message in a group chat that this predicate/etiquette already determined DeniDin is not
  actually engaging with (ambient banter, a message clearly addressed to someone else) — this is
  enforced at the code level before you ever see such a message as needing a reaction decision,
  but never call `react_to_message` retroactively on such a message either.
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

No automated test can verify prose guidance directly; covered indirectly by the billed
conversational scenarios in `quickstart.md` (holiday greeting → creative emoji; trivial 1:1 "ok" →
no forced reaction) and by the code-level `is_message_addressed_to_bot()` unit/integration tests
covering the hard, zero-tolerance group-ambient-silence requirement.
