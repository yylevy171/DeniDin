"""
Morning MCP server connection lookup shared by the legacy AIHandler and the
Feature 063 backbone. Moved out of handlers/ai_handler.py with its body
unchanged - one implementation, used by both paths.
"""
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def resolve_morning_mcp_connection(
    locator, config, correlation_id: str, role,
) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """(server_url, auth_token, mcp_config) for the Morning MCP server, or None
    (logged) when the server is unavailable or the auth token is not configured.
    Logs the REQ-SEC-002 audit line (role, URL host, masked token) on success."""
    server_url = locator.current_server_url()
    if not server_url:
        logger.warning("Morning MCP server unavailable - proceeding without invoicing tools")
        return None

    mcp_config = getattr(config, 'mcp', {}) or {}
    auth_token = mcp_config.get('morning_auth_token')
    if not auth_token:
        logger.warning("mcp.morning_auth_token not configured - proceeding without invoicing tools")
        return None

    masked_token = f"{auth_token[:4]}...{auth_token[-4:]}" if len(auth_token) > 8 else "***"
    logger.info(
        f"Attaching Morning MCP tools for request={correlation_id}, role={role}, "
        f"url_host={server_url.split('/')[2] if '//' in server_url else server_url}, "
        f"token={masked_token}"
    )
    return server_url, auth_token, mcp_config
