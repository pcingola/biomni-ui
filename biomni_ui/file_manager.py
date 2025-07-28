import json
import os
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from biomni_ui.config import config
from biomni_ui.file_validator import FileValidator, FileValidationError


class FileManagerError(Exception):
    """Exception raised by file manager operations."""
    pass


class UploadedFile:
    """Represents an uploaded file with metadata."""
    
    def __init__(self, file_id: str, metadata: dict[str, Any]):
        self.file_id = file_id
        self.metadata = metadata
    
    @property
    def original_filename(self) -> str:
        return self.metadata['original_filename']
    
    @property
    def safe_filename(self) -> str:
        return self.metadata['safe_filename']
    
    @property
    def file_extension(self) -> str:
        return self.metadata['file_extension']
    
    @property
    def file_size(self) -> int:
        return self.metadata['file_size']
    
    @property
    def mime_type(self) -> str:
        return self.metadata['mime_type']
    
    @property
    def upload_time(self) -> datetime:
        return datetime.fromisoformat(self.metadata['upload_time'])
    
    @property
    def file_hash(self) -> str:
        return self.metadata['file_hash']
    
    def get_file_path(self, session_id: str) -> Path:
        """Get the full path to the uploaded file."""
        uploads_dir = config.get_session_uploads_path(session_id)
        return uploads_dir / f"{self.file_id}.{self.file_extension}"
    
    def get_processed_path(self, session_id: str, suffix: str = "") -> Path:
        """Get the path for processed version of the file."""
        processed_dir = config.get_session_processed_path(session_id)
        if suffix:
            return processed_dir / f"{self.file_id}_{suffix}.{self.file_extension}"
        return processed_dir / f"{self.file_id}_processed.{self.file_extension}"


class FileManager:
    """Manages file uploads, storage, and lifecycle for sessions."""
    
    def __init__(self):
        self.validator = FileValidator()
    
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
            
            # Create metadata
            metadata = {
                **validation_result,
                'file_id': file_id,
                'session_id': session_id,
                'upload_time': datetime.now().isoformat(),
                'file_path': str(final_path)
            }
            
            # Save metadata
            self._save_file_metadata(session_id, file_id, metadata)
            
            return UploadedFile(file_id, metadata)
            
        except Exception as e:
            # Clean up temp file if it still exists
            if temp_path.exists():
                temp_path.unlink()
            raise FileManagerError(f"Failed to save uploaded file: {e}")
    
    def get_uploaded_file(self, session_id: str, file_id: str) -> UploadedFile | None:
        """
        Retrieve an uploaded file by ID.
        
        Args:
            session_id: Session identifier
            file_id: File identifier
            
        Returns:
            UploadedFile or None if not found
        """
        metadata = self._load_file_metadata(session_id, file_id)
        if metadata:
            return UploadedFile(file_id, metadata)
        return None
    
    def list_session_files(self, session_id: str) -> list[UploadedFile]:
        """
        List all uploaded files for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of UploadedFile objects
        """
        uploads_dir = config.get_session_uploads_path(session_id)
        metadata_file = uploads_dir / "metadata.json"
        
        if not metadata_file.exists():
            return []
        
        try:
            with open(metadata_file, 'r') as f:
                all_metadata = json.load(f)
            
            files = []
            for file_id, metadata in all_metadata.items():
                files.append(UploadedFile(file_id, metadata))
            
            return files
        except (json.JSONDecodeError, IOError):
            return []
    
    def delete_file(self, session_id: str, file_id: str) -> bool:
        """
        Delete an uploaded file and its metadata.
        
        Args:
            session_id: Session identifier
            file_id: File identifier
            
        Returns:
            bool: True if file was deleted, False if not found
        """
        uploaded_file = self.get_uploaded_file(session_id, file_id)
        if not uploaded_file:
            return False
        
        try:
            # Delete the actual file
            file_path = uploaded_file.get_file_path(session_id)
            if file_path.exists():
                file_path.unlink()
            
            # Delete processed files
            processed_dir = config.get_session_processed_path(session_id)
            if processed_dir.exists():
                for processed_file in processed_dir.glob(f"{file_id}_*"):
                    processed_file.unlink()
            
            # Remove from metadata
            self._remove_file_metadata(session_id, file_id)
            
            return True
        except Exception:
            return False
    
    def cleanup_session_files(self, session_id: str) -> None:
        """
        Clean up all files for a session.
        
        Args:
            session_id: Session identifier
        """
        session_path = config.get_session_data_path() / session_id
        if session_path.exists():
            try:
                shutil.rmtree(session_path)
            except Exception:
                pass  # Best effort cleanup
    
    def cleanup_expired_files(self) -> int:
        """
        Clean up files that have exceeded retention period.
        
        Returns:
            int: Number of files cleaned up
        """
        if config.file_retention_hours <= 0:
            return 0
        
        cutoff_time = datetime.now() - timedelta(hours=config.file_retention_hours)
        cleaned_count = 0
        
        sessions_dir = config.get_session_data_path()
        if not sessions_dir.exists():
            return 0
        
        for session_dir in sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            session_id = session_dir.name
            files = self.list_session_files(session_id)
            
            for uploaded_file in files:
                if uploaded_file.upload_time < cutoff_time:
                    if self.delete_file(session_id, uploaded_file.file_id):
                        cleaned_count += 1
        
        return cleaned_count
    
    def get_file_content(self, session_id: str, file_id: str) -> bytes | None:
        """
        Get the raw content of an uploaded file.
        
        Args:
            session_id: Session identifier
            file_id: File identifier
            
        Returns:
            bytes: File content or None if not found
        """
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
    
    def _ensure_session_directories(self, session_id: str) -> None:
        """Ensure all required directories exist for a session."""
        uploads_dir = config.get_session_uploads_path(session_id)
        processed_dir = config.get_session_processed_path(session_id)
        
        uploads_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)
    
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
    
    def _save_file_metadata(self, session_id: str, file_id: str, metadata: dict[str, Any]) -> None:
        """Save file metadata to session metadata file."""
        uploads_dir = config.get_session_uploads_path(session_id)
        metadata_file = uploads_dir / "metadata.json"
        
        # Load existing metadata
        all_metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    all_metadata = json.load(f)
            except (json.JSONDecodeError, IOError):
                all_metadata = {}
        
        # Add new metadata
        all_metadata[file_id] = metadata
        
        # Save updated metadata
        try:
            with open(metadata_file, 'w') as f:
                json.dump(all_metadata, f, indent=2)
        except IOError as e:
            raise FileManagerError(f"Cannot save file metadata: {e}")
    
    def _load_file_metadata(self, session_id: str, file_id: str) -> dict[str, Any] | None:
        """Load metadata for a specific file."""
        uploads_dir = config.get_session_uploads_path(session_id)
        metadata_file = uploads_dir / "metadata.json"
        
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                all_metadata = json.load(f)
            return all_metadata.get(file_id)
        except (json.JSONDecodeError, IOError):
            return None
    
    def _remove_file_metadata(self, session_id: str, file_id: str) -> None:
        """Remove metadata for a specific file."""
        uploads_dir = config.get_session_uploads_path(session_id)
        metadata_file = uploads_dir / "metadata.json"
        
        if not metadata_file.exists():
            return
        
        try:
            with open(metadata_file, 'r') as f:
                all_metadata = json.load(f)
            
            if file_id in all_metadata:
                del all_metadata[file_id]
                
                with open(metadata_file, 'w') as f:
                    json.dump(all_metadata, f, indent=2)
        except (json.JSONDecodeError, IOError):
            pass  # Best effort removal