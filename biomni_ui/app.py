import asyncio
import logging
import re
import tiktoken
from pathlib import Path

import chainlit as cl

from biomni_ui.biomni_wrapper import AsyncBiomniWrapper
from biomni_ui.config import config
from biomni_ui.file_manager import FileManager, FileManagerError
from biomni_ui.file_processor import FileProcessor
from biomni_ui.file_validator import FileValidationError
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

# Initialize file manager and processor
file_manager = FileManager()
file_processor = FileProcessor()


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
        file_upload_info = ""
        if config.file_upload_enabled:
            allowed_types = ", ".join(config.allowed_file_types[:10])  # Show first 10 types
            more_types = f" and {len(config.allowed_file_types) - 10} more" if len(config.allowed_file_types) > 10 else ""
            file_upload_info = f"""

📎 **File Upload Support**: You can upload files for analysis!
Supported formats: {allowed_types}{more_types}
Maximum file size: {config.max_file_size_mb}MB
"""
        
        welcome_msg = f"""Welcome to Biomni UI.

I am your biomedical AI assistant. I can help you with biomedical research tasks, data analysis, experimental design, literature research, and database queries.{file_upload_info}

Please ask your question and I will use specialized tools and knowledge to assist you.
"""
        
        await cl.Message(content=welcome_msg).send()
        
        logger.info(f"New session started: {session_id}")
        
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        await cl.Message(content=f"Error starting session: {str(e)}").send()


@cl.on_file_upload(accept=config.allowed_file_types if config.file_upload_enabled else [])
async def handle_file_upload(files: list[cl.File]):
    """Handle file uploads from users."""
    if not config.file_upload_enabled:
        await cl.Message(content="File upload is currently disabled.").send()
        return
    
    session_id = cl.user_session.get("session_id")
    if not session_id:
        await cl.Message(content="Session not found. Please refresh the page.").send()
        return
    
    uploaded_files = []
    errors = []
    
    for file in files:
        try:
            # Ensure file content is bytes
            file_content = file.content
            if isinstance(file_content, str):
                file_content = file_content.encode('utf-8')
            elif file_content is None:
                raise FileValidationError("File content is empty")
            
            # Save the uploaded file
            uploaded_file = file_manager.save_uploaded_file(
                session_id=session_id,
                file_content=file_content,
                original_filename=file.name
            )
            
            # Add to session tracking
            session_manager.add_uploaded_file(session_id, uploaded_file.file_id)
            
            uploaded_files.append(uploaded_file)
            logger.info(f"File uploaded successfully: {file.name} (ID: {uploaded_file.file_id})")
            
        except (FileValidationError, FileManagerError) as e:
            error_msg = f"Failed to upload {file.name}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error uploading {file.name}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
    
    # Send feedback to user
    if uploaded_files:
        file_list = "\n".join([
            f"✅ **{f.original_filename}** ({f.file_extension.upper()}, {f.file_size:,} bytes)"
            for f in uploaded_files
        ])
        
        success_msg = f"Successfully uploaded {len(uploaded_files)} file(s):\n\n{file_list}"
        
        if len(uploaded_files) == 1:
            success_msg += f"\n\nYou can now ask questions about this file, and I'll analyze it using appropriate biomedical tools."
        else:
            success_msg += f"\n\nYou can now ask questions about these files, and I'll analyze them using appropriate biomedical tools."
        
        await cl.Message(content=success_msg).send()
    
    if errors:
        error_msg = "Some files could not be uploaded:\n\n" + "\n".join([f"❌ {error}" for error in errors])
        await cl.Message(content=error_msg).send()


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

    # Add file context if files are uploaded
    enhanced_message = user_message
    if config.file_upload_enabled:
        uploaded_files = file_manager.list_session_files(session_id)
        if uploaded_files:
            file_context = file_processor.get_file_context_for_query(session_id, uploaded_files)
            enhanced_message = f"{file_context}\n\nUser query: {user_message}"
            logger.info(f"Session {session_id}: Added context for {len(uploaded_files)} uploaded files")

    response_msg = cl.Message(content="Processing...")
    await response_msg.send()

    try:
        await stream_response(enhanced_message, biomni_wrapper, response_msg, session_id)
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