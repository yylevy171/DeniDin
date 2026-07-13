"""
Locates the current Morning MCP server URL via a shared status file (Feature 018).

DeniDin never imports apps/morning-mcp-app code or pings the server directly; it only
reads the status file the Morning app publishes when its ngrok tunnel is up. This keeps
the two apps independent (CLAUDE.md: no cross-app imports) while letting DeniDin discover
the current (rotating, free-tier ngrok) tunnel URL for each Responses API call.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class MorningMcpLocator:
    """Resolves the current Morning MCP server URL from a shared status file.

    Never raises to the caller: any failure to read/parse the status file, or a
    stale/missing file, is treated as "server unavailable" so callers can gracefully
    degrade (no MCP tools attached, normal reply) rather than crash (CONSTITUTION §VI).
    """

    def __init__(self, mcp_config: dict):
        """
        Args:
            mcp_config: the AppConfiguration.mcp dict (morning_status_file,
                url_max_age_seconds, ...).
        """
        self._status_file = Path(mcp_config.get('morning_status_file', 'data/morning_mcp_status.json'))
        self._max_age_seconds = mcp_config.get('url_max_age_seconds', 0) or 0

    def current_server_url(self) -> Optional[str]:
        """
        Return the Morning MCP server's current public URL, or None if unavailable.

        Returns:
            The `server_url` from the status file if present, parseable, and fresh
            enough (per `url_max_age_seconds`); otherwise None.
        """
        if not self._status_file.exists():
            logger.warning(f"Morning MCP status file not found: {self._status_file}")
            return None

        try:
            with self._status_file.open('r', encoding='utf-8') as f:
                status = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to read Morning MCP status file {self._status_file}: {e}")
            return None

        if status.get('status') != 'running':
            logger.warning(
                f"Morning MCP server reports status={status.get('status')!r} "
                f"(not 'running'): {self._status_file}"
            )
            return None

        server_url = status.get('server_url')
        if not server_url:
            logger.warning(f"Morning MCP status file missing 'server_url': {self._status_file}")
            return None

        if self._max_age_seconds > 0:
            updated_at_raw = status.get('updated_at')
            if not updated_at_raw:
                logger.warning(f"Morning MCP status file missing 'updated_at' (required for freshness check): {self._status_file}")
                return None
            try:
                updated_at = datetime.fromisoformat(updated_at_raw)
            except ValueError as e:
                logger.warning(f"Morning MCP status file has invalid 'updated_at': {e}")
                return None
            age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
            if age_seconds > self._max_age_seconds:
                logger.warning(
                    f"Morning MCP status file is stale ({age_seconds:.0f}s old, "
                    f"max {self._max_age_seconds}s) - treating server as unavailable"
                )
                return None

        return server_url
