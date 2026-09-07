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
from tests.billed._ledger_069_acceptance import ledger_events_for_chat
from tests.e2e_helpers import converse_until_ledger_events_captured, reset_chat_session

logger = logging.getLogger("tests.billed.ledger_069_post_turn")
logger.setLevel(logging.DEBUG)


@pytest.fixture(autouse=True)
def reset_069_chat(denidin_app):
    """Every Feature 069 acceptance scenario is self-contained: it seeds its own
    Morning client and drives its own conversation to a single recognition
    verdict. Feature 070 keeps ONE permanent, never-expiring session per chat,
    so without an explicit reset a prior test's turns stay in the next test's
    1-hour post-turn recognition window (`_assemble_recognition_input` anchors
    the window on the newest message, and these tests run seconds apart) - which
    can skew an `assert_no_ledger_event` scenario or a "captured without a
    question" turn count.

    Reset before AND after, mirroring `tests/billed/conftest.py`'s own
    ledger-event / reminder wipe fixtures. Imported into every Feature 069
    acceptance module (billed and expensive) so it applies uniformly; binds to
    whichever `denidin_app` fixture that module defines.
    """
    reset_chat_session(denidin_app.ai_handler.session_manager, GODFATHER_CHAT_ID)
    yield
    reset_chat_session(denidin_app.ai_handler.session_manager, GODFATHER_CHAT_ID)

SENDER_DATA = {
    "chatId": GODFATHER_CHAT_ID,
    "sender": GODFATHER_CHAT_ID,
    "senderName": "E2E Godfather",
}
FIX_DIR = Path(__file__).parent.parent / "fixtures" / "ledger_069"


def events_reader(denidin_app):
    """`events_for_chat(chat_id)` callable for `converse_until_ledger_events_captured`."""
    def _reader(chat_id):
        return ledger_events_for_chat(denidin_app, chat_id)
    return _reader


def drive_capture_conversation(denidin_app, first_text, answer_bank, *, id_prefix,
                               base_ts=None, max_turns=5):
    """One post-turn-capture conversation, stopping the moment a LedgerEvent lands.

    Returns `(events, transcript, event_epoch)`. Per data-model.md §3 decision #10
    the ledgerer dates `event_datetime` from the **completing** message (the turn
    on which the event became complete — later than the trigger for a resolution
    detour), never the trigger. `event_epoch` is that turn's synthetic Green API
    timestamp: `base + (completing_turn - 1) * 30`. Pass it straight into
    `assert_ledger_event_matches_manifest(trigger_epoch=...)`. `events` is
    non-empty only when capture actually happened within `max_turns`.
    """
    from denidin import handle_text_message

    base_epoch = base_ts if base_ts is not None else int(time.time())
    events, transcript = converse_until_ledger_events_captured(
        handle_text_message=handle_text_message,
        chat_id=GODFATHER_CHAT_ID,
        first_message_text=first_text,
        answer_bank=answer_bank,
        events_for_chat=events_reader(denidin_app),
        base_timestamp=base_epoch,
        base_id_message=id_prefix,
        sender_data=SENDER_DATA,
        max_turns=max_turns,
        test_logger=logger,
    )
    for entry in transcript:
        logger.info("TURN %s | sent=%r | reply=%r", entry["turn"], entry["sent"], entry["reply"])
    # converse_until_ledger_events_captured spaces turn N at base + (N-1)*30 and
    # stops on the turn that captured — that turn is the completing message.
    completing_turn = transcript[-1]["turn"] if transcript else 1
    event_epoch = base_epoch + (completing_turn - 1) * 30
    return events, transcript, event_epoch
