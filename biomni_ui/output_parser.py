"""
Robust parser for Biomni model output with proper formatting and streaming support.
"""
from __future__ import annotations

import re
from typing import Generator, List, Tuple
from dataclasses import dataclass
from enum import Enum


class BlockType(Enum):
    """Types of content blocks in the output."""
    TEXT = "text"
    CODE = "code"
    OBSERVATION = "observation"
    SOLUTION = "solution"


@dataclass
class ContentBlock:
    """Represents a parsed content block."""
    type: BlockType
    content: str
    raw_content: str = ""


class BiomniOutputParser:
    """Parser for Biomni model output with streaming support."""
    
    AI_MESSAGE_DELIMITER = "================================== Ai Message =================================="
    HUMAN_MESSAGE_DELIMITER = "================================ Human Message ================================="
    
    def __init__(self):
        self.buffer = ""
        self.parsed_messages: List[str] = []
        
    def add_chunk(self, chunk: str) -> Generator[str, None, None]:
        """
        Add a chunk of streaming text and yield any complete messages.
        
        Args:
            chunk: New text chunk from streaming
            
        Yields:
            Complete formatted messages ready for display
        """
        self.buffer += chunk
        
        # Check for complete AI messages
        while self.AI_MESSAGE_DELIMITER in self.buffer:
            # Find the delimiter
            delimiter_pos = self.buffer.find(self.AI_MESSAGE_DELIMITER)
            
            # Extract everything before the delimiter (discard if it's the first message)
            before_delimiter = self.buffer[:delimiter_pos].strip()
            
            # Find the next delimiter or end of buffer
            remaining = self.buffer[delimiter_pos + len(self.AI_MESSAGE_DELIMITER):]
            next_delimiter_pos = remaining.find(self.AI_MESSAGE_DELIMITER)
            
            if next_delimiter_pos != -1:
                # We have a complete message
                message_content = remaining[:next_delimiter_pos].strip()
                self.buffer = remaining[next_delimiter_pos:]
                
                # Filter out Human Message sections from the content
                filtered_content = self._filter_human_messages(message_content)
                
                if filtered_content:
                    formatted_message = self._format_message(filtered_content)
                    self.parsed_messages.append(formatted_message)
                    yield formatted_message
            else:
                # No complete message yet, keep the current message in buffer
                self.buffer = self.AI_MESSAGE_DELIMITER + remaining
                break
    
    def finalize(self) -> str | None:
        """
        Process any remaining content in the buffer.
        
        Returns:
            Final formatted message if any content remains
        """
        if self.AI_MESSAGE_DELIMITER in self.buffer:
            # Extract the last message
            delimiter_pos = self.buffer.find(self.AI_MESSAGE_DELIMITER)
            remaining = self.buffer[delimiter_pos + len(self.AI_MESSAGE_DELIMITER):].strip()
            
            if remaining:
                # Filter out Human Message sections from the content
                filtered_content = self._filter_human_messages(remaining)
                
                if filtered_content:
                    formatted_message = self._format_message(filtered_content)
                    self.parsed_messages.append(formatted_message)
                    return formatted_message
        
        return None
    
    def _filter_human_messages(self, content: str) -> str:
        """
        Filter out Human Message sections from content.
        
        Args:
            content: Raw content that may contain Human Message sections
            
        Returns:
            Content with Human Message sections removed
        """
        # Split on Human Message delimiter and keep only parts that don't start with Human Message
        parts = content.split(self.HUMAN_MESSAGE_DELIMITER)
        
        # The first part is always before any Human Message, so keep it
        filtered_parts = [parts[0]]
        
        # For subsequent parts, we need to check if they contain AI Message delimiters
        # If they do, we keep the part after the next AI Message delimiter
        for i in range(1, len(parts)):
            part = parts[i]
            # Look for the next AI Message delimiter in this part
            ai_delimiter_pos = part.find(self.AI_MESSAGE_DELIMITER)
            if ai_delimiter_pos != -1:
                # Keep everything after the AI Message delimiter
                filtered_parts.append(part[ai_delimiter_pos + len(self.AI_MESSAGE_DELIMITER):])
        
        return "".join(filtered_parts).strip()
    
    def _format_message(self, content: str) -> str:
        """
        Format a single AI message by processing XML tags and content.
        
        Args:
            content: Raw message content
            
        Returns:
            Formatted message string
        """
        blocks = self._parse_content_blocks(content)
        formatted_blocks = []
        
        for block in blocks:
            if block.type == BlockType.TEXT:
                formatted_blocks.append(block.content)
            elif block.type == BlockType.CODE:
                formatted_blocks.append(self._format_code_block(block.content))
            elif block.type == BlockType.OBSERVATION:
                formatted_blocks.append(self._format_observation_block(block.content))
            elif block.type == BlockType.SOLUTION:
                formatted_blocks.append(self._format_solution_block(block.content))
        
        return "\n\n".join(formatted_blocks).strip()
    
    def _parse_content_blocks(self, content: str) -> List[ContentBlock]:
        """
        Parse content into blocks based on XML tags.
        
        Args:
            content: Raw content to parse
            
        Returns:
            List of content blocks
        """
        blocks = []
        current_pos = 0
        
        # Pattern to match XML tags
        xml_pattern = r'<(execute|observation|solution)>(.*?)</\1>'
        
        for match in re.finditer(xml_pattern, content, re.DOTALL):
            # Add text before the XML tag as a text block
            before_tag = content[current_pos:match.start()].strip()
            if before_tag:
                blocks.append(ContentBlock(
                    type=BlockType.TEXT,
                    content=before_tag,
                    raw_content=before_tag
                ))
            
            # Add the XML content as appropriate block type
            tag_name = match.group(1)
            tag_content = match.group(2).strip()
            
            if tag_name == "execute":
                block_type = BlockType.CODE
            elif tag_name == "observation":
                block_type = BlockType.OBSERVATION
            elif tag_name == "solution":
                block_type = BlockType.SOLUTION
            else:
                block_type = BlockType.TEXT
            
            blocks.append(ContentBlock(
                type=block_type,
                content=tag_content,
                raw_content=match.group(0)
            ))
            
            current_pos = match.end()
        
        # Add any remaining text after the last XML tag
        remaining_text = content[current_pos:].strip()
        if remaining_text:
            blocks.append(ContentBlock(
                type=BlockType.TEXT,
                content=remaining_text,
                raw_content=remaining_text
            ))
        
        return blocks
    
    def _format_code_block(self, content: str) -> str:
        """Format code content with proper markdown."""
        # Remove common Python comment prefixes and clean up
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove common prefixes but preserve the actual code
            line = line.strip()
            if line.startswith('# '):
                cleaned_lines.append(line)
            elif line and not line.startswith('#'):
                cleaned_lines.append(line)
            elif line.startswith('#') and ('=' in line or line.startswith('# ===')):
                # Keep section headers
                cleaned_lines.append(line)
        
        code_content = '\n'.join(cleaned_lines).strip()
        
        return f"**🔧 Code Execution:**\n\n```python\n{code_content}\n```"
    
    def _format_observation_block(self, content: str) -> str:
        """Format observation content."""
        return f"**📊 Observation:**\n\n{content}"
    
    def _format_solution_block(self, content: str) -> str:
        """Format solution content."""
        return f"**✅ Solution:**\n\n{content}"


class StreamingBiomniParser:
    """
    Simplified streaming parser that processes output in real-time.
    """
    
    def __init__(self):
        self.parser = BiomniOutputParser()
        self.has_started = False
    
    def process_chunk(self, chunk: str) -> Generator[str, None, None]:
        """
        Process a streaming chunk and yield formatted messages.
        
        Args:
            chunk: Raw text chunk from streaming
            
        Yields:
            Formatted message chunks ready for display
        """
        # Check if we've encountered the first AI message
        if not self.has_started:
            if BiomniOutputParser.AI_MESSAGE_DELIMITER in chunk:
                self.has_started = True
            else:
                # Skip content before first AI message
                return
        
        # Process the chunk through the parser
        yield from self.parser.add_chunk(chunk)
    
    def finalize(self) -> str | None:
        """Finalize parsing and return any remaining content."""
        return self.parser.finalize()


def parse_biomni_output(raw_output: str) -> List[str]:
    """
    Parse complete Biomni output into formatted messages.
    
    Args:
        raw_output: Complete raw output from Biomni
        
    Returns:
        List of formatted message strings
    """
    parser = BiomniOutputParser()
    
    # Process all content at once
    messages = list(parser.add_chunk(raw_output))
    
    # Get any final message
    final_message = parser.finalize()
    if final_message:
        messages.append(final_message)
    
    return messages


def clean_legacy_prefixes(text: str) -> str:
    """
    Clean legacy prefixes from text for backward compatibility.
    
    Args:
        text: Text with potential legacy prefixes
        
    Returns:
        Cleaned text
    """
    # Remove common prefixes for cleaner output
    if text.startswith('[BIOMNI]'):
        return text[8:].strip()
    elif text.startswith('[LOG]'):
        return text[5:].strip()
    elif text.startswith('[RESULT]'):
        return text[8:].strip()
    elif text.startswith('[ERROR]'):
        return f"ERROR: {text[7:].strip()}"
    return text.strip()