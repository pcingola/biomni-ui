import asyncio
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import AsyncGenerator

from biomni_ui.config import config
from biomni_ui.session_manager import session_manager


class AsyncBiomniWrapper:
    """Async wrapper for Biomni A1 agent to prevent UI blocking."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent = None
        self._output_queue: asyncio.Queue[str] = asyncio.Queue()
        self._is_running = False
        self.session_outputs_path = session_manager.get_session_outputs_path(session_id)
    
    async def initialize_agent(self) -> None:
        """Initialize the Biomni A1 agent with shared data path."""
        # Import Biomni here to avoid import issues if not installed
        try:
            from biomni.agent import A1
            use_mock = False
        except ImportError:
            print("Biomni not available, using mock implementation for testing")
            from biomni_ui.mock_biomni import MockA1 as A1
            use_mock = True
        
        # Use the shared Biomni data path (not session-specific)
        biomni_data_path = config.get_biomni_data_path()
        
        # Change working directory to session outputs path for any file operations
        original_cwd = os.getcwd()
        os.chdir(str(self.session_outputs_path))
        
        try:
            if use_mock:
                # For mock, we don't need all the Biomni-specific parameters
                self.agent = A1(
                    path=str(biomni_data_path),
                    llm=config.biomni_llm_model
                )
            else:
                self.agent = A1(
                    path=str(biomni_data_path),  # Shared data path
                    llm=config.biomni_llm_model,
                    timeout_seconds=config.biomni_timeout_seconds,
                    base_url=config.biomni_base_url,
                    api_key=config.biomni_api_key
                )
        finally:
            # Restore original working directory
            os.chdir(original_cwd)
    
    async def execute_query(self, query: str) -> AsyncGenerator[str, None]:
        """Execute a query asynchronously and yield output in real-time."""
        if not self.agent:
            await self.initialize_agent()
        
        self._is_running = True
        
        # Change to session outputs directory for execution
        original_cwd = os.getcwd()
        os.chdir(str(self.session_outputs_path))
        
        try:
            # Create a task to capture output and run the agent
            output_task = asyncio.create_task(self._capture_output_and_run(query))
            
            # Yield output as it becomes available with improved streaming
            output_received = False
            while self._is_running:
                try:
                    # Wait for output with a shorter timeout for better responsiveness
                    output = await asyncio.wait_for(self._output_queue.get(), timeout=0.05)
                    output_received = True
                    if output and output.strip():
                        yield output
                except asyncio.TimeoutError:
                    # Check if the task is done
                    if output_task.done():
                        break
                    continue
            
            # Wait for the task to complete and get final result
            final_result = await output_task
            
            # Yield any remaining output in the queue
            while not self._output_queue.empty():
                try:
                    output = self._output_queue.get_nowait()
                    if output and output.strip():
                        output_received = True
                        yield output
                except asyncio.QueueEmpty:
                    break
            
            # Yield final result if it's not empty and we haven't received other output
            if final_result and final_result.strip():
                yield f"\n**Final Result:**\n{final_result}"
                output_received = True
            
            # If no output was received at all, yield a message
            if not output_received:
                yield "**No output captured** - This might indicate an issue with output redirection."
                
        except Exception as e:
            yield f"\n**Error occurred:**\n{str(e)}"
        finally:
            self._is_running = False
            # Restore original working directory
            os.chdir(original_cwd)
    
    async def _capture_output_and_run(self, query: str) -> str:
        """Capture stdout/stderr and run the agent in a thread."""
        
        async def send_output(content: str, prefix: str = "") -> None:
            """Helper to send output to queue with proper formatting."""
            if content and content.strip():
                formatted_content = f"{prefix}{content}" if prefix else content
                await self._output_queue.put(formatted_content)
        
        def run_agent():
            """Run the agent and capture output."""
            output_buffer = StringIO()
            error_buffer = StringIO()
            
            try:
                # Capture stdout/stderr during execution
                with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                    log, final_result = self.agent.go(query)
                
                # Force flush buffers
                sys.stdout.flush()
                sys.stderr.flush()
                
                return {
                    'log': log,
                    'final_result': final_result,
                    'captured_output': output_buffer.getvalue(),
                    'captured_errors': error_buffer.getvalue()
                }
                
            except Exception as e:
                return {
                    'log': [],
                    'final_result': str(e),
                    'captured_output': output_buffer.getvalue(),
                    'captured_errors': error_buffer.getvalue(),
                    'error': str(e)
                }
        
        # Run agent in executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_agent)
        
        # Process results and send to queue
        if result.get('error'):
            await send_output(f"**Execution Error:**\n{result['error']}")
        
        # Send captured stdout if any
        if result['captured_output']:
            await send_output(result['captured_output'], "**Captured Output:**\n")
        
        # Send captured stderr if any
        if result['captured_errors']:
            await send_output(result['captured_errors'], "**Captured Errors:**\n")
        
        # Send log entries with real-time streaming
        if result['log']:
            for entry in result['log']:
                if entry and entry.strip():
                    await send_output(entry)
                    # Small delay for streaming effect
                    await asyncio.sleep(0.05)
        
        return result['final_result']
    
    def stop_execution(self) -> None:
        """Stop the current execution."""
        self._is_running = False
    
    def is_running(self) -> bool:
        """Check if the agent is currently running."""
        return self._is_running
    
    def get_session_files(self) -> list[Path]:
        """Get list of files created in the session outputs directory."""
        if not self.session_outputs_path.exists():
            return []
        
        files = []
        for item in self.session_outputs_path.rglob("*"):
            if item.is_file():
                files.append(item)
        return files