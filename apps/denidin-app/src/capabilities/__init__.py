"""
Domain capabilities for the Dynamic Capability Backbone (Feature 063).

`toolsets.py` is the single place mapping each CapabilityTag to the real tools
`load_capabilities` attaches (local function tools + the shared Morning MCP entry).
Subpackages (docx/ledger_events/media_analysis/reminders) hold the local tools'
schemas and `dispatch_direct_tool_call` handlers; invoicing/client capabilities
have no Python package - they are Morning MCP tools plus a prompt file only.
Each subpackage imports its backing manager/extractor from its existing, unmodified
location (`src/managers/...`, `src/handlers/extractors/...`) — REQ-063-03.
"""
