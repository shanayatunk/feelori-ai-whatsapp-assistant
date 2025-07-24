# ai_conversation_engine/src/services/sanitizer.py

import html
import re
import unicodedata
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Pre-compile regex patterns for better performance
CONTROL_CHAR_REGEX = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
EXCESSIVE_WHITESPACE_REGEX = re.compile(r'\s+')
SUSPICIOUS_PATTERNS_REGEX = re.compile(r'<script[^>]*>.*?</script>|javascript:|data:|vbscript:', re.IGNORECASE | re.DOTALL)

# Constants for sanitization rules
MAX_MESSAGE_LENGTH = 4096
MIN_MESSAGE_LENGTH = 1
MAX_CONSECUTIVE_CHARS = 100  # Prevent spam with long strings of repeated characters

class InputSanitizer:
    @staticmethod
    def sanitize(message: str, strict_mode: bool = True) -> str:  # Default to True for security
        """
        Cleans and sanitizes user-provided text input with enhanced security.
        
        Args:
            message: The input message to sanitize.
            strict_mode: If True, applies additional security measures like removing script tags.
            
        Returns:
            A sanitized message string, or an empty string if input is invalid.
        """
        if not isinstance(message, str):
            logger.warning(f"Non-string input received for sanitization: {type(message)}")
            return ""

        if not message or len(message.strip()) < MIN_MESSAGE_LENGTH:
            return ""

        try:
            # 1. Normalize Unicode characters to a standard form (NFKC)
            sanitized_message = unicodedata.normalize('NFKC', message)
            
            # 2. Truncate to a safe maximum length
            sanitized_message = sanitized_message[:MAX_MESSAGE_LENGTH]
            
            # 3. Always remove suspicious patterns for security (regardless of strict_mode)
            sanitized_message = SUSPICIOUS_PATTERNS_REGEX.sub('', sanitized_message)
            
            # 4. In strict mode, apply additional sanitization
            if strict_mode:
                # Remove additional potentially dangerous patterns
                sanitized_message = re.sub(r'on\w+\s*=', '', sanitized_message, flags=re.IGNORECASE)
                sanitized_message = re.sub(r'style\s*=', '', sanitized_message, flags=re.IGNORECASE)
            
            # 5. Escape HTML special characters to prevent XSS attacks.
            sanitized_message = html.escape(sanitized_message, quote=True)
            
            # 6. Remove non-printable control characters.
            sanitized_message = CONTROL_CHAR_REGEX.sub('', sanitized_message)
            
            # 7. Normalize all whitespace (tabs, newlines, etc.) to a single space.
            sanitized_message = EXCESSIVE_WHITESPACE_REGEX.sub(' ', sanitized_message)
            
            # 8. Prevent character spam (e.g., "aaaaa...").
            sanitized_message = InputSanitizer._prevent_character_spam(sanitized_message)
            
            # 9. Strip any leading or trailing whitespace that may have been introduced.
            sanitized_message = sanitized_message.strip()
            
            # 10. Perform a final length check after all transformations.
            if len(sanitized_message) < MIN_MESSAGE_LENGTH:
                return ""
                
            return sanitized_message
            
        except Exception as e:
            # Log errors with traceback for easier debugging.
            logger.error(
                "Error during sanitization",
                error=str(e),
                exc_info=True
            )
            return ""

    @staticmethod
    def _prevent_character_spam(message: str) -> str:
        """
        Reduces long runs of identical consecutive characters to a max limit.
        
        Args:
            message: The input message string.
            
        Returns:
            The message with character spam reduced.
        """
        if not message:
            return message
            
        result = []
        prev_char = None
        consecutive_count = 0
        
        for char in message:
            if char == prev_char:
                consecutive_count += 1
            else:
                # Reset counter for a new character
                consecutive_count = 1
                prev_char = char
            
            # Append character only if it's below the consecutive limit
            if consecutive_count < MAX_CONSECUTIVE_CHARS:
                result.append(char)
                
        return ''.join(result)

    @staticmethod
    def validate_message_content(message: str) -> dict:
        """
        Validates message content and returns a dictionary with detailed results.
        
        Args:
            message: The message to validate.
            
        Returns:
            A dictionary containing validation status, errors, and warnings.
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'sanitized_length': 0,
            'original_length': len(message) if isinstance(message, str) else 0
        }
        
        if not isinstance(message, str):
            validation_result['is_valid'] = False
            validation_result['errors'].append('Input must be a string')
            return validation_result
            
        if len(message) > MAX_MESSAGE_LENGTH:
            validation_result['warnings'].append(f'Message truncated from {len(message)} to {MAX_MESSAGE_LENGTH} characters')
            
        if len(message.strip()) < MIN_MESSAGE_LENGTH:
            validation_result['is_valid'] = False
            validation_result['errors'].append('Message too short to be meaningful')
            
        sanitized = InputSanitizer.sanitize(message)
        validation_result['sanitized_length'] = len(sanitized)
        
        if SUSPICIOUS_PATTERNS_REGEX.search(message):
            validation_result['warnings'].append('Suspicious patterns (like script tags) were detected and removed')
            
        return validation_result

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitizes a string to be safely used as a filename.
        
        Removes path separators, dangerous characters, and controls length.
        
        Args:
            filename: The original filename.
            
        Returns:
            A sanitized, safe filename string.
        """
        if not isinstance(filename, str) or not filename.strip():
            return "untitled"
            
        # Remove path separators and other dangerous characters.
        dangerous_chars = r'[<>:"/\\|?*\x00-\x1f]'
        sanitized = re.sub(dangerous_chars, '_', filename)
        
        # Remove leading/trailing dots and spaces, which can cause issues on some filesystems.
        sanitized = sanitized.strip('. ')
        
        # Ensure filename length is within reasonable limits (e.g., 255 bytes).
        if len(sanitized) > 255:
            # Try to preserve the file extension
            if '.' in sanitized:
                name, ext = sanitized.rsplit('.', 1)
                ext = '.' + ext
            else:
                name, ext = sanitized, ''
            
            # Truncate the name part
            name = name[:255 - len(ext)]
            sanitized = name + ext
            
        return sanitized or "untitled"