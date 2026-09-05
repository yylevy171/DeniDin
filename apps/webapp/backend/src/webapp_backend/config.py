"""Flat JSON config for webapp-backend (mirrors morning-mcp-app's shape; no env vars)."""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Union

_APP_FIELDS = {
    "environment",
    "denidin_data_root",
    "denidin_src_path",
    "password_hash_file",
    "password_salt",
    "session_expiry_hours",
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
    password_salt: str = "denidin-pw"
    session_expiry_hours: float = 168.0
    denidin_src_path: str = ""
    http: HttpConfig = field(default_factory=HttpConfig)

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
