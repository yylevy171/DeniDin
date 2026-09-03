"""Feature 069 — Phase 11 acceptance tier (text + DOCX flows), BILLED.

Real text-only OpenAI calls + real Morning sandbox. NO MOCKING. These prove the
**post-turn recognition** mechanism end to end:

  operator turn → reply sent → ONE text-only `recognize_ledger_event` call →
  zero-AI `persist_recognized_event` → a `LedgerEvent` file on disk

plus the **mandatory client-resolution** contract for `הסכם` / `בנק` / `חשבונית`
(FR-069-005/022) — the persisted `client_name` is always an EXACT Morning client
name (after a resolution detour when needed), never raw operator/OCR text, unless
the operator explicitly elects "store it anyway" (US8 → `[לקוח לא אומת במורנינג]`
marker).

Fidelity is checked bidirectionally against a committed ground-truth manifest —
`tests/fixtures/ledger_069/<name>.manifest.json`, C9
(`contracts/payload-fidelity-manifest.md`), via `_ledger_069_acceptance`.

Morning sandbox roster this file assumes
-----------------------------------------
* US6 / US1 exact-match: a fresh client seeded in-test via `_seed_client(name=...)`.
* US5 ambiguity: two partial matches seeded in-test (`agreement_ambiguous.manifest.json`
  → `seed_clients`).
* US10 near-match: one client seeded in-test (`agreement_doc_multi.manifest.json`).
* US4 / US8: a brand-new client the operator supplies full name + email + phone for
  during the detour — created by the run, not pre-seeded.
See `tests/billed/GROUND_TRUTH_CLIENTS.md` for the permanent-fixture philosophy;
none of the names here are permanent fixtures (each run seeds its own).

Run (billed — no per-run approval needed; sound off each result live):
    scripts/run_single_test.sh "tests/billed/test_e2e_ledger_post_turn_capture.py::<node>"
    scripts/run_multiple_billed_tests.sh <node> <node> ...
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _seed_client,
    _send_turn,
    _send_turn_and_approve,
)
from tests.billed._ledger_069_acceptance import (
    assert_event_matches_manifest,
    assert_no_ledger_event,
    ledger_events_for_chat,
    load_manifest,
    resolution_answer_bank,
)
from tests.e2e_helpers import (
    ClarificationAnswerBank,
    converse_until_ledger_events_captured,
    create_real_notification,
    get_response,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_SENDER_DATA = {
    "chatId": GODFATHER_CHAT_ID,
    "sender": GODFATHER_CHAT_ID,
    "senderName": "E2E Godfather",
}
_FIX = Path(__file__).parent.parent / "fixtures" / "ledger_069"


def _events_for_chat(denidin_app):
    def _reader(chat_id):
        return ledger_events_for_chat(denidin_app, chat_id)
    return _reader


def _drive(denidin_app, first_text, answer_bank, *, id_prefix, base_ts=None, max_turns=5):
    """One post-turn-capture conversation, stopping the moment a LedgerEvent lands."""
    from denidin import handle_text_message

    events, transcript = converse_until_ledger_events_captured(
        handle_text_message=handle_text_message,
        chat_id=GODFATHER_CHAT_ID,
        first_message_text=first_text,
        answer_bank=answer_bank,
        events_for_chat=_events_for_chat(denidin_app),
        base_timestamp=base_ts or int(time.time()),
        base_id_message=id_prefix,
        sender_data=_SENDER_DATA,
        max_turns=max_turns,
        test_logger=logger,
    )
    for entry in transcript:
        logger.info("TURN %s | sent=%r | reply=%r", entry["turn"], entry["sent"], entry["reply"])
    return events, transcript


@pytest.mark.billed
class TestLedgerPostTurnCaptureText:

    # ---- US1: the mechanism moved (no inline capture tool anymore) ----------
    def test_us1_mechanism_move_agreement_text_exact_client(self, denidin_app):
        """A fee agreement stated as plain text, client already an EXACT Morning
        match → exactly one agreement recorded, post-turn, against the exact
        Morning name. No `capture_ledger_event` tool is offered to the model
        anymore (that is the mechanism move) — the only path to a `LedgerEvent`
        is the post-turn recognition call."""
        name, _, _ = _seed_client(GODFATHER_CHAT_ID, "F069_US1", phone="0525550101")
        text = (
            f"סגרתי היום הסכם שכר טרחה עם {name}: מקדמה קבועה 5,000 ש\"ח + מע\"מ, "
            f"ובנוסף שכר הצלחה 10% + מע\"מ מכל סכום שייפסק."
        )
        events, _ = _drive(
            denidin_app, text,
            ClarificationAnswerBank([], fallback="כן, זה נכון, תרשום"),
            id_prefix="F069_US1",
        )
        assert events, "no LedgerEvent recorded for a clear fee-agreement turn"
        for ev in events:
            assert ev["source_type"] == "הסכם"
            assert ev["client_name"] == name, (
                f"client_name must be the exact seeded Morning name {name!r}, got {ev['client_name']!r}"
            )
        # the model must never have been handed an inline capture tool
        last = denidin_app.ai_handler.last_response
        if last is not None:
            assert not any(
                c["name"] == "capture_ledger_event" for c in last.mcp_calls
            ), "capture_ledger_event must not exist as an inline tool anymore (mechanism move)"

    # ---- US3: false-positive / regression guards ---------------------------
    def test_us3_regression_guard_ordinary_turn_no_capture(self, denidin_app):
        """An ordinary admin question that is not a ledger event → the post-turn
        recognition call returns `none` and nothing is persisted."""
        _send_turn(GODFATHER_CHAT_ID, "מה השעה עכשיו ומה מזג האוויר?", "F069_US3A")
        assert_no_ledger_event(denidin_app, GODFATHER_CHAT_ID)

    def test_us3_bare_email_is_not_a_ledger_event(self, denidin_app):
        """T041b / T008c guard: a message that is *only* an email address (a
        client detail the operator is supplying mid-flow, or noise) must never
        be recognised as a completed ledger event."""
        _send_turn(GODFATHER_CHAT_ID, "yaron.test.f069@example.com", "F069_US3B")
        assert_no_ledger_event(denidin_app, GODFATHER_CHAT_ID)

    # ---- US4: FLAGSHIP — brand-new client, full resolution detour ----------
    def test_us4_new_client_agreement_full_detour(self, denidin_app):
        """`agreement_new_client.txt`: the operator states a multi-component fee
        agreement for a client Morning has never seen. The turn cannot complete
        until the operator supplies full name + email + phone and `add_client`
        runs; only then does the post-turn recognition call record the agreement,
        every fee component, against the newly-created exact Morning name.
        Bidirectional manifest fidelity — the detour lost nothing."""
        manifest = load_manifest("agreement_new_client")
        res = manifest["client_resolution"]
        agreement_text = (_FIX / "agreement_new_client.txt").read_text(encoding="utf-8")
        bank = resolution_answer_bank(
            full_name=res["operator_stated_name"],
            email=res["new_client_email"],
            phone=res["new_client_phone"],
        )
        events, _ = _drive(
            denidin_app,
            "קיבלתי עכשיו את ההסכם הבא, תרשום אותו ביומן:\n\n" + agreement_text,
            bank, id_prefix="F069_US4", max_turns=6,
        )
        assert_event_matches_manifest(events, manifest)

    # ---- US5: ambiguous client — operator picks one ----------------------
    def test_us5_ambiguous_agreement_operator_picks(self, denidin_app):
        """`agreement_ambiguous.txt`: two partial Morning matches for the stated
        name. The recognition/turn must ask which one; once the operator picks,
        the agreement is recorded against that exact Morning name."""
        manifest = load_manifest("agreement_ambiguous")
        res = manifest["client_resolution"]
        for seed in manifest["seed_clients"]:
            _seed_client(GODFATHER_CHAT_ID, seed["id_prefix"], name=seed["name"],
                         phone="0525550102")
            time.sleep(2)  # Morning search-index settle
        agreement_text = (_FIX / "agreement_ambiguous.txt").read_text(encoding="utf-8")
        bank = ClarificationAnswerBank(
            [
                {
                    "topic": "which_of_the_matches",
                    "keywords": ["איזה", "מצאתי", "יותר מ", "האם הכוונה", "שתי", "כמה"],
                    "answer": f"הכוונה ל{res['operator_picks']}",
                },
            ],
            fallback=f"הכוונה ל{res['operator_picks']}",
        )
        events, _ = _drive(
            denidin_app,
            "תרשום ביומן את ההסכם הזה:\n\n" + agreement_text,
            bank, id_prefix="F069_US5", max_turns=6,
        )
        assert_event_matches_manifest(events, manifest)

    # ---- US6: exact match → silent, no disambiguation question -----------
    def test_us6_exact_match_captures_without_a_question(self, denidin_app):
        """When the stated client is a single EXACT Morning match, the operator
        is NOT asked to disambiguate — the agreement is recorded on the same
        turn."""
        name, _, _ = _seed_client(GODFATHER_CHAT_ID, "F069_US6", phone="0525550103")
        time.sleep(2)
        text = (
            f"רשום ביומן: הסכם שכר טרחה עם {name} מהיום — מקדמה 7,000 ש\"ח + מע\"מ, "
            f"ושכר הצלחה 20% + מע\"מ."
        )
        events, transcript = _drive(
            denidin_app, text,
            ClarificationAnswerBank([], fallback="כן תרשום"),
            id_prefix="F069_US6", max_turns=3,
        )
        assert events, "exact-match agreement was not recorded"
        assert transcript[0]["reply"], "no reply on turn 1"
        # turn 1 should already have captured (no detour) for a clean exact match
        assert len(transcript) <= 2, (
            f"an exact-match client should not trigger a resolution detour, "
            f"took {len(transcript)} turns: {[t['sent'] for t in transcript]!r}"
        )
        for ev in events:
            assert ev["client_name"] == name

    # ---- US8: store-anyway election + its refusal twin -------------------
    def test_us8_store_anyway_marks_the_record(self, denidin_app):
        """`agreement_new_client.txt`, but the operator declines to resolve the
        client and explicitly elects to store it as-stated. The agreement is
        persisted with the operator-stated name and the description carries
        `[לקוח לא אומת במורנינג]`. No 'בטוח?' confirmation turn is required —
        a proactive election is honoured directly."""
        manifest = load_manifest("agreement_new_client")
        stated = manifest["client_resolution"]["operator_stated_name"]
        agreement_text = (_FIX / "agreement_new_client.txt").read_text(encoding="utf-8")
        bank = ClarificationAnswerBank(
            [
                {
                    "topic": "resolve_or_store_anyway",
                    "keywords": ["אימייל", "טלפון", "שם מלא", "חדש", "ליצור", "מצאתי", "לקוח"],
                    "answer": "אל תיצור לקוח ואל תחפש, תרשום את זה ככה עם השם שנתתי, גם בלי אימות במורנינג",
                },
            ],
            fallback="תרשום ככה בלי אימות במורנינג",
        )
        events, _ = _drive(
            denidin_app,
            f"תרשום ביומן, ואל תטרח לאמת את הלקוח במורנינג — תרשום עם השם {stated} כמו שהוא:\n\n"
            + agreement_text,
            bank, id_prefix="F069_US8", max_turns=5,
        )
        assert_event_matches_manifest(events, manifest, stated_name_for_store_anyway=stated)

    def test_us8_dont_store_persists_nothing(self, denidin_app):
        """The twin: operator says not to store it → the recognition call returns
        `declined` and nothing is persisted."""
        _send_turn(
            GODFATHER_CHAT_ID,
            "חשבתי לרשום הסכם עם מישהו חדש אבל עזוב, אל תרשום כלום ביומן בינתיים.",
            "F069_US8B",
        )
        assert_no_ledger_event(denidin_app, GODFATHER_CHAT_ID)


@pytest.mark.billed
class TestLedgerPostTurnCaptureMorningCreate:

    # ---- US2: an in-conversation Morning create → synchronous חשבונית -----
    def test_us2_morning_create_is_captured_synchronously(self, denidin_app):
        """When the operator has DeniDin create a Morning document in-conversation
        (here a type-320 `create_combo_document`), the resulting `חשבונית` ledger
        event is captured synchronously from that `create_*` call — not left to
        the post-turn recognition pass — against the exact resolved client, with
        the document's own number/date/total."""
        name, _, _ = _seed_client(GODFATHER_CHAT_ID, "F069_US2", phone="0525550104")
        time.sleep(2)
        (_ask, _ask_ai), (reply, approve_ai) = _send_turn_and_approve(
            GODFATHER_CHAT_ID,
            f"תפיק ל{name} חשבונית מס-קבלה על סך 1,200 ש\"ח כולל מע\"מ עבור ייעוץ משפטי.",
            "F069_US2",
        )
        assert approve_ai is not None
        create_calls = [
            c for c in approve_ai.mcp_calls
            if c["name"] in (
                "create_combo_document", "create_invoice", "create_transaction_account",
                "create_credit_note", "create_receipt",
            ) and c.get("error") is None
        ]
        assert create_calls, f"no successful Morning create call. reply={reply!r}"
        events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)
        invoice_events = [e for e in events if e["source_type"] == "חשבונית"]
        assert len(invoice_events) == 1, (
            f"exactly one חשבונית ledger event expected, got {len(invoice_events)}: {events!r}"
        )
        ev = invoice_events[0]
        assert ev["client_name"] == name, (
            f"חשבונית ledger event client must be the exact resolved name {name!r}, got {ev['client_name']!r}"
        )
        assert ev.get("accounting_document_display_number"), (
            "the synchronous חשבונית capture must carry the real Morning document number"
        )


@pytest.mark.billed
class TestLedgerPostTurnCaptureDocx:

    # ---- US10: DOCX fee agreement routed as a synthetic turn -------------
    def test_us10_docx_multi_component_agreement_two_hop(  # pylint: disable=too-many-locals
        self, denidin_app
    ):
        """`agreement_doc_multi.docx` arrives as a documentMessage. `DOCXExtractor`
        classifies it `הסכם` (deterministic, no OpenAI call), the media path
        rewrites the notification to a synthetic text turn carrying the verbatim
        stash, and the shared conversational path resolves the near-match client
        and records every fee component post-turn. Two-hop fidelity: the docx
        extraction lost nothing AND the detour lost nothing.

        Text-only recognition (`config.ai_model`) → billed, not expensive.
        """
        from http.server import HTTPServer, SimpleHTTPRequestHandler
        import threading
        from urllib.parse import unquote

        docx_path = _FIX / "agreement_doc_multi.docx"
        assert docx_path.exists(), (
            f"missing fixture {docx_path} — run tests/fixtures/ledger_069/build_agreement_doc_multi.py"
        )
        manifest = load_manifest("agreement_doc_multi")
        for seed in manifest.get("seed_clients", []):
            _seed_client(GODFATHER_CHAT_ID, seed["id_prefix"], name=seed["name"],
                         phone="0525550110")
            time.sleep(2)

        fixtures_dir = _FIX

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(fixtures_dir), **kw)

            def translate_path(self, path):
                return super().translate_path(unquote(path))

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 8769), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            from denidin import handle_text_message
            import denidin as denidin_module

            notification = create_real_notification({
                "typeWebhook": "incomingMessageReceived",
                "timestamp": int(time.time()),
                "idMessage": "F069_US10_DOC",
                "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us",
                                 "typeInstance": "whatsapp"},
                "senderData": _SENDER_DATA,
                "messageData": {
                    "typeMessage": "documentMessage",
                    "fileMessageData": {
                        "downloadUrl": "http://127.0.0.1:8769/agreement_doc_multi.docx",
                        "fileName": "agreement_doc_multi.docx",
                        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "caption": "ההסכם החתום, תרשום ביומן",
                    },
                },
            })
            denidin_module._process_media_message(notification)  # media entry point
            first_reply = get_response(notification)
            logger.info("US10 media/synthetic-turn reply: %r", first_reply)

            events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)
            # follow-up detour turns if the client wasn't resolved on the synthetic turn
            res = manifest["client_resolution"]
            bank = ClarificationAnswerBank(
                [
                    {"topic": "near_match_confirm",
                     "keywords": ["מצאתי", "האם הכוונה", "התכוונת", "דומה", "נכון"],
                     "answer": f"כן, הכוונה ל{res['morning_name_after_resolution']}"},
                ],
                fallback=f"כן, {res['morning_name_after_resolution']}",
            )
            turn = 0
            text = first_reply
            ts = int(time.time())
            while not events and turn < 4:
                turn += 1
                nxt, _ = bank.compose_answer(text or "")
                follow = create_real_notification({
                    "typeWebhook": "incomingMessageReceived",
                    "timestamp": ts + turn * 30,
                    "idMessage": f"F069_US10_F{turn}",
                    "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us",
                                     "typeInstance": "whatsapp"},
                    "senderData": _SENDER_DATA,
                    "messageData": {"typeMessage": "textMessage",
                                    "textMessageData": {"textMessage": nxt}},
                })
                handle_text_message(follow)
                text = get_response(follow)
                events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)

            assert events, "US10: no LedgerEvent after routing the docx agreement + detour"
            assert_event_matches_manifest(events, manifest)
        finally:
            server.shutdown()
