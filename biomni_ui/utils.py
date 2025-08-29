import glob
import os
import chainlit as cl
import shutil

from pathlib import Path
from aixtools.agents import get_agent
from aixtools.logging.logging_config import get_logger
from pydantic_ai import Agent
from string import Template

from biomni_ui.models import Resource, SelectedToolsModel, ExecutionResult
from biomni_ui.mcp_servers import _SERVER_MAP, MCPServerStreamableHTTPRestrictiveContext
from biomni_ui.config import config
from biomni_ui.constants import TOOL_SELECTOR_PROMPT, EXECUTOR_PROMPT, AVAILABLE_LIBRARIES
from biomni_ui.models import Step

logger = get_logger(__name__)

HISTORY = "history"
IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

async def get_initial_tools() -> list[Resource]:
    """Get initial tools from all MCP servers.

    Returns:
        list[Resource]: A list of resources representing the available tools.
    """
    tools: list[Resource] = []
    for server in _SERVER_MAP.values():
        try:
            for tool in (await server.get_tools(None)).values():
                if tool.tool_def.name not in {t.name for t in tools}:
                    tools.append(Resource(name=tool.tool_def.name, reason=tool.tool_def.description))
        except Exception as e:
            logger.error(f"Error getting tools from {server}: {e}")
            raise Exception(f"Failed to get initial tools from {server}: {e}")
    return tools


def scan_data_lake() -> list[Resource]:
    """
    Scan the data lake directory and return a list of resources.
    Returns:
        list[Resource]: A list of resources representing the data lake items.
    """
    files = glob.glob(f"{config.biomni_data_path}/biomni_data/data_lake/*", recursive=True)
    return [Resource(name=os.path.basename(f), reason=f"Dataset: {os.path.basename(f)}") for f in files]

def get_libraries_for_query() -> list[Resource]:
    """
    Get libraries relevant to the query.

    Returns:
        list[Resource]: A list of resources representing the libraries.
    """
    libraries = []
    for name, reason in AVAILABLE_LIBRARIES.items():
        libraries.append(Resource(name=name, reason=reason))
    return libraries

async def build_tool_selector(tools: list[Resource], data: list[Resource], libraries: list[Resource]) -> Agent:
    """
    Build the tool selector agent with the provided tools and data.

    Args:
        tools (list[Resource]): A list of resources representing the available tools.
        data (list[Resource]): A list of resources representing the data lake items.

    Returns:
        Agent: The constructed tool selector agent.
    """
    
    return get_agent(
        output_type=SelectedToolsModel,
        system_prompt=TOOL_SELECTOR_PROMPT.format(tools=tools, data=data, libraries=libraries),
        mcp_servers=_SERVER_MAP.values(),
    )

def _bullets(resources):
    return "\n".join(f"- {r.name}: {r.reason or '—'}" for r in resources)

async def build_executor(selected_tools: SelectedToolsModel, session_dir: str) -> Agent:
    allowed = [t.name for t in selected_tools.tools]
    restricted = {
        name: MCPServerStreamableHTTPRestrictiveContext(
            url=server.url, allowed_resources=allowed
        )
        for name, server in _SERVER_MAP.items()
    }

    tmpl = Template(EXECUTOR_PROMPT)  # EXECUTOR_PROMPT must use $VARS
    system_prompt = tmpl.safe_substitute(
        BIOMNI_DATA_PATH=config.biomni_data_path,
        TOOLS=_bullets(selected_tools.tools),
        DATA=_bullets(selected_tools.data_lake),
        LIBRARIES=_bullets(selected_tools.libraries),
        SESSION_OUTPUTS=session_dir,
    )

    return get_agent(
        system_prompt=system_prompt,
        output_type=ExecutionResult,
        mcp_servers=list(restricted.values()),
    )
    
def update_history(
    history: list[str] | None,
    user_message: str | None = None,
    run_return: object | None = None,
) -> list[str]:
    """Append the user message or the agent output to `history` and return it."""
    if history is None:
        history = []

    if user_message:
        history.append(user_message)

    if run_return is not None:
        history.append(str(run_return))

    return history

    
def _md_table(items: list[Resource], title: str) -> str:
    if not items:
        return f"#### {title}\n_None_\n"
    rows = "\n".join(f"| {r.name} | {r.reason or '—'} |" for r in items)
    return f"""#### {title}
| Name | Reason |
| --- | --- |
{rows}
"""

def selected_to_markdown(selected: SelectedToolsModel) -> str:
    parts = ["### Selected resources\n"]
    if selected.tools:
        parts.append(_md_table(selected.tools, "Tools"))
    if selected.data_lake:
        parts.append(_md_table(selected.data_lake, "Data Lake"))
    if selected.libraries:
        parts.append(_md_table(selected.libraries, "Libraries"))
    return "\n".join(parts)

def step_to_markdown(i: int, s: Step) -> str:
    parts = [f"### {i}. {s.name}\n{s.description}\n"]

    if s.resources:
        res_rows = "\n".join(f"| {r.name} | {getattr(r, 'reason', None) or '—'} |" for r in s.resources)
        parts.append("Resources used:\n\n| Name | Reason |\n| --- | --- |\n" + res_rows + "\n")

    if s.cites:
        seen, cites = set(), []
        for c in s.cites:
            if c and c not in seen:
                seen.add(c); cites.append(c)
        if cites:
            parts.append("Cites:\n" + "\n".join(f"- {c}" for c in cites) + "\n")

    if s.result:
        parts.append(f"**Result:** {s.result}\n")

    if s.stderr:
        parts.append(f"**Stderr**\n\n```text\n{s.stderr}\n```\n")

    return "\n".join(parts)

def execution_to_markdown(ex: ExecutionResult) -> str:
    steps_md = "\n".join(step_to_markdown(i, s) for i, s in enumerate(ex.step, start=1))
    return f"## Execution\n\n{steps_md}\n\n## Summary\n\n{ex.summary}\n"

def gather_execution_elements(
    ex: ExecutionResult,
    session_dir: str | Path,
) -> list:
    """Create Chainlit elements for the notebook and each step's output files.
    Files are moved into `session_dir` before creating Chainlit elements.
    """
    session_dir = Path(session_dir).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    elements: list = []
    seen: set[Path] = set()
    
    def add_path(path_str: str, label: str | None = None):
        p = Path(path_str)

        if not p.exists():
            logger.warning("Skipped missing file: %s", p)
            return

        # Copy/move into session_dir
        target = session_dir / p.name
        counter = 1
        while target.exists():  # avoid overwriting
            target = session_dir / f"{p.stem}_{counter}{p.suffix}"
            counter += 1

        shutil.move(str(p), target)
        p = target.resolve()

        if p in seen:
            return
        seen.add(p)

        name = label or p.name
        if p.suffix.lower() in IMG_EXTS:
            elements.append(cl.Image(path=str(p), name=name, display="inline"))
        else:
            elements.append(cl.File(path=str(p), name=name, display="inline"))

    # Add notebook first (if present)
    if ex.jupyter_notebook:
        add_path(ex.jupyter_notebook, label=Path(ex.jupyter_notebook).name)

    # Add step outputs
    for idx, step in enumerate(ex.step, start=1):
        for f in (step.output_files or []):
            add_path(f, label=f"Step {idx}: {Path(f).name}")

    return elements

def _clip(s: str, n: int = 180) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n].rstrip() + "…"

def _dedupe_keep_order(items):
    seen, out = set(), []
    for x in items:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out

def _tool_names_from_parts(parts):
    # Works for both ToolCallPart (has args) and ToolReturnPart (has content)
    names = [getattr(p, "tool_name", None) for p in parts if hasattr(p, "tool_name")]
    return _dedupe_keep_order(names)

def _summarize_names(names: list[str], max_show: int = 3) -> str:
    if not names:
        return ""
    if len(names) <= max_show:
        return ", ".join(names)
    head = ", ".join(names[:max_show])
    return f"{head} +{len(names) - max_show} more"

def format_progress_line(node, title: str| None) -> str:
    """Return a user-friendly, reactive progress line based only on the node's data."""
    tname = type(node).__name__

    prefix = f"### {title}\n*⏳ Thinking...* - " if title else ""

    # UserPromptNode: reflect the user’s question
    if hasattr(node, "user_prompt"):
        q = getattr(node, "user_prompt", "") or getattr(node, "prompt", "")
        return f'{prefix}User asked: "{_clip(q)}"...'

    # ModelRequestNode: either sending a request, or receiving tool results (ToolReturnPart)
    if hasattr(node, "request"):
        parts = getattr(node.request, "parts", []) or []
        tool_returns = [p for p in parts if hasattr(p, "tool_name") and hasattr(p, "content")]
        if tool_returns:
            names = _tool_names_from_parts(tool_returns)
            return f"{prefix}Received results from: {_summarize_names(names)}..."
        return f"{prefix}Sending request to the model..."

    # CallToolsNode: the model asked to call tools (ToolCallPart present)
    if hasattr(node, "model_response"):
        parts = getattr(node.model_response, "parts", []) or []
        tool_calls = [p for p in parts if hasattr(p, "tool_name") and hasattr(p, "args")]
        if tool_calls:
            names = _tool_names_from_parts(tool_calls)
            return f"{prefix}Calling tools: {_summarize_names(names)}..."
        return f"{prefix}Processing model response..."

    # End: the run is concluding
    if tname == "End":
        return f"{prefix}Preparing final report..."

    # Fallback: unknown node types
    return f"{prefix}Working..."
