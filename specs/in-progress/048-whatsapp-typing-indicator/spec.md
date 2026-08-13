# Feature Specification: WhatsApp Typing Indicator While Processing

**Feature Branch**: `feature/048-whatsapp-typing-indicator`
**Created**: 2026-08-13
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-13 backlog
conversation; run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description: "whatsapp typing dots when processing" — show WhatsApp's native "typing…"
indicator while DeniDin is processing a message (OpenAI call, tool calls, media extraction,
etc.), so the user sees the bot is working instead of silence until the reply lands.

## Notes captured so far

- Mechanism is presumably a Green API presence/typing-indicator endpoint — **not yet
  confirmed**. Per `CONSTITUTION.md`'s "no unverified third-party assumptions" rule, this needs
  an actual Green API call/doc check before any design decision is finalized: does the
  capability exist, what are its start/stop semantics, does it need to be re-sent periodically
  for a long-running turn, etc.
- Open scope questions: applies to all message types or just conversational (text) turns? Does
  it need to stop/reset if the reply ends up being a silent `[[NO_REPLY]]` (Feature 039)?
