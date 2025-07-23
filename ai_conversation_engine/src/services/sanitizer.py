# ai_conversation_engine/src/services/sanitizer.py

import html
import re

# Pre-compile the regex for removing control characters for better performance
CONTROL_CHAR_REGEX = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
MAX_MESSAGE_LENGTH = 4096 # Based on WhatsApp's limit

class InputSanitizer:
    @staticmethod
    def sanitize(message: str) -> str:
        """
        Cleans and sanitizes user-provided text input.
        - Escapes HTML to prevent XSS.
        - Removes ASCII control characters.
        - Truncates message to a maximum length.
        - Strips leading/trailing whitespace.
        """
        if not isinstance(message, str):
            return ""

        # 1. Truncate to a safe maximum length first
        sanitized_message = message[:MAX_MESSAGE_LENGTH]
        
        # 2. Escape HTML special characters
        sanitized_message = html.escape(sanitized_message)
        
        # 3. Remove control characters
        sanitized_message = CONTROL_CHAR_REGEX.sub('', sanitized_message)
        
        # 4. Strip whitespace
        return sanitized_message.strip()