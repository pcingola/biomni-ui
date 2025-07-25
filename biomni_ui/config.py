from pathlib import Path
from pydantic import Field, validator
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
    biomni_use_tool_retriever: bool = Field(default=True, description="Whether to use tool retriever in Biomni")
    biomni_base_url: str | None = Field(default=None, description="Custom base URL for Biomni LLM")
    biomni_api_key: str = Field(default="EMPTY", description="API key for custom Biomni LLM")
    
    # UI Configuration
    session_data_path: str = Field(default_factory=lambda: str(Path.home() / "biomni-ui-data" / "sessions"), description="Path to session data directory")
    log_level: str = Field(default="INFO", description="Logging level")
    chainlit_port: int = Field(default=8000, gt=0, le=65535, description="Port for Chainlit server")
    chainlit_host: str = Field(default="0.0.0.0", description="Host for Chainlit server")
    
    # Session Management
    session_cleanup_hours: int = Field(default=24, gt=0, description="Hours after which to cleanup old sessions")
    max_session_duration_hours: int = Field(default=12, gt=0, description="Maximum duration for a session in hours")
    max_concurrent_sessions: int = Field(default=10, gt=0, description="Maximum number of concurrent sessions")
    
    # Logging Configuration
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format string")
    log_file_max_bytes: int = Field(default=10485760, gt=0, description="Maximum log file size in bytes")
    log_file_backup_count: int = Field(default=5, gt=0, description="Number of log file backups to keep")
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()
    
    @validator("session_data_path")
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
    
    def get_session_path(self, session_id: str) -> Path:
        """Get path for a specific session."""
        return self.get_session_data_path() / session_id
    
    def get_session_logs_path(self, session_id: str) -> Path:
        """Get logs path for a specific session."""
        return self.get_session_path(session_id) / "logs"
    
    def get_session_outputs_path(self, session_id: str) -> Path:
        """Get outputs path for a specific session."""
        return self.get_session_path(session_id) / "outputs"


# Global config instance
config = Config()