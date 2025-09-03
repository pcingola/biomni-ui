# app.py
from __future__ import annotations

import asyncio
import traceback
import chainlit as cl

from aixtools.logging.logging_config import get_logger

from biomni_ui.config import config
from biomni_ui.file_manager import FileManager, FileManagerError
from biomni_ui.file_validator import FileValidationError
from biomni_ui.session_manager import session_manager
from biomni_ui.agents import BiomniAgentOrchestrator

# ─────────────────────────────────────────────────────────────────────────────
# Globals
# ─────────────────────────────────────────────────────────────────────────────
logger = get_logger(__name__)
file_manager = FileManager()
orchestrator = BiomniAgentOrchestrator(file_manager)

HISTORY = "history"
EXAMPLE_QUERIES = [
    ("Genes per chromosome plot", "Give me a plot with the number of genes per chromosome", "chart-column"),
    ("SRY inquiry", "What is the SRY?", "dna"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
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


async def handle_user_query(message: cl.Message):
    session_id: str | None = cl.user_session.get("session_id")
    if not session_id:
        await cl.Message("Session missing – refresh the page.").send()
        return

    session_outputs = session_manager.get_session_outputs_path(session_id)
    logger.info("[%s] New query submitted: %s", session_id, message.content)

    # Initial status (we will stream into this message)
    status = cl.Message(content="Starting…")
    await status.send()

    # File uploads (if any)
    if config.file_upload_enabled and message.elements:
        logger.info("[%s] New file(s): %s", session_id, ", ".join(e.name for e in message.elements))
        await status.update(content="Processing file uploads…")
        await handle_file_attachments(message.elements, session_id)

    # Define a progress callback that streams into the same message
    async def progress_cb(line: str):
        status.content = line
        await status.update()

    try:
        history: list[str] = cl.user_session.get(HISTORY, [])
        result = await orchestrator.run_full_pipeline(
            query=message.content.strip(),
            session_id=session_id,
            session_outputs_dir=session_outputs,
            history=history,
            progress=progress_cb,  # ← keeps streaming to the user
        )

        # Persist history
        cl.user_session.set(HISTORY, result["history"])

        # Show selection summary
        await cl.Message(content=result["selected_md"]).send()

        # Final report + artifacts
        await cl.Message(
            content=result["report_md"],
            elements=result["elements"],
        ).send()

    except Exception as exc:
        stack = traceback.format_exc()
        await cl.Message(
            content=f"❌ Error: {exc}",
            elements=[cl.Text(name="Stack trace", content=stack, language="python")],
        ).send()
        logger.error("Pipeline failed: %s\n%s", exc, stack)
    finally:
        # Remove the streaming status message once we're done
        await status.remove()


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
        "> This model can produce hallucinations. Always verify results independently.\n\n"
    )
    await cl.Message(content=welcome).send()

    actions = [
        cl.Action(name="run_example", payload={"value": prompt}, label=label, icon=icon)
        for label, prompt, icon in EXAMPLE_QUERIES
    ]
    await cl.Message(content="👋 Try an example:", actions=actions).send()


@cl.action_callback("run_example")
async def on_action(action: cl.Action):
    fake_msg = cl.Message(content=action.payload.get("value"), elements=[])
    await handle_user_query(fake_msg)


@cl.on_message
async def on_message(message: cl.Message):
    await handle_user_query(message)
