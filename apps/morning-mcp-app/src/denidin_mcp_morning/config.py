"""Configuration loading and validation for the Morning MCP server.

Reads a flat config/config.json (schema: config/config.schema.json) — no
environment variables are read anywhere in this module, per CONSTITUTION.md §I.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json
import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "config.schema.json"


class ConfigError(Exception):
    """Raised when config/config.json is missing, malformed, or fails schema validation."""


@dataclass(frozen=True)
class TenantMorningCredentials:
    """One tenant's own Morning API credentials + MCP bearer token (Feature 055
    Phase 6, REQ-CAP-006/contracts/invoicing-capability.md) - "own Morning
    account" means own credentials/audit trail, not a separate server/tunnel.

    Additive: an empty `tenants` list on `MorningMCPConfig` (today's shape,
    every existing config.<env>.json) preserves the original single-shared-
    account behavior exactly (REQ-PARITY-001) - this dataclass and everything
    that reads it only comes into play once a config file actually lists at
    least one tenant.
    """

    tenant_id: str
    api_key_id: str
    api_key_secret: str
    mcp_auth_token: str


@dataclass(frozen=True)
class MorningMCPConfig:
    """Typed, validated configuration for the Morning MCP server."""

    api_key_id: str
    api_key_secret: str
    api_url: str
    # Feature 053: the OAuth2 token endpoint's host - genuinely different from
    # api_url (see auth.py's docstring), so it's its own required, explicit
    # config field, never derived from api_url.
    auth_url: str
    # Which environment this container/process IS. Read by watchdog.py
    # against shared/active_env.json to detect a stale/mismatched container
    # (2026-07-21 incident). 'dev', 'prod', or 'test'.
    environment: Optional[str]
    default_currency: str
    default_vat_rate: float
    refresh_before_seconds: int
    rate_limit_per_second: float
    # Feature 038: max estimated tiktoken (o200k_base) size of list_invoices'
    # formatted reply before it's truncated to a best-effort prefix. Default
    # (2500) matches the observed practical MCP tool-call output limit -
    # config-driven, not a hardcoded constant, so raising it later (or
    # lowering it for a specific test - MorningMCPConfig is a plain
    # dataclass, so test code can construct/replace() its own instance) is a
    # config change, never a code change.
    list_invoices_token_budget: int
    mcp_server_name: str
    mcp_host: str
    mcp_port: int
    mcp_transport: str
    mcp_log_level: str
    mcp_auth_token: Optional[str]
    mcp_ngrok_authtoken: Optional[str]
    mcp_ngrok_domain: Optional[str]
    mcp_status_file: Optional[str]
    openai_api_key: Optional[str]
    enable_mcp_server: bool
    # Feature 055 Phase 6 (REQ-CAP-006): additive, empty by default. Non-empty
    # switches the server from one shared secret/account to a per-tenant token
    # map + per-tenant MorningClient (see server.py's create_server/
    # build_asgi_app).
    tenants: Tuple[TenantMorningCredentials, ...] = field(default_factory=tuple)


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

    tenants_raw = raw.get("tenants") or []
    seen_tenant_ids: Dict[str, str] = {}
    seen_tokens: Dict[str, str] = {}
    tenants: List[TenantMorningCredentials] = []
    for entry in tenants_raw:
        tenant_id = entry["tenant_id"]
        mcp_auth_token = entry["mcp_auth_token"]
        # contracts/invoicing-capability.md's "Tenant Config PROVIDES" clause:
        # one mcp_auth_token per tenant, unique across all tenants in this
        # environment, enforced at config-load time - two tenants sharing a
        # token would silently merge their invoicing access, a config error,
        # never a valid state.
        if mcp_auth_token in seen_tokens:
            raise ConfigError(
                f"Config file has duplicate tenant mcp_auth_token, shared between "
                f"tenants {seen_tokens[mcp_auth_token]!r} and {tenant_id!r} ({path}) - "
                "each tenant must have its own unique token"
            )
        if tenant_id in seen_tenant_ids:
            raise ConfigError(f"Config file lists tenant_id {tenant_id!r} more than once ({path})")
        seen_tokens[mcp_auth_token] = tenant_id
        seen_tenant_ids[tenant_id] = mcp_auth_token
        tenants.append(
            TenantMorningCredentials(
                tenant_id=tenant_id,
                api_key_id=entry["api_key_id"],
                api_key_secret=entry["api_key_secret"],
                mcp_auth_token=mcp_auth_token,
            )
        )

    return MorningMCPConfig(
        api_key_id=raw["api_key_id"],
        api_key_secret=raw["api_key_secret"],
        api_url=raw["api_url"],
        auth_url=raw["auth_url"],
        environment=raw.get("environment") or None,
        default_currency=raw.get("default_currency", "ILS"),
        default_vat_rate=raw.get("default_vat_rate", 0.17),
        refresh_before_seconds=raw.get("refresh_before_seconds", 300),
        rate_limit_per_second=raw.get("rate_limit_per_second", 3),
        list_invoices_token_budget=raw.get("list_invoices_token_budget", 2500),
        mcp_server_name=mcp_section.get("server_name", "denidin-morning"),
        mcp_host=mcp_section.get("host", "127.0.0.1"),
        mcp_port=mcp_section.get("port", 8000),
        mcp_transport=mcp_section.get("transport", "streamable-http"),
        mcp_log_level=mcp_section.get("log_level", "INFO"),
        mcp_auth_token=mcp_section.get("auth_token") or None,
        mcp_ngrok_authtoken=mcp_section.get("ngrok_authtoken") or None,
        mcp_ngrok_domain=mcp_section.get("ngrok_domain") or None,
        mcp_status_file=mcp_section.get("status_file") or None,
        openai_api_key=raw.get("openai_api_key") or None,
        enable_mcp_server=feature_flags.get("enable_mcp_server", False),
        tenants=tuple(tenants),
    )
