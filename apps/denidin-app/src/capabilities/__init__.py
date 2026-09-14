"""
Domain capabilities for the Dynamic Capability Backbone (Feature 063).

4 subpackages (invoicing/ledger_events/reminders/media_analysis) — write/read stays a
prompt-file/tool-attachment distinction, not a Python package split (research.md R5).
Each subpackage imports its backing manager/extractor from its existing, unmodified
location (`src/managers/...`, `src/handlers/extractors/...`) — REQ-063-03.
"""
