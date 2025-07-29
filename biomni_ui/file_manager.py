import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from biomni_ui.config import config
from biomni_ui.file_validator import FileValidator, FileValidationError


class FileManagerError(Exception):
    """Exception raised by file manager operations."""
    pass


class UploadedFile:
    """Represents an uploaded file with basic metadata."""
    
    def __init__(self, file_id: str, original_filename: str, file_extension: str, file_size: int, session_id: str):
        self.file_id = file_id
        self.original_filename = original_filename
        self.file_extension = file_extension
        self.file_size = file_size
        self.session_id = session_id
        self.upload_time = datetime.now()
    
    def get_file_path(self, session_id: str) -> Path:
        """Get the full path to the uploaded file."""
        uploads_dir = config.get_session_uploads_path(session_id)
        return uploads_dir / f"{self.file_id}.{self.file_extension}"


class FileManager:
    """Simple file manager for session uploads."""
    
    def __init__(self):
        self.validator = FileValidator()
        self._session_files: dict[str, list[UploadedFile]] = {}
    
    def save_uploaded_file(self, session_id: str, file_content: bytes, 
                          original_filename: str) -> UploadedFile:
        """
        Save an uploaded file to session storage.
        
        Args:
            session_id: Session identifier
            file_content: Raw file content
            original_filename: Original filename from upload
            
        Returns:
            UploadedFile: File metadata and access object
            
        Raises:
            FileManagerError: If file cannot be saved
            FileValidationError: If file validation fails
        """
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        
        # Create session directories
        self._ensure_session_directories(session_id)
        
        # Create temporary file for validation
        temp_path = self._create_temp_file(file_content, original_filename)
        
        try:
            # Validate the file
            validation_result = self.validator.validate_file(temp_path, original_filename)
            
            # Create final file path
            file_extension = validation_result['file_extension']
            uploads_dir = config.get_session_uploads_path(session_id)
            final_path = uploads_dir / f"{file_id}.{file_extension}"
            
            # Move file to final location
            shutil.move(str(temp_path), str(final_path))
            
            # Create uploaded file object
            uploaded_file = UploadedFile(
                file_id=file_id,
                original_filename=validation_result['original_filename'],
                file_extension=file_extension,
                file_size=validation_result['file_size'],
                session_id=session_id
            )
            
            # Store in memory
            if session_id not in self._session_files:
                self._session_files[session_id] = []
            self._session_files[session_id].append(uploaded_file)
            
            return uploaded_file
            
        except Exception as e:
            # Clean up temp file if it still exists
            if temp_path.exists():
                temp_path.unlink()
            raise FileManagerError(f"Failed to save uploaded file: {e}")
    
    def get_uploaded_file(self, session_id: str, file_id: str) -> UploadedFile | None:
        """Retrieve an uploaded file by ID."""
        session_files = self._session_files.get(session_id, [])
        for uploaded_file in session_files:
            if uploaded_file.file_id == file_id:
                return uploaded_file
        return None
    
    def list_session_files(self, session_id: str) -> list[UploadedFile]:
        """List all uploaded files for a session."""
        return self._session_files.get(session_id, [])
    
    def delete_file(self, session_id: str, file_id: str) -> bool:
        """Delete an uploaded file."""
        uploaded_file = self.get_uploaded_file(session_id, file_id)
        if not uploaded_file:
            return False
        
        try:
            # Delete the actual file
            file_path = uploaded_file.get_file_path(session_id)
            if file_path.exists():
                file_path.unlink()
            
            # Remove from memory
            if session_id in self._session_files:
                self._session_files[session_id] = [
                    f for f in self._session_files[session_id] if f.file_id != file_id
                ]
            
            return True
        except Exception:
            return False
    
    def cleanup_session_files(self, session_id: str) -> None:
        """Clean up all files for a session."""
        # Remove from memory
        if session_id in self._session_files:
            del self._session_files[session_id]
        
        # Remove from disk
        session_path = config.get_session_data_path() / session_id
        if session_path.exists():
            try:
                shutil.rmtree(session_path)
            except Exception:
                pass  # Best effort cleanup
    
    def get_file_content(self, session_id: str, file_id: str) -> bytes | None:
        """Get the raw content of an uploaded file."""
        uploaded_file = self.get_uploaded_file(session_id, file_id)
        if not uploaded_file:
            return None
        
        file_path = uploaded_file.get_file_path(session_id)
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except IOError:
            return None
    
    def get_file_context_for_query(self, session_id: str, uploaded_files: list[UploadedFile]) -> str:
        """Generate context string about uploaded files for inclusion in queries."""
        if not uploaded_files:
            return ""
        
        context_parts = ["Available uploaded files:"]
        
        for uploaded_file in uploaded_files:
            file_path = uploaded_file.get_file_path(session_id)
            if file_path.exists():
                # Use absolute path to ensure subprocess can find the file regardless of working directory
                absolute_path = file_path.resolve()
                context_parts.append(
                    f"- {uploaded_file.original_filename} "
                    f"({uploaded_file.file_extension.upper()}, {uploaded_file.file_size} bytes) "
                    f"at path: {absolute_path}"
                )
        
        return "\n".join(context_parts)
    
    def _ensure_session_directories(self, session_id: str) -> None:
        """Ensure all required directories exist for a session."""
        uploads_dir = config.get_session_uploads_path(session_id)
        uploads_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_temp_file(self, content: bytes, filename: str) -> Path:
        """Create a temporary file for validation."""
        import tempfile
        
        # Get file extension for temp file
        extension = Path(filename).suffix
        
        # Create temp file
        temp_fd, temp_path = tempfile.mkstemp(suffix=extension)
        try:
            with os.fdopen(temp_fd, 'wb') as f:
                f.write(content)
        except Exception:
            os.close(temp_fd)
            raise
        
        return Path(temp_path)