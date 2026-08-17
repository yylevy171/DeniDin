"""
Unit tests for constitution template rendering + per-tenant supplement
concatenation (Feature 055: Multi-Tenancy, tasks.md Phase 7, T027a/T028a,
REQ-CONST-001/002/003).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Exercises
AIHandler._load_constitution/_load_constitution_supplement directly, same
pattern as the existing test_ai_handler_constitution.py (constructs a real
AIHandler against a real tmp_path constitution file - no mocking of internal
code, CONSTITUTION §I/§V).

REQ-PARITY-001: config.bot_name defaults to "DeniDin" (the pre-055 hardcoded
literal) and config.constitution_supplement_file defaults to None - a config
that never sets either renders byte-identically to before this feature existed,
which test_ai_handler_constitution.py's own (untouched, still-passing) fixtures
already prove implicitly (their content contains no {bot_name} placeholder at
all, so the render step is a no-op on them).
"""
from unittest.mock import MagicMock

import pytest

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration


def _config(tmp_path, **overrides):
    kwargs = {
        "green_api_instance_id": "test",
        "green_api_token": "test",
        "ai_api_key": "test-key",
        "data_root": "test_data",
        "constitution_config": {"file": "runtime_constitution.md", "base_dir": str(tmp_path)},
    }
    kwargs.update(overrides)
    return AppConfiguration(**kwargs)


def _write_common_constitution(tmp_path, content=None):
    content = content or (
        "# {bot_name} AI Assistant Constitution\n\n"
        "## Core Identity\n"
        "You are {bot_name}, a helpful AI assistant.\n\n"
        "That name {bot_name}, or a variant of it, settles it.\n"
    )
    (tmp_path / "runtime_constitution.md").write_text(content, encoding="utf-8")
    return content.strip()


class TestBotNameTemplateRendering:
    """REQ-CONST-002: {bot_name} substituted per tenant."""

    def test_bot_name_placeholder_is_substituted(self, tmp_path):
        _write_common_constitution(tmp_path)
        config = _config(tmp_path, bot_name="Jabaloola")
        handler = AIHandler(MagicMock(), config)

        rendered = handler._load_constitution()  # pylint: disable=protected-access

        assert "Jabaloola" in rendered
        assert "{bot_name}" not in rendered

    def test_every_occurrence_of_the_placeholder_is_substituted(self, tmp_path):
        """Not just the first match - the self-recognition section names the
        bot 3 times in the real file; all must render, per REQ-CONST-002's
        note that a wrong/un-substituted name would break that mechanism."""
        content = _write_common_constitution(tmp_path)
        placeholder_count = content.count("{bot_name}")
        config = _config(tmp_path, bot_name="Jabaloola")
        handler = AIHandler(MagicMock(), config)

        rendered = handler._load_constitution()  # pylint: disable=protected-access

        assert rendered.count("Jabaloola") == placeholder_count

    def test_default_bot_name_is_denidin_when_not_configured(self, tmp_path):
        """REQ-PARITY-001: a config that never sets bot_name renders exactly
        as the pre-055 hardcoded literal did."""
        _write_common_constitution(tmp_path)
        config = _config(tmp_path)  # bot_name omitted -> dataclass default
        handler = AIHandler(MagicMock(), config)

        rendered = handler._load_constitution()  # pylint: disable=protected-access

        assert "DeniDin" in rendered
        assert "{bot_name}" not in rendered

    def test_content_with_no_placeholder_at_all_is_unaffected(self, tmp_path):
        """A pre-055-shaped fixture (no {bot_name} anywhere) renders byte-
        identically - the substitution is a no-op, never an error."""
        content = _write_common_constitution(
            tmp_path, content="# DeniDin Constitution\n\nYou are DeniDin.\n"
        )
        config = _config(tmp_path, bot_name="Jabaloola")
        handler = AIHandler(MagicMock(), config)

        rendered = handler._load_constitution()  # pylint: disable=protected-access

        assert rendered == content


class TestSameTenantRenderingIsStable:
    """SC-006: two calls for the SAME tenant produce byte-identical rendered
    common section - the stable prefix OpenAI's prompt caching relies on."""

    def test_two_calls_same_tenant_produce_identical_output(self, tmp_path):
        _write_common_constitution(tmp_path)
        config = _config(tmp_path, bot_name="Jabaloola")
        handler = AIHandler(MagicMock(), config)

        first = handler._load_constitution()  # pylint: disable=protected-access
        second = handler._load_constitution()  # pylint: disable=protected-access

        assert first == second


class TestDifferentTenantsRenderDifferently:
    """Two different tenants' rendered common sections differ only in
    bot_name (and any other template values), never in supplement content
    leaking across (each AIHandler instance is its own tenant's, so this is
    really about proving no shared mutable cache state between them)."""

    def test_two_tenants_get_different_rendered_bot_names(self, tmp_path):
        _write_common_constitution(tmp_path)
        config_a = _config(tmp_path, bot_name="DeniDin")
        config_b = _config(tmp_path, bot_name="Jabaloola")
        handler_a = AIHandler(MagicMock(), config_a)
        handler_b = AIHandler(MagicMock(), config_b)

        rendered_a = handler_a._load_constitution()  # pylint: disable=protected-access
        rendered_b = handler_b._load_constitution()  # pylint: disable=protected-access

        assert "DeniDin" in rendered_a and "Jabaloola" not in rendered_a
        assert "Jabaloola" in rendered_b and "DeniDin" not in rendered_b

    def test_the_only_difference_is_the_bot_name(self, tmp_path):
        _write_common_constitution(tmp_path)
        config_a = _config(tmp_path, bot_name="DeniDin")
        config_b = _config(tmp_path, bot_name="Jabaloola")
        handler_a = AIHandler(MagicMock(), config_a)
        handler_b = AIHandler(MagicMock(), config_b)

        rendered_a = handler_a._load_constitution()  # pylint: disable=protected-access
        rendered_b = handler_b._load_constitution()  # pylint: disable=protected-access

        assert rendered_a.replace("DeniDin", "X") == rendered_b.replace("Jabaloola", "X")


class TestConstitutionSupplementConcatenation:
    """REQ-CONST-001/003: a tenant's supplement is a standalone .md file,
    concatenated after the rendered common section; missing/empty is not an
    error and adds no stray blank section."""

    def test_supplement_is_appended_after_the_common_section(self, tmp_path):
        _write_common_constitution(tmp_path)
        supplement_file = tmp_path / "supplement.md"
        supplement_file.write_text("## Tenant-Specific Rules\nAlways mention pricing.", encoding="utf-8")
        config = _config(tmp_path, bot_name="Jabaloola", constitution_supplement_file=str(supplement_file))
        handler = AIHandler(MagicMock(), config)

        rendered = handler._load_constitution()  # pylint: disable=protected-access

        assert "Jabaloola" in rendered
        assert "Tenant-Specific Rules" in rendered
        assert rendered.index("Jabaloola") < rendered.index("Tenant-Specific Rules")

    def test_no_supplement_configured_produces_no_stray_section(self, tmp_path):
        content = _write_common_constitution(tmp_path)
        config = _config(tmp_path, bot_name="Jabaloola")  # constitution_supplement_file omitted
        handler = AIHandler(MagicMock(), config)

        rendered = handler._load_constitution()  # pylint: disable=protected-access

        assert rendered == content.replace("{bot_name}", "Jabaloola")

    def test_declared_but_missing_supplement_file_produces_no_error_and_no_stray_section(self, tmp_path):
        content = _write_common_constitution(tmp_path)
        config = _config(
            tmp_path, bot_name="Jabaloola",
            constitution_supplement_file=str(tmp_path / "does_not_exist.md"),
        )
        handler = AIHandler(MagicMock(), config)

        rendered = handler._load_constitution()  # pylint: disable=protected-access

        assert rendered == content.replace("{bot_name}", "Jabaloola")

    def test_empty_supplement_file_produces_no_error_and_no_stray_section(self, tmp_path):
        content = _write_common_constitution(tmp_path)
        supplement_file = tmp_path / "empty_supplement.md"
        supplement_file.write_text("", encoding="utf-8")
        config = _config(tmp_path, bot_name="Jabaloola", constitution_supplement_file=str(supplement_file))
        handler = AIHandler(MagicMock(), config)

        rendered = handler._load_constitution()  # pylint: disable=protected-access

        assert rendered == content.replace("{bot_name}", "Jabaloola")

    def test_two_tenants_supplements_never_leak_across(self, tmp_path):
        _write_common_constitution(tmp_path)
        supplement_a = tmp_path / "supplement_a.md"
        supplement_a.write_text("Tenant A's private rule.", encoding="utf-8")
        supplement_b = tmp_path / "supplement_b.md"
        supplement_b.write_text("Tenant B's private rule.", encoding="utf-8")

        config_a = _config(tmp_path, bot_name="A", constitution_supplement_file=str(supplement_a))
        config_b = _config(tmp_path, bot_name="B", constitution_supplement_file=str(supplement_b))
        handler_a = AIHandler(MagicMock(), config_a)
        handler_b = AIHandler(MagicMock(), config_b)

        rendered_a = handler_a._load_constitution()  # pylint: disable=protected-access
        rendered_b = handler_b._load_constitution()  # pylint: disable=protected-access

        assert "Tenant A's private rule" in rendered_a
        assert "Tenant B's private rule" not in rendered_a
        assert "Tenant B's private rule" in rendered_b
        assert "Tenant A's private rule" not in rendered_b

    def test_supplement_mtime_change_is_picked_up_on_next_load(self, tmp_path):
        """Same mtime-based reload behavior the common file already has (Feature
        002+), independently applied to the supplement file."""
        _write_common_constitution(tmp_path)
        supplement_file = tmp_path / "supplement.md"
        supplement_file.write_text("Version 1", encoding="utf-8")
        config = _config(tmp_path, bot_name="Jabaloola", constitution_supplement_file=str(supplement_file))
        handler = AIHandler(MagicMock(), config)

        first = handler._load_constitution()  # pylint: disable=protected-access
        assert "Version 1" in first

        import time
        time.sleep(0.01)
        supplement_file.write_text("Version 2", encoding="utf-8")

        second = handler._load_constitution()  # pylint: disable=protected-access
        assert "Version 2" in second
        assert "Version 1" not in second
