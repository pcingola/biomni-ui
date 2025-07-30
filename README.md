# Biomni UI

A web-based interface for the Biomni biomedical AI agent that provides an intuitive chat interface for biomedical research tasks, data analysis, and file processing.

> **⚠️ MVP Status**: This project is currently in MVP (Minimum Viable Product) status. Features and APIs may change as development continues.

## Description

Biomni UI transforms the powerful Biomni command-line tool into an accessible web application. It enables researchers to interact with biomedical AI through a simple chat interface, upload various file types for analysis, and manage research sessions with automatic file tracking and output generation.

## Features

- **Async Execution**: Non-blocking execution of Biomni queries to prevent UI freezing
- **Session Management**: Isolated sessions with dedicated directories for logs and outputs
- **Real-time Streaming**: Live output streaming from Biomni to the UI
- **File Upload Support**: Upload and analyze documents, images, and bioinformatics data
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

Copy `.env.example` to `.env` and configure the following variables:

### Required
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`: API keys for LLM access

### Optional
- `BIOMNI_LLM_MODEL`: LLM model to use (default: anthropic/claude-sonnet-4)
- `BIOMNI_DATA_PATH`: Path to Biomni data directory (default: ./data)
- `SESSION_DATA_PATH`: Path to session data directory (default: ~/biomni-ui-data/sessions)
- `CHAINLIT_PORT`: Port for the web interface (default: 8000)
- `CHAINLIT_HOST`: Host for the web interface (default: 0.0.0.0)
- `LOG_LEVEL`: Logging level (default: INFO)
- `BIOMNI_TIMEOUT_SECONDS`: Timeout for Biomni operations (default: 600)
- `BIOMNI_MOCK_MODE`: Use mock mode for testing (default: false)

### File Upload
- `FILE_UPLOAD_ENABLED`: Enable file upload functionality (default: true)
- `MAX_FILE_SIZE_MB`: Maximum file size in MB (default: 100)

## Usage

### Quick Start

1. Configure your environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

2. Start the application:
```bash
./scripts/run.sh
```

3. Open your browser and navigate to `http://localhost:8000`

4. Start asking biomedical questions and upload files for analysis

### File Upload

Upload files by dragging and dropping into the chat interface or using the upload button.

**Supported formats**: PDF, DOCX, TXT, MD, PNG, JPG, TIFF, CSV, TSV, JSON, XML, YAML, Excel, FASTA, FASTQ, BED, VCF, GFF, GTF

**Example workflow**:
1. Upload `experiment_data.csv`
2. Ask: "Analyze this experimental data and identify significant patterns"
3. View generated plots and analysis files

### Development Mode

For testing without full Biomni setup, set `BIOMNI_MOCK_MODE=true` in your `.env` file.

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
