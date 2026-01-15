"""
Unit tests for state persistence utility.
Tests directory creation, state loading, and saving functionality.
"""
import pytest
import tempfile
import os
import json
import shutil
from pathlib import Path
from src.utils.state import ensure_state_dir, load_message_state, save_message_state
from src.models.state import MessageState


class TestStateUtils:
    """Test suite for state utility functions."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_ensure_state_dir_creates_directory(self, temp_dir):
        """Test that ensure_state_dir() creates state/ directory."""
        state_dir = os.path.join(temp_dir, 'state')
        
        # Ensure it doesn't exist
        assert not os.path.exists(state_dir)
        
        # Call function
        ensure_state_dir(state_dir)
        
        # Verify directory was created
        assert os.path.exists(state_dir)
        assert os.path.isdir(state_dir)

    def test_ensure_state_dir_does_not_fail_if_exists(self, temp_dir):
        """Test that ensure_state_dir() doesn't fail if directory already exists."""
        state_dir = os.path.join(temp_dir, 'state')
        
        # Create directory first
        os.makedirs(state_dir)
        
        # Call function - should not raise
        ensure_state_dir(state_dir)
        
        # Verify directory still exists
        assert os.path.exists(state_dir)

    def test_load_message_state_returns_messagestate_instance(self, temp_dir):
        """Test that load_message_state() returns MessageState instance."""
        state_dir = os.path.join(temp_dir, 'state')
        ensure_state_dir(state_dir)
        
        state_file = os.path.join(state_dir, 'last_message.json')
        
        # Create a sample state file
        sample_state = {
            'last_message_id': 'msg_12345',
            'last_timestamp': 1234567890
        }
        with open(state_file, 'w') as f:
            json.dump(sample_state, f)
        
        # Load state
        state = load_message_state(state_file)
        
        assert isinstance(state, MessageState)
        assert state.last_message_id == 'msg_12345'
        assert state.last_timestamp == 1234567890

    def test_load_message_state_returns_default_if_file_not_exists(self, temp_dir):
        """Test that load_message_state() returns default state if file doesn't exist."""
        state_dir = os.path.join(temp_dir, 'state')
        ensure_state_dir(state_dir)
        
        non_existent_file = os.path.join(state_dir, 'does_not_exist.json')
        
        # Load state from non-existent file
        state = load_message_state(non_existent_file)
        
        assert isinstance(state, MessageState)
        assert state.last_message_id is None
        assert state.last_timestamp is None

    def test_save_message_state_writes_json_file(self, temp_dir):
        """Test that save_message_state() writes JSON file."""
        state_dir = os.path.join(temp_dir, 'state')
        ensure_state_dir(state_dir)
        
        state_file = os.path.join(state_dir, 'last_message.json')
        
        # Create state
        state = MessageState(
            last_message_id='msg_99999',
            last_timestamp=9999999999
        )
        
        # Save state
        save_message_state(state, state_file)
        
        # Verify file was created
        assert os.path.exists(state_file)
        
        # Verify content
        with open(state_file, 'r') as f:
            data = json.load(f)
        
        assert data['last_message_id'] == 'msg_99999'
        assert data['last_timestamp'] == 9999999999

    def test_error_handling_for_corrupted_json(self, temp_dir):
        """Test error handling for corrupted JSON files."""
        state_dir = os.path.join(temp_dir, 'state')
        ensure_state_dir(state_dir)
        
        corrupted_file = os.path.join(state_dir, 'corrupted.json')
        
        # Write corrupted JSON
        with open(corrupted_file, 'w') as f:
            f.write('{invalid json content')
        
        # Loading should handle the error gracefully
        # Either by raising a specific exception or returning default state
        try:
            state = load_message_state(corrupted_file)
            # If no exception, should return default state
            assert isinstance(state, MessageState)
            assert state.last_message_id is None
        except (json.JSONDecodeError, ValueError) as e:
            # Or it might raise an appropriate exception
            assert isinstance(e, (json.JSONDecodeError, ValueError))

    def test_state_round_trip(self, temp_dir):
        """Test full round-trip: save and load state."""
        state_dir = os.path.join(temp_dir, 'state')
        ensure_state_dir(state_dir)
        
        state_file = os.path.join(state_dir, 'test_state.json')
        
        # Create and save state
        original_state = MessageState(
            last_message_id='msg_round_trip',
            last_timestamp=1111111111
        )
        save_message_state(original_state, state_file)
        
        # Load state back
        loaded_state = load_message_state(state_file)
        
        # Verify they match
        assert loaded_state.last_message_id == original_state.last_message_id
        assert loaded_state.last_timestamp == original_state.last_timestamp

    def test_state_file_permissions(self, temp_dir):
        """Test that state file is created with appropriate permissions."""
        state_dir = os.path.join(temp_dir, 'state')
        ensure_state_dir(state_dir)
        
        state_file = os.path.join(state_dir, 'last_message.json')
        
        state = MessageState(
            last_message_id='msg_permissions',
            last_timestamp=2222222222
        )
        save_message_state(state, state_file)
        
        # Verify file exists and is readable
        assert os.path.exists(state_file)
        assert os.access(state_file, os.R_OK)
        assert os.access(state_file, os.W_OK)
