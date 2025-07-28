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
    uploaded_files: list[str] = field(default_factory=list)  # List of file IDs


class SessionManager:
    """Manages user sessions with isolated directories and file uploads."""
    
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
        uploads_path = config.get_session_uploads_path(session_id)
        processed_path = config.get_session_processed_path(session_id)
        
        outputs_path.mkdir(parents=True, exist_ok=True)
        uploads_path.mkdir(parents=True, exist_ok=True)
        processed_path.mkdir(parents=True, exist_ok=True)
        
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
    
    def add_uploaded_file(self, session_id: str, file_id: str) -> None:
        """Add an uploaded file ID to the session."""
        session_data = self.get_session(session_id)
        if session_data and file_id not in session_data.uploaded_files:
            session_data.uploaded_files.append(file_id)
    
    def remove_uploaded_file(self, session_id: str, file_id: str) -> None:
        """Remove an uploaded file ID from the session."""
        session_data = self.get_session(session_id)
        if session_data and file_id in session_data.uploaded_files:
            session_data.uploaded_files.remove(file_id)
    
    def get_uploaded_files(self, session_id: str) -> list[str]:
        """Get list of uploaded file IDs for a session."""
        session_data = self.get_session(session_id)
        return session_data.uploaded_files if session_data else []
    
    def close_session(self, session_id: str) -> None:
        """Close a session and clean up files if configured."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = SessionStatus.CLOSED
            
            # Clean up files if file upload is enabled
            if config.file_upload_enabled:
                self._cleanup_session_files(session_id)
            
            del self.active_sessions[session_id]
    
    def _cleanup_session_files(self, session_id: str) -> None:
        """Clean up session files (called during session close)."""
        try:
            # Import here to avoid circular imports
            from biomni_ui.file_manager import FileManager
            file_manager = FileManager()
            file_manager.cleanup_session_files(session_id)
        except Exception:
            pass  # Best effort cleanup
    
    def get_session_outputs_path(self, session_id: str) -> Path:
        """Get the outputs path for a session."""
        return config.get_session_outputs_path(session_id)
    
    def get_session_uploads_path(self, session_id: str) -> Path:
        """Get the uploads path for a session."""
        return config.get_session_uploads_path(session_id)
    
    def get_session_processed_path(self, session_id: str) -> Path:
        """Get the processed files path for a session."""
        return config.get_session_processed_path(session_id)


# Global session manager instance
session_manager = SessionManager()