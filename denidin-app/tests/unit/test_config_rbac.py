"""Unit tests for AppConfiguration RBAC fields."""

import pytest
import json
import tempfile
import os
from src.models.config import AppConfiguration


class TestAppConfigurationRBACFields:
    """Test RBAC-related configuration fields."""
    
    def test_config_with_godfather_phone(self):
        """Test that godfather_phone is properly stored."""
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key",
            godfather_phone="+972507654321"
        )
        assert config.godfather_phone == "+972507654321"
    
    def test_config_without_godfather_phone_defaults_to_none(self):
        """Test that godfather_phone defaults to None."""
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key"
        )
        assert config.godfather_phone is None
    
    def test_config_with_admin_phones_list(self):
        """Test that admin_phones list can be configured."""
        admin_phones = ["+972509999999", "+972508888888"]
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key",
            user_roles={"admin_phones": admin_phones}
        )
        assert config.user_roles["admin_phones"] == admin_phones
    
    def test_config_with_blocked_phones_list(self):
        """Test that blocked_phones list can be configured."""
        blocked_phones = ["+972501111111", "+972502222222"]
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key",
            user_roles={"blocked_phones": blocked_phones}
        )
        assert config.user_roles["blocked_phones"] == blocked_phones
    
    def test_config_with_enable_rbac_feature_flag(self):
        """Test that enable_rbac feature flag can be set."""
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key",
            feature_flags={"enable_rbac": True}
        )
        assert config.feature_flags["enable_rbac"] is True
    
    def test_config_with_enable_rbac_disabled(self):
        """Test that enable_rbac can be disabled."""
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key",
            feature_flags={"enable_rbac": False}
        )
        assert config.feature_flags["enable_rbac"] is False
    
    def test_config_without_enable_rbac_flag(self):
        """Test that enable_rbac defaults to not present in feature_flags."""
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key"
        )
        assert "enable_rbac" not in config.feature_flags


class TestAppConfigurationRBACFromFile:
    """Test loading RBAC configuration from JSON files."""
    
    def test_load_config_with_godfather_phone_from_json(self):
        """Test loading godfather_phone from JSON file."""
        config_data = {
            "green_api_instance_id": "test_instance",
            "green_api_token": "test_token",
            "ai_api_key": "test_key",
            "godfather_phone": "+972507654321"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            config = AppConfiguration.from_file(temp_file)
            assert config.godfather_phone == "+972507654321"
        finally:
            os.unlink(temp_file)
    
    def test_load_config_with_user_roles_from_json(self):
        """Test loading user_roles from JSON file."""
        config_data = {
            "green_api_instance_id": "test_instance",
            "green_api_token": "test_token",
            "ai_api_key": "test_key",
            "user_roles": {
                "admin_phones": ["+972509999999"],
                "blocked_phones": ["+972501111111", "+972502222222"]
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            config = AppConfiguration.from_file(temp_file)
            assert config.user_roles["admin_phones"] == ["+972509999999"]
            assert len(config.user_roles["blocked_phones"]) == 2
        finally:
            os.unlink(temp_file)
    
    def test_load_config_with_enable_rbac_flag_from_json(self):
        """Test loading enable_rbac feature flag from JSON file."""
        config_data = {
            "green_api_instance_id": "test_instance",
            "green_api_token": "test_token",
            "ai_api_key": "test_key",
            "feature_flags": {
                "enable_memory_system": True,
                "enable_rbac": True
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            config = AppConfiguration.from_file(temp_file)
            assert config.feature_flags["enable_rbac"] is True
            assert config.feature_flags["enable_memory_system"] is True
        finally:
            os.unlink(temp_file)
    
    def test_load_config_with_all_rbac_fields_from_json(self):
        """Test loading complete RBAC configuration from JSON file."""
        config_data = {
            "green_api_instance_id": "test_instance",
            "green_api_token": "test_token",
            "ai_api_key": "test_key",
            "godfather_phone": "+972507654321",
            "user_roles": {
                "admin_phones": ["+972509999999"],
                "blocked_phones": ["+972501111111"]
            },
            "feature_flags": {
                "enable_rbac": False
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            config = AppConfiguration.from_file(temp_file)
            assert config.godfather_phone == "+972507654321"
            assert config.user_roles["admin_phones"] == ["+972509999999"]
            assert config.user_roles["blocked_phones"] == ["+972501111111"]
            assert config.feature_flags["enable_rbac"] is False
        finally:
            os.unlink(temp_file)


class TestAppConfigurationRBACDefaults:
    """Test default values for RBAC fields."""
    
    def test_user_roles_defaults_to_empty_dict(self):
        """Test that user_roles defaults to empty dictionary."""
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key"
        )
        assert config.user_roles == {}
    
    def test_feature_flags_defaults_to_empty_dict(self):
        """Test that feature_flags defaults to empty dictionary."""
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key"
        )
        assert config.feature_flags == {}
    
    def test_can_add_admin_phones_to_empty_user_roles(self):
        """Test that admin_phones can be added to user_roles after creation."""
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key"
        )
        config.user_roles["admin_phones"] = ["+972509999999"]
        assert config.user_roles["admin_phones"] == ["+972509999999"]
    
    def test_can_set_enable_rbac_in_feature_flags_after_creation(self):
        """Test that enable_rbac can be set in feature_flags after creation."""
        config = AppConfiguration(
            green_api_instance_id="test_instance",
            green_api_token="test_token",
            ai_api_key="test_key"
        )
        config.feature_flags["enable_rbac"] = True
        assert config.feature_flags["enable_rbac"] is True
