"""Tests for denidin_mcp_morning.errors — friendly error mapping (T015/T016).

Real objects, no mocking. Covers the mapping logic that keeps raw
exceptions/stack traces from reaching MCP callers (CONSTITUTION §X) and
keeps user-facing text Hebrew by default (REQ-I18N-001).
"""
import requests

from denidin_mcp_morning.errors import friendly_error_message, mask_secret
from denidin_mcp_morning.tools import ClientNameNotResolvedError, ClientNotFoundError


def _http_error(status_code: int, body: str = "") -> requests.exceptions.HTTPError:
    """Build a real requests.HTTPError with a real (not mocked) Response."""
    response = requests.Response()
    response.status_code = status_code
    response._content = body.encode("utf-8")
    return requests.exceptions.HTTPError(response=response)


def test_auth_error_401_maps_to_hebrew_auth_message():
    message = friendly_error_message(_http_error(401), "corr-1")
    assert "❌" in message
    assert "Morning" in message


def test_auth_error_403_maps_to_same_auth_message():
    message_401 = friendly_error_message(_http_error(401), "corr-1")
    message_403 = friendly_error_message(_http_error(403), "corr-1")
    assert message_401 == message_403


def test_rate_limit_429_maps_to_hebrew_rate_limit_message():
    message = friendly_error_message(_http_error(429), "corr-1")
    assert "❌" in message


def test_not_found_404_maps_to_hebrew_not_found_message():
    message = friendly_error_message(_http_error(404), "corr-1")
    assert "❌" in message


def test_server_error_5xx_maps_to_hebrew_network_message():
    message = friendly_error_message(_http_error(500), "corr-1")
    assert "❌" in message


def test_generic_4xx_maps_to_hebrew_rejected_message():
    message = friendly_error_message(_http_error(400), "corr-1")
    assert "❌" in message


def test_network_error_without_response_maps_to_hebrew_network_message():
    exc = requests.exceptions.ConnectionError("connection refused")
    message = friendly_error_message(exc, "corr-1")
    assert "❌" in message


def test_value_error_never_echoes_raw_english_text():
    """CONSTITUTION §X + REQ-I18N-001: internal exception text is developer
    detail (logged), not returned verbatim to the caller."""
    exc = ValueError("Unsupported status: 'bogus'. Expected 'paid', 'unpaid', or 'cancelled'.")
    message = friendly_error_message(exc, "corr-1")
    assert "❌" in message
    assert "bogus" not in message
    assert "Unsupported" not in message


def test_client_not_found_error_returns_its_own_specific_message_not_generic_invalid_request():
    """bugfix-028 B4(c), caught 2026-08-12: ClientNotFoundError IS a
    ValueError, so without a dedicated branch ABOVE the generic ValueError
    one, it fell into that generic branch and got replaced with the generic
    "invalid request" text - discarding the specific, actionable "client not
    found" message the exception was raised with, defeating half the point
    of raising it in the first place. Unlike ordinary ValueErrors, this
    message IS meant to reach the caller verbatim - it's already Hebrew,
    user-facing text (format_client_not_found() + the searched name), not
    internal developer detail."""
    exc = ClientNotFoundError("לא נמצא לקוח בשם הזה. (מרדכי קיואן)")
    message = friendly_error_message(exc, "corr-1")
    assert message == str(exc)
    assert "הבקשה אינה תקינה" not in message, (
        "must not fall through to the generic ValueError branch"
    )


def test_client_name_not_resolved_error_returns_its_own_specific_message_not_generic_invalid_request():
    """client-name-resolution architecture fix follow-up (2026-08-12):
    ClientNameNotResolvedError IS a ValueError too, same trap as
    ClientNotFoundError above - needs its own branch ABOVE the generic
    ValueError one, or the specific "call resolve_client_name first"
    procedural text gets discarded in favor of the generic message."""
    exc = ClientNameNotResolvedError(
        "יש לפנות תחילה לכלי resolve_client_name עם שם הלקוח, לוודא שם מדויק "
        "התואם למאוחסן במורנינג, ולקרוא לכלי הזה שוב עם name_resolved=true והשם המדויק שהוחזר."
    )
    message = friendly_error_message(exc, "corr-1")
    assert message == str(exc)
    assert "הבקשה אינה תקינה" not in message, (
        "must not fall through to the generic ValueError branch"
    )


def test_unexpected_exception_returns_generic_hebrew_message():
    message = friendly_error_message(RuntimeError("boom"), "corr-1")
    assert "❌" in message
    assert "boom" not in message


def test_no_message_ever_contains_a_raw_url():
    """Regression: FastMCP's default (unmapped) behavior leaks the Morning API
    URL from the exception string directly to the caller — confirmed live."""
    message = friendly_error_message(
        _http_error(404, body="https://sandbox.d.greeninvoice.co.il/api/v1/documents/x"),
        "corr-1",
    )
    assert "greeninvoice.co.il" not in message


def test_mask_secret_keeps_only_prefix_and_suffix():
    assert mask_secret("6ab47b18-0d57-4d59-9a64-bc8d30aa188d") == "6ab4...188d"


def test_mask_secret_handles_short_values():
    assert mask_secret("abc") == "***"


def test_mask_secret_handles_empty_value():
    assert mask_secret("") == "***"
