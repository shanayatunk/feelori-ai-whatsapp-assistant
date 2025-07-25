# shared/exceptions.py

from typing import Optional, Dict

class AIServiceError(Exception):
    """Base exception for all AI service-related errors."""
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict] = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

class ValidationError(AIServiceError):
    """Input validation errors."""
    pass

class InvalidInputError(AIServiceError):
    """Raised when user input fails validation."""
    pass

class ExternalServiceError(AIServiceError):
    """External service communication errors."""
    pass

class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""
    pass

class CircuitBreakerOpenError(AIServiceError):
    """Raised when a circuit breaker is open."""
    pass

class RateLimitExceededError(AIServiceError):
    """Raised when the rate limit is exceeded."""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Try again in {retry_after} seconds.")

# From whatsapp_gateway
class APIError(Exception):
    """Custom exception for API errors."""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)