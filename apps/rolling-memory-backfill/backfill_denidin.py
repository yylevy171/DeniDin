"""The backfill tools' own DeniDin (Feature 063, REQ-063-08).

Every DeniDin manager takes the DeniDin object as its only constructor argument and
reads its settings off DeniDin's config. These tools are not the DeniDin app - they
never import ``denidin.py`` (which loads the app's own config at import) - so they
build this minimal stand-in instead, holding only what they use: the config fields
the managers and the nightly roll read, the OpenAI client, and whichever managers
the tool constructs (every other one is None).
"""
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI


@dataclass(frozen=True)
class BackfillConfig:
    """The config fields read by SessionManager / RollMarkerStore / MemoryManager and
    the nightly roll (daily_summary_roll_service)."""
    data_root: str
    memory: Dict[str, Any]
    ai_model: str = ""
    ai_embedding_model: str = ""


def backfill_config(data_root: Path, *, memory: Optional[Dict[str, Any]] = None,
                    ai_model: str = "", ai_embedding_model: str = "") -> BackfillConfig:
    """A BackfillConfig whose storage lives under `data_root` (sessions/, memory/,
    memory_rolls/), whatever storage dirs the target env's own `memory` block names
    (those are its container paths); the rest of `memory` is kept as given."""
    memory_block = copy.deepcopy(memory or {})
    memory_block.setdefault("session", {})["storage_dir"] = str(Path(data_root) / "sessions")
    memory_block.setdefault("longterm", {})["storage_dir"] = str(Path(data_root) / "memory")
    return BackfillConfig(data_root=str(data_root), memory=memory_block,
                          ai_model=ai_model, ai_embedding_model=ai_embedding_model)


class BackfillDeniDin:  # pylint: disable=too-few-public-methods
    """See the module docstring. The tool sets the managers it constructs."""

    def __init__(self, config: BackfillConfig, ai_client: Optional[OpenAI] = None):
        self.config = config
        self.ai_client = ai_client
        self.session_manager: Any = None
        self.roll_marker_store: Any = None
        self.memory_manager: Any = None
