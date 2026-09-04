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

from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID
from tests.billed._ledger_069_acceptance import ledger_events_for_chat
from tests.e2e_helpers import converse_until_ledger_events_captured

logger = logging.getLogger("tests.billed.ledger_069_post_turn")
logger.setLevel(logging.DEBUG)

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

    Returns `(events, transcript)`; `events` is non-empty only when capture
    actually happened within `max_turns`.
    """
    from denidin import handle_text_message

    events, transcript = converse_until_ledger_events_captured(
        handle_text_message=handle_text_message,
        chat_id=GODFATHER_CHAT_ID,
        first_message_text=first_text,
        answer_bank=answer_bank,
        events_for_chat=events_reader(denidin_app),
        base_timestamp=base_ts or int(time.time()),
        base_id_message=id_prefix,
        sender_data=SENDER_DATA,
        max_turns=max_turns,
        test_logger=logger,
    )
    for entry in transcript:
        logger.info("TURN %s | sent=%r | reply=%r", entry["turn"], entry["sent"], entry["reply"])
    return events, transcript
