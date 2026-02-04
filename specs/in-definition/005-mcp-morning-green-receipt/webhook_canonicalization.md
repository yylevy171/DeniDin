# Webhook Canonicalization and Verification

Purpose: Provide an unambiguous algorithm for verifying incoming webhooks from Morning/GreenInvoice and prevent replay/falsified requests.

## Expected headers
- `X-Data-Signature`: HMAC-SHA256 digest of the canonicalized JSON payload, encoded as **lowercase hex**.
- `X-Data-Timestamp`: UTC ISO8601 timestamp of the event (e.g. `2026-02-03T12:34:56Z`). Required to mitigate replay attacks.

## Canonicalization algorithm (receiver)
1. Parse the incoming request body as JSON.
2. Re-serialize using UTF-8, no extraneous whitespace, `sort_keys=True`, and `separators=(",",":")`.
3. Use the resulting byte sequence as the message for HMAC-SHA256 using the shared `webhook_secret`.
4. Compare the lowercase hex digest with the `X-Data-Signature` header using a constant-time compare.

## Example (Python)

```py
import json, hmac, hashlib
from datetime import datetime, timezone

def canonicalize(body_bytes: bytes) -> bytes:
    obj = json.loads(body_bytes)
    return json.dumps(obj, separators=(',', ':'), sort_keys=True, ensure_ascii=False).encode('utf-8')

def verify_webhook(body_bytes: bytes, signature_header: str, secret: str, timestamp_header: str, window_seconds: int = 300) -> bool:
    # timestamp freshness
    ts = datetime.fromisoformat(timestamp_header.replace('Z', '+00:00'))
    if abs((datetime.now(timezone.utc) - ts).total_seconds()) > window_seconds:
        return False

    canonical = canonicalize(body_bytes)
    mac = hmac.new(secret.encode('utf-8'), canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac.lower(), signature_header.lower())
```

## Signature encoding
- Provider MUST use lowercase hexadecimal encoding for the HMAC digest. The receiver MUST normalize the header to lowercase before comparison.

## Replay protection
- Enforce `X-Data-Timestamp` freshness within 5 minutes by default. Log and reject out-of-window requests.

## Tests (required)
- Unit tests for canonicalization handling: whitespace differences, key order changes.
- Integration tests with recorded example payloads and known secrets to validate end-to-end verification and replay-window enforcement.

## Notes
- If the provider publishes a different canonicalization or includes `signature_version`, implement that version and provide a compatibility adapter. Document any deviations in `webhook_canonicalization.md`.
