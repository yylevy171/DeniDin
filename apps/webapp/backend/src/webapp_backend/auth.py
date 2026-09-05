"""Password gate + in-memory session-token store (Feature 068).

No per-user accounts: one shared password, hashed ``sha256(salt + password)``, stored as a
single-line hex file an operator writes by hand. Session tokens are opaque, held only in this
process's memory (a restart logs everyone out), and expire on inactivity — ``last_active_at``
is refreshed on every validated request. Concurrent sessions are allowed; one logout never
affects another token.
"""
import hashlib
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Dict, Optional, Union

try:  # apps/denidin-app/src is normally already on sys.path (see webapp_backend/__init__.py)
    from utils.time_utils import now_local
except ImportError:  # pragma: no cover - defensive for odd import orders
    import sys as _sys

    _src = Path(__file__).resolve().parents[4] / "denidin-app" / "src"
    if _src.is_dir() and str(_src) not in _sys.path:
        _sys.path.insert(0, str(_src))
    from utils.time_utils import now_local

_HEX = set("0123456789abcdef")


def hash_password(password: str, salt: str) -> str:
    """``sha256(salt + password)`` as lowercase hex. Comparison is always literal — callers
    must not trim/normalize ``password`` (2026-09-05 decision)."""
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


class PasswordVerifier:
    """Loads the stored hash once at construction. A missing or malformed file is not fatal:
    the backend still starts, ``usable`` is ``False``, and every ``verify()`` returns ``False``
    until the file is fixed (2026-09-05 decision)."""

    def __init__(self, hash_file: Union[str, Path], salt: str) -> None:
        self._salt = salt
        self._expected: Optional[str] = None
        self.load_error: Optional[str] = None
        try:
            raw = Path(hash_file).read_text(encoding="utf-8").strip().lower()
        except FileNotFoundError:
            self.load_error = "password hash file not found"
            return
        except OSError as exc:
            self.load_error = f"password hash file unreadable: {exc}"
            return
        if len(raw) != 64 or any(ch not in _HEX for ch in raw):
            self.load_error = "password hash file is malformed (expected 64 hex chars)"
            return
        self._expected = raw

    @property
    def usable(self) -> bool:
        return self._expected is not None

    def verify(self, submitted: str) -> bool:
        if self._expected is None or not isinstance(submitted, str):
            return False
        return secrets.compare_digest(hash_password(submitted, self._salt), self._expected)


class SessionStore:
    """token -> last_active_at (aware Asia/Jerusalem datetime)."""

    def __init__(self, expiry_hours: float = 168.0) -> None:
        self._expiry = timedelta(hours=expiry_hours)
        self._tokens: Dict[str, "object"] = {}

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = now_local()
        return token

    def check(self, token: Optional[str]) -> str:
        """``"ok"`` (and refreshes last-activity) / ``"expired"`` (and drops it) / ``"unknown"``."""
        if not token or token not in self._tokens:
            return "unknown"
        if now_local() - self._tokens[token] > self._expiry:
            del self._tokens[token]
            return "expired"
        self._tokens[token] = now_local()
        return "ok"

    def validate(self, token: Optional[str]) -> bool:
        return self.check(token) == "ok"

    def invalidate(self, token: str) -> None:
        self._tokens.pop(token, None)

    def __contains__(self, token: object) -> bool:
        return token in self._tokens

    @property
    def active_count(self) -> int:
        return len(self._tokens)
