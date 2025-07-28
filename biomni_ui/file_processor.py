import logging
from pathlib import Path
from typing import Any

from biomni_ui.file_manager import UploadedFile

logger = logging.getLogger(__name__)


class FileProcessorError(Exception):
    """Exception raised during file processing."""
    pass


class FileProcessor:
    """Simple file processor that prepares files for Biomni by providing file paths."""
    
    def process_file(self, session_id: str, uploaded_file: UploadedFile) -> dict[str, Any]:
        """
        Process an uploaded file to prepare it for Biomni.
        
        Args:
            session_id: Session identifier
            uploaded_file: UploadedFile object
            
        Returns:
            dict: Processing results with file path and basic metadata
        """
        file_path = uploaded_file.get_file_path(session_id)
        
        if not file_path.exists():
            raise FileProcessorError(f"File not found: {file_path}")
        
        return {
            'file_id': uploaded_file.file_id,
            'original_filename': uploaded_file.original_filename,
            'file_path': str(file_path),
            'file_extension': uploaded_file.file_extension,
            'file_size': uploaded_file.file_size,
            'mime_type': uploaded_file.mime_type,
            'processing_status': 'ready',
            'biomni_ready': True
        }
    
    def get_file_context_for_query(self, session_id: str, uploaded_files: list[UploadedFile]) -> str:
        """
        Generate context string about uploaded files for inclusion in queries.
        
        Args:
            session_id: Session identifier
            uploaded_files: List of uploaded files
            
        Returns:
            str: Context string describing available files
        """
        if not uploaded_files:
            return ""
        
        context_parts = ["Available uploaded files:"]
        
        for uploaded_file in uploaded_files:
            file_path = uploaded_file.get_file_path(session_id)
            if file_path.exists():
                context_parts.append(
                    f"- {uploaded_file.original_filename} "
                    f"({uploaded_file.file_extension.upper()}, {uploaded_file.file_size} bytes) "
                    f"at path: {file_path}"
                )
        
        return "\n".join(context_parts)