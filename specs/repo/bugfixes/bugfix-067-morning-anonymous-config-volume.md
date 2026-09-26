# bugfix-067: morning-mcp-app declares an anonymous `/app/config` volume

**Status**: Done - implemented and verified (image builds with no declared volumes), merging to master. Ships in the next release (version chosen by the human).
**Found via**: verifying prod's mounts after the 0.7.7 deploy (2026-09-26), a follow-up to bugfix-066.

## Problem
`apps/morning-mcp-app/Dockerfile` had `VOLUME ["/app/config"]`. Docker attaches an anonymous volume at that path; `docker compose up -d` reuses it across recreates, so files baked into a newer image under `/app/config` (`config.example.json`, `config.schema.json`) are silently frozen at whatever the volume held when first created. This is the same trap bugfix-062 fixed for `denidin-app` (its Dockerfile's VOLUME is now only `/app/data`, `/app/logs`). In prod the volume's files matched the 0.7.7 image at the time of checking, so nothing was wrong yet.

## Fix
Remove the `VOLUME ["/app/config"]` line. Config other than `config.json` is baked into the image and used as shipped; compose still bind-mounts `config.<env>.json` over `/app/config/config.json`. `/app/logs` is created by `docker-entrypoint.sh` (`mkdir -p /app/logs`).

## Verification
Build the image, confirm no anonymous volume is declared (`docker inspect` Config.Volumes empty) and `/app/config` holds `config.example.json` + `config.schema.json`.
