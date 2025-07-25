import asyncio
import logging
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
        
        # Add welcome message to conversation history
        session_manager.add_conversation_entry(
            session_id, 
            "system", 
            "Session started",
            {"session_id": session_id}
        )
        
        # Send welcome message
        welcome_msg = f"""Welcome to Biomni UI.

Session ID: {session_id}

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
    """Handle incoming messages."""
    session_id = cl.user_session.get("session_id")
    biomni_wrapper = cl.user_session.get("biomni_wrapper")
    
    if not session_id or not biomni_wrapper:
        await cl.Message(content="Session not found. Please refresh the page.").send()
        return
    
    user_message = message.content
    logger.info(f"Session {session_id}: User message received")
    
    # Add user message to conversation history
    session_manager.add_conversation_entry(session_id, "user", user_message)
    
    # Create a message for the response
    response_msg = cl.Message(content="")
    await response_msg.send()
    
    try:
        # Show processing indicator
        response_msg.content = "Processing..."
        await response_msg.update()
        
        # Execute query asynchronously and stream the response
        full_response = ""
        async for output_chunk in biomni_wrapper.execute_query(user_message):
            if output_chunk.strip():
                full_response += output_chunk + "\n"
                
                # Update the message with accumulated response
                response_msg.content = full_response
                await response_msg.update()
                
                # Small delay to make streaming visible
                await asyncio.sleep(0.1)
        
        # Add final response to conversation history
        session_manager.add_conversation_entry(
            session_id, 
            "assistant", 
            full_response,
            {"execution_completed": True}
        )
        
        # Check for generated files
        generated_files = biomni_wrapper.get_session_files()
        if generated_files:
            file_list = "\n".join([f"- {f.name}" for f in generated_files])
            files_msg = f"\n\nGenerated files:\n{file_list}"
            response_msg.content += files_msg
            await response_msg.update()
        
        logger.info(f"Session {session_id}: Query completed successfully")
        
    except Exception as e:
        error_msg = f"Error occurred: {str(e)}"
        response_msg.content = error_msg
        await response_msg.update()
        
        # Add error to conversation history
        session_manager.add_conversation_entry(
            session_id, 
            "system", 
            f"Error: {str(e)}",
            {"error": True}
        )
        
        logger.error(f"Session {session_id}: Error processing message: {e}")


@cl.on_chat_end
async def end():
    """Handle chat session end."""
    session_id = cl.user_session.get("session_id")
    
    if session_id:
        # Add session end to conversation history
        session_manager.add_conversation_entry(
            session_id, 
            "system", 
            "Session ended"
        )
        
        # Close the session
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