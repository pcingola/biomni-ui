import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Any

from biomni_ui.config import config


class FileValidationError(Exception):
    """Exception raised when file validation fails."""
    pass


class FileValidator:
    """Validates uploaded files for security and compatibility."""
    
    # MIME type mappings for common file types
    MIME_TYPE_MAP = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'txt': 'text/plain',
        'md': 'text/markdown',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'tiff': 'image/tiff',
        'tif': 'image/tiff',
        'bmp': 'image/bmp',
        'gif': 'image/gif',
        'csv': 'text/csv',
        'tsv': 'text/tab-separated-values',
        'json': 'application/json',
        'xml': 'application/xml',
        'yaml': 'application/x-yaml',
        'yml': 'application/x-yaml',
        'fasta': 'text/plain',
        'fa': 'text/plain',
        'fastq': 'text/plain',
        'fq': 'text/plain',
        'bed': 'text/plain',
        'vcf': 'text/plain',
        'gff': 'text/plain',
        'gtf': 'text/plain',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xls': 'application/vnd.ms-excel',
        'ods': 'application/vnd.oasis.opendocument.spreadsheet'
    }
    
    # File signatures (magic bytes) for validation
    FILE_SIGNATURES = {
        'pdf': [b'%PDF'],
        'png': [b'\x89PNG\r\n\x1a\n'],
        'jpg': [b'\xff\xd8\xff'],
        'jpeg': [b'\xff\xd8\xff'],
        'tiff': [b'II*\x00', b'MM\x00*'],
        'tif': [b'II*\x00', b'MM\x00*'],
        'bmp': [b'BM'],
        'gif': [b'GIF87a', b'GIF89a'],
        'docx': [b'PK\x03\x04'],
        'xlsx': [b'PK\x03\x04'],
        'zip': [b'PK\x03\x04']
    }
    
    def __init__(self):
        self.max_size_bytes = config.max_file_size_mb * 1024 * 1024
        self.allowed_extensions = set(config.allowed_file_types)
    
    def validate_file(self, file_path: Path, original_filename: str) -> dict[str, Any]:
        """
        Validate an uploaded file for security and compatibility.
        
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
        
        # Extract file extension
        file_extension = self._get_file_extension(original_filename)
        
        # Validate file extension
        self._validate_extension(file_extension)
        
        # Validate file size
        file_size = self._validate_size(file_path)
        
        # Validate MIME type
        mime_type = self._validate_mime_type(file_path, file_extension)
        
        # Validate file signature
        self._validate_file_signature(file_path, file_extension)
        
        # Validate filename
        safe_filename = self._validate_filename(original_filename)
        
        # Calculate file hash
        file_hash = self._calculate_file_hash(file_path)
        
        return {
            'original_filename': original_filename,
            'safe_filename': safe_filename,
            'file_extension': file_extension,
            'file_size': file_size,
            'mime_type': mime_type,
            'file_hash': file_hash,
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
    
    def _validate_mime_type(self, file_path: Path, extension: str) -> str:
        """Validate MIME type."""
        # Get MIME type from file content
        detected_mime, _ = mimetypes.guess_type(str(file_path))
        
        # Get expected MIME type for extension
        expected_mime = self.MIME_TYPE_MAP.get(extension)
        
        # For text-based bioinformatics files, be more lenient
        text_based_extensions = {'fasta', 'fa', 'fastq', 'fq', 'bed', 'vcf', 'gff', 'gtf', 'txt', 'md'}
        
        if extension in text_based_extensions:
            if detected_mime and not detected_mime.startswith('text/'):
                raise FileValidationError(
                    f"Invalid MIME type for {extension} file: {detected_mime}"
                )
            return detected_mime or 'text/plain'
        
        # For other files, check against expected MIME type
        if expected_mime and detected_mime:
            if not self._mime_types_compatible(detected_mime, expected_mime):
                raise FileValidationError(
                    f"MIME type mismatch: expected {expected_mime}, got {detected_mime}"
                )
        
        return detected_mime or expected_mime or 'application/octet-stream'
    
    def _mime_types_compatible(self, detected: str, expected: str) -> bool:
        """Check if detected MIME type is compatible with expected."""
        # Exact match
        if detected == expected:
            return True
        
        # Handle common variations
        variations = {
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': [
                'application/zip'
            ],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': [
                'application/zip'
            ]
        }
        
        return detected in variations.get(expected, [])
    
    def _validate_file_signature(self, file_path: Path, extension: str) -> None:
        """Validate file signature (magic bytes)."""
        signatures = self.FILE_SIGNATURES.get(extension)
        if not signatures:
            return  # No signature validation for this file type
        
        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)  # Read first 32 bytes
            
            for signature in signatures:
                if header.startswith(signature):
                    return  # Valid signature found
            
            raise FileValidationError(
                f"Invalid file signature for {extension} file"
            )
        except IOError as e:
            raise FileValidationError(f"Cannot read file for signature validation: {e}")
    
    def _validate_filename(self, filename: str) -> str:
        """Validate and sanitize filename."""
        # Remove path components
        safe_name = os.path.basename(filename)
        
        # Check for dangerous characters
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            if char in safe_name:
                raise FileValidationError(f"Filename contains dangerous character: {char}")
        
        # Check length
        if len(safe_name) > 255:
            raise FileValidationError("Filename too long (max 255 characters)")
        
        # Check for reserved names (Windows)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
            'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4',
            'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        name_without_ext = Path(safe_name).stem.upper()
        if name_without_ext in reserved_names:
            raise FileValidationError(f"Filename uses reserved name: {name_without_ext}")
        
        return safe_name
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file."""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except IOError as e:
            raise FileValidationError(f"Cannot calculate file hash: {e}")
    
    def is_image_file(self, extension: str) -> bool:
        """Check if file extension represents an image."""
        image_extensions = {'png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'gif'}
        return extension.lower() in image_extensions
    
    def is_document_file(self, extension: str) -> bool:
        """Check if file extension represents a document."""
        document_extensions = {'pdf', 'docx', 'txt', 'md'}
        return extension.lower() in document_extensions
    
    def is_data_file(self, extension: str) -> bool:
        """Check if file extension represents a data file."""
        data_extensions = {
            'csv', 'tsv', 'json', 'xml', 'yaml', 'yml',
            'xlsx', 'xls', 'ods'
        }
        return extension.lower() in data_extensions
    
    def is_bioinformatics_file(self, extension: str) -> bool:
        """Check if file extension represents a bioinformatics file."""
        bio_extensions = {
            'fasta', 'fa', 'fastq', 'fq', 'bed', 'vcf', 'gff', 'gtf'
        }
        return extension.lower() in bio_extensions