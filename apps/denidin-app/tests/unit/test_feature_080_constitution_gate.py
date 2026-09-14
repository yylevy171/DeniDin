"""Feature 080 — the "Proactive Progress Updates" constitution section's markers
(`<!-- FEATURE_080_PROGRESS_UPDATES_START/END -->`) are always stripped from the assembled
prompt, leaving the directive text in place. The feature flag that used to gate this on/off
has been removed (2026-09-12, explicit operator instruction - never gated by request); the
gate function now only strips the now-inert markers themselves. Tests the gate function
directly (no live OpenAI client needed) rather than constructing a full AIHandler, per
CONSTITUTION §I/§V - this is pure string-transform logic, nothing to mock.
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


def _gate(content: str) -> str:
    fake_self = SimpleNamespace(config=SimpleNamespace(feature_flags={}))
    return AIHandler._apply_feature_080_constitution_gate(fake_self, content)  # noqa: SLF001


class TestFeature080ConstitutionGate:
    def test_keeps_content_strips_only_markers(self):
        result = _gate(CONTENT_WITH_MARKERS)
        assert "Proactive Progress Updates" in result
        assert "some directive text" in result
        assert "FEATURE_080_PROGRESS_UPDATES" not in result

    def test_no_markers_present_returns_content_unchanged(self):
        content = "just plain constitution text, no feature 080 block at all"
        assert _gate(content) == content

    def test_real_runtime_constitution_file_gates_correctly(self):
        """Guards against the markers ever silently drifting out of
        config/runtime_constitution.md (e.g. an edit that removes one but not the other)."""
        content = open("config/runtime_constitution.md", encoding="utf-8").read()
        assert "<!-- FEATURE_080_PROGRESS_UPDATES_START -->" in content
        assert "<!-- FEATURE_080_PROGRESS_UPDATES_END -->" in content

        result = _gate(content)
        # Use the section heading, not the bare phrase - several OTHER sections
        # legitimately cross-reference "Proactive Progress Updates" by name outside
        # the marked block itself (CLAUDE.md's bidirectional cross-reference rule).
        heading = "## Proactive Progress Updates"
        assert heading in result
        assert "FEATURE_080_PROGRESS_UPDATES" not in result
