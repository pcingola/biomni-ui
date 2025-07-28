import asyncio
import json
import os
import sys
import time
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
    
    @classmethod
    def from_json(cls, json_str: str) -> "BiomniSubprocessConfig":
        """Create config from JSON string."""
        return cls.model_validate_json(json_str)


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
    
    def _build_subprocess_command(self, query: str, config_json: str) -> list[str]:
        """Build the subprocess command."""
        wrapper_script = Path(__file__).parent / "biomni_subprocess_wrapper.py"
        return [
            sys.executable,
            str(wrapper_script),
            self.session_id,
            query,
            config_json
        ]
    
    async def _create_subprocess(self, cmd: list[str]) -> asyncio.subprocess.Process:
        """Create and return the async subprocess."""
        return await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.session_outputs_path)
        )
    
    def _clean_stdout_text(self, text: str) -> str:
        """Clean and format stdout text."""
        if text.startswith('[BIOMNI]'):
            return text[8:].strip()
        elif text.startswith('[LOG]'):
            return text[5:].strip()
        elif text.startswith('[RESULT]'):
            return text[8:].strip()
        return text
    
    def _format_stderr_text(self, text: str) -> str:
        """Format stderr text with appropriate prefix."""
        if text.startswith('[ERROR]'):
            return f"ERROR: {text[7:].strip()}"
        else:
            return f"STDERR: {text}"
    
    async def _read_stdout_stream(self, process: asyncio.subprocess.Process) -> AsyncGenerator[str, None]:
        """Read stdout stream and yield formatted output."""
        if not process.stdout:
            return
            
        while self._is_running:
            line = await process.stdout.readline()
            if not line:  # EOF
                break
            
            text = line.decode('utf-8').strip()
            if text:
                cleaned_text = self._clean_stdout_text(text)
                if cleaned_text:
                    yield cleaned_text
    
    async def _read_stderr_stream(self, process: asyncio.subprocess.Process) -> AsyncGenerator[str, None]:
        """Read stderr stream and yield formatted output."""
        if not process.stderr:
            return
            
        while self._is_running:
            line = await process.stderr.readline()
            if not line:  # EOF
                break
            
            text = line.decode('utf-8').strip()
            if text:
                yield self._format_stderr_text(text)
    
    async def _queue_stream_output(self, stream_reader, stream_type: str, output_queue: asyncio.Queue):
        """Queue output from a stream reader."""
        async for line in stream_reader:
            await output_queue.put((stream_type, line))
        await output_queue.put((stream_type, None))  # EOF marker
    
    async def _process_output_streams(self, process: asyncio.subprocess.Process) -> AsyncGenerator[str, None]:
        """Process both stdout and stderr streams concurrently."""
        output_queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
        
        # Create stream readers
        stdout_reader = self._read_stdout_stream(process)
        stderr_reader = self._read_stderr_stream(process)
        
        # Start both stream processors
        stdout_task = asyncio.create_task(
            self._queue_stream_output(stdout_reader, 'stdout', output_queue)
        )
        stderr_task = asyncio.create_task(
            self._queue_stream_output(stderr_reader, 'stderr', output_queue)
        )
        
        # Track which streams are still active
        active_streams = {'stdout', 'stderr'}
        
        # Read from queue and yield output
        while active_streams and self._is_running:
            try:
                stream_type, line = await asyncio.wait_for(output_queue.get(), timeout=0.1)
                
                if line is None:  # EOF marker
                    active_streams.discard(stream_type)
                else:
                    yield line
                    
            except asyncio.TimeoutError:
                # Check if tasks are still running
                if stdout_task.done() and stderr_task.done():
                    break
                continue
    
    async def execute_query(self, query: str) -> AsyncGenerator[str, None]:
        """Execute a query asynchronously using subprocess and yield output in real-time."""
        self._is_running = True
        
        try:
            # Prepare subprocess configuration and command
            config_json = self._prepare_subprocess_config()
            cmd = self._build_subprocess_command(query, config_json)
            
            # Create and start subprocess
            process = await self._create_subprocess(cmd)
            
            # Process output streams
            async for output_line in self._process_output_streams(process):
                yield output_line
            
            # Wait for process to complete
            await process.wait()
            
            if process.returncode != 0:
                yield f"ERROR: Process failed with exit code {process.returncode}"
                
        except Exception as e:
            yield f"ERROR: {str(e)}"
        finally:
            self._is_running = False
    
    def stop_execution(self) -> None:
        """Stop the current execution."""
        self._is_running = False
    
    def is_running(self) -> bool:
        """Check if the agent is currently running."""
        return self._is_running