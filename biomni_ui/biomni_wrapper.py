import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import AsyncGenerator

from biomni_ui.config import config
from biomni_ui.session_manager import session_manager


class AsyncBiomniWrapper:
    """Async wrapper for Biomni A1 agent to prevent UI blocking."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._is_running = False
        self.session_outputs_path = session_manager.get_session_outputs_path(session_id)
    
    
    async def execute_query(self, query: str) -> AsyncGenerator[str, None]:
        """Execute a query asynchronously using subprocess and yield output in real-time."""
        self._is_running = True
        
        try:
            # Prepare config for subprocess
            config_data = {
                'session_outputs_path': str(self.session_outputs_path),
                'biomni_data_path': str(config.get_biomni_data_path()),
                'biomni_llm_model': config.biomni_llm_model,
                'biomni_timeout_seconds': config.biomni_timeout_seconds,
                'biomni_base_url': config.biomni_base_url,
                'biomni_api_key': config.biomni_api_key
            }
            config_json = json.dumps(config_data)
            
            # Get the subprocess wrapper script path
            wrapper_script = Path(__file__).parent / "biomni_subprocess_wrapper.py"
            
            # Create subprocess command
            cmd = [
                sys.executable,
                str(wrapper_script),
                self.session_id,
                query,
                config_json
            ]
            
            # Create async subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.session_outputs_path)
            )
            
            # Read both stdout and stderr concurrently using asyncio.gather
            async def read_stdout():
                """Read stdout and yield formatted output."""
                if not process.stdout:
                    return
                    
                while self._is_running:
                    line = await process.stdout.readline()
                    if not line:  # EOF
                        break
                    
                    text = line.decode('utf-8').strip()
                    if text:
                        # Clean up output
                        if text.startswith('[BIOMNI]'):
                            text = text[8:].strip()
                        elif text.startswith('[LOG]'):
                            text = text[5:].strip()
                        elif text.startswith('[RESULT]'):
                            text = text[8:].strip()
                        
                        if text:
                            yield text
            
            async def read_stderr():
                """Read stderr and yield formatted output."""
                if not process.stderr:
                    return
                    
                while self._is_running:
                    line = await process.stderr.readline()
                    if not line:  # EOF
                        break
                    
                    text = line.decode('utf-8').strip()
                    if text:
                        # Format stderr with prefix
                        if text.startswith('[ERROR]'):
                            text = f"ERROR: {text[7:].strip()}"
                        else:
                            text = f"STDERR: {text}"
                        yield text
            
            # Use a queue to merge outputs from both streams
            output_queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
            
            async def queue_stdout():
                async for line in read_stdout():
                    await output_queue.put(('stdout', line))
                await output_queue.put(('stdout', None))  # EOF marker
            
            async def queue_stderr():
                async for line in read_stderr():
                    await output_queue.put(('stderr', line))
                await output_queue.put(('stderr', None))  # EOF marker
            
            # Start both readers
            stdout_task = asyncio.create_task(queue_stdout())
            stderr_task = asyncio.create_task(queue_stderr())
            
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