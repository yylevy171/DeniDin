"""
Unit tests for the player's config/data-root safety checks (Feature 043,
tasks.md T013a).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md SS VI).

Per contracts/player-cli.md: --data-root is required, no default anywhere in
code; a --data-root resolving to the literal production path also requires
an explicit --confirm-production-data-root override. These are hard safety
requirements (spec.md's Environment/data-safety), not nice-to-haves.
"""
import pytest

from player.config_safety import PlayerSafetyError, validate_data_root


class TestValidateDataRoot:
    def test_none_data_root_raises(self):
        with pytest.raises(PlayerSafetyError):
            validate_data_root(None, confirm_production=False)

    def test_empty_string_data_root_raises(self):
        with pytest.raises(PlayerSafetyError):
            validate_data_root("", confirm_production=False)

    def test_ordinary_test_data_root_accepted(self):
        result = validate_data_root("test_data", confirm_production=False)
        assert str(result) == "test_data"

    def test_literal_production_path_without_confirm_raises(self):
        with pytest.raises(PlayerSafetyError):
            validate_data_root("data", confirm_production=False)

    def test_literal_production_path_with_confirm_accepted(self):
        result = validate_data_root("data", confirm_production=True)
        assert str(result) == "data"

    def test_absolute_path_ending_in_data_without_confirm_raises(self):
        with pytest.raises(PlayerSafetyError):
            validate_data_root("/mnt/prod-box/apps/denidin-app/data", confirm_production=False)

    def test_absolute_path_ending_in_data_with_confirm_accepted(self):
        result = validate_data_root("/mnt/prod-box/apps/denidin-app/data", confirm_production=True)
        assert str(result) == "/mnt/prod-box/apps/denidin-app/data"

    def test_path_ending_in_dev_data_not_treated_as_production(self):
        """dev_data isn't the production default - shouldn't require the
        override flag."""
        result = validate_data_root("dev_data", confirm_production=False)
        assert str(result) == "dev_data"
