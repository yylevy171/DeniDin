"""
Unit tests for MessageState model.
Tests state persistence and loading functionality.
"""
import json
import pytest
import tempfile
import os
from pathlib import Path
from src.models.state import MessageState


class TestMessageState:
    """Test suite for MessageState model."""

    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            state_data = {
                'last_message_id': 'msg_12345',
                'last_timestamp': 1234567890
            }
            json.dump(state_data, f)
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for state files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_load_from_nonexistent_file_returns_default_state(self, temp_dir):
        """Test that load() from non-existent file returns default state."""
        non_existent_path = os.path.join(temp_dir, 'does_not_exist.json')
        state = MessageState.load(non_existent_path)
        
        assert state.last_message_id is None
        assert state.last_timestamp is None

    def test_load_from_valid_json_file_returns_state(self, temp_state_file):
        """Test that load() from valid JSON file returns state."""
        state = MessageState.load(temp_state_file)
        
        assert state.last_message_id == 'msg_12345'
        assert state.last_timestamp == 1234567890

    def test_save_persists_to_file(self, temp_dir):
        """Test that save() persists to state/last_message.json."""
        state_file = os.path.join(temp_dir, 'last_message.json')
        state = MessageState(
            last_message_id='msg_99999',
            last_timestamp=9999999999
        )
        
        state.save(state_file)
        
        # Verify file was created
        assert os.path.exists(state_file)
        
        # Verify content is correct
        with open(state_file, 'r') as f:
            data = json.load(f)
        assert data['last_message_id'] == 'msg_99999'
        assert data['last_timestamp'] == 9999999999

    def test_update_updates_message_id_and_timestamp(self):
        """Test that update() updates message_id and timestamp."""
        state = MessageState(
            last_message_id='msg_old',
            last_timestamp=1000000000
        )
        
        state.update('msg_new', 2000000000)
        
        assert state.last_message_id == 'msg_new'
        assert state.last_timestamp == 2000000000

    def test_json_serialization(self, temp_dir):
        """Test JSON serialization/deserialization."""
        state_file = os.path.join(temp_dir, 'test_state.json')
        
        # Create and save state
        original_state = MessageState(
            last_message_id='msg_serialize_test',
            last_timestamp=1234567890
        )
        original_state.save(state_file)
        
        # Load state back
        loaded_state = MessageState.load(state_file)
        
        assert loaded_state.last_message_id == original_state.last_message_id
        assert loaded_state.last_timestamp == original_state.last_timestamp

    def test_json_deserialization(self, temp_state_file):
        """Test JSON deserialization from file."""
        state = MessageState.load(temp_state_file)
        
        assert isinstance(state, MessageState)
        assert state.last_message_id == 'msg_12345'
        assert state.last_timestamp == 1234567890

    def test_default_state_values(self):
        """Test that default state has None values."""
        state = MessageState()
        
        assert state.last_message_id is None
        assert state.last_timestamp is None
