## Initial prompt

```text
I want to build a minimal Chainlit UI to interface with Biomni (included as a submodule in this project), with the following constraints:

- The model should run asynchronously to avoid blocking the UI. Use built-in async capabilities, and stream outputs live from Biomni to the UI.
- Support basic session handling and logging: save conversation history and execution results in isolated directories using simple session IDs.
- Only expose the main A1 agent functionality.
- No authentication needed for now.
- Configuration (e.g. model, API key, data paths) should be handled via .env files. Do not validate variables used only by Biomni, Biomni handles its own requirements.
- Separate the Biomni data path from the directory used for logs and intermediate results. The latter should live outside the project directory.
- Avoid adding unnecessary features. Focus strictly on the core functionality for this first iteration.
- Keep the UI minimal and professional, no emojis or extra visuals.
```

### Output summary

#### Project Overview

A Chainlit-based user interface for Biomni that provides async execution and session management. The system allows users to interact with Biomni's biomedical AI capabilities through a web interface while maintaining session isolation and real-time output streaming.

#### Architecture

##### Core Components

1. **Configuration Management** (`config.py`)
   - Uses PydanticSettings for environment-based configuration
   - Validates paths and creates directories automatically
   - Supports external data directories outside the project

2. **Session Management** (`session_manager.py`)
   - Creates isolated sessions with unique UUIDs
   - Manages session directories for logs and outputs
   - Tracks conversation history in memory
   - Simple cleanup on session end

3. **Async Biomni Wrapper** (`biomni_wrapper.py`)
   - Wraps Biomni A1 agent for non-blocking execution
   - Uses shared Biomni data path to avoid re-downloading datasets
   - Changes working directory to session outputs for file isolation
   - Captures and streams output in real-time using asyncio queues

4. **Chainlit Application** (`app.py`)
   - Simple, professional UI without emojis
   - Handles session lifecycle (start, message, end, stop)
   - Streams responses in real-time
   - Tracks generated files and displays them to users

5. **Logging Utilities** (`logger.py`)
   - Session-specific logging to isolated directories
   - Configurable log levels and formats

##### Key Design Decisions

1. **External Data Storage**: All data directories are external to the project to avoid version control issues and allow for better scalability.

2. **Shared Biomni Data**: Uses a single shared Biomni data directory to avoid re-downloading the large dataset for each session.

3. **Session Isolation**: Each session gets its own directory structure for outputs and logs while sharing the Biomni data lake.

4. **In-Memory Session Management**: Simple in-memory session tracking without persistence for MVP simplicity.

5. **Async Execution**: Biomni agent runs in background threads with real-time output streaming to prevent UI blocking.

#### Directory Structure

```
biomni-ui/
├── biomni_ui/
│   ├── __init__.py
│   ├── app.py              # Main Chainlit application
│   ├── config.py           # PydanticSettings configuration
│   ├── session_manager.py  # Session isolation and management
│   ├── biomni_wrapper.py   # Async Biomni A1 wrapper
│   ├── logger.py           # Logging utilities
│   └── .env.example        # Environment configuration template
├── scripts/
│   ├── config.sh           # Common configuration for scripts
│   └── run.sh              # Application startup script
├── Biomni/                 # Biomni submodule
├── pyproject.toml          # Project configuration and dependencies
└── README.md               # Documentation

# External directories (configurable)
~/biomni-ui-data/
├── biomni_data/            # Shared Biomni data lake
└── sessions/               # Session-specific data
    └── {session_id}/
        ├── logs/           # Session logs
        └── outputs/        # Generated files
```

#### Configuration

The system uses environment variables for configuration:

- **Required**: API keys (ANTHROPIC_API_KEY or OPENAI_API_KEY)
- **Optional**: Paths, ports, logging levels, Biomni settings

All configuration is handled through PydanticSettings with sensible defaults.

#### Session Flow

1. **Session Start**: Creates unique session ID and isolated directories
2. **Message Processing**: Executes Biomni queries asynchronously with real-time streaming
3. **File Tracking**: Monitors and reports generated files
4. **Session End**: Cleans up in-memory data and closes session

#### Dependencies

- **chainlit**: Web UI framework
- **pydantic**: Configuration and data validation
- **pydantic-settings**: Environment-based configuration
- **python-dotenv**: Environment variable loading

#### Installation Requirements

1. Biomni conda environment (biomni_e1)
2. uv for dependency management
3. Proper API key configuration

#### Future Enhancements

For production use, consider:
- Session persistence to disk
- User authentication
- Session cleanup scheduling
- Enhanced error handling
- Performance monitoring
- Multi-user support with proper isolation