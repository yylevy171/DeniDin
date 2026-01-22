"""
State persistence utility functions.
Handles state directory creation and message state operations.
"""
import os

from src.models.state import MessageState


def ensure_state_dir(state_dir: str) -> None:
    """
    Ensure the state directory exists.

    Args:
        state_dir: Path to the state directory
    """
    os.makedirs(state_dir, exist_ok=True)


def load_message_state(state_file: str) -> MessageState:
    """
    Load message state from a file.

    Args:
        state_file: Path to the state file

    Returns:
        MessageState instance
    """
    return MessageState.load(state_file)


def save_message_state(state: MessageState, state_file: str) -> None:
    """
    Save message state to a file.

    Args:
        state: MessageState instance to save
        state_file: Path to save the state file
    """
    state.save(state_file)
