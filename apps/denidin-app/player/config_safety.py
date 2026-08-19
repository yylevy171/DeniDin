"""
Player config/data-root safety checks (Feature 043, tasks.md T013).

Per contracts/player-cli.md and spec.md's Environment/data-safety: the
player writes to real ledger data, so `--data-root` must always be supplied
explicitly (no default anywhere in code), and a value that resolves to the
literal production default requires an extra, explicit override flag.
"""
from pathlib import Path
from typing import Optional

# Matches AppConfiguration's own dataclass default (models/config.py) - the
# literal basename a real production data_root always ends in.
_PRODUCTION_DATA_ROOT_NAME = "data"


class PlayerSafetyError(Exception):
    """Raised when the player refuses to start due to a safety check
    failure - never silently falls back to a default."""


def validate_data_root(data_root: Optional[str], confirm_production: bool) -> Path:
    """
    Validates a `--data-root` value before the player touches anything.

    Raises PlayerSafetyError (never returns a fallback) if:
    - `data_root` is missing/empty - there is no default, ever.
    - `data_root` resolves to the literal production path (its own name is
      exactly "data", matching AppConfiguration's default) and
      `confirm_production` wasn't explicitly passed.

    Returns the validated Path otherwise (relative or absolute, as given -
    not resolved/made absolute, matching how AppConfiguration.data_root is
    used elsewhere in this codebase).
    """
    if not data_root:
        raise PlayerSafetyError(
            "--data-root is required and has no default - refusing to start. "
            "Pass the target events/sessions/media root explicitly."
        )

    path = Path(data_root)
    if path.name == _PRODUCTION_DATA_ROOT_NAME and not confirm_production:
        raise PlayerSafetyError(
            f"--data-root={data_root!r} resolves to the literal production data "
            f"root name ({_PRODUCTION_DATA_ROOT_NAME!r}) - refusing to start "
            f"without --confirm-production-data-root. This is a deliberate "
            f"safety gate (spec.md's Environment/data-safety), not a bug."
        )

    return path
