import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import AsyncGenerator
from pydantic import BaseModel

from biomni_ui.config import config
from biomni_ui.session_manager import session_manager
from biomni_ui.output_parser import StreamingBiomniParser, clean_legacy_prefixes

# Configure logger for this module
logger = logging.getLogger(__name__)


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
        self.output_parser = StreamingBiomniParser()
    
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
        """Clean and format output text using legacy prefix cleaning."""
        return clean_legacy_prefixes(text)
    
    async def _execute_mock_query(self, query: str) -> AsyncGenerator[str, None]:
        """Execute a mock query by reading from biomni_output.txt file."""
        self._is_running = True
        
        try:
            # Path to the mock output file
            mock_file_path = Path("biomni_output.txt")
            
            if not mock_file_path.exists():
                logger.error(f"[{self.session_id}][MOCK] Mock file not found: {mock_file_path}")
                yield f"ERROR: Mock file not found: {mock_file_path}\n"
                return
            
            logger.info(f"[{self.session_id}][MOCK] Reading from mock file: {mock_file_path}")
            yield f"[MOCK MODE] Reading from {mock_file_path}\n"
            yield f"[MOCK MODE] Query: {query}\n"
            
            # Read the file content
            with open(mock_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split content into lines and simulate streaming
            lines = content.split('\n')
            
            for line in lines:
                if not self._is_running:
                    break
                
                if line.strip():  # Skip empty lines
                    # Log the mock output
                    logger.info(f"[{self.session_id}][MOCK]: {line}")
                    
                    cleaned_text = self._clean_output_text(line)
                    if cleaned_text:
                        # Process through the parser
                        for parsed_message in self.output_parser.process_chunk(cleaned_text + "\n"):
                            yield parsed_message
                
                # Add a small delay to simulate real-time streaming
                await asyncio.sleep(0.01)
            
            # Finalize the parser to get any remaining content
            final_message = self.output_parser.finalize()
            if final_message:
                yield final_message
                
            logger.info(f"[{self.session_id}][MOCK] Mock execution completed")
            yield "[MOCK MODE] Execution completed\n"
                
        except Exception as e:
            logger.error(f"[{self.session_id}][MOCK] Exception: {str(e)}")
            yield f"ERROR: {str(e)}\n"
        finally:
            self._is_running = False
    
    async def execute_query(self, query: str) -> AsyncGenerator[str, None]:
        """Execute a query asynchronously using subprocess and yield output in real-time."""
        # Check if mock mode is enabled
        if config.biomni_mock_mode:
            logger.info(f"[{self.session_id}] Mock mode enabled, using mock execution")
            async for message in self._execute_mock_query(query):
                yield message
            return
        
        self._is_running = True
        
        try:
            # Prepare subprocess configuration
            config_json = self._prepare_subprocess_config()
            
            # Create and start subprocess
            process = await self._create_subprocess(query, config_json)
            
            # Read stdout line by line and process through parser
            if process.stdout:
                while self._is_running:
                    line = await process.stdout.readline()
                    if not line:  # EOF
                        break
                    
                    text = line.decode('utf-8').rstrip('\r\n')
                    if text:
                        # Log the raw stdout output
                        logger.info(f"[{self.session_id}][BIOMNI]: {text}")
                        
                        cleaned_text = self._clean_output_text(text)
                        if cleaned_text:
                            # Process through the new parser
                            for parsed_message in self.output_parser.process_chunk(cleaned_text + "\n"):
                                yield parsed_message
            
            # Wait for process to complete
            await process.wait()
            
            # Finalize the parser to get any remaining content
            final_message = self.output_parser.finalize()
            if final_message:
                yield final_message
            
            # Check for errors
            if process.returncode != 0:
                if process.stderr:
                    stderr_output = await process.stderr.read()
                    error_text = stderr_output.decode('utf-8').strip()
                    if error_text:
                        # Log the stderr output
                        logger.error(f"[{self.session_id}][BIOMNI]: {error_text}")
                        yield f"ERROR: {error_text}\n"
                logger.error(f"[{self.session_id}][BIOMNI] Process failed with exit code {process.returncode}")
                yield f"ERROR: Process failed with exit code {process.returncode}\n"
                
        except Exception as e:
            logger.error(f"[{self.session_id}][BIOMNI] Exception: {str(e)}")
            yield f"ERROR: {str(e)}\n"
        finally:
            self._is_running = False
    
    def stop_execution(self) -> None:
        """Stop the current execution."""
        self._is_running = False
    
    def is_running(self) -> bool:
        """Check if the agent is currently running."""
        return self._is_running