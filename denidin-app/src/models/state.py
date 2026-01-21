"""
MessageState model for tracking bot state.
Handles persistence of the last processed message.
"""
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class MessageState:
    """Model for tracking the last processed message state."""
    
    last_message_id: Optional[str] = None
    last_timestamp: Optional[int] = None

    @classmethod
    def load(cls, file_path: str) -> 'MessageState':
        """
        Load state from a JSON file.
        
        Args:
            file_path: Path to the state file
            
        Returns:
            MessageState instance (default if file doesn't exist)
        """
        if not os.path.exists(file_path):
            return cls()
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return cls(**data)
        except (json.JSONDecodeError, IOError):
            # Return default state if file is corrupted or unreadable
            return cls()

    def save(self, file_path: str) -> None:
        """
        Save state to a JSON file.
        
        Args:
            file_path: Path to save the state file
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    def update(self, message_id: str, timestamp: int) -> None:
        """
        Update the state with new message information.
        
        Args:
            message_id: ID of the message
            timestamp: Timestamp of the message
        """
        self.last_message_id = message_id
        self.last_timestamp = timestamp
