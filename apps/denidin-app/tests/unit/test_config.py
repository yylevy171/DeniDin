"""  
Unit tests for AppConfiguration model.
Tests configuration loading from JSON/YAML files and validation.
"""
import ast
import dataclasses
import json
import pytest
import tempfile
import os
from pathlib import Path
from src.models.config import AppConfiguration
class TestAppConfiguration:
    """Test suite for AppConfiguration model."""

    @pytest.fixture
    def valid_config_data(self):
        """Provide valid configuration data."""
        return {
            "green_api_instance_id": "1234567890",
            "green_api_token": "abcdef123456",
            "ai_api_key": "sk-test123",
            "ai_model": "gpt-4",
            "log_level": "INFO"
        }

    @pytest.fixture
    def temp_json_config(self, valid_config_data):
        """Create a temporary JSON config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_config_data, f)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def temp_yaml_config(self, valid_config_data):
        """Create a temporary YAML config file."""
        import yaml
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(valid_config_data, f)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    def test_from_file_loads_json_correctly(self, temp_json_config):
        """Test that from_file() loads JSON config correctly."""
        config = AppConfiguration.from_file(temp_json_config)
        
        assert config.green_api_instance_id == "1234567890"
        assert config.green_api_token == "abcdef123456"
        assert config.ai_api_key == "sk-test123"
        assert config.ai_model == "gpt-4"
        assert config.log_level == "INFO"

    def test_from_file_loads_yaml_correctly(self, temp_yaml_config):
        """Test that from_file() loads YAML config correctly."""
        config = AppConfiguration.from_file(temp_yaml_config)

        assert config.green_api_instance_id == "1234567890"
        assert config.green_api_token == "abcdef123456"
        assert config.ai_api_key == "sk-test123"
        assert config.ai_model == "gpt-4"
        assert config.log_level == "INFO"

    def test_from_file_missing_required_field_raises_error(self):
        """Test that from_file() raises ValueError when required fields are missing."""
        incomplete_config = {
            "green_api_instance_id": "1234567890",
            # missing green_api_token
            "ai_api_key": "sk-test123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            assert "green_api_token" in str(exc_info.value).lower()
        finally:
            os.unlink(temp_path)

    def test_from_file_missing_green_api_instance_id(self):
        """Test that from_file() raises ValueError listing missing green_api_instance_id."""
        incomplete_config = {
            # missing green_api_instance_id
            "green_api_token": "abcdef123456",
            "ai_api_key": "sk-test123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            error_message = str(exc_info.value).lower()
            assert "green_api_instance_id" in error_message
        finally:
            os.unlink(temp_path)

    def test_from_file_missing_green_api_token(self):
        """Test that from_file() raises ValueError for missing green_api_token."""
        incomplete_config = {
            "green_api_instance_id": "1234567890",
            # missing green_api_token
            "ai_api_key": "sk-test123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            error_message = str(exc_info.value).lower()
            assert "green_api_token" in error_message
        finally:
            os.unlink(temp_path)

    def test_from_file_missing_ai_api_key(self):
        """Test that from_file() raises ValueError for missing ai_api_key."""
        incomplete_config = {
            "green_api_instance_id": "1234567890",
            "green_api_token": "abcdef123456"
            # missing ai_api_key
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            error_message = str(exc_info.value).lower()
            assert "ai_api_key" in error_message
        finally:
            os.unlink(temp_path)

    def test_from_file_lists_all_missing_fields(self):
        """Test error message clearly lists ALL missing required fields."""
        incomplete_config = {
            # missing all three required fields
            "ai_model": "gpt-4"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                AppConfiguration.from_file(temp_path)
            error_message = str(exc_info.value).lower()
            # All three required fields should be mentioned
            assert "green_api_instance_id" in error_message
            assert "green_api_token" in error_message
            assert "ai_api_key" in error_message
        finally:
            os.unlink(temp_path)

    def test_from_file_succeeds_with_all_required_fields(self):
        """Test from_file() succeeds with all required fields present in config.json."""
        config_with_required = {
            "green_api_instance_id": "1234567890",
            "green_api_token": "abcdef123456",
            "ai_api_key": "sk-test123"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_with_required, f)
            temp_path = f.name
        
        try:
            config = AppConfiguration.from_file(temp_path)
            assert config.green_api_instance_id == "1234567890"
            assert config.green_api_token == "abcdef123456"
            assert config.ai_api_key == "sk-test123"
        finally:
            os.unlink(temp_path)

    def test_validate_passes_with_valid_ranges(self, valid_config_data):
        """Test that validate() passes with valid value ranges."""
        config = AppConfiguration(**valid_config_data)
        
        # Should not raise any exception
        config.validate()

    def test_validate_fails_with_invalid_max_tokens(self, valid_config_data):
        """Test that validate() fails when ai_reply_max_tokens < 1."""
        valid_config_data['ai_reply_max_tokens'] = 0
        config = AppConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "ai_reply_max_tokens" in str(exc_info.value).lower()

    def test_max_retries_defaults_to_1(self, valid_config_data):
        """2026-08-19 fix: max_retries used to be declared in config.test.json/
        config.example.json but silently dropped on load (no matching
        dataclass field existed) - now a real field, default 1."""
        config = AppConfiguration(**valid_config_data)
        assert config.max_retries == 1

    def test_max_retries_loaded_from_file(self, tmp_path, valid_config_data):
        """from_file() must actually pick up an explicit max_retries value,
        not silently drop it (the exact gap this field's addition closes)."""
        valid_config_data['max_retries'] = 3
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(valid_config_data), encoding='utf-8')

        config = AppConfiguration.from_file(str(config_path))

        assert config.max_retries == 3

    def test_validate_fails_with_negative_max_retries(self, valid_config_data):
        """Test that validate() fails when max_retries < 0."""
        valid_config_data['max_retries'] = -1
        config = AppConfiguration(**valid_config_data)

        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "max_retries" in str(exc_info.value).lower()

    def test_validate_passes_with_zero_max_retries(self, valid_config_data):
        """0 is a valid value - it means no retries at all, not "unset"."""
        valid_config_data['max_retries'] = 0
        config = AppConfiguration(**valid_config_data)

        config.validate()  # Should not raise

    def test_accounting_ledger_update_freq_defaults_to_0(self, valid_config_data):
        """Feature 025 (round 3): a fresh environment's config that doesn't
        yet mention this field must default to 0 (inactive) - an environment
        must never accidentally start polling Morning just because this key
        was never set."""
        config = AppConfiguration(**valid_config_data)
        assert config.accounting_ledger_update_freq == 0

    def test_accounting_ledger_update_freq_loaded_from_file(self, tmp_path, valid_config_data):
        """from_file() must actually pick up an explicit value, same
        precedent as max_retries above."""
        valid_config_data['accounting_ledger_update_freq'] = 60
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(valid_config_data), encoding='utf-8')

        config = AppConfiguration.from_file(str(config_path))

        assert config.accounting_ledger_update_freq == 60

    def test_accounting_ledger_update_freq_0_is_accepted_not_coerced(self, tmp_path, valid_config_data):
        """0 is a real, valid, explicitly-settable value (means "inactive"),
        not something from_file() should treat as equivalent to "unset"."""
        valid_config_data['accounting_ledger_update_freq'] = 0
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(valid_config_data), encoding='utf-8')

        config = AppConfiguration.from_file(str(config_path))

        assert config.accounting_ledger_update_freq == 0

    def test_log_level_validates_info_debug_only(self, valid_config_data):
        """Test that log_level only accepts INFO or DEBUG."""
        # Test valid values
        for valid_level in ["INFO", "DEBUG"]:
            valid_config_data['log_level'] = valid_level
            config = AppConfiguration(**valid_config_data)
            config.validate()  # Should not raise
        
        # Test invalid value
        valid_config_data['log_level'] = "INVALID"
        config = AppConfiguration(**valid_config_data)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "log_level" in str(exc_info.value).lower()

    def test_config_dataclass_attributes_exist(self, valid_config_data):
        """Test that all required dataclass attributes exist."""
        config = AppConfiguration(**valid_config_data)
        
        # Verify all attributes are accessible
        assert hasattr(config, 'green_api_instance_id')
        assert hasattr(config, 'green_api_token')
        assert hasattr(config, 'ai_api_key')
        assert hasattr(config, 'ai_model')
        assert hasattr(config, 'log_level')
        assert hasattr(config, 'data_root')

    def test_data_root_defaults_to_data(self, valid_config_data):
        """Test that data_root defaults to 'data' when not specified."""
        config = AppConfiguration(**valid_config_data)
        assert config.data_root == 'data'

    def test_data_root_can_be_customized(self, valid_config_data):
        """Test that data_root can be set to custom value (e.g., for test isolation)."""
        valid_config_data['data_root'] = '/tmp/test_data'
        config = AppConfiguration(**valid_config_data)
        assert config.data_root == '/tmp/test_data'

    def test_validate_fails_with_empty_data_root(self, valid_config_data):
        """Test that validate() fails when data_root is empty."""
        valid_config_data['data_root'] = ''
        config = AppConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "data_root" in str(exc_info.value).lower()

    def test_validate_fails_with_whitespace_data_root(self, valid_config_data):
        """Test that validate() fails when data_root is only whitespace."""
        valid_config_data['data_root'] = '   '
        config = AppConfiguration(**valid_config_data)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "data_root" in str(exc_info.value).lower()

    def test_memory_storage_paths_use_data_root(self, tmp_path):
        """Test that memory storage paths are constructed relative to data_root."""
        temp_config = tmp_path / "config_with_data_root.json"
        config_data = {
            "green_api_instance_id": "test123",
            "green_api_token": "test_token_xyz",
            "ai_api_key": "sk-test123",
            "data_root": "test_data",
            "memory": {
                "session": {"storage_dir": "sessions"},  # Relative path
                "longterm": {"storage_dir": "memory"}     # Relative path
            }
        }
        
        with open(temp_config, 'w') as f:
            json.dump(config_data, f)
        
        config = AppConfiguration.from_file(str(temp_config))
        
        # Verify storage paths combine data_root + relative storage_dir
        assert config.memory['session']['storage_dir'] == 'test_data/sessions'
        assert config.memory['longterm']['storage_dir'] == 'test_data/memory'

        os.unlink(temp_config)


class TestMainConfigDictStaysInSyncWithAppConfiguration:
    """Regression guard, added 2026-08-21 after a real live-dev bug (Feature
    025): denidin.py's `__main__` block hand-builds its own `config_dict`
    literal (a separate subset dict passed to initialize_app()) rather than
    reusing AppConfiguration.from_file's already-loaded object directly -
    accounting_ledger_update_freq was added to the AppConfiguration dataclass
    (and correctly covered by from_file's own defaults/tests above) but
    silently missing from THIS separate dict, so config.dev.json setting it
    to 60 had zero effect - the scheduler never started, with no error
    anywhere. Static-parses denidin.py's source (not an import - __main__
    code isn't safely importable) to catch a future field added to one place
    but not the other, without needing a live container to notice."""

    def test_every_appconfiguration_field_appears_as_a_config_dict_key(self):
        denidin_py_path = Path(__file__).parent.parent.parent / "denidin.py"
        tree = ast.parse(denidin_py_path.read_text(encoding="utf-8"))

        config_dict_keys = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "config_dict"
                and isinstance(node.value, ast.Dict)
            ):
                config_dict_keys = {
                    key.value for key in node.value.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                }
                break

        assert config_dict_keys is not None, (
            "Could not find denidin.py's __main__ config_dict = {...} literal - "
            "this test needs updating if that code moved/was renamed, not skipped"
        )

        # `environment` is a legitimate, pre-existing exception: it's read
        # directly from the mounted config file by watchdog.py (a separate
        # process, outside the AppConfiguration/config_dict/initialize_app()
        # flow entirely - see watchdog.py's own docstring), never through
        # AppConfiguration at all. Every other field must appear.
        known_exceptions = {"environment"}
        dataclass_field_names = {f.name for f in dataclasses.fields(AppConfiguration)} - known_exceptions
        missing = dataclass_field_names - config_dict_keys
        assert not missing, (
            f"AppConfiguration field(s) {missing} exist but are missing from denidin.py's "
            "__main__ config_dict literal - a config value set in config.dev.json/"
            "config.prod.json for these fields will silently have NO effect on the real "
            "running app, exactly like accounting_ledger_update_freq did (2026-08-21)"
        )
