"""Feature 069 — Phase 11 post-turn-capture billed tests: shared driver.

Split out of the original single `test_e2e_ledger_post_turn_capture.py` (2026-09-04)
so `scripts/run_sanity_parallel.sh` / a plain `pytest -n … --dist loadfile` can
spread the acceptance files across xdist workers (each file pinned to one worker,
per-worker `test_data/<worker>/` isolation via `tests/billed/conftest.py`'s
Feature-075 wiring). This module is helpers only — it defines no test.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID
from tests.billed._ledger_069_acceptance import (
    _answer_bank_for,
    load_manifest,
    reset_manifest_cache,
    seed_scenario,  # noqa: F401 - re-exported: step 1 of every 069 acceptance test
)
from tests.e2e_helpers import (
    converse_until_ledger_events_captured,
    persisted_ledger_events_for_chat,
    wipe_chat_messages_on_disk,
)

logger = logging.getLogger("tests.billed.ledger_069_post_turn")
logger.setLevel(logging.DEBUG)


@pytest.fixture(autouse=True)
def clean_069_chat_history(denidin_app):
    """Every Feature 069 acceptance scenario is self-contained: it seeds its own
    Morning client and drives its own conversation to a single recognition
    verdict. Feature 070 keeps ONE permanent, never-expiring session per chat,
    so without a clean slate a prior test's turns stay in the next test's 1-hour
    post-turn recognition window (`_assemble_recognition_input` anchors the
    window on the newest message, and these tests run seconds apart) - which can
    skew an `assert_no_ledger_event` scenario or a "captured without a question"
    turn count.

    Cleaned before AND after, from the outside only - `wipe_chat_messages_on_disk`
    touches the filesystem (chat index + `session.json` + message files), never
    `SessionManager`. Mirrors `tests/billed/conftest.py`'s own ledger-event /
    reminder wipe fixtures. Imported into every Feature 069 acceptance module
    (billed and expensive) so it applies uniformly; binds to whichever
    `denidin_app` fixture that module defines.
    """
    sessions_dir = denidin_app.ai_handler.session_manager.storage_dir
    reset_manifest_cache()
    wipe_chat_messages_on_disk(sessions_dir, GODFATHER_CHAT_ID)
    yield
    wipe_chat_messages_on_disk(sessions_dir, GODFATHER_CHAT_ID)
    reset_manifest_cache()

SENDER_DATA = {
    "chatId": GODFATHER_CHAT_ID,
    "sender": GODFATHER_CHAT_ID,
    "senderName": "E2E Godfather",
}
FIX_DIR = Path(__file__).parent.parent / "fixtures" / "ledger_069"


def _events_for(denidin_app):
    """The `events_for_chat(chat_id)` callable
    `converse_until_ledger_events_captured` expects, bound to this app - a thin
    partial over the shared `persisted_ledger_events_for_chat` reader."""
    return lambda chat_id: persisted_ledger_events_for_chat(denidin_app, chat_id)


def drive_capture(denidin_app, manifest_name, *, id_prefix, first_text=None,
                  image_reply=None, base_ts=None, max_turns=6):
    """Step 2 of every Feature 069 acceptance test: one post-turn-capture
    conversation, stopping the moment a LedgerEvent lands. Returns
    `(events, transcript, event_epoch)`.

    The client-resolution answer bank is built **here**, from the manifest's
    `resolution.mode` (`_answer_bank_for`) — the test supplies only the
    scenario-specific trigger message. Turn 1 is **exactly one** of:
      - `first_text=` — a plain-text message this driver sends (`base_ts` defaults
        to now).
      - `image_reply=` — an image/document the caller already sent; pass its model
        reply here and its Green API timestamp as `base_ts` (required for media).

    Everything after turn 1 — the client-resolution detour, the real
    mutation-approval gate, the capture check — runs through the one shared
    `converse_until_ledger_events_captured`, so text and media share one loop.
    For `resolution.mode == "exact"` the driver also asserts no detour happened.

    `event_epoch` (data-model.md §3 decision #10): `event_datetime` dates from the
    **completing** message — `base + (completing_turn - 1) * 30`, not the trigger.
    Pass it straight into `assert_ledger_event_matches_manifest(..., trigger_epoch)`.
    `events` is non-empty only when capture happened within `max_turns`.
    """
    from denidin import handle_text_message

    assert (first_text is None) != (image_reply is None), (
        "drive_capture: pass exactly one of first_text / image_reply"
    )
    manifest = load_manifest(manifest_name)
    answer_bank = _answer_bank_for(manifest["resolution"])
    base_epoch = base_ts if base_ts is not None else int(time.time())
    turn1 = (
        {"first_message_text": first_text} if first_text is not None
        else {"pre_sent_first_turn": {"sent": "<image>", "reply": image_reply}}
    )
    events, transcript = converse_until_ledger_events_captured(
        handle_text_message=handle_text_message,
        chat_id=GODFATHER_CHAT_ID,
        answer_bank=answer_bank,
        events_for_chat=_events_for(denidin_app),
        base_timestamp=base_epoch,
        base_id_message=id_prefix,
        sender_data=SENDER_DATA,
        max_turns=max_turns,
        test_logger=logger,
        **turn1,
    )
    for entry in transcript:
        logger.info("TURN %s | sent=%r | reply=%r", entry["turn"], entry["sent"], entry["reply"])
    if manifest["resolution"]["mode"] == "exact":
        assert len(transcript) <= 2, (
            f"{manifest_name}: an exact Morning match must not trigger a resolution "
            f"detour, took {len(transcript)} turn(s): {[t['sent'] for t in transcript]!r}"
        )
    completing_turn = transcript[-1]["turn"] if transcript else 1
    return events, transcript, base_epoch + (completing_turn - 1) * 30
