# Feature Specification: Support Multiple Clients (Godfathers)

**Feature Branch**: `feature/055-multiple-clients-godfathers`
**Created**: 2026-08-16
**Status**: PLACEHOLDER — idea captured only, no scoping done yet. Not ready for
`speckit.clarify`/`speckit.plan`. Requires a full `speckit.specify` pass (Problem Statement,
User Stories with Given-When-Then, Requirements, Terminology, Technology Choices) before any
implementation work starts, per `.github/METHODOLOGY.md`.
**Input**: One-line ask from the user, 2026-08-16: "support multiple clients (godfathers)" —
placeholder only, no further detail given yet.

---

## Placeholder Notes

Today DeniDin's RBAC2 model (`UserManager`, see `apps/denidin-app/CLAUDE.md` / architecture
docs) assumes a single godfather role tier shared across all godfather-level users, without a
notion of a godfather being scoped to — or "owning" — a particular client or set of clients.
This feature is a placeholder for exploring what it means to support **multiple, distinct
clients each with their own godfather(s)** — e.g. whether memory scope, ledger events, Morning
MCP access, and group membership resolution need to become client-scoped rather than global.

No design decisions have been made. Open questions to resolve during `speckit.specify`
include (non-exhaustive, not yet validated with the user):
- Is "client" here the existing `Role.CLIENT` concept, or a new higher-level tenant/account
  concept that a godfather belongs to?
- Can one godfather serve multiple clients, or is it one godfather per client?
- Does memory scoping (`MemoryManager` collections), ledger events
  (`ledger_event_manager.py`), and Morning MCP access need to become per-client-scoped?
- Any impact on `GroupMembershipResolver` (Feature 039) if a WhatsApp group could span
  multiple clients?

**Priority**: TBD — not yet triaged against other backlog items.
