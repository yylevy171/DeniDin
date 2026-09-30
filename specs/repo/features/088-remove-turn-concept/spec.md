# Feature Specification: Removing the Concept of a "Turn"

**Feature ID**: 088
**Feature Branch**: `feature/088-remove-turn-concept`
**Created**: 2026-09-30
**Status**: Backlog - not yet clarified/planned
**Category**: Architecture
**Domain**: Backbone (Feature 063)

---

## Executive Summary

Raised during the Feature 063 consolidation/naming session (2026-09-30): the
backbone's model of "one incoming WhatsApp message = one turn,
made up of one or more OpenAI call rounds" was questioned as possibly the
wrong mental model going forward, or as terminology worth re-examining/
retiring. Parked for later dedicated discussion rather than decided inline
during that session - the exact shape of what "removing turn" would mean
(collapsing turn+round into a single concept, redefining turn boundaries
around something other than one inbound WhatsApp message, or something else
entirely) was never clarified.

## Open questions (need a real speckit.specify/.clarify pass, not answered here)

- What specifically is wrong with "turn" as the outer unit (one inbound
  WhatsApp message -> one final reply)? Is the objection to the word itself,
  to there being two distinct concepts (turn vs. round) at all, or to some
  other aspect of how turns are currently bounded/persisted?
- If "turn" goes away, what replaces it as the unit that
  `Session.active_capabilities`/`active_flows` persist across, that
  `capability_reset_service`'s idle timeout measures against, and that
  `resolve_button_tap`'s "any new turn clears the stale-tap guard" rule
  keys off of? These all currently depend on "turn" as a real boundary.
- Does this affect `AIHandler`'s legacy path too, or is it scoped only to
  the backbone's round-based loop?

## Status

Not specified, not clarified, not planned. Do not begin implementation
before a real `speckit.specify` -> `speckit.clarify` pass resolves the
questions above with the human.
