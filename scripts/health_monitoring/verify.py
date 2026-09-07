#!/usr/bin/env python3
"""Single source of truth for "is this app's /health endpoint actually
healthy" (bugfix-043, 2026-09-07 revision).

HTTP 200 alone is NOT enough to determine healthy. Both apps' /health
handlers already parse their own internal per-check results into a JSON
body (`{"status": "ok"|"fail", "<check_name>": "success"|"fail", ...}`)
and set 200/503 accordingly - but the prober used to check only the
transport-level status code and threw the body away entirely, so its own
log had no record of *which* check failed, only that the app overall
wasn't healthy. Here the body is always fetched and parsed, and `status`
is the actual source of truth - a non-200/unparseable/unreachable response
is still treated as unhealthy exactly as before, it's just no longer the
ONLY thing checked.

Used two ways, both against this one implementation - no separate shell
wrapper in between either path (2026-09-07 revision - an earlier version of
this fix had a verify_healthy.sh CLI wrapper; removed, both callers below
now invoke this file directly):
  - Imported directly, in-process, by prober.py (a plain Python import,
    since both live in the same directory - Python always puts the invoked
    script's own directory on sys.path[0], so no path hacks are needed).
  - Invoked as a standalone CLI, directly (`python3 verify.py ...`), by
    scripts/run_all_and_verify_healthy.sh's post-start polling loop.

Every single check attempt - success or failure alike - is logged to
--log-file (when given) as two lines: one right before the request
("checking app=<name>"), one right after with the full, raw reply -
HTTP status code, or the exact error (URLError/HTTPError/etc. with its
real message) if the request never completed. Nothing is summarized away;
whatever came back (or whatever failed) is what gets written, since this
log is what a human actually reads to find out *why* a check failed - the
prober's own JSON decision log only ever recorded a flat success/fail.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

PROBE_TIMEOUT_SECONDS = 10.0


def _log(log_file: Optional[Path], message: str) -> None:
    if log_file is None:
        return
    log_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def fetch_health_body(
    url: str,
    timeout: float = PROBE_TIMEOUT_SECONDS,
    *,
    log_file: Optional[Path] = None,
    app_name: Optional[str] = None,
) -> Optional[dict]:
    """Returns the parsed JSON body of a /health response, or None if the
    request failed at any layer (transport, non-200, or a body that isn't
    a JSON object) - a None here always means "treat as unhealthy",
    regardless of which layer actually failed.

    When log_file is given, logs the attempt and its full raw outcome -
    see module docstring."""
    _log(log_file, f"checking app={app_name}")

    reply_summary: str
    body: Optional[dict] = None
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = response.status
            raw = response.read()
        raw_text = raw.decode("utf-8", errors="replace")
        if status != 200:
            reply_summary = f"HTTP {status} body={raw_text}"
        else:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                reply_summary = f"HTTP {status} body={raw_text!r} (JSON parse error: {exc})"
            else:
                if isinstance(parsed, dict):
                    body = parsed
                    reply_summary = f"HTTP {status} body={raw_text}"
                else:
                    reply_summary = f"HTTP {status} body={raw_text!r} (not a JSON object)"
    except urllib.error.HTTPError as exc:
        # HTTPError is raised (not returned) for a non-2xx/3xx status, but it
        # still carries a real status code + body worth logging in full.
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - logging path, must never itself raise
            err_body = "<unreadable>"
        reply_summary = f"HTTPError {exc.code}: {exc.reason} body={err_body}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reply_summary = f"{type(exc).__name__}: {exc}"

    _log(log_file, f"got reply: {reply_summary}")
    return body


def is_healthy_body(body: Optional[dict]) -> bool:
    """True iff the parsed /health body's own `status` field says `"ok"` -
    this, not the HTTP status code, is the actual source of truth."""
    return isinstance(body, dict) and body.get("status") == "ok"


def probe_health(
    url: str,
    timeout: float = PROBE_TIMEOUT_SECONDS,
    *,
    log_file: Optional[Path] = None,
    app_name: Optional[str] = None,
) -> bool:
    """Convenience boolean wrapper composing fetch_health_body +
    is_healthy_body - kept as the simple True/False entry point most
    callers (prober.py's run_once) actually want."""
    return is_healthy_body(fetch_health_body(url, timeout=timeout, log_file=log_file, app_name=app_name))


def _check_one(name: str, url: Optional[str], timeout: float, log_file: Optional[Path]) -> bool:
    if not url:
        return True  # not configured for this run - nothing to report as failed
    body = fetch_health_body(url, timeout=timeout, log_file=log_file, app_name=name)
    ok = is_healthy_body(body)
    print(f"{name}: {'ok' if ok else 'fail'} body={json.dumps(body)}")
    return ok


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-shot health verification for denidin-app and/or morning-mcp-app - "
                     "exits 0 iff every URL passed reports healthy, non-zero otherwise. This is "
                     "what scripts/run_all_and_verify_healthy.sh's polling loop invokes directly."
    )
    parser.add_argument("--denidin-health-url")
    parser.add_argument("--morning-health-url")
    parser.add_argument("--timeout", type=float, default=PROBE_TIMEOUT_SECONDS)
    parser.add_argument("--log-file", type=Path, help="Append every check attempt + its full raw reply here")
    args = parser.parse_args(argv)

    if not args.denidin_health_url and not args.morning_health_url:
        parser.error("at least one of --denidin-health-url / --morning-health-url is required")

    denidin_ok = _check_one("denidin", args.denidin_health_url, args.timeout, args.log_file)
    morning_ok = _check_one("morning", args.morning_health_url, args.timeout, args.log_file)
    return 0 if (denidin_ok and morning_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
