`````markdown
<!-------------------------------------------------------------
  This file was copied from
  specs/in-definition/005-mcp-morning-green-receipt/spec.md
  to satisfy speckit toolchain requirements.
-------------------------------------------------------------->


````markdown
# Feature Spec: MCP Integration with Morning Green Receipt

**Feature ID**: 005-mcp-morning-green-receipt  
**Priority**: P2 (Medium)  
**Status**: Planning  
**Created**: January 17, 2026

# Feature artifacts moved to `specs/in-definition/005-mcp-morning-green-receipt/`

This directory previously contained the canonical feature artifacts for `005-mcp-morning-green-receipt`.

To avoid duplication and keep research artifacts authoritative, all feature documents have been consolidated under:

`specs/in-definition/005-mcp-morning-green-receipt/`

Please edit and review files there. The toolchain (`check-prerequisites.sh`) has been updated to accept `in-definition` as a fallback source for automation.

If you want this directory to be the canonical source instead, we can remove these placeholder files and replace them with symlinks to the in-definition copies.
    "morning": {
        "api_key": "PASTE_YOUR_TEST_API_KEY_HERE",
        "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1/",
        "default_currency": "ILS",
        "default_vat_rate": 0.17,
        "token_ttl_seconds": 3600,
        "refresh_before_seconds": 300
    },
    "feature_flags": {
        "enable_morning_integration": false
    }
}
````

Security note: Do not use environment variables to store `api_key` or other secrets. For CI and deployment secrets, use the organization's secret management process and inject the `config/config.json` at deploy time so that the repository never contains live secrets.

`````
