# ai_conversation_engine/src/services/document_processor.py

import os
from typing import List, Generator
from bs4 import BeautifulSoup

class DocumentProcessor:
    def __init__(self):
        self.chunk_size = int(os.getenv("CHUNK_SIZE", 500))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", 50))

    def chunk_document(self, text_content: str) -> List[str]:
        """
        Splits a long text document into smaller, manageable chunks using a generator.

        Args:
            text_content: The input text to chunk.

        Returns:
            List of text chunks.
        """
        if not text_content:
            return []

        def chunk_generator() -> Generator[str, None, None]:
            current_position = 0
            text_length = len(text_content)
            while current_position < text_length:
                end_position = min(current_position + self.chunk_size, text_length)
                yield text_content[current_position:end_position]
                current_position += (self.chunk_size - self.chunk_overlap)
                if current_position >= text_length - self.chunk_overlap and end_position == text_length:
                    break

        return list(chunk_generator())

    def extract_text_from_html(self, html_content: str) -> str:
        """
        Extracts plain text from HTML content.

        Args:
            html_content: The HTML content to process.

        Returns:
            str: Extracted plain text.
        """
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator=" ", strip=True)

    def process_document(self, content: str, document_type: str) -> List[str]:
        """
        Processes a document based on its type and returns a list of text chunks.

        Args:
            content: The document content.
            document_type: The type of document ('html' or 'text').

        Returns:
            List of text chunks.
        """
        processed_text = content
        if document_type == "html":
            processed_text = self.extract_text_from_html(content)
        
        return self.chunk_document(processed_text)