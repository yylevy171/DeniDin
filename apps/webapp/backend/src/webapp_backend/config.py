"""Flat JSON config for webapp-backend (mirrors morning-mcp-app's shape; no env vars)."""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Union

# NOTE: the password salt is NOT config — it's hardcoded in auth.PASSWORD_SALT (it is not a
# secret and changing it invalidates every password.hash). A stray "password_salt" key in a
# config file is simply ignored.
_APP_FIELDS = {
    "environment",
    "denidin_data_root",
    "denidin_src_path",
    "password_hash_file",
    "session_expiry_hours",
    "clients_data_root",
    "morning_api_key_id",
    "morning_api_key_secret",
    "morning_auth_url",
    "morning_api_url",
}


@dataclass
class HttpConfig:
    host: str = "0.0.0.0"
    port: int = 8100
    log_level: str = "INFO"


@dataclass
class AppConfig:
    environment: str
    password_hash_file: str
    denidin_data_root: str
    session_expiry_hours: float = 168.0
    denidin_src_path: str = ""
    # Feature 087 (Clients tab): environment-scoped state root, defaulting under
    # denidin_data_root unless overridden. Own Morning API credentials — a second,
    # independently-configured credential set for the same Morning account (see
    # research.md "Resolved: Morning client-list fetch shape").
    clients_data_root: str = ""
    morning_api_key_id: str = ""
    morning_api_key_secret: str = ""
    morning_auth_url: str = ""
    morning_api_url: str = "https://api.greeninvoice.co.il/api/v1"
    http: HttpConfig = field(default_factory=HttpConfig)

    def __post_init__(self) -> None:
        if not self.clients_data_root:
            self.clients_data_root = str(Path(self.denidin_data_root) / "clients")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        http = HttpConfig(**{k: v for k, v in (data.get("http") or {}).items()
                             if k in {"host", "port", "log_level"}})
        known = {k: v for k, v in data.items() if k in _APP_FIELDS}
        return cls(http=http, **known)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "AppConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def validate(self) -> None:
        if not self.environment:
            raise ValueError("config.environment is required")
        if not self.password_hash_file:
            raise ValueError("config.password_hash_file is required")
        if self.session_expiry_hours <= 0:
            raise ValueError("config.session_expiry_hours must be positive")
