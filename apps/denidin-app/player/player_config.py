"""
PlayerConfig (Feature 043) - loads the player's own startup config file.

Bundles the player-specific settings that stay constant across most runs of
the same replay (which export, which chat, how sender display names map to
phone JIDs, which data root, which denidin AppConfiguration file to reuse
for AI/OpenAI settings) into one JSON file passed as run_player.py's sole
positional argument - keeping "internal denidin config" (config.test.json/
config.dev.json/a future config.player.json - AI/OpenAI/Green
API/memory/etc. settings, none of it player-specific) cleanly separate from
this player-external config.

Genuinely per-invocation settings stay CLI-only, deliberately NOT part of
this file:
- `--start`/`--end`: which date range to replay THIS run - no reason to bake
  one date range into a reusable file.
- `--confirm-production-data-root`: a safety confirmation
  (config_safety.py) that must never persist unattended in a reusable
  file - it exists specifically to force a fresh, deliberate decision every
  single invocation; baking it into a file that gets reused across many
  runs would silently defeat that.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


class PlayerConfigError(Exception):
    """Raised when the player config file is missing/malformed - never
    silently defaults a missing field."""


@dataclass(frozen=True)
class PlayerConfig:
    export_zip: Path
    chat_id: str
    sender_map: Dict[str, str]
    data_root: str
    denidin_config: str


# export_zip/chat_id/data_root/denidin_config have no sensible default and
# must always be present. sender_map may legitimately be empty (a
# single-sender export needs no mapping - see contracts/player-cli.md).
_REQUIRED_FIELDS = ("export_zip", "chat_id", "data_root", "denidin_config")


def load_player_config(path: Path) -> PlayerConfig:
    """Loads and validates a player config JSON file. Raises PlayerConfigError
    (never returns a fallback) if the file is missing, isn't valid JSON, or
    is missing a required field."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except OSError as e:
        raise PlayerConfigError(f"{path}: could not read player config file: {e}") from e
    except json.JSONDecodeError as e:
        raise PlayerConfigError(f"{path}: not valid JSON: {e}") from e

    missing = [field for field in _REQUIRED_FIELDS if not raw.get(field)]
    if missing:
        raise PlayerConfigError(f"{path}: missing required field(s): {', '.join(missing)}")

    return PlayerConfig(
        export_zip=Path(raw["export_zip"]),
        chat_id=raw["chat_id"],
        sender_map=raw.get("sender_map", {}),
        data_root=raw["data_root"],
        denidin_config=raw["denidin_config"],
    )
