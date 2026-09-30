"""
Local-tool schemas for the Reminders capability (Feature 063). The schemas
themselves live in `src/tool_actions/tool_schemas.py` - one definition shared
with the legacy AIHandler, never a second copy.
"""
from typing import Any, Dict, List

from src.tool_actions.tool_schemas import (  # noqa: F401  (re-exported for this capability's callers)
    CREATE_REMINDER_TOOL, DELETE_REMINDER_TOOL, LIST_REMINDERS_TOOL, MODIFY_REMINDER_TOOL,
)

MODIFY_DELETE_REMINDER_TOOLS: List[Dict[str, Any]] = [MODIFY_REMINDER_TOOL, DELETE_REMINDER_TOOL]
