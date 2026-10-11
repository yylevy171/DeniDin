"""This tool's own DeniDin (Feature 063, REQ-063-08).

denidin-app's LedgerEventManager takes the DeniDin object as its only constructor
argument and stores its events under DeniDin's config `{data_root}/events/`. This tool
is not the DeniDin app, so it builds this minimal stand-in instead, holding only what
LedgerEventManager reads: `config.data_root`, and no session_manager (None - the
manager guards for its absence).
"""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LedgerConfig:
    """The one config field LedgerEventManager reads."""
    data_root: str


class LedgerDeniDin:  # pylint: disable=too-few-public-methods
    """See the module docstring."""

    def __init__(self, data_root: str):
        self.config = LedgerConfig(data_root=str(data_root))
        self.session_manager: Any = None
