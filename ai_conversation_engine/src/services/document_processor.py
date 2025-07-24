# ai_conversation_engine/src/services/document_processor.py

import os
import re
import logging
import asyncio
from typing import List, Generator, Dict, Optional, Union
from pathlib import Path
from bs4 import BeautifulSoup
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ChunkMetadata:
    """Metadata for document chunks."""
    chunk_index: int
    start_position: int
    end_position: int
    word_count: int
    document_type: str
    source_file: Optional[str] = None

class DocumentProcessorError(Exception):
    """Custom exception for document processing errors."""
    pass

class DocumentProcessor:
    """
    Advanced document processor with support for multiple formats and intelligent,
    asynchronous chunking.
    """
    
    SUPPORTED_TYPES = {"text", "html", "markdown", "plain"}
    
    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        """
        Initializes the document processor.
        
        Args:
            chunk_size: Maximum size of each chunk in characters.
            chunk_overlap: Number of characters to overlap between chunks.
        """
        self.chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", "50"))
        
        # Validate parameters
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
            
        # Pre-compile regex for performance
        self.sentence_endings = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s')
        self.paragraph_breaks = re.compile(r'\n\s*\n')

    async def _find_sentence_boundary(self, text: str, target_position: int, search_range: int = 100) -> int:
        """Finds the nearest sentence boundary to a target position asynchronously."""
        return await asyncio.to_thread(
            self._sync_find_sentence_boundary, text, target_position, search_range
        )

    def _sync_find_sentence_boundary(self, text: str, target_position: int, search_range: int = 100) -> int:
        """Synchronous implementation of finding a sentence boundary."""
        if target_position >= len(text):
            return len(text)
        
        start_search = max(0, target_position - search_range)
        search_text = text[start_search : target_position + search_range]
        
        # Find sentence endings and paragraph breaks in the search range
        sentence_ends = list(self.sentence_endings.finditer(search_text))
        paragraph_ends = list(self.paragraph_breaks.finditer(search_text))
        
        boundaries = [m.end() for m in sentence_ends] + [m.start() for m in paragraph_ends]
        
        if not boundaries:
            return target_position # No good split point found, use the original target

        # Find the boundary closest to our target position within the search text
        target_in_search = target_position - start_search
        closest_boundary = min(boundaries, key=lambda pos: abs(pos - target_in_search))
        
        return start_search + closest_boundary

    async def chunk_document(self, text_content: str, doc_type: str, source_file: Optional[str]) -> List[Dict]:
        """Asynchronously splits a long text document into smaller, manageable chunks."""
        if not text_content or not text_content.strip():
            return []

        chunks = []
        current_position = 0
        chunk_index = 0
        text_length = len(text_content)

        while current_position < text_length:
            end_position = min(current_position + self.chunk_size, text_length)
            
            # Adjust end position to a sentence boundary if not at the end of the text
            if end_position < text_length:
                end_position = await self._find_sentence_boundary(text_content, end_position)
            
            chunk_text = text_content[current_position:end_position].strip()
            
            if chunk_text:
                metadata = ChunkMetadata(
                    chunk_index=chunk_index,
                    start_position=current_position,
                    end_position=end_position,
                    word_count=len(chunk_text.split()),
                    document_type=doc_type,
                    source_file=source_file
                )
                chunks.append({"text": chunk_text, "metadata": metadata})
                chunk_index += 1
            
            # Calculate next position with overlap, ensuring forward progress
            next_position = current_position + self.chunk_size - self.chunk_overlap
            current_position = max(next_position, current_position + 1)
            
        return chunks

    async def extract_text_from_html(self, html_content: str) -> str:
        """Asynchronously extracts plain text from HTML content."""
        return await asyncio.to_thread(self._sync_extract_text_from_html, html_content)

    def _sync_extract_text_from_html(self, html_content: str) -> str:
        """Synchronous implementation of HTML text extraction."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Remove irrelevant tags
            for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                element.decompose()
            
            # Add spacing and line breaks for structure
            for element in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']):
                element.insert_after('\n')
            
            text = soup.get_text(separator=" ", strip=True)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except Exception as e:
            logger.error(f"HTML parsing failed: {e}")
            return "" # Return empty string on parse failure

    async def extract_text_from_markdown(self, markdown_content: str) -> str:
        """Asynchronously extracts plain text from Markdown content."""
        return await asyncio.to_thread(self._sync_extract_text_from_markdown, markdown_content)

    def _sync_extract_text_from_markdown(self, markdown_content: str) -> str:
        """Synchronous implementation of Markdown text extraction."""
        # Remove headers, lists, and blockquotes
        text = re.sub(r'^#{1,6}\s*|\s*>\s*|\s*[-\*+]\s*', '', markdown_content, flags=re.MULTILINE)
        # Remove bold, italic, and strikethrough
        text = re.sub(r'(\*\*|__|\*|_|~~)(.*?)\1', r'\2', text)
        # Remove links but keep the link text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove images
        text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
        # Remove code blocks and inline code
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove horizontal rules
        text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def process_document(self, content: str, document_type: str, source_file: Optional[str] = None) -> List[Dict]:
        """
        Asynchronously processes a document based on its type and returns a list of chunks.
        """
        if not content:
            return []
            
        doc_type = document_type.lower()
        if doc_type not in self.SUPPORTED_TYPES:
            raise DocumentProcessorError(f"Unsupported document type: {doc_type}")

        try:
            if doc_type == "html":
                processed_text = await self.extract_text_from_html(content)
            elif doc_type == "markdown":
                processed_text = await self.extract_text_from_markdown(content)
            else: # "text", "plain"
                processed_text = content.strip()
            
            if not processed_text:
                logger.warning(f"No text extracted from document", source=source_file)
                return []
            
            chunks = await self.chunk_document(processed_text, doc_type, source_file)
            logger.info(f"Processed document into {len(chunks)} chunks", source=source_file) # FIX: source_ifile -> source_file
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing document", source=source_file, error=str(e), exc_info=True)
            raise DocumentProcessorError(f"Failed to process document: {e}")