# ai_conversation_engine/src/services/circuit_breaker.py

import time
import logging
import asyncio
from enum import Enum
from functools import wraps
from src.exceptions import CircuitBreakerOpenError  # ✅ Added import

logger = logging.getLogger(__name__)

class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerError(Exception):
    def __init__(self, message="Circuit is open"):
        self.message = message
        super().__init__(self.message)

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60, half_open_max_calls=1):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.failure_count = 0
        self.success_count = 0  # Track successes in half-open state
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = 0
        self._lock = asyncio.Lock()

    async def _set_state(self, new_state: CircuitBreakerState):
        if self.state != new_state:
            logger.info(f"Circuit Breaker changing state from {self.state.value} to {new_state.value}")
            self.state = new_state

    async def _before_call(self):
        if self.state == CircuitBreakerState.OPEN:
            if (time.monotonic() - self.last_failure_time) > self.recovery_timeout:
                await self._set_state(CircuitBreakerState.HALF_OPEN)
                self.success_count = 0
            else:
                raise CircuitBreakerError()
    
    async def on_success(self):
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                await self._set_state(CircuitBreakerState.CLOSED)
                self.failure_count = 0
        else:
            self.failure_count = 0

    async def on_failure(self):
        self.failure_count += 1
        if self.state == CircuitBreakerState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            await self._set_state(CircuitBreakerState.OPEN)
            self.last_failure_time = time.monotonic()

    async def call(self, func, *args, **kwargs):
        """
        Executes a function with circuit breaker protection.

        Args:
            func: The async function to execute.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            The result of the function execution.

        Raises:
            CircuitBreakerError: If the circuit is open.
            Exception: Any exception raised by the function.
        """
        async with self._lock:
            await self._before_call()

        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                await self.on_success()
            return result
        except Exception:
            async with self._lock:
                await self.on_failure()
            raise  # ✅ Preserve traceback