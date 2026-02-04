# Canonical Endpoints

This file lists the canonical endpoints for Morning/GreenInvoice used across the spec and implementation. Use these values via `config/config.json` and do not hardcode URLs in implementation code — read them from config at startup.

- Sandbox (testing): `https://sandbox.d.greeninvoice.co.il/api/v1/`
- Production: `https://api.greeninvoice.co.il/api/v1/`

File-upload endpoints (may be on a gateway domain):
- File upload (production gateway): `https://apigw.greeninvoice.co.il/file-upload/v1/url`
- File upload (sandbox): `https://api.sandbox.d.greeninvoice.co.il/file-upload/v1/url`

Cache / lookup endpoints (read-only):
- Cache base: `https://cache.greeninvoice.co.il/`
- Example: `https://cache.greeninvoice.co.il/businesses/v1/occupations?locale=he_IL`

Notes:
- Implementations MUST treat `api_url` from `config/config.json` as the authoritative base URL for API calls.
- Special-purpose gateways (file-upload, cache) may have separate domains; include these as separate config fields if needed (e.g., `file_upload_url`, `cache_api_url`).
- When mocking endpoints in tests, use `config/config.test.json` to point to test fixtures or mock servers.
