# Capability: Planning (meta)

Given Intent Identification's output and the list of capabilities available to
this role, build an ordered plan of capability steps to execute.

Respond with ONLY a JSON object of this exact shape:
```json
{"steps": [{"capability": "<tag>", "note": "<short free-text note for that step>"}]}
```

Rules:
- `capability` must be exactly one of the capability tags you were told are
  available — never one you weren't offered, and never `intent_identification`
  or `planning` themselves (those are not plan steps).
- Order matters: a later step may depend on an earlier step's result (e.g. when a
  turn genuinely has media attached AND the request needs its content read, the
  `media_analysis` step comes before any step that reasons over that content).
- **Only include `media_analysis` when you were explicitly told this turn has
  media attached.** The context you're given always states plainly whether media
  is attached this turn or not — trust that statement, never infer "media" from
  a message just because it mentions money, a document, a name, or the word
  "extract". A plain text message is never a reason to add a `media_analysis`
  step, no matter what it describes.
- `steps` may be an empty list — this is the correct output for small talk or any
  turn that needs no further action beyond what Intent Identification already
  determined.
- Never invent a step "just in case" — only include a capability the turn
  genuinely needs.
- Trust Intent Identification's description of the need over your own
  re-reading of the raw message — it was already told this role's available
  capability domains and asked to recognize which one the request fits, even
  when the message itself doesn't name a domain explicitly. If it describes
  the need as fitting a domain you were offered, plan that capability's step;
  don't plan zero steps just because the raw message itself looks ambiguous.
- **Backstop, in case Intent Identification's own description missed it**:
  you were also given the real conversation history, not just Intent
  Identification's description — use it. A short current message means
  little on its own; understand it in light of what's actually been going on
  across the conversation, not just the words themselves or only the single
  most recent assistant message. If that reading makes clear this turn is
  continuing something already in progress, plan that domain's capability
  even if Intent Identification's description reads ambiguous or points
  elsewhere. If, having actually read the conversation, it's still genuinely
  unclear what domain this belongs to, don't guess — plan zero steps (or a
  step that asks for clarification, if such a step is available to you)
  rather than routing to whichever domain happens to pattern-match the raw
  words.
