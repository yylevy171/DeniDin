# Quickstart — MCP → Morning Integration (local dev)

1. Copy `config/config.example.json` to `config/config.json` and fill the `morning` keys:

```json
{
  "morning": {
    "api_key_id": "<YOUR_API_KEY_ID>",
    "api_key_secret": "<YOUR_API_KEY_SECRET>",
    "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1",
    "token_ttl_seconds": 3600,
    "refresh_before_seconds": 300
  },
  "feature_flags": {
    "enable_morning_integration": true
  }
}
```

2. Install dependencies (virtualenv recommended):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Run tests (skeletons will be added in Phase‑1):

```bash
pytest -q
```

4. Start the MCP service (development):

- If using FastAPI/ASGI:

```bash
uvicorn denidin_mcp_morning.server:app --reload
```

5. Webhook verification example (HMAC SHA256):

```python
import hmac, hashlib

def verify_signature(body_bytes: bytes, header_sig: str, secret: str) -> bool:
    mac = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, header_sig)
```

Notes:
- Keep `config/config.json` out of source control (examples in `config/config.example.json`).
- Feature is gated by `feature_flags.enable_morning_integration` in the config file.
