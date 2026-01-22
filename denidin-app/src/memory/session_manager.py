"""
Session Manager for conversation history.

Manages chat sessions with role-based token limits and message persistence.
Supports UUID-based architecture with separate file storage for messages.
"""

import json
import uuid
import threading
import time
import tiktoken
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict
from src.utils.logger import get_logger
from src.models.user import Role

logger = get_logger(__name__)


@dataclass
class Message:
    """Individual message in a conversation."""
    message_id: str
    chat_id: str  # Session UUID reference
    role: str  # "user" or "assistant"
    content: str
    sender: Optional[str] = None
    recipient: Optional[str] = None
    timestamp: Optional[str] = None
    received_at: Optional[str] = None
    was_received: bool = True
    order_num: int = 0
    image_path: Optional[str] = None


@dataclass
class Session:
    """Chat session with conversation history."""
    session_id: str
    whatsapp_chat: str
    message_ids: List[str]
    message_counter: int = 0
    created_at: str = ""
    last_active: str = ""
    total_tokens: int = 0


class SessionManager:
    """
    Manages chat sessions with conversation history.
    
    Features:
    - UUID-based sessions linked to WhatsApp chat IDs
    - Messages stored as separate JSON files in session directories
    - Background cleanup thread for expired sessions
    - Date-based archival to expired/YYYY-MM-DD/ folders
    """
    
    def __init__(
        self,
        storage_dir: str = "data/sessions",
        session_timeout_hours: int = 24,
        cleanup_interval_seconds: int = 3600
    ):
        """
        Initialize SessionManager.
        
        Args:
            storage_dir: Directory for session storage
            session_timeout_hours: Hours before session expires
            cleanup_interval_seconds: Cleanup thread interval
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_timeout_hours = session_timeout_hours
        self.cleanup_interval_seconds = cleanup_interval_seconds
        
        # In-memory index: whatsapp_chat -> session_id
        self.chat_to_session: Dict[str, str] = {}
        
        # Start background cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_running = True
        self._cleanup_thread.start()
        
        # Wait for first cleanup to complete (avoid race conditions)
        time.sleep(3)
        
        # Load existing sessions from disk (after cleanup)
        self._load_sessions()
        
        logger.info(
            f"SessionManager initialized: timeout={session_timeout_hours}h, "
            f"cleanup_interval={cleanup_interval_seconds}s"
        )
    
    def get_session(self, chat_id: str) -> Session:
        """
        Get or create session for a WhatsApp chat.
        
        Args:
            chat_id: WhatsApp chat ID (e.g., "1234567890@c.us")
            
        Returns:
            Session object
        """
        # Check if session exists in index
        if chat_id in self.chat_to_session:
            session_id = self.chat_to_session[chat_id]
            session = self._load_session(session_id)
            return session
        
        # Create new session
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        session = Session(
            session_id=session_id,
            whatsapp_chat=chat_id,
            message_ids=[],
            message_counter=0,
            created_at=now,
            last_active=now,
            total_tokens=0
        )
        
        # Save to disk and index
        self._save_session(session)
        self.chat_to_session[chat_id] = session_id
        
        logger.info(f"Created new session {session_id} for chat {chat_id}")
        return session
    
    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        user_role: str,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        image_path: Optional[str] = None
    ) -> str:
        """
        Add message to session.
        
        Args:
            chat_id: WhatsApp chat ID
            role: Message role ("user" or "assistant")
            content: Message content
            user_role: User role for token limits (not used yet)
            sender: Message sender (optional)
            recipient: Message recipient (optional)
            image_path: Path to image file (optional)
            
        Returns:
            Message UUID
        """
        session = self.get_session(chat_id)
        
        # Increment message counter
        session.message_counter += 1
        
        # Create message
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        message = Message(
            message_id=message_id,
            chat_id=session.session_id,  # FK to session UUID
            role=role,
            content=content,
            sender=sender,
            recipient=recipient,
            timestamp=now,
            received_at=now,
            was_received=True,
            order_num=session.message_counter,
            image_path=image_path
        )
        
        # Save message to session directory
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"
        messages_dir.mkdir(parents=True, exist_ok=True)
        
        message_file = messages_dir / f"{message_id}.json"
        with open(message_file, 'w') as f:
            json.dump(asdict(message), f, indent=2)
        
        # Update session
        session.message_ids.append(message_id)
        session.last_active = now
        self._save_session(session)
        
        logger.debug(f"Added message {message_id} to session {session.session_id}")
        return message_id
    
    def get_conversation_history(self, whatsapp_chat: str, max_tokens: int = None) -> List[Dict]:
        """
        Get conversation history in AI format.
        
        Args:
            whatsapp_chat: WhatsApp chat ID
            max_tokens: Maximum tokens to retrieve (not implemented yet)
            
        Returns:
            List of messages in format [{"role": "user", "content": "..."}]
        """
        session = self.get_session(whatsapp_chat)
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"
        
        history = []
        for message_id in session.message_ids:
            message_file = messages_dir / f"{message_id}.json"
            
            if message_file.exists():
                with open(message_file) as f:
                    message_data = json.load(f)
                
                history.append({
                    "role": message_data["role"],
                    "content": message_data["content"]
                })
        
        return history
    
    def clear_session(self, chat_id: str):
        """
        Clear all messages from a session.
        
        Args:
            chat_id: WhatsApp chat ID
        """
        session = self.get_session(chat_id)
        
        # Delete message files
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"
        
        if messages_dir.exists():
            for message_file in messages_dir.glob("*.json"):
                message_file.unlink()
        
        # Reset session
        session.message_ids = []
        session.total_tokens = 0
        self._save_session(session)
        
        logger.info(f"Cleared session {session.session_id}")
    
    def _save_session(self, session: Session):
        """Save session metadata to disk."""
        session_dir = self.storage_dir / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        session_file = session_dir / "session.json"
        
        # Convert session to dict and ensure timestamps are strings
        session_dict = asdict(session)
        if isinstance(session_dict['last_active'], datetime):
            session_dict['last_active'] = session_dict['last_active'].isoformat()
        if isinstance(session_dict['created_at'], datetime):
            session_dict['created_at'] = session_dict['created_at'].isoformat()
        
        with open(session_file, 'w') as f:
            json.dump(session_dict, f, indent=2)
    
    def _load_session(self, session_id: str) -> Session:
        """Load session metadata from disk."""
        session_file = self.storage_dir / session_id / "session.json"
        
        with open(session_file) as f:
            data = json.load(f)
        
        return Session(**data)
    
    def _load_sessions(self):
        """Load all sessions from disk into memory index."""
        if not self.storage_dir.exists():
            return
        
        for session_dir in self.storage_dir.iterdir():
            if not session_dir.is_dir() or session_dir.name == "expired":
                continue
            
            session_file = session_dir / "session.json"
            if session_file.exists():
                try:
                    session = self._load_session(session_dir.name)
                    self.chat_to_session[session.whatsapp_chat] = session.session_id
                    logger.debug(f"Loaded session {session.session_id}")
                except Exception as e:
                    logger.error(f"Failed to load session {session_dir.name}: {e}")
    
    def _cleanup_expired_sessions(self):
        """Move expired sessions to dated archive folders."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self.session_timeout_hours)
        
        expired_base = self.storage_dir / "expired"
        
        for session_dir in self.storage_dir.iterdir():
            if not session_dir.is_dir() or session_dir.name == "expired":
                continue
            
            session_file = session_dir / "session.json"
            if not session_file.exists():
                continue
            
            try:
                session = self._load_session(session_dir.name)
                last_active = datetime.fromisoformat(session.last_active)
                
                if last_active < cutoff:
                    # Create dated subfolder based on session's last_active date
                    archive_date = last_active.strftime("%Y-%m-%d")
                    archive_dir = expired_base / archive_date
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Move entire session directory
                    dest = archive_dir / session_dir.name
                    session_dir.rename(dest)
                    
                    # Remove from index
                    if session.whatsapp_chat in self.chat_to_session:
                        del self.chat_to_session[session.whatsapp_chat]
                    
                    logger.info(
                        f"Archived expired session {session.session_id} "
                        f"to expired/{archive_date}/"
                    )
            except Exception as e:
                logger.error(f"Failed to cleanup session {session_dir.name}: {e}")
    
    def _cleanup_loop(self):
        """Background thread that periodically cleans up expired sessions."""
        while self._cleanup_running:
            if self._cleanup_running:
                logger.debug("Running scheduled session cleanup")
                self._cleanup_expired_sessions()
            time.sleep(self.cleanup_interval_seconds)
    
    def stop_cleanup_thread(self):
        """Stop the background cleanup thread."""
        self._cleanup_running = False
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        logger.info("SessionManager cleanup thread stopped")
    
    def is_session_expired(self, session: Session) -> bool:
        """
        Check if a session has expired based on last_active timestamp.
        
        Args:
            session: Session object to check
            
        Returns:
            True if session is expired, False otherwise
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self.session_timeout_hours)
        last_active = datetime.fromisoformat(session.last_active)
        
        return last_active < cutoff
    
    def find_orphaned_sessions(self) -> List[Session]:
        """
        Find all sessions that exist on disk but are not in memory index.
        Used for startup recovery.
        
        Returns:
            List of Session objects found on disk
        """
        orphaned_sessions = []
        
        for session_dir in self.storage_dir.iterdir():
            if not session_dir.is_dir() or session_dir.name == "expired":
                continue
            
            session_file = session_dir / "session.json"
            if not session_file.exists():
                continue
            
            try:
                session = self._load_session(session_dir.name)
                orphaned_sessions.append(session)
                logger.debug(f"Found orphaned session: {session.session_id}")
            except Exception as e:
                logger.error(f"Failed to load orphaned session {session_dir.name}: {e}")
        
        return orphaned_sessions
    
    def count_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        """
        Count tokens in text using tiktoken.
        
        Args:
            text: Text to count tokens for
            model: Model name for tokenizer
            
        Returns:
            Token count
        """
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    
    def add_message_with_tokens(
        self,
        chat_id: str,
        role: str,
        content: str,
        user_role: Role,
        sender: Optional[str] = None,
        recipient: Optional[str] = None
    ) -> str:
        """
        Add message and update session token count.
        
        Args:
            chat_id: WhatsApp chat ID
            role: Message role ("user" or "assistant")
            content: Message content
            user_role: User role (for tracking, not enforced here)
            sender: Message sender (optional)
            recipient: Message recipient (optional)
            
        Returns:
            Message UUID
        """
        # Add message normally
        message_id = self.add_message(chat_id, role, content, user_role, sender, recipient)
        
        # Count and add tokens
        tokens = self.count_tokens(content)
        session = self.get_session(chat_id)
        session.total_tokens += tokens
        self._save_session(session)
        
        return message_id
    
    def add_message_with_token_limit(
        self,
        chat_id: str,
        role: str,
        content: str,
        user_role: Role,
        token_limit: int,
        sender: Optional[str] = None,
        recipient: Optional[str] = None
    ) -> str:
        """
        Add message with token limit enforcement and auto-pruning.
        
        Args:
            chat_id: WhatsApp chat ID
            role: Message role ("user" or "assistant")
            content: Message content
            user_role: User role
            token_limit: Maximum tokens allowed for this role
            sender: Message sender (optional)
            recipient: Message recipient (optional)
            
        Returns:
            Message UUID
            
        Raises:
            ValueError: If token limit is exceeded and cannot prune
        """
        # Count tokens for new message
        new_tokens = self.count_tokens(content)
        
        # Check if blocked user (0 token limit)
        if token_limit == 0:
            raise ValueError("Token limit exceeded: BLOCKED users cannot add messages")
        
        # Get current session
        session = self.get_session(chat_id)
        current_tokens = session.total_tokens
        
        # Check if adding this message would exceed limit
        if current_tokens + new_tokens > token_limit:
            # Prune oldest messages until we're under limit
            self._prune_until_under_limit(chat_id, token_limit, new_tokens)
        
        # Add message with token tracking
        return self.add_message_with_tokens(chat_id, role, content, user_role, sender, recipient)
    
    def calculate_session_tokens(self, chat_id: str) -> int:
        """
        Calculate total tokens for all messages in session.
        
        Args:
            chat_id: WhatsApp chat ID
            
        Returns:
            Total token count
        """
        session = self.get_session(chat_id)
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"
        
        total = 0
        for message_id in session.message_ids:
            message_file = messages_dir / f"{message_id}.json"
            if message_file.exists():
                with open(message_file) as f:
                    message_data = json.load(f)
                total += self.count_tokens(message_data["content"])
        
        return total
    
    def get_session_token_count(self, chat_id: str) -> int:
        """
        Get current token count for session.
        
        Args:
            chat_id: WhatsApp chat ID
            
        Returns:
            Current token count
        """
        session = self.get_session(chat_id)
        return session.total_tokens
    
    def prune_to_limit(self, chat_id: str, keep_count: int):
        """
        Prune session to keep only specified number of most recent messages.
        
        Args:
            chat_id: WhatsApp chat ID
            keep_count: Number of messages to keep
        """
        session = self.get_session(chat_id)
        
        if len(session.message_ids) <= keep_count:
            return
        
        # Calculate how many to remove
        remove_count = len(session.message_ids) - keep_count
        
        # Remove oldest messages
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"
        
        for i in range(remove_count):
            message_id = session.message_ids.pop(0)
            message_file = messages_dir / f"{message_id}.json"
            if message_file.exists():
                message_file.unlink()
        
        # Recalculate tokens
        session.total_tokens = self.calculate_session_tokens(chat_id)
        self._save_session(session)
    
    def _prune_until_under_limit(self, chat_id: str, token_limit: int, new_message_tokens: int):
        """
        Remove oldest messages until session is under limit with room for new message.
        
        Args:
            chat_id: WhatsApp chat ID
            token_limit: Maximum allowed tokens
            new_message_tokens: Tokens in message to be added
        """
        session = self.get_session(chat_id)
        session_dir = self.storage_dir / session.session_id
        messages_dir = session_dir / "messages"
        
        while session.total_tokens + new_message_tokens > token_limit and session.message_ids:
            # Remove oldest message
            message_id = session.message_ids.pop(0)
            message_file = messages_dir / f"{message_id}.json"
            
            if message_file.exists():
                with open(message_file) as f:
                    message_data = json.load(f)
                # Subtract tokens from total
                session.total_tokens -= self.count_tokens(message_data["content"])
                message_file.unlink()
        
        self._save_session(session)

