"""
Local-tool schema for the Ledger Events — Query capability (Feature 063):
`query_ledger_events`. The schema itself lives in `src/tool_actions/tool_schemas.py`
- one definition shared with the legacy AIHandler. Capturing ledger events is not
a capability at all: it is denidin.py's shared post-turn recognition, and
Morning-document-sourced capture is the accounting-reconciliation service's own job.
"""
from src.tool_actions.tool_schemas import QUERY_LEDGER_EVENTS_TOOL  # noqa: F401
