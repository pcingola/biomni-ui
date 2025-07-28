from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configuration class for Biomni UI application using PydanticSettings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Biomni Configuration (passed through to Biomni)
    biomni_llm_model: str = Field(default="anthropic/claude-sonnet-4", description="LLM model to use for Biomni")
    biomni_data_path: str = Field(default="./data", description="Path to Biomni data directory")
    biomni_timeout_seconds: int = Field(default=600, gt=0, description="Timeout for Biomni operations in seconds")
    biomni_base_url: str | None = Field(default=None, description="Custom base URL for Biomni LLM")
    biomni_api_key: str = Field(default="EMPTY", description="API key for custom Biomni LLM")
    
    # UI Configuration
    session_data_path: str = Field(default_factory=lambda: str(Path.home() / "biomni-ui-data" / "sessions"), description="Path to session data directory")
    log_level: str = Field(default="INFO", description="Logging level")
    chainlit_port: int = Field(default=8000, gt=0, le=65535, description="Port for Chainlit server")
    chainlit_host: str = Field(default="0.0.0.0", description="Host for Chainlit server")
    
    # File Upload Configuration
    file_upload_enabled: bool = Field(default=True, description="Enable file upload functionality")
    max_file_size_mb: int = Field(default=100, gt=0, le=1000, description="Maximum file size in MB")
    allowed_file_types: list[str] = Field(
        default=[
            "pdf", "docx", "txt", "md",  # Documents
            "png", "jpg", "jpeg", "tiff", "tif", "bmp", "gif",  # Images
            "csv", "tsv", "json", "xml", "yaml", "yml",  # Data files
            "fasta", "fa", "fastq", "fq", "bed", "vcf", "gff", "gtf",  # Bioinformatics
            "xlsx", "xls", "ods"  # Spreadsheets
        ],
        description="List of allowed file extensions"
    )
    file_retention_hours: int = Field(default=24, gt=0, le=168, description="Hours to retain uploaded files")
    enable_file_scanning: bool = Field(default=False, description="Enable virus/malware scanning of uploaded files")
    
    # Logging Configuration
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format string")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("session_data_path")
    @classmethod
    def validate_session_path(cls, v):
        """Validate and create session data path if it doesn't exist."""
        path = Path(v)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValueError(f"Cannot create session directory {v}: {e}")
        return str(path.resolve())
    
    def get_biomni_data_path(self) -> Path:
        """Get Biomni data path as Path object."""
        return Path(self.biomni_data_path)
    
    def get_session_data_path(self) -> Path:
        """Get session data path as Path object."""
        return Path(self.session_data_path)
    
    def get_session_outputs_path(self, session_id: str) -> Path:
        """Get outputs path for a specific session."""
        return self.get_session_data_path() / session_id / "outputs"
    
    def get_session_uploads_path(self, session_id: str) -> Path:
        """Get uploads path for a specific session."""
        return self.get_session_data_path() / session_id / "uploads"
    
    def get_session_processed_path(self, session_id: str) -> Path:
        """Get processed files path for a specific session."""
        return self.get_session_data_path() / session_id / "processed"
    
    @field_validator("allowed_file_types")
    @classmethod
    def validate_file_types(cls, v):
        """Validate and normalize file types."""
        if not v:
            raise ValueError("At least one file type must be allowed")
        # Normalize to lowercase and remove dots
        normalized = [ext.lower().lstrip('.') for ext in v]
        return normalized


# Global config instance
config = Config()