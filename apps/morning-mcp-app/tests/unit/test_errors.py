"""Tests for denidin_mcp_morning.errors — friendly error mapping (T015/T016).

Real objects, no mocking. Covers the mapping logic that keeps raw
exceptions/stack traces from reaching MCP callers (CONSTITUTION §X) and
keeps user-facing text Hebrew by default (REQ-I18N-001).
"""
import requests

from denidin_mcp_morning.errors import friendly_error_message, mask_secret


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
