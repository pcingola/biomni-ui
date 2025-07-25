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
                    use_tool_retriever=config.biomni_use_tool_retriever,
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
            # Run the agent in a separate thread to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Create a task to capture output and run the agent
            output_task = asyncio.create_task(self._capture_output_and_run(query))
            
            # Yield output as it becomes available
            while self._is_running or not self._output_queue.empty():
                try:
                    # Wait for output with a timeout to check if execution is done
                    output = await asyncio.wait_for(self._output_queue.get(), timeout=0.1)
                    yield output
                except asyncio.TimeoutError:
                    # Check if the task is done
                    if output_task.done():
                        break
                    continue
            
            # Wait for the task to complete and get final result
            final_result = await output_task
            
            # Yield any remaining output
            while not self._output_queue.empty():
                output = await self._output_queue.get()
                yield output
            
            # Yield final result if it's not empty
            if final_result and final_result.strip():
                yield f"\n**Final Result:**\n{final_result}"
                
        except Exception as e:
            yield f"\n**Error occurred:**\n{str(e)}"
        finally:
            self._is_running = False
            # Restore original working directory
            os.chdir(original_cwd)
    
    async def _capture_output_and_run(self, query: str) -> str:
        """Capture stdout/stderr and run the agent in a thread."""
        def run_agent():
            """Run the agent and capture output."""
            output_buffer = StringIO()
            error_buffer = StringIO()
            
            try:
                with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                    log, final_result = self.agent.go(query)
                
                # Send captured output to the queue
                captured_output = output_buffer.getvalue()
                if captured_output:
                    asyncio.run_coroutine_threadsafe(
                        self._output_queue.put(captured_output), 
                        asyncio.get_event_loop()
                    )
                
                # Send any errors
                captured_errors = error_buffer.getvalue()
                if captured_errors:
                    asyncio.run_coroutine_threadsafe(
                        self._output_queue.put(f"**Errors:**\n{captured_errors}"), 
                        asyncio.get_event_loop()
                    )
                
                # Process the log entries for real-time output
                if log:
                    for entry in log:
                        if entry and entry.strip():
                            asyncio.run_coroutine_threadsafe(
                                self._output_queue.put(entry), 
                                asyncio.get_event_loop()
                            )
                
                return final_result
                
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    self._output_queue.put(f"**Execution Error:**\n{str(e)}"), 
                    asyncio.get_event_loop()
                )
                return str(e)
        
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, run_agent)
    
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