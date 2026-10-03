"""The webapp's own DeniDin (Feature 063, REQ-063-08).

Every DeniDin manager takes the DeniDin object as its only constructor argument and
reads its settings off DeniDin's config. The webapp is a read-only viewer, not the
DeniDin app, so it builds this minimal stand-in holding only what the managers it
reuses read: ``config.data_root``. It has no SessionManager - LedgerEventManager uses
one only to back-link newly persisted events, which the webapp never does.
"""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WebappConfig:
    """The one config field the reused managers read."""
    data_root: str


class WebappDeniDin:  # pylint: disable=too-few-public-methods
    """See the module docstring."""

    def __init__(self, data_root: str) -> None:
        self.config = WebappConfig(data_root=str(data_root))
        self.session_manager: Any = None
