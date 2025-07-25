# ai_conversation_engine/src/exceptions.py

class AIServiceError(Exception):
    """Base exception for all AI service-related errors."""
    pass

class InvalidInputError(AIServiceError):
    """Raised when user input fails validation."""
    pass

class CircuitBreakerOpenError(AIServiceError):
    """Raised when a circuit breaker is open."""
    pass

class RateLimitExceededError(AIServiceError):
    """Raised when the rate limit is exceeded."""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Try again in {retry_after} seconds.")