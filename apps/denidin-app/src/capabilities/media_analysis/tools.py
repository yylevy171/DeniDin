"""Tool schema for the Media Analysis capability (Feature 063, 2026-09-24)."""
from typing import Any, Dict

ANALYZE_MEDIA_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "analyze_media",
    "description": (
        "Reads the image/PDF/DOCX the user attached to THIS turn (real vision/"
        "document extraction) and returns its extracted text plus a document "
        "analysis. Takes no arguments - it always analyzes this turn's attached "
        "media. Returns a message saying so if nothing is attached."
    ),
    "strict": True,
    "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
}
