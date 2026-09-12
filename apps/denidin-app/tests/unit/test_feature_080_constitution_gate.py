"""Feature 080 (T011) — the "Proactive Progress Updates" constitution section is stripped
from the assembled prompt when feature_flags.verbosity_and_telemetry_080 is off (default),
and stays in place (markers only removed) when it's on. Tests the gate function directly
(no live OpenAI client needed) rather than constructing a full AIHandler, per CONSTITUTION
§I/§V - this is pure string-transform logic, nothing to mock.
"""
from types import SimpleNamespace

from src.handlers.ai_handler import AIHandler

CONTENT_WITH_MARKERS = (
    "before\n"
    "<!-- FEATURE_080_PROGRESS_UPDATES_START -->\n"
    "## Proactive Progress Updates\nsome directive text\n"
    "<!-- FEATURE_080_PROGRESS_UPDATES_END -->\n"
    "after"
)


def _gate(content: str, flag_on: bool) -> str:
    fake_self = SimpleNamespace(config=SimpleNamespace(feature_flags={
        'verbosity_and_telemetry_080': flag_on
    }))
    return AIHandler._apply_feature_080_constitution_gate(fake_self, content)  # noqa: SLF001


class TestFeature080ConstitutionGate:
    def test_flag_off_strips_the_whole_block(self):
        result = _gate(CONTENT_WITH_MARKERS, flag_on=False)
        assert "Proactive Progress Updates" not in result
        assert "FEATURE_080_PROGRESS_UPDATES" not in result
        assert result == "before\n\nafter"

    def test_flag_on_keeps_content_strips_only_markers(self):
        result = _gate(CONTENT_WITH_MARKERS, flag_on=True)
        assert "Proactive Progress Updates" in result
        assert "some directive text" in result
        assert "FEATURE_080_PROGRESS_UPDATES" not in result

    def test_no_markers_present_returns_content_unchanged(self):
        content = "just plain constitution text, no feature 080 block at all"
        assert _gate(content, flag_on=False) == content
        assert _gate(content, flag_on=True) == content

    def test_real_runtime_constitution_file_gates_correctly(self):
        """Guards against the markers ever silently drifting out of
        config/runtime_constitution.md (e.g. an edit that removes one but not the other)."""
        content = open("config/runtime_constitution.md", encoding="utf-8").read()
        assert "<!-- FEATURE_080_PROGRESS_UPDATES_START -->" in content
        assert "<!-- FEATURE_080_PROGRESS_UPDATES_END -->" in content

        off = _gate(content, flag_on=False)
        on = _gate(content, flag_on=True)
        # Use the section heading, not the bare phrase - several OTHER sections
        # legitimately cross-reference "Proactive Progress Updates" by name outside
        # the marked block itself (CLAUDE.md's bidirectional cross-reference rule).
        heading = "## Proactive Progress Updates"
        assert heading not in off
        assert heading in on
        assert len(on) > len(off)  # on keeps the directive text, off strips it
