# Feature Specification: User-Editable Context Memory File

**Feature Branch**: `feature/049-user-editable-context-memory`
**Created**: 2026-08-13
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-13 backlog
conversation; run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description (clarified 2026-08-13): give the user some ability to control memory and
context. Concretely: a text memory file that acts as a dynamic runtime "const" the user can
tweak via chat — viewable, appendable, and deletable-from by the user — which gets included in
the model's context on every prompt from that user, alongside whatever else `AIHandler` already
assembles.

## Notes captured so far

- Conceptually similar in spirit to `config/runtime_constitution.md` (a stable, prepended text
  block) but **per-user** and **user-writable at runtime**, unlike the constitution, which is
  shared, git-tracked, and operator-only.
- Open questions for `speckit.clarify`:
  - Scope: per-user (per phone/entity_id) or per-role (shared across all clients)?
  - Where does it live — a new field under `data/` (per `data_root`), or folded into the
    existing Tier-2 ChromaDB memory system (`memory_manager.py`) rather than a flat file?
  - How does "add/delete" work conversationally — dedicated tool calls the model invokes (like
    `capture_ledger_event`), or a slash-style command DeniDin recognizes in message text?
  - Interaction with prompt caching: the constitution's cacheable-prefix property depends on
    stable, byte-identical content ordered *before* anything dynamic — worth confirming during
    planning whether a per-user editable block needs the same "append after constitution"
    placement as existing dynamic content (recalled memories, date), or breaks caching further.
  - Token budget impact — this adds to every call's context; needs a size cap analogous to
    existing session/memory limits.
