"""
The Dynamic Capability Backbone (Feature 063).

New, standalone backbone module (one tool-driven loop: load_capabilities /
unload_capabilities / load_flows / unload_flows / reset_to_backbone attach a capability's prompt AND real tools,
persisted per chat - see contracts/capability-resolution-loop.md) — the one AI implementation,
built by `denidin.py::initialize_app` (Feature 067 removed the legacy AIHandler and the flag).

See specs/repo/features/063-refactor-oversized-handlers/ for the full design
(spec.md, plan.md, research.md, data-model.md, contracts/).
"""
