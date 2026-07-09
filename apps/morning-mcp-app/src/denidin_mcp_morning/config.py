"""Configuration loading and validation for the Morning MCP server.

Reads a flat config/config.json (schema: config/config.schema.json) — no
environment variables are read anywhere in this module, per CONSTITUTION.md §I.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import json
import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "config.schema.json"


class ConfigError(Exception):
    """Raised when config/config.json is missing, malformed, or fails schema validation."""


@dataclass(frozen=True)
class MorningMCPConfig:
    """Typed, validated configuration for the Morning MCP server."""

    api_key_id: str
    api_key_secret: str
    api_url: str
    default_currency: str
    default_vat_rate: float
    token_ttl_seconds: int
    refresh_before_seconds: int
    rate_limit_per_second: float
    mcp_server_name: str
    mcp_host: str
    mcp_port: int
    mcp_transport: str
    mcp_log_level: str
    mcp_auth_token: Optional[str]
    mcp_ngrok_authtoken: Optional[str]
    mcp_ngrok_domain: Optional[str]
    enable_mcp_server: bool


def _load_schema() -> Dict[str, Any]:
    if not _SCHEMA_PATH.exists():
        raise ConfigError(f"Config schema not found: {_SCHEMA_PATH}")
    with _SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


def load_config(path: Path) -> MorningMCPConfig:
    """Load and validate a flat config.json into a typed MorningMCPConfig.

    Args:
        path: Path to the config JSON file (e.g. config/config.json).

    Returns:
        A validated MorningMCPConfig with defaults applied for optional fields.

    Raises:
        ConfigError: if the file is missing, not valid JSON, or fails schema validation.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as config_file:
            raw: Dict[str, Any] = json.load(config_file)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file is not valid JSON: {path}") from exc

    schema = _load_schema()
    try:
        jsonschema.validate(raw, schema)
    except jsonschema.ValidationError as exc:
        raise ConfigError(f"Config file failed schema validation ({path}): {exc.message}") from exc

    mcp_section = raw.get("mcp") or {}
    feature_flags = raw.get("feature_flags") or {}

    return MorningMCPConfig(
        api_key_id=raw["api_key_id"],
        api_key_secret=raw["api_key_secret"],
        api_url=raw["api_url"],
        default_currency=raw.get("default_currency", "ILS"),
        default_vat_rate=raw.get("default_vat_rate", 0.17),
        token_ttl_seconds=raw.get("token_ttl_seconds", 3600),
        refresh_before_seconds=raw.get("refresh_before_seconds", 300),
        rate_limit_per_second=raw.get("rate_limit_per_second", 3),
        mcp_server_name=mcp_section.get("server_name", "denidin-morning"),
        mcp_host=mcp_section.get("host", "127.0.0.1"),
        mcp_port=mcp_section.get("port", 8000),
        mcp_transport=mcp_section.get("transport", "streamable-http"),
        mcp_log_level=mcp_section.get("log_level", "INFO"),
        mcp_auth_token=mcp_section.get("auth_token") or None,
        mcp_ngrok_authtoken=mcp_section.get("ngrok_authtoken") or None,
        mcp_ngrok_domain=mcp_section.get("ngrok_domain") or None,
        enable_mcp_server=feature_flags.get("enable_mcp_server", False),
    )
