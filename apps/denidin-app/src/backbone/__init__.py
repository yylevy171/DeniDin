"""
The Dynamic Capability Backbone (Feature 063).

New, standalone orchestrator module — selected at startup by
`denidin.py::initialize_app` only when `config.feature_flags['enable_capability_backbone']`
is true. Never imported by, and never imports from, `src/handlers/ai_handler.py`
(REQ-063-07: the legacy path stays byte-for-byte untouched for as long as the flag exists).

See specs/repo/features/063-refactor-oversized-handlers/ for the full design
(spec.md, plan.md, research.md, data-model.md, contracts/).
"""
