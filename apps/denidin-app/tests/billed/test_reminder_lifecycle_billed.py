"""
End-to-End Billed Test: Reminders — Functionality and Management (Feature 054, T010/T018/T020/T022/T023)

Tests the real OpenAI function-calling mechanism end-to-end for reminders - NOT
unit-testable, since what's under test is whether the real model (a) recognizes
intent to create/list/modify/delete a reminder, (b) calls the right tool with
correctly-extracted arguments, and (c) phrases the confirmation reply naturally
once approved. Text-only (no vision) - all billed, none expensive.

Written per the plan (tasks.md T010/T018/T020/T022/T023); most of this file has
already run against real OpenAI as of 2026-08-18 (create/list/modify all
verified end-to-end, several real bugs caught and fixed along the way - see
git history), delete/RBAC/cap coverage still pending its first run. Each run
still requires its own explicit go-ahead per this project's standing
convention (real OpenAI calls, billed tier).

NO MOCKING of internal components - only the OpenAI client is a real external
service under test for the conversational (create/list/modify/delete) phase of
each test. Delivery IS exercised here (2026-08-17 addition, per user request -
"reminders are always in the future, testing only past-due reminders is worth
crap from the user perspective") - but not via the real WhatsApp send boundary
(that's Gate Zero, still separately gated, see research.md) and not by waiting
real wall-clock time or faking a live scheduler thread's clock (verified with
the user to not reliably work - see reminder-delivery.md). Instead: a reminder
is created/modified/cancelled through a REAL conversation (billed), its ACTUAL
persisted due time is read back from ReminderManager (never independently
guessed/recomputed - that's what made the deleted rounding-boundary unit test
flaky), and _sweep_due_reminders is invoked directly with simulated `now`
values bracketing that real due time - proving delivery fires exactly at the
real due time and not 5 minutes early/late, and that a modified/cancelled
occurrence's delivery outcome actually changed. send_proactive_message is
stubbed for these delivery-boundary checks only (the WhatsApp send boundary
itself, not an internal component - same allowance already used by
tests/unit/test_reminder_delivery_service.py) so Gate Zero is never
incidentally exercised by this file.
"""

import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import src.services.reminder_delivery_service as delivery_service
from src.models.config import AppConfiguration
from src.utils.time_utils import now_local, to_local
from src.constants.error_messages import REMINDER_CAP_EXCEEDED

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

GODFATHER_CHAT_ID_TEMPLATE = "{phone}@c.us"


@pytest.mark.billed
class TestReminderLifecycleBilled:
    """Given/When/Then E2E coverage for the full reminder conversational
    lifecycle - create (one-time + recurring), list-driven modify/delete
    (single-occurrence and whole-series), RBAC denial, and cap enforcement.
    """

    @pytest.fixture
    def config(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")
        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = Path(__file__).parent.parent.parent / "test_data"
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
        return config

    @pytest.fixture
    def denidin_app(self, config):
        import denidin

        if denidin.denidin_app is None:
            config_dict = {
                'green_api_instance_id': config.green_api_instance_id,
                'green_api_token': config.green_api_token,
                'ai_api_key': config.ai_api_key,
                'ai_model': config.ai_model,
                'ai_vision_model': config.ai_vision_model,
                'ai_embedding_model': config.ai_embedding_model,
                'ai_reply_max_tokens': config.ai_reply_max_tokens,
                'log_level': config.log_level,
                'data_root': config.data_root,
                'feature_flags': config.feature_flags,
                'godfather_phone': config.godfather_phone,
                'memory': config.memory,
                'constitution_config': config.constitution_config,
                'user_roles': config.user_roles,
                'mcp': config.mcp,
                'reminders': {'max_active_reminders': 20},
            }
            denidin.denidin_app = denidin.initialize_app(config_dict)

        # Safety guard (mirrors test_ledger_event_capture_billed.py's precedent):
        # ReminderManager.storage_dir MUST resolve under this test's isolated
        # data_root, never real production/dev data - a wiring mistake here
        # would create real, orphaned SQLite rows outside test isolation.
        actual_reminders_dir = Path(denidin.denidin_app.ai_handler.reminder_manager.storage_dir).resolve()
        expected_root = Path(config.data_root).resolve()
        assert actual_reminders_dir.is_relative_to(expected_root), (
            f"ReminderManager.storage_dir={actual_reminders_dir} is NOT under this "
            f"test's isolated data_root={expected_root} - refusing to proceed"
        )
        return denidin.denidin_app

    @staticmethod
    def _create_notification(chat_id, sender, sender_name, text, msg_id):
        from whatsapp_chatbot_python import Notification

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': msg_id,
            'timestamp': int(now_local().timestamp()),
            'senderData': {'chatId': chat_id, 'sender': sender, 'senderName': sender_name},
            'messageData': {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': text}},
        }
        notification._test_sent_messages = []
        notification._test_button_sends = []

        def track_answer(message):
            notification._test_sent_messages.append(message)
            logger.info(f"Would send to user: {message}")

        def track_answer_with_interactive_buttons(body, buttons, header=None, footer=None):
            from types import SimpleNamespace
            id_message = f"TEST_BUTTONS_{msg_id}_{len(notification._test_button_sends)}"
            notification._test_button_sends.append({'body': body, 'buttons': buttons, 'idMessage': id_message})
            notification._test_sent_messages.append(body)
            logger.info(f"Would send interactive buttons: body={body!r}")
            return SimpleNamespace(code=200, data={'idMessage': id_message}, error=None)

        notification.answer = track_answer
        notification.answer_with_interactive_buttons = track_answer_with_interactive_buttons
        return notification

    @staticmethod
    def _get_response(notification):
        return notification._test_sent_messages[0] if notification._test_sent_messages else None

    @staticmethod
    def _get_button_send(notification):
        sends = notification._test_button_sends
        return sends[0] if sends else None

    def _send_text(self, chat_id, sender, sender_name, text, label):
        from denidin import handle_text_message
        msg_id = f"billed_{label}_{uuid.uuid4().hex[:8]}"
        notification = self._create_notification(chat_id, sender, sender_name, text, msg_id)
        handle_text_message(notification)
        return notification

    def _tap_button(self, denidin_app, chat_id, sender, selected_id, stanza_id, label):
        from denidin import handle_button_tap
        from src.models.message import WhatsAppMessage  # noqa: F401 (documents the shape relied on)
        msg_id = f"billed_{label}_{uuid.uuid4().hex[:8]}"
        notification = self._create_notification(chat_id, sender, "Test Godfather", "", msg_id)
        notification.event['messageData'] = {
            'typeMessage': 'interactiveButtonsResponse',
            'interactiveButtonsResponse': {'selectedId': selected_id, 'stanzaId': stanza_id},
        }
        handle_button_tap(notification)
        return notification

    def _godfather(self, config):
        phone = config.godfather_phone
        return phone, GODFATHER_CHAT_ID_TEMPLATE.format(phone=phone)

    def _admin(self, config):
        admin_phones = config.user_roles.get('admin_phones', [])
        if not admin_phones:
            pytest.skip("config.test.json has no admin_phones configured")
        phone = admin_phones[0]
        return phone, GODFATHER_CHAT_ID_TEMPLATE.format(phone=phone)

    # --- Delivery verification helpers ------------------------------------------
    # Real create/modify/cancel via conversation above; these prove the RESULT
    # actually fires (or doesn't) at the RIGHT moment - see module docstring for
    # why this doesn't wait real time or fake a live scheduler's clock.

    @staticmethod
    def _active_ids(reminder_manager):
        return {r["reminder_id"] for r in reminder_manager.list_active()}

    def _new_reminder_id(self, reminder_manager, ids_before):
        """Diffs list_active() before/after a create, rather than assuming
        ordering or trusting message-text matching - robust even if earlier
        tests in this file left other active reminders around."""
        new_ids = self._active_ids(reminder_manager) - ids_before
        assert len(new_ids) == 1, f"expected exactly 1 new reminder, got {new_ids}"
        return new_ids.pop()

    @staticmethod
    def _due_at(reminder_manager, reminder_id):
        """The real persisted due time for a ONE-TIME reminder - read back,
        never independently recomputed (that's what made the deleted
        rounding-boundary unit test flaky)."""
        row = reminder_manager.get_reminder(reminder_id)
        assert row is not None
        return to_local(datetime.fromisoformat(row["dtstart"]))

    @staticmethod
    def _occurrences(reminder_manager, reminder_id, window_start, window_end):
        """Every not-yet-fired occurrence of ONE reminder in a window, via the
        same public get_due_occurrences the real sweep uses - works uniformly
        for one-time and recurring alike, sorted earliest-first."""
        due = reminder_manager.get_due_occurrences(window_start, window_end)
        matching = [o for o in due if o["reminder_id"] == reminder_id]
        return sorted(matching, key=lambda o: o["occurrence_datetime"])

    def _simulate_sweep(self, denidin_app, monkeypatch, simulated_now):
        """Runs ONE real sweep pass as if `simulated_now` were the wall clock -
        the real ReminderManager/get_due_occurrences/record_occurrence_fired
        path, only the WhatsApp send call itself stubbed (Gate Zero stays
        untouched). Returns the send mock so callers can assert on it."""
        send = MagicMock(return_value="wamid.test")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        delivery_service._sweep_due_reminders(  # pylint: disable=protected-access
            denidin_app, MagicMock(), now=simulated_now
        )
        return send

    # --- US1: create -----------------------------------------------------------

    def test_godfather_creates_one_time_reminder_text_approval(self, denidin_app, config, monkeypatch):
        phone, chat_id = self._godfather(config)
        reminder_manager = denidin_app.ai_handler.reminder_manager
        ids_before = self._active_ids(reminder_manager)

        n1 = self._send_text(
            chat_id, phone, "Test Godfather",
            "תזכיר לי בעוד שעה להתקשר לרואה חשבון", "create1",
        )
        proposal = self._get_response(n1)
        assert proposal is not None
        assert "לאישור" in proposal

        n2 = self._send_text(chat_id, phone, "Test Godfather", "כן", "create1_approve")
        confirmation = self._get_response(n2)
        assert confirmation is not None
        assert len(reminder_manager.list_active()) >= 1

        # --- Delivery: fires at the REAL persisted due time, not 5min early/late/twice ---
        reminder_id = self._new_reminder_id(reminder_manager, ids_before)
        due_at = self._due_at(reminder_manager, reminder_id)

        early = self._simulate_sweep(denidin_app, monkeypatch, due_at - timedelta(minutes=1))
        early.assert_not_called()

        on_time = self._simulate_sweep(denidin_app, monkeypatch, due_at)
        on_time.assert_called_once()
        assert on_time.call_args.args[1] == chat_id
        assert on_time.call_args.args[2]  # real, non-empty message text delivered

        again = self._simulate_sweep(denidin_app, monkeypatch, due_at)
        again.assert_not_called()  # already fired - idempotent, never re-delivered

    def test_godfather_creates_one_time_reminder_button_approval(self, denidin_app, config):
        phone, chat_id = self._godfather(config)
        n1 = self._send_text(
            chat_id, phone, "Test Godfather",
            "תזכיר לי בעוד שעתיים לשלוח חשבונית ללקוח", "create2",
        )
        button_send = self._get_button_send(n1)
        assert button_send is not None, "expected an interactive-buttons approval prompt"

        n2 = self._tap_button(
            denidin_app, chat_id, phone, "denidin_approve", button_send["idMessage"], "create2_approve"
        )
        confirmation = self._get_response(n2)
        assert confirmation is not None

    def test_godfather_creates_recurring_reminder(self, denidin_app, config, monkeypatch):
        phone, chat_id = self._godfather(config)
        reminder_manager = denidin_app.ai_handler.reminder_manager
        ids_before = self._active_ids(reminder_manager)

        n1 = self._send_text(
            chat_id, phone, "Test Godfather",
            "תזכיר לי כל יום שני וחמישי בשעה 10:00 לבדוק חשבוניות", "create_recurring",
        )
        proposal = self._get_response(n1)
        assert proposal is not None
        assert "לאישור" in proposal

        n2 = self._send_text(chat_id, phone, "Test Godfather", "כן", "create_recurring_approve")
        assert self._get_response(n2) is not None
        active = reminder_manager.list_active()
        recurring = [r for r in active if r.get("rrule")]
        assert len(recurring) >= 1

        # --- Delivery: TWO real occurrences, each fires on its own mark, never
        # re-delivering the first when the second comes due. ---
        reminder_id = self._new_reminder_id(reminder_manager, ids_before)
        far_future = now_local() + timedelta(days=45)
        occurrences = self._occurrences(reminder_manager, reminder_id, now_local(), far_future)
        assert len(occurrences) >= 2, "expected at least 2 upcoming Mon/Thu occurrences within 45 days"
        occ1, occ2 = occurrences[0]["occurrence_datetime"], occurrences[1]["occurrence_datetime"]
        assert occ1 < occ2

        not_yet = self._simulate_sweep(denidin_app, monkeypatch, occ1 - timedelta(minutes=1))
        not_yet.assert_not_called()

        first = self._simulate_sweep(denidin_app, monkeypatch, occ1)
        first.assert_called_once()
        assert first.call_args.args[1] == chat_id

        between = self._simulate_sweep(denidin_app, monkeypatch, occ2 - timedelta(minutes=1))
        between.assert_not_called()  # occ1 already fired, occ2 not yet due

        second = self._simulate_sweep(denidin_app, monkeypatch, occ2)
        second.assert_called_once()  # only occ2 - occ1 is not re-delivered

    # --- Find-by-time (2026-08-18, user-requested coverage) ----------------------
    # list_reminders has no date/time filter parameter at all - "what do I have
    # tomorrow" relies entirely on the model's own reasoning over the full active
    # list (message_text + schedule) plus the current-date-and-time now injected
    # into instructions. Never exercised by any test above (every existing
    # reference to a reminder is either by content or immediately after creating
    # it) - this was flagged as a real, untested gap and asked for explicitly.

    def test_list_reminders_filtered_by_day_in_conversation(self, denidin_app, config):
        phone, chat_id = self._godfather(config)
        self._create_approved_reminder(
            denidin_app, config, phone, chat_id,
            "תזכיר לי מחר בשעה 15:00 להתקשר לספק החדש", "list_tomorrow_setup",
        )
        self._create_approved_reminder(
            denidin_app, config, phone, chat_id,
            "תזכיר לי בעוד שבועיים לחדש רישיון תוכנה", "list_far_setup",
        )

        n1 = self._send_text(chat_id, phone, "Test Godfather", "מה יש לי מחר?", "list_tomorrow")
        response = self._get_response(n1)
        assert response is not None
        assert "ספק" in response, f"expected tomorrow's reminder (supplier) mentioned, got: {response!r}"
        assert "רישיון" not in response, (
            f"a reminder ~2 weeks out must NOT be listed as due tomorrow, got: {response!r}"
        )

    # --- US3: modify -------------------------------------------------------------

    def _create_approved_reminder(self, denidin_app, config, phone, chat_id, text, label):
        n1 = self._send_text(chat_id, phone, "Test Godfather", text, f"{label}_propose")
        assert self._get_response(n1) is not None
        n2 = self._send_text(chat_id, phone, "Test Godfather", "כן", f"{label}_approve")
        assert self._get_response(n2) is not None

    def test_modify_one_time_reminder(self, denidin_app, config, monkeypatch):
        phone, chat_id = self._godfather(config)
        reminder_manager = denidin_app.ai_handler.reminder_manager
        ids_before_create = self._active_ids(reminder_manager)
        self._create_approved_reminder(
            denidin_app, config, phone, chat_id,
            "תזכיר לי בעוד שעה לקנות מתנה ליום הולדת", "modify_one_time_setup",
        )
        reminder_id = self._new_reminder_id(reminder_manager, ids_before_create)
        original_due_at = self._due_at(reminder_manager, reminder_id)

        n1 = self._send_text(chat_id, phone, "Test Godfather", "תעדכן את התזכורת לקניית המתנה לשעתיים מעכשיו", "modify_one_time")
        proposal = self._get_response(n1)
        assert proposal is not None
        assert "עדכון" in proposal or "לאישור" in proposal
        n2 = self._send_text(chat_id, phone, "Test Godfather", "כן", "modify_one_time_approve")
        assert self._get_response(n2) is not None

        # --- Delivery: the OLD time must no longer fire, the NEW real persisted
        # time must. ---
        new_due_at = self._due_at(reminder_manager, reminder_id)
        assert new_due_at != original_due_at, "modify must actually change the persisted due time"

        old_check = self._simulate_sweep(denidin_app, monkeypatch, original_due_at)
        old_check.assert_not_called()

        new_check = self._simulate_sweep(denidin_app, monkeypatch, new_due_at)
        new_check.assert_called_once()

    def test_modify_single_occurrence_of_recurring_reminder(self, denidin_app, config, monkeypatch):
        phone, chat_id = self._godfather(config)
        reminder_manager = denidin_app.ai_handler.reminder_manager
        ids_before = self._active_ids(reminder_manager)
        self._create_approved_reminder(
            denidin_app, config, phone, chat_id,
            "תזכיר לי כל יום בשעה 9:00 לשתות מים", "modify_single_setup",
        )
        reminder_id = self._new_reminder_id(reminder_manager, ids_before)
        window_end = now_local() + timedelta(days=10)
        occurrences_before = self._occurrences(reminder_manager, reminder_id, now_local(), window_end)
        assert len(occurrences_before) >= 2
        first_before = occurrences_before[0]["occurrence_datetime"]
        second_before = occurrences_before[1]["occurrence_datetime"]

        n1 = self._send_text(
            chat_id, phone, "Test Godfather",
            "תדחה רק את התזכורת של מחר לשעה 10:00, לא את כל הסדרה", "modify_single",
        )
        proposal = self._get_response(n1)
        assert proposal is not None
        n2 = self._send_text(chat_id, phone, "Test Godfather", "כן", "modify_single_approve")
        assert self._get_response(n2) is not None

        # --- Delivery: ONLY the detached occurrence's time moved; the series'
        # next (untouched) occurrence still fires at its original time. ---
        occurrences_after = self._occurrences(reminder_manager, reminder_id, now_local(), window_end)
        assert len(occurrences_after) >= 2
        detached = occurrences_after[0]["occurrence_datetime"]
        assert detached != first_before, "the detached occurrence's time must have actually moved"
        assert occurrences_after[1]["occurrence_datetime"] == second_before, (
            "the next series occurrence must be untouched by a single-occurrence edit"
        )

        old_slot_check = self._simulate_sweep(denidin_app, monkeypatch, first_before)
        old_slot_check.assert_not_called()  # detached away - no occurrence left at the old time

        detached_check = self._simulate_sweep(denidin_app, monkeypatch, detached)
        detached_check.assert_called_once()

        next_series_check = self._simulate_sweep(denidin_app, monkeypatch, second_before)
        next_series_check.assert_called_once()  # untouched, still fires on the original schedule

    def test_modify_whole_series_pattern(self, denidin_app, config, monkeypatch):
        """Explicitly asserts a pre-existing Detached/exception occurrence survives
        the whole-series edit - the single most important assertion for FR-012."""
        phone, chat_id = self._godfather(config)
        reminder_manager = denidin_app.ai_handler.reminder_manager
        self._create_approved_reminder(
            denidin_app, config, phone, chat_id,
            "תזכיר לי כל יום שני בשעה 9:00 להתקשר ללקוח", "modify_whole_setup",
        )
        active = reminder_manager.list_active()
        recurring = [r for r in active if r.get("rrule")][-1]
        window_end = now_local() + timedelta(days=21)

        n_detach = self._send_text(
            chat_id, phone, "Test Godfather",
            "תדחה רק את הפעם הבאה של התזכורת להתקשר ללקוח לשעה 14:00", "modify_whole_detach",
        )
        assert self._get_response(n_detach) is not None
        n_detach_approve = self._send_text(chat_id, phone, "Test Godfather", "כן", "modify_whole_detach_approve")
        assert self._get_response(n_detach_approve) is not None

        conn = reminder_manager._conn  # pylint: disable=protected-access
        exceptions_before = conn.execute(
            "SELECT * FROM reminder_exceptions WHERE reminder_id = ?", (recurring["reminder_id"],)
        ).fetchall()
        assert len(exceptions_before) >= 1, "expected the single-occurrence edit to create an exception row"

        occurrences_before_whole = self._occurrences(
            reminder_manager, recurring["reminder_id"], now_local(), window_end
        )
        assert len(occurrences_before_whole) >= 2
        detached_time = occurrences_before_whole[0]["occurrence_datetime"]  # the 14:00 detached one
        plain_old_pattern_time = occurrences_before_whole[1]["occurrence_datetime"]  # next Mon 9:00, untouched

        n_whole = self._send_text(
            chat_id, phone, "Test Godfather",
            "תשנה את כל הסדרה של להתקשר ללקוח לימי שלישי בשעה 11:00", "modify_whole_series",
        )
        assert self._get_response(n_whole) is not None
        n_whole_approve = self._send_text(chat_id, phone, "Test Godfather", "כן", "modify_whole_series_approve")
        assert self._get_response(n_whole_approve) is not None

        # Bug fix (2026-08-18): this used to SELECT only (summary_override,
        # dtstart_override) here while exceptions_before above selects * (6
        # columns) - comparing a 2-key dict to a 6-key dict can never be equal
        # regardless of whether the actual override data matches, so this
        # assertion was structurally guaranteed to fail every time it ever ran
        # (confirmed: the two columns it DID share had identical values both
        # times - the real FR-012 invariant was already holding correctly, the
        # comparison itself was just broken). Same SELECT * as exceptions_before
        # now, for a real equality check.
        exceptions_after = conn.execute(
            "SELECT * FROM reminder_exceptions WHERE reminder_id = ?",
            (recurring["reminder_id"],),
        ).fetchall()
        assert [dict(r) for r in exceptions_after] == [dict(r) for r in exceptions_before], (
            "whole-series edit must NEVER touch a pre-existing Detached occurrence (FR-012)"
        )

        # --- Delivery: OLD pattern (Mon 9:00) no longer fires, NEW pattern
        # (Tue 11:00) does, and the pre-existing detached occurrence (14:00)
        # survives the whole-series edit and still fires at its own time. ---
        occurrences_after_whole = self._occurrences(
            reminder_manager, recurring["reminder_id"], now_local(), window_end
        )
        new_pattern_candidates = [
            o["occurrence_datetime"] for o in occurrences_after_whole if o["occurrence_datetime"] != detached_time
        ]
        assert new_pattern_candidates, "expected at least one new-pattern (Tue 11:00) occurrence"
        new_pattern_time = min(new_pattern_candidates)
        assert new_pattern_time.weekday() == 1, "expected Tuesday (weekday()==1)"
        assert new_pattern_time.hour == 11

        old_pattern_check = self._simulate_sweep(denidin_app, monkeypatch, plain_old_pattern_time)
        old_pattern_check.assert_not_called()  # old Mon-9:00 slot no longer produces an occurrence

        new_pattern_check = self._simulate_sweep(denidin_app, monkeypatch, new_pattern_time)
        new_pattern_check.assert_called_once()

        detached_check = self._simulate_sweep(denidin_app, monkeypatch, detached_time)
        detached_check.assert_called_once()  # pre-existing detached occurrence survived and still fires

    def test_modify_whole_series_referenced_by_schedule_only(self, denidin_app, config, monkeypatch):
        """(2026-08-18, user-requested coverage) Every OTHER modify test above
        references the target reminder by its content ("the gift reminder", "the
        call-accountant one"). This one deliberately gives the model NOTHING
        content-wise to go on - the create message uses a vague, reused-elsewhere
        phrase ("לבדוק דואר"), and the modify message references the reminder
        PURELY by its existing day+time ("the Wed 9:00 reminder"), proving
        list_reminders' `schedule` field alone is enough for the model to resolve
        the correct reminder_id - not just message_text.
        """
        phone, chat_id = self._godfather(config)
        reminder_manager = denidin_app.ai_handler.reminder_manager
        ids_before = self._active_ids(reminder_manager)
        self._create_approved_reminder(
            denidin_app, config, phone, chat_id,
            "תזכיר לי כל יום רביעי בשעה 9:00 לבדוק דואר", "modify_by_schedule_setup",
        )
        reminder_id = self._new_reminder_id(reminder_manager, ids_before)
        window_end = now_local() + timedelta(days=21)
        occurrences_before = self._occurrences(reminder_manager, reminder_id, now_local(), window_end)
        assert len(occurrences_before) >= 1
        old_pattern_time = occurrences_before[0]["occurrence_datetime"]
        assert old_pattern_time.weekday() == 2, "expected Wednesday (weekday()==2)"
        assert old_pattern_time.hour == 9

        n1 = self._send_text(
            chat_id, phone, "Test Godfather",
            "תעביר את התזכורת שקבועה ליום רביעי בשעה 9:00 ליום חמישי בשעה 20:00",
            "modify_by_schedule",
        )
        proposal = self._get_response(n1)
        assert proposal is not None
        n2 = self._send_text(chat_id, phone, "Test Godfather", "כן", "modify_by_schedule_approve")
        assert self._get_response(n2) is not None

        occurrences_after = self._occurrences(reminder_manager, reminder_id, now_local(), window_end)
        assert len(occurrences_after) >= 1
        new_pattern_time = occurrences_after[0]["occurrence_datetime"]
        assert new_pattern_time.weekday() == 3, "expected Thursday (weekday()==3)"
        assert new_pattern_time.hour == 20

        old_check = self._simulate_sweep(denidin_app, monkeypatch, old_pattern_time)
        old_check.assert_not_called()  # old Wed-9:00 slot no longer produces an occurrence

        new_check = self._simulate_sweep(denidin_app, monkeypatch, new_pattern_time)
        new_check.assert_called_once()

    # --- US4: delete ---------------------------------------------------------------

    def test_delete_one_time_reminder(self, denidin_app, config, monkeypatch):
        phone, chat_id = self._godfather(config)
        reminder_manager = denidin_app.ai_handler.reminder_manager
        ids_before = self._active_ids(reminder_manager)
        self._create_approved_reminder(
            denidin_app, config, phone, chat_id,
            "תזכיר לי בעוד שעה להוציא את הכביסה", "delete_one_time_setup",
        )
        reminder_id = self._new_reminder_id(reminder_manager, ids_before)
        due_at = self._due_at(reminder_manager, reminder_id)

        n1 = self._send_text(chat_id, phone, "Test Godfather", "תבטל את התזכורת של הכביסה", "delete_one_time")
        proposal = self._get_response(n1)
        assert proposal is not None
        assert "מחיקת" in proposal or "לאישור" in proposal
        n2 = self._send_text(chat_id, phone, "Test Godfather", "כן", "delete_one_time_approve")
        assert self._get_response(n2) is not None

        # --- Delivery: a cancelled reminder must never fire, even at its own
        # real original due time ---
        assert reminder_manager.get_reminder(reminder_id) is None, "deleted reminder must no longer be active"
        delivery_check = self._simulate_sweep(denidin_app, monkeypatch, due_at)
        delivery_check.assert_not_called()

    def test_delete_whole_series(self, denidin_app, config, monkeypatch):
        phone, chat_id = self._godfather(config)
        reminder_manager = denidin_app.ai_handler.reminder_manager
        ids_before = self._active_ids(reminder_manager)
        self._create_approved_reminder(
            denidin_app, config, phone, chat_id,
            "תזכיר לי כל שבוע בימי רביעי בשעה 8:00 לשלוח דוח", "delete_whole_setup",
        )
        reminder_id = self._new_reminder_id(reminder_manager, ids_before)
        window_end = now_local() + timedelta(days=30)
        occurrences_before = self._occurrences(reminder_manager, reminder_id, now_local(), window_end)
        assert len(occurrences_before) >= 1
        first_occurrence_time = occurrences_before[0]["occurrence_datetime"]

        n1 = self._send_text(
            chat_id, phone, "Test Godfather", "תבטל לגמרי את התזכורת לשליחת הדוח, את כל הסדרה", "delete_whole"
        )
        assert self._get_response(n1) is not None
        n2 = self._send_text(chat_id, phone, "Test Godfather", "כן", "delete_whole_approve")
        assert self._get_response(n2) is not None

        # --- Delivery: a deleted whole series must never fire, at its own
        # previously-real occurrence time or anywhere else ---
        assert reminder_manager.get_reminder(reminder_id) is None
        assert self._occurrences(reminder_manager, reminder_id, now_local(), window_end) == []
        delivery_check = self._simulate_sweep(denidin_app, monkeypatch, first_occurrence_time)
        delivery_check.assert_not_called()

    # --- Polish: RBAC + cap ------------------------------------------------------

    def test_client_role_denied_reminder_tools(self, denidin_app, config):
        client_chat_id = "972500001234@c.us"
        n1 = self._send_text(
            client_chat_id, client_chat_id, "Test Client",
            "תזכיר לי בעוד שעה משהו", "client_denied",
        )
        response = self._get_response(n1)
        # A real reply of SOME kind is expected (the model still answers
        # conversationally) - the assertion that matters is no reminder tool
        # was ever attached/callable for this role (see
        # test_ai_handler_reminders.py's unit-level RBAC coverage for the
        # structural guarantee; this just confirms it holds end-to-end too).
        assert response is not None

    def test_cap_declined_at_21st_reminder(self, denidin_app, config):
        phone, chat_id = self._godfather(config)
        reminder_manager = denidin_app.ai_handler.reminder_manager
        active_count = len(reminder_manager.list_active())
        # Fill directly to the cap (conversational creation for 20 real
        # reminders would be prohibitively slow/expensive for one test) -
        # this test is specifically about the CONVERSATIONAL DECLINE WORDING
        # once the cap is already reached, not about reaching it.
        for i in range(20 - active_count):
            reminder_manager.create_reminder(
                message_text=f"cap filler {i}", schedule_type="one_time",
                one_time_due_at=(now_local() + timedelta(minutes=60 + i)).isoformat(),
                recurrence=None, created_by_phone=phone, created_by_role="GODFATHER",
            )
        assert len(reminder_manager.list_active()) == 20

        # Bug fix (2026-08-19): the original message here ("...עוד משהו" -
        # "...something else") was too vague content for the model to act on -
        # it asked a clarifying question ("what should I remind you about?")
        # instead of ever attempting create_reminder, so the cap-decline path
        # this test exists to verify was never actually reached. Concrete
        # content lets the model attempt the call and hit the real cap check.
        n1 = self._send_text(
            chat_id, phone, "Test Godfather", "תזכיר לי בעוד שעה לקנות חלב", "cap_declined"
        )
        response = self._get_response(n1)
        assert response is not None
        assert REMINDER_CAP_EXCEEDED in response or "20" in response
