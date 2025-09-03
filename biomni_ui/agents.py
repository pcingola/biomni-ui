# biomni_ui/agents.py
from __future__ import annotations

import asyncio
import traceback
from typing import Awaitable, Callable, Optional, Tuple, Any, Dict, List

from pydantic_ai import Agent

from aixtools.logging.logging_config import get_logger
from biomni_ui.models import SelectedToolsModel
from biomni_ui.utils import (
    get_initial_tools,
    scan_data_lake,
    build_tool_selector,
    build_executor,
    selected_to_markdown,
    execution_to_markdown,
    gather_execution_elements,
    update_history,
    format_progress_line,
)
from biomni_ui.file_manager import FileManager
from biomni_ui.session_manager import session_manager
from biomni_ui.config import config

logger = get_logger(__name__)


ProgressCb = Callable[[str], Awaitable[None]]  # receives a line to stream to the UI


class BiomniAgentOrchestrator:
    """
    Encapsulates tool selection + execution with streaming support via a progress callback.
    """

    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager

    async def _run_agent(
        self,
        agent: Agent,
        prompt: str | List[str],
        title: Optional[str],
        progress: ProgressCb,
    ):
        """
        Streams node updates via `progress`. Returns agent_run.result at the end.
        """
        try:
            async with agent.iter(prompt) as agent_run:
                async for node in agent_run:
                    line = format_progress_line(node, title=title)
                    logger.debug(line)
                    await progress(line)
                return agent_run.result
        except Exception as exc:
            stack = traceback.format_exc()
            logger.error("Agent run failed: %s\n%s", exc, stack)
            raise

    async def discover(self) -> Tuple[list, list, list]:
        """
        Parallel discovery of tools, data lake entries, and libraries.
        """
        initial_tools, data_items, libraries = await asyncio.gather(
            get_initial_tools(),
            asyncio.to_thread(scan_data_lake),
            asyncio.to_thread(self._get_libraries_for_query_proxy),
        )
        return initial_tools, data_items, libraries

    def _get_libraries_for_query_proxy(self):
        # utils.get_libraries_for_query expects no args and is CPU/light IO bound in your code
        from biomni_ui.utils import get_libraries_for_query

        return get_libraries_for_query()

    def build_file_context(self, session_id: str, original_query: str) -> str:
        """
        If files exist in the session and upload is enabled, injects a context preamble.
        """
        enhanced_query = original_query
        if config.file_upload_enabled:
            ups = self.file_manager.list_session_files(session_id)
            if ups:
                ctx = self.file_manager.get_file_context_for_query(session_id, ups)
                enhanced_query = f"FILES INPUT CONTENT:\n{ctx}\n\nUser query: {original_query}"
        return enhanced_query

    async def run_full_pipeline(
        self,
        *,
        query: str,
        session_id: str,
        session_outputs_dir: str,
        history: list[str] | None,
        progress: ProgressCb,
    ) -> Dict[str, Any]:
        """
        Orchestrates:
          1) discovery
          2) tool selection
          3) plan & execution
          4) final report building

        Streams status via `progress`.
        Returns dict with: history, selected, execution, report_md, elements
        """
        history = history or []

        await progress("Discovering available resources…")
        initial_tools, data_items, libraries = await self.discover()

        await progress(
            f"✅ Discovered **{len(initial_tools)}** tools, **{len(data_items)}** data-lake items, and **{len(libraries)}** libraries."
        )

        enhanced_query = self.build_file_context(session_id, query)
        history = update_history(history, user_message=enhanced_query)

        # Tool selection
        await progress("### Selecting the most relevant resources...")
        selector_agent = await build_tool_selector(initial_tools, data_items, libraries)
        selected = await self._run_agent(
            selector_agent,
            prompt=enhanced_query,
            title="Selecting the most relevant resources",
            progress=progress,
        )
        history = update_history(history, run_return=selected.output)

        # Selected tools summary (markdown)
        if isinstance(selected.output, SelectedToolsModel):
            selected_md = selected_to_markdown(selected.output)
        else:
            logger.warning("Selector did not return SelectedToolsModel: %s", selected.output)
            selected_md = f"### Selected resources\n\n{selected.output}"

        # Execute
        await progress("### Executing...")
        executor_agent = await build_executor(selected.output, session_dir=session_outputs_dir)
        execution = await self._run_agent(
            executor_agent,
            prompt=enhanced_query,
            title="Executing",
            progress=progress,
        )
        history = update_history(history, run_return=execution)

        # Final report
        report_md = execution_to_markdown(execution.output)
        elements = gather_execution_elements(execution.output, session_outputs_dir)

        return {
            "history": history,
            "selected": selected,
            "selected_md": selected_md,
            "execution": execution,
            "report_md": report_md,
            "elements": elements,
        }
