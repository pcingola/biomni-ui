# File Upload Feature

The Biomni UI supports comprehensive file upload functionality, allowing users to upload various types of files for analysis by the biomedical AI assistant.

## Overview

The file upload system provides:
- **Secure file validation** with type and size checking
- **Session-based isolation** with automatic cleanup
- **Seamless integration** with Biomni tools
- **Support for multiple file types** including documents, images, and bioinformatics data

## Supported File Types

### Documents
- **PDF** (.pdf) - Research papers, reports
- **Word Documents** (.docx) - Manuscripts, protocols
- **Text Files** (.txt, .md) - Plain text data, markdown files

### Images
- **PNG** (.png) - Microscopy images, figures
- **JPEG** (.jpg, .jpeg) - Photographs, medical images
- **TIFF** (.tiff, .tif) - High-quality scientific images
- **BMP, GIF** (.bmp, .gif) - Other image formats

### Data Files
- **CSV/TSV** (.csv, .tsv) - Experimental data, measurements
- **JSON** (.json) - Structured data, configurations
- **XML** (.xml) - Structured data, annotations
- **YAML** (.yaml, .yml) - Configuration files
- **Excel** (.xlsx, .xls, .ods) - Spreadsheet data

### Bioinformatics Files
- **FASTA** (.fasta, .fa) - Sequence data
- **FASTQ** (.fastq, .fq) - Sequencing data with quality scores
- **BED** (.bed) - Genomic coordinates
- **VCF** (.vcf) - Variant call format
- **GFF/GTF** (.gff, .gtf) - Gene annotations

## Configuration

File upload settings can be configured via environment variables:

```bash
# Enable/disable file uploads
FILE_UPLOAD_ENABLED=true

# Maximum file size in MB
MAX_FILE_SIZE_MB=100

# File retention period in hours
FILE_RETENTION_HOURS=24

# Enable virus scanning (optional)
ENABLE_FILE_SCANNING=false

# Override allowed file types (optional)
# ALLOWED_FILE_TYPES=pdf,docx,txt,png,jpg,csv,json,fasta
```

## Usage

### Uploading Files

1. **Drag and Drop**: Drag files directly into the chat interface
2. **File Picker**: Click the upload button to select files
3. **Multiple Files**: Upload multiple files simultaneously

### File Validation

The system automatically validates:
- **File Type**: Checks extension and MIME type
- **File Size**: Enforces maximum size limits
- **File Signature**: Validates file headers for security
- **Filename Safety**: Sanitizes filenames to prevent security issues

### Integration with Biomni

Once uploaded, files are automatically available to Biomni tools:

```
Available uploaded files:
- experiment_data.csv (CSV, 15,234 bytes) at path: /sessions/abc123/uploads/file123.csv
- microscopy_image.tiff (TIFF, 2,456,789 bytes) at path: /sessions/abc123/uploads/file456.tiff

User query: Analyze the experimental data and identify any patterns
```

## Architecture

### File Storage Structure

```
~/biomni-ui-data/sessions/{session_id}/
├── uploads/           # Original uploaded files
│   ├── {file_id}.{ext}
│   └── metadata.json
├── processed/         # Processed/converted files
│   └── {file_id}_processed.{ext}
└── outputs/          # Analysis outputs
    └── ...
```

### Security Features

- **File Type Validation**: Multiple layers of file type checking
- **Size Limits**: Configurable maximum file sizes
- **Path Sanitization**: Prevents directory traversal attacks
- **Session Isolation**: Files are isolated per user session
- **Automatic Cleanup**: Files are automatically deleted after retention period

### Error Handling

The system provides comprehensive error handling:
- **Validation Errors**: Clear messages for invalid files
- **Size Errors**: Specific feedback for oversized files
- **Type Errors**: Information about supported file types
- **Storage Errors**: Graceful handling of storage issues

## API Reference

### FileManager

Main class for handling file operations:

```python
from biomni_ui.file_manager import FileManager

file_manager = FileManager()

# Save uploaded file
uploaded_file = file_manager.save_uploaded_file(
    session_id="abc123",
    file_content=file_bytes,
    original_filename="data.csv"
)

# List session files
files = file_manager.list_session_files("abc123")

# Delete file
file_manager.delete_file("abc123", "file_id")
```

### FileValidator

Validates uploaded files:

```python
from biomni_ui.file_validator import FileValidator

validator = FileValidator()

# Validate file
result = validator.validate_file(file_path, "data.csv")
```

### FileProcessor

Processes files for Biomni integration:

```python
from biomni_ui.file_processor import FileProcessor

processor = FileProcessor()

# Process file
result = processor.process_file(session_id, uploaded_file)

# Get file context for queries
context = processor.get_file_context_for_query(session_id, files)
```

## Best Practices

### For Users

1. **File Naming**: Use descriptive filenames
2. **File Size**: Keep files under the size limit
3. **File Format**: Use supported formats for best results
4. **Data Quality**: Ensure data files are well-formatted

### For Developers

1. **Validation**: Always validate files before processing
2. **Error Handling**: Provide clear error messages
3. **Security**: Never trust user input
4. **Cleanup**: Implement proper file cleanup
5. **Logging**: Log file operations for debugging

## Troubleshooting

### Common Issues

**File Upload Fails**
- Check file size is under limit
- Verify file type is supported
- Ensure filename doesn't contain special characters

**File Not Found**
- Files may have been cleaned up due to retention policy
- Check session is still active
- Verify file was uploaded successfully

**Processing Errors**
- Check file format is valid
- Ensure file is not corrupted
- Verify file contains expected data

### Debug Information

Enable debug logging to see detailed file operations:

```bash
LOG_LEVEL=DEBUG
```

This will show:
- File validation steps
- Storage operations
- Processing details
- Error stack traces

## Limitations

- Maximum file size: 100MB (configurable)
- File retention: 24 hours (configurable)
- Concurrent uploads: Limited by session
- File types: Only supported formats accepted
- Processing: Some file types may have limited processing capabilities

## Future Enhancements

Planned improvements include:
- **Virus Scanning**: Optional malware detection
- **File Compression**: Automatic compression for large files
- **Batch Processing**: Process multiple files together
- **File Previews**: Show file contents in UI
- **Advanced Validation**: More sophisticated file checking