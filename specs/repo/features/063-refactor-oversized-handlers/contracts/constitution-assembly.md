# Contract: Backbone + Capability Plugin Constitution Assembly

**Component**: New module (`src/backbone/orchestrator.py`, R1/R5) — `_load_backbone()` +
`_load_capability_plugin(tag)` + `_build_instructions()`. This is **new code**, structurally
mirroring `ai_handler.py`'s existing `_load_constitution`/`_build_instructions` mtime-cache
pattern for consistency, but implemented in the new orchestrator module. `ai_handler.py`'s own
`_load_constitution`/`_build_instructions` are not touched, not extended, not parameterized —
they keep loading `config/runtime_constitution.md` exactly as today (REQ-063-07).

## `_load_backbone()` (new, structurally mirrors `ai_handler.py::_load_constitution`)
- Loads `config/backbone.md` (a new, separate file from `runtime_constitution.md`) via the same
  mtime-cache approach `_load_constitution` already uses, reimplemented in the new module.

## `_load_capability_plugin(tag: CapabilityTag) -> str` (new)
- Resolves `Path(base_dir) / capabilities_dir / f"{tag}.md"`.
- Independent mtime cache per tag (a dict keyed by tag, mirroring today's single
  `self._constitution_mtime` scalar generalized to `self._capability_mtimes: Dict[str, float]`).
- Missing file: log WARNING, return `""` (that plugin silently contributes nothing rather than
  crashing the turn) — mirrors `_load_constitution`'s existing "file not found → fallback" pattern.

## `_build_instructions(backbone, effective_capabilities, today_timestamp)` (new, in the new orchestrator)
Mirrors `ai_handler.py::_build_instructions`'s existing fixed assembly order/shape, reimplemented
in the new module with the constitution argument becoming a composite:

```
instructions = backbone_content
             + "".join(load_capability_plugin(tag) for tag in CANONICAL_ORDER
                        if tag in effective_capabilities)
             + memory_context   (unchanged position)
             + "---"            (unchanged)
             + today_date       (unchanged position, computed fresh per call)
```

`CANONICAL_ORDER` is the fixed 6-tuple from `data-model.md`'s `CapabilityTag` table — never
re-sorted by classifier output order or request recency, so REQ-063-06's cache-prefix property
holds: any two turns with the same `effective_capabilities` set produce a byte-identical
`backbone_content + plugins` block.

## Legacy path (flag off)
`ai_handler.py::_build_instructions` runs exactly as it does today —
`instructions = runtime_constitution.md content + memory_context + "---" + today_date` — because
it is the same, unmodified code and unmodified file; this new module's `_build_instructions` is
never invoked at all when the flag is off (`denidin.py` never constructs the new orchestrator in
that case, per REQ-063-07/R1).
