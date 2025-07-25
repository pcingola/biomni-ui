# Biomni UI

A Chainlit-based user interface for Biomni with async execution and session management.

## Features

- **Async Execution**: Non-blocking execution of Biomni queries to prevent UI freezing
- **Session Management**: Isolated sessions with dedicated directories for logs and outputs
- **Real-time Streaming**: Live output streaming from Biomni to the UI
- **File Management**: Automatic tracking of files generated during sessions
- **Configuration**: Environment-based configuration using `.env` files

## Requirements

- Python 3.12+
- Conda (for Biomni environment)
- uv (for dependency management)
- Valid API keys (Anthropic or OpenAI)

## Installation

1. Clone the repository with submodules:
```bash
git clone --recurse-submodules <repository-url>
cd biomni-ui
```

2. Set up Biomni environment first:
```bash
cd Biomni
# Follow the setup instructions in Biomni/biomni_env/README.md
./biomni_env/setup.sh
conda activate biomni_e1
```

3. Install Biomni UI dependencies using uv:
```bash
cd ..
uv sync
```

4. Configure environment variables:
```bash
cp biomni_ui/.env.example .env
# Edit .env with your configuration
```

## Configuration

Copy `biomni_ui/.env.example` to `.env` and configure the following variables:

### Required
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `CUSTOM`: API keys for LLM access

### Optional
- `BIOMNI_LLM_MODEL`: LLM model to use (default: claude-sonnet-4-20250514)
- `BIOMNI_DATA_PATH`: Path to Biomni data directory (default: ~/biomni-ui-data/biomni_data)
- `SESSION_DATA_PATH`: Path to session data directory (default: ~/biomni-ui-data/sessions)
- `CHAINLIT_PORT`: Port for the web interface (default: 8000)
- `LOG_LEVEL`: Logging level (default: INFO)

## Usage

### With Full Biomni Setup

1. Activate the Biomni conda environment:
```bash
conda activate biomni_e1
```

2. Start the application:
```bash
./scripts/run.sh
```

3. Open your browser and navigate to `http://localhost:8000`

4. Start asking biomedical questions and get responses from Biomni

### Testing with Mock (No Biomni Required)

For local testing without the full Biomni setup:

1. Install dependencies:
```bash
uv sync
```

2. Create a minimal `.env` file:
```bash
echo "BIOMNI_DATA_PATH=/tmp/mock-biomni-data" > .env
```

3. Run the full UI with mock:
```bash
./scripts/run.sh
```

The system will automatically detect that Biomni is not available and use the mock implementation instead.

## Architecture

### Components

- **`config.py`**: Environment-based configuration using PydanticSettings
- **`session_manager.py`**: Session isolation and management
- **`biomni_wrapper.py`**: Async wrapper for Biomni A1 agent
- **`app.py`**: Main Chainlit application
- **`logger.py`**: Session-specific logging utilities

### Directory Structure

```
biomni-ui/
├── biomni_ui/           # Main application code
├── scripts/             # Utility scripts
├── Biomni/              # Biomni submodule
├── pyproject.toml       # Project configuration and dependencies
└── .env                 # Configuration file

# External data directories (configurable)
~/biomni-ui-data/
├── biomni_data/         # Shared Biomni data lake
└── sessions/            # Session-specific data
    └── {session_id}/
        ├── logs/        # Session logs
        └── outputs/     # Generated files
```

### Session Management

Each user session gets:
- Unique session ID
- Isolated directory for outputs and logs
- In-memory conversation history
- Automatic cleanup on session end

### Async Execution

- Biomni agent runs in background thread
- Real-time output streaming to UI
- Non-blocking user interface
- Proper error handling and timeouts

## Development

The application follows these principles:
- Simple and direct implementation
- Environment-based configuration
- Proper type hints and error handling
- Session isolation for security and organization

## Troubleshooting

### Common Issues

1. **Conda Environment**: Ensure you're in the biomni_e1 environment:
   ```bash
   conda activate biomni_e1
   ```

2. **Biomni Setup**: Follow Biomni setup instructions:
   ```bash
   cd Biomni
   ./biomni_env/setup.sh
   ```

3. **Dependencies**: Install dependencies with uv:
   ```bash
   uv sync
   ```

4. **Import Error**: Ensure Biomni submodule is initialized:
   ```bash
   git submodule update --init --recursive
   ```

5. **API Key Error**: Verify your API keys are set in `.env`

6. **Permission Error**: Check that data directories are writable

7. **Port Already in Use**: Change `CHAINLIT_PORT` in `.env`

### Logs

- Application logs: Console output
- Session logs: `{SESSION_DATA_PATH}/{session_id}/logs/session.log`
- Generated files: `{SESSION_DATA_PATH}/{session_id}/outputs/`
