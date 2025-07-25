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
class SessionData:
    """Represents session data and metadata."""
    session_id: str
    created_at: datetime
    status: SessionStatus


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
    
    def close_session(self, session_id: str) -> None:
        """Close a session."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = SessionStatus.CLOSED
            del self.active_sessions[session_id]
    
    def get_session_outputs_path(self, session_id: str) -> Path:
        """Get the outputs path for a session."""
        return config.get_session_outputs_path(session_id)


# Global session manager instance
session_manager = SessionManager()