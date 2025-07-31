import asyncio
import logging
from pathlib import Path

import chainlit as cl

from biomni_ui.biomni_wrapper import AsyncBiomniWrapper
from biomni_ui.config import config
from biomni_ui.file_manager import FileManager, FileManagerError
from biomni_ui.file_validator import FileValidationError
from biomni_ui.session_manager import session_manager

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format=config.log_format
)
logger = logging.getLogger(__name__)

# Initialize file manager
file_manager = FileManager()


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
        
        welcome_msg = (
            "Welcome to Biomni UI.\n\n"
            "I am your biomedical AI assistant. I can help you with biomedical research tasks, data analysis, experimental design, literature research, and database queries.\n\n"
            "**Disclaimer:** Use only public, non-confidential, non-clinical data. Do not upload or share private, sensitive, or patient-identifiable information.\n\n"
            "Please ask your question and I will use specialized tools and knowledge to assist you."
        )
        
        await cl.Message(content=welcome_msg).send()
        
        logger.info(f"New session started: {session_id}")
        
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        await cl.Message(content=f"Error starting session: {str(e)}").send()


async def handle_file_attachments(elements: list, session_id: str):
    """Handle file attachments from message elements."""
    if not config.file_upload_enabled:
        await cl.Message(content="File upload is currently disabled.").send()
        return
    
    uploaded_files = []
    errors = []
    
    for element in elements:
        try:
            # Read file content from the element's path
            with open(element.path, "rb") as f:
                file_content = f.read()
            
            if not file_content:
                raise FileValidationError("File content is empty")
            
            # Save the uploaded file
            uploaded_file = file_manager.save_uploaded_file(
                session_id=session_id,
                file_content=file_content,
                original_filename=element.name
            )
            
            # Add to session tracking
            session_manager.add_uploaded_file(session_id, uploaded_file.file_id)
            
            uploaded_files.append(uploaded_file)
            logger.info(f"File uploaded successfully: {element.name} (ID: {uploaded_file.file_id})")
            
        except (FileValidationError, FileManagerError) as e:
            error_msg = f"Failed to upload {element.name}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error uploading {element.name}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
    
    # Send feedback to user
    if uploaded_files:
        file_list = "\n".join([
            f"**{f.original_filename}** ({f.file_extension.upper()}, {f.file_size:,} bytes)"
            for f in uploaded_files
        ])
        
        success_msg = f"Successfully uploaded {len(uploaded_files)} file(s):\n\n{file_list}"

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

    user_message = message.content
    logger.info(f"Session {session_id}: User message received")

    # Handle file attachments if present
    if config.file_upload_enabled and message.elements:
        await handle_file_attachments(message.elements, session_id)

    # Add system instructions and file context
    enhanced_message = user_message
    
    # Add general system instructions with output path
    session_outputs_path = session_manager.get_session_outputs_path(session_id)
    system_instructions = """
SYSTEM INSTRUCTIONS:
1. File Generation: When you create any files, use this format:
   <file path="filename.ext" type="filetype">description</file>
   
   Supported types: data, image, notebook, report, genomic
   Examples:
   - <file path="results.csv" type="data">Analysis results</file>
   - <file path="plot.png" type="image">Visualization</file>
   - <file path="analysis.ipynb" type="notebook">Complete analysis</file>
   
   - Only provide the files that are relevant to the user.
   - Only print file tags when files are actually generated.
   - Add a <solution></solution> block after the file tags providing info about the file.

2. Display Rules:
   - DO NOT use plt.show(), display(), or similar commands to show plots
   - Save all plots to files instead (e.g., plt.savefig('filename.png'))
   - The UI will automatically display generated files

3. Analysis Summary:
   - Always generate a Jupyter notebook as the last step to summarize the analysis
   - Include all key findings, visualizations, and conclusions in the notebook
   
4. Generate a detailed summary using Markdown formatting. 
- Use bullet points, bold labels, and sections. 
- Do NOT use Markdown heading syntax (e.g., `#`, `===`, or `---`) to start lines or as separators.
- If you want to emphasize a section, use bold titles or surround with asterisks or code blocks.
   
"""
    
    if config.file_upload_enabled:
        uploaded_files = file_manager.list_session_files(session_id)
        if uploaded_files:
            file_context = file_manager.get_file_context_for_query(session_id, uploaded_files)
            enhanced_message = f"{system_instructions}{file_context}\n\nUser query: {user_message}"
            logger.info(f"Session {session_id}: Added context for {len(uploaded_files)} uploaded files")
        else:
            enhanced_message = f"{system_instructions}User query: {user_message}"
    else:
        enhanced_message = f"{system_instructions}User query: {user_message}"

    response_msg = cl.Message(content="Processing...")
    await response_msg.send()

    try:
        # Stream response with simple text streaming
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
    session_id: str
) -> None:
    """Stream response with parsed message handling."""
    full_response = ""
    message_count = 0

    async for parsed_message in biomni_wrapper.execute_query(user_message):
        if not parsed_message.strip():
            continue

        message_count += 1
        
        # Add separator between messages if we have multiple
        if message_count > 1:
            full_response += "\n\n---\n\n"
        
        full_response += parsed_message
        
        # Update with accumulated parsed content
        response_msg.content = full_response.strip()
        await response_msg.update()

    # After streaming is complete, check for generated files
    generated_files = biomni_wrapper.output_parser.get_generated_files()
    if generated_files:
        await display_generated_files(generated_files, session_id)

    logger.info(f"Session {session_id}: Query completed successfully with {message_count} messages")


async def display_generated_files(generated_files, session_id: str):
    """Display generated files using Chainlit's file display capabilities."""
    elements = []
    sent = []
        
    for file_info in generated_files:
        
        # Skip if we've already sent this file to avoid duplicates
        if file_info.path in sent:       
            continue
        sent.append(file_info.path)
        
        file_path = Path(config.session_data_path) / session_id / "outputs" / file_info.path
                
        # Check if file actually exists
        if file_path.exists():
            file_size = file_path.stat().st_size
            logger.info(f"Session {session_id}: File exists, size: {file_size} bytes")
            
            try:
                # Determine the appropriate Chainlit element type
                if file_info.file_type == "image" or file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.svg']:
                    logger.info(f"Session {session_id}: Creating image element for {file_info.path}")
                    element = cl.Image(path=str(file_path), name=file_info.path, display="inline")
                else:
                    logger.info(f"Session {session_id}: Creating file element for {file_info.path}")
                    element = cl.File(path=str(file_path), name=file_info.path, display="inline")
                
                elements.append(element)
                logger.info(f"Session {session_id}: Successfully created element for {file_info.path}")
            except Exception as e:
                logger.error(f"Session {session_id}: Error creating element for file {file_path}: {e}")
        else:
            logger.warning(f"Session {session_id}: File does not exist: {file_path}")
    
    # Send files as a separate message if any were found
    if elements:
        logger.info(f"Session {session_id}: Sending message with {len(elements)} elements")
        await cl.Message(
            content=f"📁 **Generated {len(elements)} file(s):**",
            elements=elements
        ).send()
    else:
        logger.warning(f"Session {session_id}: No elements to display")


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