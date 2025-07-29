import os
from pathlib import Path
from typing import Any

from biomni_ui.config import config


class FileValidationError(Exception):
    """Exception raised when file validation fails."""
    pass


class FileValidator:
    """Simple file validator for basic security and compatibility."""
    
    def __init__(self):
        self.max_size_bytes = config.max_file_size_mb * 1024 * 1024
        self.allowed_extensions = set(config.allowed_file_types)
    
    def validate_file(self, file_path: Path, original_filename: str) -> dict[str, Any]:
        """
        Validate an uploaded file for basic security and compatibility.
        
        Args:
            file_path: Path to the uploaded file
            original_filename: Original filename from upload
            
        Returns:
            dict: Validation results with metadata
            
        Raises:
            FileValidationError: If validation fails
        """
        if not file_path.exists():
            raise FileValidationError(f"File does not exist: {file_path}")
        
        # Extract and validate file extension
        file_extension = self._get_file_extension(original_filename)
        self._validate_extension(file_extension)
        
        # Validate file size
        file_size = self._validate_size(file_path)
        
        # Validate filename
        safe_filename = self._validate_filename(original_filename)
        
        return {
            'original_filename': original_filename,
            'safe_filename': safe_filename,
            'file_extension': file_extension,
            'file_size': file_size,
            'mime_type': 'application/octet-stream',  # Simple default
            'validation_passed': True
        }
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract and normalize file extension."""
        extension = Path(filename).suffix.lower().lstrip('.')
        if not extension:
            raise FileValidationError("File has no extension")
        return extension
    
    def _validate_extension(self, extension: str) -> None:
        """Validate file extension against allowed types."""
        if extension not in self.allowed_extensions:
            raise FileValidationError(
                f"File type '{extension}' not allowed. "
                f"Allowed types: {', '.join(sorted(self.allowed_extensions))}"
            )
    
    def _validate_size(self, file_path: Path) -> int:
        """Validate file size."""
        file_size = file_path.stat().st_size
        if file_size > self.max_size_bytes:
            max_mb = self.max_size_bytes / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            raise FileValidationError(
                f"File too large: {actual_mb:.1f}MB (max: {max_mb:.1f}MB)"
            )
        return file_size
    
    def _validate_filename(self, filename: str) -> str:
        """Validate and sanitize filename."""
        # Remove path components
        safe_name = os.path.basename(filename)
        
        # Check for basic dangerous characters
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            if char in safe_name:
                raise FileValidationError(f"Filename contains dangerous character: {char}")
        
        # Check length
        if len(safe_name) > 255:
            raise FileValidationError("Filename too long (max 255 characters)")
        
        return safe_name