import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncGenerator
from pydantic import BaseModel

from biomni_ui.config import config
from biomni_ui.session_manager import session_manager


class BiomniSubprocessConfig(BaseModel):
    """Configuration data for Biomni subprocess execution."""
    
    session_outputs_path: str
    biomni_data_path: str
    biomni_llm_model: str
    biomni_timeout_seconds: int
    biomni_base_url: str | None
    biomni_api_key: str
    
    def to_json(self) -> str:
        """Convert config to JSON string for subprocess communication."""
        return self.model_dump_json()


class AsyncBiomniWrapper:
    """Async wrapper for Biomni A1 agent to prevent UI blocking."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._is_running = False
        self.session_outputs_path = session_manager.get_session_outputs_path(session_id)
    
    def _prepare_subprocess_config(self) -> str:
        """Prepare configuration for subprocess execution."""
        subprocess_config = BiomniSubprocessConfig(
            session_outputs_path=str(self.session_outputs_path),
            biomni_data_path=str(config.get_biomni_data_path()),
            biomni_llm_model=config.biomni_llm_model,
            biomni_timeout_seconds=config.biomni_timeout_seconds,
            biomni_base_url=config.biomni_base_url,
            biomni_api_key=config.biomni_api_key
        )
        return subprocess_config.to_json()
    
    async def _create_subprocess(self, query: str, config_json: str) -> asyncio.subprocess.Process:
        """Create and return the async subprocess."""
        wrapper_script = Path(__file__).parent / "biomni_subprocess_wrapper.py"
        
        # Create a shell command that activates conda environment first
        shell_cmd = f"""
        eval "$(conda shell.bash hook)" && \
        conda activate biomni_e1 && \
        python {wrapper_script} {self.session_id} '{query}' '{config_json}'
        """
        
        return await asyncio.create_subprocess_shell(
            shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.session_outputs_path),
            executable="/bin/bash"
        )
    
    def _clean_output_text(self, text: str) -> str:
        """Clean and format output text."""
        # Remove common prefixes for cleaner output
        if text.startswith('[BIOMNI]'):
            return text[8:].strip()
        elif text.startswith('[LOG]'):
            return text[5:].strip()
        elif text.startswith('[RESULT]'):
            return text[8:].strip()
        elif text.startswith('[ERROR]'):
            return f"ERROR: {text[7:].strip()}"
        return text.strip()
    
    async def execute_query(self, query: str) -> AsyncGenerator[str, None]:
        """Execute a query asynchronously using subprocess and yield output in real-time."""
        self._is_running = True
        
        try:
            # Prepare subprocess configuration
            config_json = self._prepare_subprocess_config()
            
            # Create and start subprocess
            process = await self._create_subprocess(query, config_json)
            
            # Read stdout line by line
            if process.stdout:
                while self._is_running:
                    line = await process.stdout.readline()
                    if not line:  # EOF
                        break
                    
                    text = line.decode('utf-8').rstrip('\r\n')
                    if text:
                        cleaned_text = self._clean_output_text(text)
                        if cleaned_text:
                            yield cleaned_text + "\n"
            
            # Wait for process to complete
            await process.wait()
            
            # Check for errors
            if process.returncode != 0:
                if process.stderr:
                    stderr_output = await process.stderr.read()
                    error_text = stderr_output.decode('utf-8').strip()
                    if error_text:
                        yield f"ERROR: {error_text}\n"
                yield f"ERROR: Process failed with exit code {process.returncode}\n"
                
        except Exception as e:
            yield f"ERROR: {str(e)}\n"
        finally:
            self._is_running = False
    
    def stop_execution(self) -> None:
        """Stop the current execution."""
        self._is_running = False
    
    def is_running(self) -> bool:
        """Check if the agent is currently running."""
        return self._is_running