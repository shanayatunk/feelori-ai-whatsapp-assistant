# ai_conversation_engine/src/services/circuit_breaker.py

import time
import asyncio
import logging
from enum import Enum
from typing import Optional, Callable, Any, Dict
from functools import wraps
from dataclasses import dataclass
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# Metrics for monitoring circuit breaker behavior
CIRCUIT_BREAKER_CALLS = Counter('circuit_breaker_calls_total', 'Total circuit breaker calls', ['name', 'state', 'result'])
CIRCUIT_BREAKER_STATE_CHANGES = Counter('circuit_breaker_state_changes_total', 'Circuit breaker state changes', ['name', 'from_state', 'to_state'])
CIRCUIT_BREAKER_EXECUTION_TIME = Histogram('circuit_breaker_execution_seconds', 'Circuit breaker execution time', ['name'])
CIRCUIT_BREAKER_STATE_GAUGE = Gauge('circuit_breaker_state', 'Current circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)', ['name'])

class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 1
    half_open_success_threshold: int = 1
    expected_exception: Optional[type] = None
    call_timeout: Optional[float] = None
    name: str = "default"

class CircuitBreakerOpenError(Exception):
    """Custom exception raised when the circuit is open."""
    def __init__(self, message="Circuit is open and cannot execute calls", circuit_name="unknown"):
        self.message = message
        self.circuit_name = circuit_name
        super().__init__(self.message)

class CircuitBreakerTimeoutError(Exception):
    """Custom exception raised when a call times out."""
    def __init__(self, message="Circuit breaker call timed out", timeout_duration=None):
        self.message = message
        self.timeout_duration = timeout_duration
        super().__init__(self.message)

class CircuitBreakerStats:
    """Statistics tracking for circuit breaker."""
    def __init__(self):
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.timeout_calls = 0
        self.rejected_calls = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.state_change_history = []
    
    def record_success(self):
        self.total_calls += 1
        self.successful_calls += 1
        self.last_success_time = time.time()
    
    def record_failure(self):
        self.total_calls += 1
        self.failed_calls += 1
        self.last_failure_time = time.time()
    
    def record_timeout(self):
        self.total_calls += 1
        self.timeout_calls += 1
        self.failed_calls += 1
        self.last_failure_time = time.time()
    
    def record_rejection(self):
        self.rejected_calls += 1
    
    def record_state_change(self, from_state: CircuitBreakerState, to_state: CircuitBreakerState):
        self.state_change_history.append({
            'from': from_state.value,
            'to': to_state.value,
            'timestamp': time.time()
        })
        # Keep only last 100 state changes
        if len(self.state_change_history) > 100:
            self.state_change_history = self.state_change_history[-100:]

class CircuitBreaker:
    """
    A comprehensive circuit breaker implementation to prevent repeated calls to a failing service.
    
    Features:
    - Configurable failure thresholds and recovery timeouts
    - Half-open state for gradual recovery testing
    - Call timeouts to prevent hanging
    - Comprehensive metrics and statistics
    - Thread-safe async implementation
    - Custom exception handling
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = 0
        self.last_state_change_time = time.time()
        self._lock = asyncio.Lock()
        self.stats = CircuitBreakerStats()
        self._state_change_callbacks = []
        
        # Initialize metrics
        CIRCUIT_BREAKER_STATE_GAUGE.labels(name=self.config.name).set(0)  # CLOSED = 0
        
        logger.info(f"Circuit breaker '{self.config.name}' initialized", 
                   extra={
                       'circuit_name': self.config.name,
                       'failure_threshold': self.config.failure_threshold,
                       'recovery_timeout': self.config.recovery_timeout
                   })

    def add_state_change_callback(self, callback: Callable[[CircuitBreakerState, CircuitBreakerState], None]):
        """Add a callback function to be called when state changes."""
        self._state_change_callbacks.append(callback)

    async def _set_state(self, new_state: CircuitBreakerState):
        """Change the circuit breaker state and trigger callbacks."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.last_state_change_time = time.time()
            
            # Update metrics
            CIRCUIT_BREAKER_STATE_CHANGES.labels(
                name=self.config.name, 
                from_state=old_state.value, 
                to_state=new_state.value
            ).inc()
            
            # Set gauge value (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
            state_values = {
                CircuitBreakerState.CLOSED: 0,
                CircuitBreakerState.HALF_OPEN: 1,
                CircuitBreakerState.OPEN: 2
            }
            CIRCUIT_BREAKER_STATE_GAUGE.labels(name=self.config.name).set(state_values[new_state])
            
            # Record in stats
            self.stats.record_state_change(old_state, new_state)
            
            logger.info(f"Circuit breaker '{self.config.name}' state changed: {old_state.value} -> {new_state.value}")
            
            # Trigger callbacks
            for callback in self._state_change_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    logger.error(f"Error in state change callback: {e}")

    async def _can_execute(self) -> bool:
        """Check if a call can be executed based on current state."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (time.monotonic() - self.last_failure_time) > self.config.recovery_timeout:
                await self._set_state(CircuitBreakerState.HALF_OPEN)
                self.success_count = 0
                self.half_open_calls = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Allow limited calls in half-open state
            return self.half_open_calls < self.config.half_open_max_calls
        return False

    async def on_success(self):
        """Handle successful call execution."""
        self.stats.record_success()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.half_open_success_threshold:
                await self._set_state(CircuitBreakerState.CLOSED)
                self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    async def on_failure(self, exception: Exception = None):
        """Handle failed call execution."""
        if isinstance(exception, CircuitBreakerTimeoutError):
            self.stats.record_timeout()
        else:
            self.stats.record_failure()
        
        self.failure_count += 1
        
        # Open circuit if failure threshold reached or if in half-open state
        if (self.state == CircuitBreakerState.HALF_OPEN or 
            self.failure_count >= self.config.failure_threshold):
            await self._set_state(CircuitBreakerState.OPEN)
            self.last_failure_time = time.monotonic()

    async def call(self, func, *args, **kwargs):
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: The async function to execute
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            The result of the function call
            
        Raises:
            CircuitBreakerOpenError: When the circuit is open
            CircuitBreakerTimeoutError: When the call times out
            Exception: Any exception raised by the function
        """
        start_time = time.time()
        
        async with self._lock:
            # Check if we can execute the call
            if not await self._can_execute():
                self.stats.record_rejection()
                CIRCUIT_BREAKER_CALLS.labels(
                    name=self.config.name, 
                    state=self.state.value, 
                    result='rejected'
                ).inc()
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.config.name}' is {self.state.value}",
                    self.config.name
                )
            
            # Track half-open calls
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_calls += 1
            
            try:
                # Execute the function with optional timeout
                if self.config.call_timeout:
                    try:
                        result = await asyncio.wait_for(
                            func(*args, **kwargs), 
                            timeout=self.config.call_timeout
                        )
                    except asyncio.TimeoutError:
                        timeout_error = CircuitBreakerTimeoutError(
                            f"Call timed out after {self.config.call_timeout} seconds",
                            self.config.call_timeout
                        )
                        await self.on_failure(timeout_error)
                        CIRCUIT_BREAKER_CALLS.labels(
                            name=self.config.name, 
                            state=self.state.value, 
                            result='timeout'
                        ).inc()
                        raise timeout_error
                else:
                    result = await func(*args, **kwargs)
                
                # Handle success
                await self.on_success()
                CIRCUIT_BREAKER_CALLS.labels(
                    name=self.config.name, 
                    state=self.state.value, 
                    result='success'
                ).inc()
                
                # Record execution time
                execution_time = time.time() - start_time
                CIRCUIT_BREAKER_EXECUTION_TIME.labels(name=self.config.name).observe(execution_time)
                
                return result
                
            except Exception as e:
                # Check if this is an expected exception that shouldn't trigger circuit opening
                if (self.config.expected_exception and 
                    isinstance(e, self.config.expected_exception)):
                    # Don't count expected exceptions as failures
                    CIRCUIT_BREAKER_CALLS.labels(
                        name=self.config.name, 
                        state=self.state.value, 
                        result='expected_error'
                    ).inc()
                    raise e
                
                # Handle failure
                await self.on_failure(e)
                CIRCUIT_BREAKER_CALLS.labels(
                    name=self.config.name, 
                    state=self.state.value, 
                    result='failure'
                ).inc()
                
                # Record execution time even for failures
                execution_time = time.time() - start_time
                CIRCUIT_BREAKER_EXECUTION_TIME.labels(name=self.config.name).observe(execution_time)
                
                # Re-raise the original exception
                raise e

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the circuit breaker."""
        return {
            'name': self.config.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time,
            'last_state_change_time': self.last_state_change_time,
            'stats': {
                'total_calls': self.stats.total_calls,
                'successful_calls': self.stats.successful_calls,
                'failed_calls': self.stats.failed_calls,
                'timeout_calls': self.stats.timeout_calls,
                'rejected_calls': self.stats.rejected_calls,
                'last_failure_time': self.stats.last_failure_time,
                'last_success_time': self.stats.last_success_time,
                'state_changes': len(self.stats.state_change_history)
            },
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'recovery_timeout': self.config.recovery_timeout,
                'half_open_max_calls': self.config.half_open_max_calls,
                'call_timeout': self.config.call_timeout
            }
        }

    async def reset(self):
        """Reset the circuit breaker to its initial state."""
        async with self._lock:
            await self._set_state(CircuitBreakerState.CLOSED)
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
            self.last_failure_time = 0
            self.stats = CircuitBreakerStats()
            logger.info(f"Circuit breaker '{self.config.name}' has been reset")

    async def force_open(self):
        """Force the circuit breaker to open state."""
        async with self._lock:
            await self._set_state(CircuitBreakerState.OPEN)
            self.last_failure_time = time.monotonic()
            logger.warning(f"Circuit breaker '{self.config.name}' has been forced open")

    async def force_close(self):
        """Force the circuit breaker to closed state."""
        async with self._lock:
            await self._set_state(CircuitBreakerState.CLOSED)
            self.failure_count = 0
            logger.info(f"Circuit breaker '{self.config.name}' has been forced closed")

def circuit_breaker(config: CircuitBreakerConfig):
    """
    Decorator to apply circuit breaker protection to a function.
    
    Usage:
        @circuit_breaker(CircuitBreakerConfig(name="my_service", failure_threshold=3))
        async def my_service_call():
            # Your service call here
            pass
    """
    cb = CircuitBreaker(config)
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await cb.call(func, *args, **kwargs)
        
        # Attach circuit breaker instance to the wrapped function
        wrapper.circuit_breaker = cb
        return wrapper
    
    return decorator

# Example usage and factory functions
class CircuitBreakerFactory:
    """Factory for creating pre-configured circuit breakers."""
    
    @staticmethod
    def create_http_client_breaker(name: str) -> CircuitBreaker:
        """Create a circuit breaker optimized for HTTP client calls."""
        config = CircuitBreakerConfig(
            name=name,
            failure_threshold=5,
            recovery_timeout=30,
            half_open_max_calls=2,
            call_timeout=10.0
        )
        return CircuitBreaker(config)
    
    @staticmethod
    def create_database_breaker(name: str) -> CircuitBreaker:
        """Create a circuit breaker optimized for database calls."""
        config = CircuitBreakerConfig(
            name=name,
            failure_threshold=3,
            recovery_timeout=60,
            half_open_max_calls=1,
            call_timeout=5.0
        )
        return CircuitBreaker(config)
    
    @staticmethod
    def create_external_api_breaker(name: str) -> CircuitBreaker:
        """Create a circuit breaker optimized for external API calls."""
        config = CircuitBreakerConfig(
            name=name,
            failure_threshold=10,
            recovery_timeout=120,
            half_open_max_calls=3,
            call_timeout=20.0
        )
        return CircuitBreaker(config)