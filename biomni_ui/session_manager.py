import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from biomni_ui.config import config


class SessionStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


@dataclass
class ConversationEntry:
    """Represents a single conversation entry."""
    timestamp: datetime
    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionData:
    """Represents session data and metadata."""
    session_id: str
    created_at: datetime
    status: SessionStatus
    conversation_history: list[ConversationEntry] = field(default_factory=list)
    
    def add_conversation_entry(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add an entry to the conversation history."""
        entry = ConversationEntry(
            timestamp=datetime.now(),
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.conversation_history.append(entry)


class SessionManager:
    """Manages user sessions with isolated directories."""
    
    def __init__(self):
        self.active_sessions: dict[str, SessionData] = {}
        self._ensure_base_directories()
    
    def _ensure_base_directories(self) -> None:
        """Ensure base session directories exist."""
        config.get_session_data_path().mkdir(parents=True, exist_ok=True)
    
    def create_session(self) -> str:
        """Create a new session and return session ID."""
        session_id = str(uuid.uuid4())
        
        # Create session directories
        session_path = config.get_session_path(session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        
        logs_path = config.get_session_logs_path(session_id)
        logs_path.mkdir(parents=True, exist_ok=True)
        
        outputs_path = config.get_session_outputs_path(session_id)
        outputs_path.mkdir(parents=True, exist_ok=True)
        
        # Create session data
        session_data = SessionData(
            session_id=session_id,
            created_at=datetime.now(),
            status=SessionStatus.ACTIVE
        )
        
        # Add to active sessions
        self.active_sessions[session_id] = session_data
        
        return session_id
    
    def get_session(self, session_id: str) -> SessionData | None:
        """Get session data by ID."""
        return self.active_sessions.get(session_id)
    
    def add_conversation_entry(self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add an entry to the conversation history."""
        session_data = self.get_session(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")
        
        session_data.add_conversation_entry(role, content, metadata)
    
    def get_conversation_history(self, session_id: str) -> list[ConversationEntry]:
        """Get conversation history for a session."""
        session_data = self.get_session(session_id)
        if not session_data:
            return []
        return session_data.conversation_history
    
    def close_session(self, session_id: str) -> None:
        """Close a session."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = SessionStatus.CLOSED
            del self.active_sessions[session_id]
    
    def get_session_path(self, session_id: str) -> Path:
        """Get the base path for a session."""
        return config.get_session_path(session_id)
    
    def get_session_logs_path(self, session_id: str) -> Path:
        """Get the logs path for a session."""
        return config.get_session_logs_path(session_id)
    
    def get_session_outputs_path(self, session_id: str) -> Path:
        """Get the outputs path for a session."""
        return config.get_session_outputs_path(session_id)


# Global session manager instance
session_manager = SessionManager()