"""mtime-cached reader for one directory of prompt files (one file per tag) -
shared by the capability prompts and the flow prompts, so both hot-reload the
same way and share the same missing-file behaviour."""
import logging
from pathlib import Path
from typing import Callable, Dict

logger = logging.getLogger(__name__)


class MtimePromptCache:
    """`directory` is a callable (the directory may depend on live config).
    A missing file logs a WARNING and returns the last cached content ("" if
    none) - that prompt silently contributes nothing rather than crashing the
    turn (mirrors _load_constitution's fallback pattern)."""

    def __init__(self, kind: str, directory: Callable[[], Path]):
        self._kind = kind
        self._directory = directory
        self._content: Dict[str, str] = {}
        self._mtimes: Dict[str, float] = {}

    def get(self, name: str) -> str:
        path = self._directory() / f"{name}.md"
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            logger.warning("%s prompt file not found for %s at %s", self._kind.capitalize(), name, path)
            return self._content.get(name, "")
        if name not in self._mtimes or mtime != self._mtimes[name]:
            self._content[name] = path.read_text(encoding="utf-8")
            self._mtimes[name] = mtime
        return self._content[name]
