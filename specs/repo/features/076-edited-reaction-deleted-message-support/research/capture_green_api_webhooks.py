#!/usr/bin/env python3
"""
Feature 076 — Gate Zero webhook capture.

Polls the REAL dev Green API instance's ReceiveNotification/DeleteNotification
queue and prints every incoming notification VERBATIM, so the exact wire format
of `editedMessage` / `deletedMessage` / `reactionMessage` is observed rather than
inferred from docs (CONSTITUTION.md §"NO UNVERIFIED THIRD-PARTY ASSUMPTIONS").

This is a throwaway research script, host-run, NOT part of the app. It only makes
HTTPS calls to Green API's polling API — it starts no container and touches no
config. It DOES consume+delete notifications from the dev queue, so only run it
while the dev `denidin-app` container is NOT running (otherwise you race it).

Usage:
    python3 specs/repo/features/076-edited-reaction-deleted-message-support/research/capture_green_api_webhooks.py [--seconds 240]

Then, from your phone, in the chat with the dev bot number:
    1. send a text message
    2. edit that message (long-press → Edit)
    3. react to it with an emoji, then remove the reaction
    4. delete it "for everyone"
Every raw notification prints here and is appended to capture.jsonl next to this file.
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[5] / "apps" / "denidin-app"
CONFIG = APP_DIR / "config" / "config.dev.json"
OUT = Path(__file__).resolve().parent / "capture.jsonl"

INTERESTING = {"editedMessage", "deletedMessage", "reactionMessage"}


def _api(base: str, method: str, receipt_id: int | None = None) -> dict | list | None:
    if method == "receiveNotification":
        url = f"{base}/receiveNotification/{TOKEN}?receiveTimeout=5"
        req = urllib.request.Request(url)
    else:  # deleteNotification
        url = f"{base}/deleteNotification/{TOKEN}/{receipt_id}"
        req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw.strip() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=240)
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text())
    global TOKEN
    iid = cfg["green_api_instance_id"]
    TOKEN = cfg["green_api_token"]
    base = f"https://api.green-api.com/waInstance{iid}"

    print(f"Polling dev instance {iid} for {args.seconds}s. Raw notifications -> {OUT}")
    print("Go edit / react / delete a message now.\n", flush=True)

    deadline = time.time() + args.seconds
    seen = 0
    with OUT.open("a") as fh:
        while time.time() < deadline:
            try:
                note = _api(base, "receiveNotification")
            except Exception as e:  # noqa: BLE001 - research script
                print(f"receiveNotification error: {e}", file=sys.stderr, flush=True)
                time.sleep(2)
                continue
            if not note:
                continue
            receipt_id = note["receiptId"]
            body = note["body"]
            fh.write(json.dumps(body, ensure_ascii=False) + "\n")
            fh.flush()
            seen += 1
            type_message = (body.get("messageData") or {}).get("typeMessage")
            marker = "  <<< INTERESTING" if type_message in INTERESTING else ""
            print(f"--- notification #{seen} (receiptId={receipt_id}) "
                  f"typeMessage={type_message}{marker}", flush=True)
            print(json.dumps(body, ensure_ascii=False, indent=2), flush=True)
            print(flush=True)
            try:
                _api(base, "deleteNotification", receipt_id)
            except Exception as e:  # noqa: BLE001
                print(f"deleteNotification({receipt_id}) error: {e}", file=sys.stderr, flush=True)

    print(f"\nDone. {seen} notification(s) captured to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
