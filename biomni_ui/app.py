import asyncio
import logging
import re
import tiktoken
from pathlib import Path

import chainlit as cl

from biomni_ui.biomni_wrapper import AsyncBiomniWrapper
from biomni_ui.config import config
from biomni_ui.session_manager import session_manager

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format=config.log_format
)
logger = logging.getLogger(__name__)

# Initialize tokenizer for LLM token counting
tokenizer = tiktoken.get_encoding("cl100k_base")

# Define a pattern to split text into sentences for better streaming
SENTENCE_END_PATTERN = re.compile(r"[.!?\n]")



@cl.on_chat_start
async def start():
    """Initialize a new chat session."""
    try:
        # Create a new session
        session_id = session_manager.create_session()
        
        # Store session ID in user session
        cl.user_session.set("session_id", session_id)
        
        # Create Biomni wrapper for this session
        biomni_wrapper = AsyncBiomniWrapper(session_id)
        cl.user_session.set("biomni_wrapper", biomni_wrapper)
        
        # Send welcome message
        welcome_msg = f"""Welcome to Biomni UI.

I am your biomedical AI assistant. I can help you with biomedical research tasks, data analysis, experimental design, literature research, and database queries.

Please ask your question and I will use specialized tools and knowledge to assist you.
"""
        
        await cl.Message(content=welcome_msg).send()
        
        logger.info(f"New session started: {session_id}")
        
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        await cl.Message(content=f"Error starting session: {str(e)}").send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages and delegate processing."""
    session_id = cl.user_session.get("session_id")
    biomni_wrapper = cl.user_session.get("biomni_wrapper")

    if not session_id or not biomni_wrapper:
        await cl.Message(content="Session not found. Please refresh the page.").send()
        return

    user_message = message.content.strip()
    logger.info(f"Session {session_id}: User message received")

    response_msg = cl.Message(content="Processing...")
    await response_msg.send()

    try:
        await stream_response(user_message, biomni_wrapper, response_msg, session_id)
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        response_msg.content = error_msg
        await response_msg.update()
        logger.error(f"Session {session_id}: Error processing message: {e}")


async def stream_response(
    user_message: str,
    biomni_wrapper,
    response_msg: cl.Message,
    session_id: str,
    token_threshold: int = 30
) -> None:
    """Stream response in semantically complete slices."""
    full_response = ""
    current_chunk = ""
    tokens_since_last_update = 0

    async for output_chunk in biomni_wrapper.execute_query(user_message):
        if not output_chunk.strip():
            continue

        current_chunk += output_chunk
        tokens_in_chunk = len(tokenizer.encode(output_chunk))
        tokens_since_last_update += tokens_in_chunk

        # If sentence-ending punctuation is found and token threshold reached
        if SENTENCE_END_PATTERN.search(current_chunk) and tokens_since_last_update >= token_threshold:
            full_response += current_chunk
            response_msg.content = full_response + "▌"
            await response_msg.update()
            current_chunk = ""
            tokens_since_last_update = 0

    # Final update
    if current_chunk:
        full_response += current_chunk
        response_msg.content = full_response.strip()
        await response_msg.update()

    logger.info(f"Session {session_id}: Query completed successfully")


@cl.on_chat_end
async def end():
    """Handle chat session end."""
    session_id = cl.user_session.get("session_id")
    
    if session_id:
        session_manager.close_session(session_id)
        logger.info(f"Session ended: {session_id}")


@cl.on_stop
async def stop():
    """Handle stop signal."""
    session_id = cl.user_session.get("session_id")
    biomni_wrapper = cl.user_session.get("biomni_wrapper")
    
    if biomni_wrapper and biomni_wrapper.is_running():
        biomni_wrapper.stop_execution()
        logger.info(f"Session {session_id}: Execution stopped by user")


if __name__ == "__main__":
    # Run the Chainlit app
    cl.run(
        host=config.chainlit_host,
        port=config.chainlit_port,
        debug=config.log_level == "DEBUG"
    )