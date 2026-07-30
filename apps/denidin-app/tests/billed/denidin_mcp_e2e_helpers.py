"""
Shared helpers for Feature 018 real-API E2E tests: DeniDin (WhatsApp bot) driving
the already-running Morning MCP server over its already-open ngrok tunnel via
OpenAI's Responses API.

These tests assume the test environment is already up:
- apps/morning-mcp-app is already running (./run_morning_mcp.sh) against sandbox
  credentials, with feature_flags.enable_mcp_server=true, mcp.auth_token set, and
  its ngrok tunnel already open (mcp.ngrok_authtoken configured).
- The shared status file (mcp.status_file in the Morning app's config, matching
  mcp.morning_status_file in denidin-app's config) is therefore already populated
  with the live tunnel URL.
Tests do NOT start the Morning server, do NOT start ngrok, and do NOT write the
status file. If the environment is not actually up, `require_live_morning_tunnel`
fails immediately with a clear "no tunnel" message - it does not skip, and it
does not try to bring anything up itself.

App-wall (uncrossable, per explicit user instruction): denidin-app and
morning-mcp-app are two distinct apps that happen to share a repo. This module
never reads morning-mcp-app's config or any other file, and never imports its
code. The only things that connect the two apps are: (1) an out-of-band shared
bearer token, independently configured in each app's own config, and (2) the
shared status file (the documented, intentional integration contract of this
feature - the one deliberate crossing point, not a shortcut). Verification of
tool-call success is done via the real OpenAI Responses API's own `mcp_call`
output (exposed on AIResponse.mcp_calls - see src/handlers/ai_handler.py),
never via Morning's raw REST API or Morning's own credentials.

NO MOCKING anywhere: real webhook -> real router handler -> real OpenAI
Responses API -> real Morning MCP server, over the real tunnel.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from whatsapp_chatbot_python import Notification

logger = logging.getLogger(__name__)

DENIDIN_APP_DIR = Path(__file__).resolve().parents[2]


class NoMorningTunnelError(Exception):
    """Raised when the shared status file reports no live Morning MCP tunnel.

    This means the test environment is not up (Morning server/ngrok tunnel not
    running) - the fix is to start apps/morning-mcp-app (./run_morning_mcp.sh),
    not to retry or mock around it.
    """


def require_live_morning_tunnel(status_file_path: Path, max_age_seconds: int = 0) -> str:
    """Read the shared status file and return the live Morning MCP server URL.

    Mirrors src.handlers.morning_mcp_locator.MorningMcpLocator's freshness logic,
    but FAILS LOUDLY instead of gracefully degrading - these E2E tests require a
    genuinely live environment, so "no tunnel" must surface as an immediate,
    clear test failure rather than a silent skip or a retried startup attempt.

    Raises:
        NoMorningTunnelError: if the status file is missing, unparseable, missing
            `server_url`, or stale (per `max_age_seconds`).
    """
    if not status_file_path.exists():
        raise NoMorningTunnelError(
            f"NO TUNNEL: status file not found at {status_file_path}. "
            f"Start apps/morning-mcp-app first (./run_morning_mcp.sh) with "
            f"feature_flags.enable_mcp_server=true and mcp.ngrok_authtoken configured."
        )

    try:
        status = json.loads(status_file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NoMorningTunnelError(f"NO TUNNEL: failed to read/parse status file {status_file_path}: {exc}") from exc

    if status.get("status") != "running":
        raise NoMorningTunnelError(
            f"NO TUNNEL: Morning MCP server reports status={status.get('status')!r} "
            f"(not 'running') at {status_file_path}. Start apps/morning-mcp-app "
            f"(./run_morning_mcp.sh) with feature_flags.enable_mcp_server=true and "
            f"mcp.ngrok_authtoken configured."
        )

    server_url = status.get("server_url")
    if not server_url:
        raise NoMorningTunnelError(f"NO TUNNEL: status file {status_file_path} has no 'server_url'.")

    if max_age_seconds > 0:
        updated_at_raw = status.get("updated_at")
        if not updated_at_raw:
            raise NoMorningTunnelError(f"NO TUNNEL: status file {status_file_path} missing 'updated_at'.")
        age_seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(updated_at_raw)).total_seconds()
        if age_seconds > max_age_seconds:
            raise NoMorningTunnelError(
                f"NO TUNNEL: status file {status_file_path} is stale "
                f"({age_seconds:.0f}s old, max {max_age_seconds}s) - is the Morning server/tunnel still running?"
            )

    return server_url


def build_text_webhook(chat_id: str, sender_name: str, text: str, message_id: str) -> dict:
    """Build a real Green API incomingMessageReceived webhook event dict for a
    textMessage, matching the shape used by this repo's existing E2E tests."""
    return {
        'typeWebhook': 'incomingMessageReceived',
        'timestamp': int(time.time()),
        'idMessage': message_id,
        'instanceData': {
            'idInstance': 7103000000,
            'wid': '972501234567@c.us',
            'typeInstance': 'whatsapp'
        },
        'senderData': {
            'chatId': chat_id,
            'sender': chat_id,
            'senderName': sender_name
        },
        'messageData': {
            'typeMessage': 'textMessage',
            'textMessageData': {
                'textMessage': text
            }
        }
    }


def create_real_notification(event_dict: dict) -> Notification:
    """Create a real SDK Notification object (no mocking), tracking answer() calls."""
    notification = Notification.__new__(Notification)
    notification.event = event_dict
    notification._test_sent_messages = []

    def track_answer(message):
        notification._test_sent_messages.append(message)
        logger.info(f"Would send to user: {message}")

    notification.answer = track_answer
    return notification


def get_response(notification: Notification) -> Optional[str]:
    return notification._test_sent_messages[0] if notification._test_sent_messages else None
