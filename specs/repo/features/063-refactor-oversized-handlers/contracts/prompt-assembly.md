# Contract: Backbone + Per-Step Capability Prompt Assembly

**Component**: New module (`src/backbone/orchestrator.py`, R1/R5) — `_load_backbone()` +
`_load_capability_prompt(tag)` + `_build_instructions(active_tag, accumulated_context,
today_timestamp)`. This is **new code**, structurally mirroring `ai_handler.py`'s existing
`_load_constitution`/`_build_instructions` mtime-cache pattern for consistency, but implemented in
the new orchestrator module. `ai_handler.py`'s own `_load_constitution`/`_build_instructions` are
not touched, not extended, not parameterized — they keep loading `config/runtime_constitution.md`
exactly as today (REQ-063-07).

## `_load_backbone()` (new, structurally mirrors `ai_handler.py::_load_constitution`)
- Loads `config/prompts/backbone.md` via the same mtime-cache approach `_load_constitution`
  already uses, reimplemented in the new module.

## `_load_capability_prompt(tag: CapabilityTag) -> str` (new)
- Resolves `Path(base_dir) / prompts_dir / capabilities_dir / f"{tag}.md"`.
- Independent mtime cache per tag (a dict keyed by tag, mirroring today's single
  `self._constitution_mtime` scalar generalized to `self._capability_mtimes: Dict[str, float]`).
- Missing file: log WARNING, return `""` (that capability silently contributes nothing rather
  than crashing the turn) — mirrors `_load_constitution`'s existing "file not found → fallback"
  pattern.

## `_build_instructions(active_tag, accumulated_context, today_timestamp)` (new, per-call, not per-turn)
Mirrors `ai_handler.py::_build_instructions`'s existing fixed assembly order/shape, reimplemented
for the orchestration loop's per-step calls (`contracts/orchestration-loop.md`):

```
instructions = backbone_content
             + load_capability_prompt(active_tag)     # exactly ONE capability per call
             + accumulated_context                     # prior steps' results this turn, if any
             + "---"
             + today_date
```

`active_tag` is always exactly one of the 9 `CapabilityTag`s (Intent Identification, Planning, or
one domain capability) — never a union of several, unlike the original (superseded) multi-plugin
design. This is what gives REQ-063-06's cache-prefix property its strength (`research.md` R3):
`backbone_content + load_capability_prompt(tag)` is a **fixed, small set of possible prefixes**
(1 Backbone × 9 capabilities = 9 distinct byte-stable prefixes total, system-wide), so any two
calls anywhere in the system using the same `active_tag` share a cache hit on that prefix,
regardless of which turn/conversation/plan they belong to — not just within one turn's own
matched-capability-set as the original design would have given.

## Legacy path (flag off)
`ai_handler.py::_build_instructions` runs exactly as it does today —
`instructions = runtime_constitution.md content + memory_context + "---" + today_date` — because
it is the same, unmodified code and unmodified file; this new module's `_build_instructions` is
never invoked at all when the flag is off (`denidin.py` never constructs the new orchestrator in
that case, per REQ-063-07/R1).
