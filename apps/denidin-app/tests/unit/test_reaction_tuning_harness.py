"""
Feature 084 (WhatsApp reactions) - unit tests for the reaction-judgment tuning harness's
own plumbing (contracts/reaction-judgment-tuning.md): rotation-state selection
(tests/_reaction_tuning_rotation.py) and the send_reaction capture stub
(tests/_reaction_capture.py). Pure plumbing only - never asserts on emoji choice.
"""
import json

from tests._reaction_capture import ReactionCaptureStub, ReactionTuningJudgmentLog
from tests._reaction_tuning_rotation import (
    load_rotation_state,
    record_run,
    save_rotation_state,
    select_subset,
)


class TestRotationStateRoundTrip:
    def test_missing_file_loads_as_empty_state(self, tmp_path):
        assert load_rotation_state(tmp_path / "nope.tsv") == {}

    def test_save_then_load_round_trips(self, tmp_path):
        path = tmp_path / "state.tsv"
        state = {"scenario_b": "2026-09-01T00:00:00+03:00", "scenario_a": "2026-09-02T00:00:00+03:00"}
        save_rotation_state(path, state)
        assert load_rotation_state(path) == state

    def test_save_writes_names_sorted(self, tmp_path):
        path = tmp_path / "state.tsv"
        save_rotation_state(path, {"zebra": "t1", "alpha": "t2"})
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines == ["alpha\tt2", "zebra\tt1"]

    def test_blank_lines_are_skipped_on_load(self, tmp_path):
        path = tmp_path / "state.tsv"
        path.write_text("a\t2026-09-01\n\nb\t2026-09-02\n", encoding="utf-8")
        assert load_rotation_state(path) == {"a": "2026-09-01", "b": "2026-09-02"}


class TestSelectSubset:
    def test_never_run_names_come_before_any_run_name(self):
        pool = ["a", "b", "c"]
        state = {"a": "2026-09-01T00:00:00+03:00"}
        assert select_subset(pool, state, subset_size=2) == ["b", "c"]

    def test_least_recently_run_selected_first_among_run_names(self):
        pool = ["a", "b", "c"]
        state = {
            "a": "2026-09-05T00:00:00+03:00",
            "b": "2026-09-01T00:00:00+03:00",
            "c": "2026-09-03T00:00:00+03:00",
        }
        assert select_subset(pool, state, subset_size=3) == ["b", "c", "a"]

    def test_subset_size_caps_the_result(self):
        assert len(select_subset(["a", "b", "c"], {}, subset_size=1)) == 1

    def test_ties_fall_back_to_pool_order(self):
        pool = ["x", "y", "z"]
        assert select_subset(pool, {}, subset_size=3) == ["x", "y", "z"]


class TestRecordRun:
    def test_stamps_given_names_at_the_given_timestamp(self):
        updated = record_run({}, ["a", "b"], "2026-09-12T00:00:00+03:00")
        assert updated == {"a": "2026-09-12T00:00:00+03:00", "b": "2026-09-12T00:00:00+03:00"}

    def test_does_not_mutate_the_input_state(self):
        original = {"a": "old"}
        record_run(original, ["a"], "new")
        assert original == {"a": "old"}

    def test_leaves_untouched_names_alone(self):
        updated = record_run({"a": "old", "z": "keep"}, ["a"], "new")
        assert updated == {"a": "new", "z": "keep"}


class TestReactionCaptureStub:
    def test_records_zero_calls_when_nothing_reacts(self):
        stub = ReactionCaptureStub()
        with stub.installed():
            pass
        assert stub.calls == []

    def test_records_a_react_to_message_tool_call(self):
        from src.handlers import ai_handler

        stub = ReactionCaptureStub()
        with stub.installed():
            ai_handler.send_reaction(None, "972500000000@c.us", "wamid.2", "✅")
        assert len(stub.calls) == 1
        assert stub.calls[0].source == "react_to_message"

    def test_fresh_stub_per_scenario_does_not_leak_calls(self):
        from src.handlers import ai_handler

        first = ReactionCaptureStub()
        with first.installed():
            ai_handler.send_reaction(None, "chat@c.us", "wamid.1", "👀")

        second = ReactionCaptureStub()
        with second.installed():
            pass

        assert len(first.calls) == 1
        assert second.calls == []


class TestReactionTuningJudgmentLog:
    def test_append_writes_a_json_array_entry(self, tmp_path):
        log = ReactionTuningJudgmentLog(tmp_path, "20260912T000000")
        stub = ReactionCaptureStub()
        log.append("some_scenario", stub.calls, reply_text="hi")
        on_disk = json.loads(log.path.read_text(encoding="utf-8"))
        assert len(on_disk) == 1
        assert on_disk[0]["scenario"] == "some_scenario"
        assert on_disk[0]["reply_text"] == "hi"
        assert on_disk[0]["reactions"] == []

    def test_zero_call_outcome_is_a_valid_loggable_entry(self, tmp_path):
        log = ReactionTuningJudgmentLog(tmp_path, "round1")
        log.append("ambient_scenario", [])
        assert log.entries[0]["reactions"] == []

    def test_appends_accumulate_within_the_same_round(self, tmp_path):
        log = ReactionTuningJudgmentLog(tmp_path, "round1")
        log.append("scenario_a", [])
        log.append("scenario_b", [])
        assert [e["scenario"] for e in log.entries] == ["scenario_a", "scenario_b"]

    def test_reopening_the_same_round_file_loads_prior_entries(self, tmp_path):
        first = ReactionTuningJudgmentLog(tmp_path, "round1")
        first.append("scenario_a", [])

        second = ReactionTuningJudgmentLog(tmp_path, "round1")
        assert len(second.entries) == 1
        second.append("scenario_b", [])
        assert len(second.entries) == 2

    def test_captured_reaction_calls_are_serialized_as_dicts(self, tmp_path):
        from src.handlers import ai_handler

        stub = ReactionCaptureStub()
        with stub.installed():
            ai_handler.send_reaction(None, "chat@c.us", "wamid.1", "👀")

        log = ReactionTuningJudgmentLog(tmp_path, "round1")
        log.append("scenario_a", stub.calls)
        on_disk = json.loads(log.path.read_text(encoding="utf-8"))
        assert on_disk[0]["reactions"] == [
            {"source": "react_to_message", "chat_id": "chat@c.us", "id_message": "wamid.1", "reaction": "👀"}
        ]
