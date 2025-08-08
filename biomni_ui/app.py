# biomni-ui: Chainlit app for Biomni UI

import asyncio
import traceback

import chainlit as cl

from aixtools.logging.logging_config import get_logger

from pydantic import ValidationError
from pydantic_ai import Agent
from typing import Any

# --- biomni-ui imports -------------------------------------------------------
from biomni_ui.config import config
from biomni_ui.file_manager import FileManager, FileManagerError
from biomni_ui.file_validator import FileValidationError
from biomni_ui.models import SelectedToolsModel, ExecutionResult
from biomni_ui.session_manager import session_manager
from biomni_ui.utils import (
    get_initial_tools,
    scan_data_lake,
    build_tool_selector,
    build_executor,
    get_libraries_for_query,
    selected_to_markdown,
    execution_to_markdown,
    update_history,
    gather_execution_elements,
    format_progress_line,
    coerce_execution_result
)

# ─────────────────────────────────────────────────────────────────────────────
# Globals
# ─────────────────────────────────────────────────────────────────────────────
file_manager = FileManager()
logger = get_logger(__name__)

HISTORY = "history"
EXAMPLE_QUERIES = [
    ("Genes per chromosome plot", "Give me a plot with the number of genes per chromosome", "chart-column"),
    ("SRY inquiry", "What is the SRY?", "dna"),
]

# ─────────────────────────────────────────────────────────────────────────────
# File uploads and attachments
# ─────────────────────────────────────────────────────────────────────────────

async def handle_file_attachments(elements: list[cl.File], session_id: str) -> None:
    if not config.file_upload_enabled:
        await cl.Message("File upload is currently disabled.").send()
        return

    uploaded, errors = [], []

    for element in elements:
        try:
            with open(element.path, "rb") as fh:
                data = fh.read()
            if not data:
                raise FileValidationError("File content is empty")

            up = file_manager.save_uploaded_file(session_id, data, element.name)
            session_manager.add_uploaded_file(session_id, up.file_id)
            uploaded.append(up)
            logger.info("Uploaded %s (ID=%s)", element.name, up.file_id)
        except (FileValidationError, FileManagerError) as exc:
            errors.append(f"{element.name}: {exc}")
            logger.error("Upload failed %s: %s", element.name, exc)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{element.name}: {exc}")
            logger.exception("Unexpected upload error for %s", element.name)

    if uploaded:
        lst = "\n".join(
            f"**{u.original_filename}** ({u.file_extension.upper()}, {u.file_size:,} bytes)"
            for u in uploaded
        )
        await cl.Message(f"✅ Uploaded {len(uploaded)} file(s):\n\n{lst}").send()
    if errors:
        await cl.Message("Some files failed:\n\n" + "\n".join(errors)).send()


# ─────────────────────────────────────────────────────────────────────────────
# Agent runner
# ─────────────────────────────────────────────────────────────────────────────

def _extract_raw_output(result: Any) -> Any:
    """Prefer typed .data, fall back to .output."""
    if result is None:
        return None
    return getattr(result, "data", None) or getattr(result, "output", None)


async def run_agent(agent: Agent, prompt: str | list[str], msg: cl.Message, title: str | None):
    """
    Like your print-based version, but:
      - streams model tokens to the UI,
      - appends a per-node trace to the UI,
      - returns (result.data or result.output, nodes).
    """
    result = None

    try:
        async with agent.iter(prompt) as agent_run:
            async for node in agent_run:
                
                msg.content = format_progress_line(node, title=title)
                await msg.update()
                # Capture final output when the graph ends
                if Agent.is_end_node(node):
                    result = agent_run.result

        await msg.remove()
        return result.output if result else None

    except Exception as exc:
        # Show a readable error + stack
        stack = traceback.format_exc()
        msg.content = f"❌ Error: {exc}"
        msg.elements.append(cl.Text(name="Stack trace", content=stack, language="python"))
        await msg.update()
        return None
    
async def handle_user_query(message: cl.Message):
    session_id: str | None = cl.user_session.get("session_id")
    session_outputs = session_manager.get_session_outputs_path(session_id)
    if not session_id:
        await cl.Message("Session missing – refresh the page.").send()
        return

    initial_status = cl.Message(content="Starting…")
    await initial_status.send()

    history: list[str] = cl.user_session.get(HISTORY, [])

    # File uploads
    if config.file_upload_enabled and message.elements:
        initial_status.content = "Processing file uploads…"
        await initial_status.update()
        await handle_file_attachments(message.elements, session_id)

    # Discover resources
    initial_status.content = "Discovering available resources…"
    await initial_status.update()
    initial_tools, data_items, libraries = await asyncio.gather(
        get_initial_tools(),
        asyncio.to_thread(scan_data_lake),
        asyncio.to_thread(get_libraries_for_query),
    )
    await initial_status.remove()
    await cl.Message(
        content=(
            f"✅ Discovered **{len(initial_tools)}** tools, "
            f"**{len(data_items)}** data-lake items, and **{len(libraries)}** libraries."
        )
    ).send()

    # Build prompt context
    query = message.content.strip()
    enhanced_query = query
    if config.file_upload_enabled:
        ups = file_manager.list_session_files(session_id)
        if ups:
            ctx = file_manager.get_file_context_for_query(session_id, ups)
            enhanced_query = f"FILES INPUT CONTENT:\n{ctx}\n\nUser query: {query}"
    history = update_history(history, user_message=enhanced_query)

    # TOOL SELECTION
    tool_selection_status = cl.Message(content="### Selecting the most relevant resources...")
    await tool_selection_status.send()
    selector_agent = await build_tool_selector(initial_tools, data_items, libraries)
    selected = await run_agent(selector_agent, enhanced_query, msg=tool_selection_status, title="Selecting the most relevant resources")
    history = update_history(history, run_return=selected)
    await tool_selection_status.remove()
    if isinstance(selected, SelectedToolsModel):
        await cl.Message(content=selected_to_markdown(selected)).send()
    else:
        await cl.Message(content=f"### Selected resources\n\n{selected}").send()

    # PLAN & EXECUTION
    execution_status = cl.Message(content="### Executing...")
    await execution_status.send()
    executor_agent = await build_executor(selected, session_dir=session_outputs)
    execution = await run_agent(executor_agent, enhanced_query, msg=execution_status, title="Executing")
    history = update_history(history, run_return=execution)
    cl.user_session.set(HISTORY, history)
    await execution_status.remove()

    # FINAL REPORT
    if isinstance(execution, ExecutionResult):
        report_md = execution_to_markdown(execution)
        elements = gather_execution_elements(execution, session_outputs)

        await cl.Message(
            content=report_md,
            elements=elements,  # images/files show inline with the report
        ).send()
    else:
        execution = coerce_execution_result(execution.data if execution else None) \
            or coerce_execution_result(execution.output if execution else None)

        if execution:
            # your existing rendering path
            elements = gather_execution_elements(execution, session_outputs)

            await cl.Message(
                content=report_md,
                elements=elements,  # images/files show inline with the report
            ).send()
            await cl.Message(
                content=report_md,
                elements=elements,  # images/files show inline with the report
            ).send()
        else:
            await cl.Message(content=f"### ✅ Finished\n\n{execution}").send()
        
# ─────────────────────────────────────────────────────────────────────────────
# Chainlit lifecycle events
# ─────────────────────────────────────────────────────────────────────────────
    
@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set(HISTORY, [])
    session_id = session_manager.create_session()
    cl.user_session.set("session_id", session_id)
    logger.info("New session created: %s", session_id)

    welcome = (
        "## PydanticAI-Biomni MCP UI\n\n"
        "I can help with biomedical research tasks: data analysis, experimental design, "
        "literature research, and database queries.\n\n"
        "> **Disclaimer:** Use only public, non-confidential, non-clinical data.\n"
    )
    await cl.Message(content=welcome).send()
    
    
    actions = [
        cl.Action(name="run_example", payload={"value": prompt}, label=label, icon=icon)
        for label, prompt, icon  in EXAMPLE_QUERIES
    ]
    await cl.Message(content="👋 Try an example:", actions=actions).send()

@cl.action_callback("run_example")
async def on_action(action: cl.Action):
    # Create a synthetic inbound message (no need to send this one)
    fake_msg = cl.Message(content=action.payload.get("value"), elements=[])
    await handle_user_query(fake_msg)

@cl.on_message
async def on_message(message: cl.Message):
    await handle_user_query(message)