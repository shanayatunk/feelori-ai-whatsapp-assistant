# ai_conversation_engine/src/services/circuit_breaker.py

import time
import asyncio
import logging
from enum import Enum
from typing import Optional, Callable, Any, Dict, List
from functools import wraps
from dataclasses import dataclass, field
from collections import deque
from prometheus_client import Counter, Histogram, Gauge
import threading

# Import the centralized exception
from src.exceptions import CircuitBreakerError

logger = logging.getLogger(__name__)

# Metrics for monitoring circuit breaker behavior
CIRCUIT_BREAKER_CALLS = Counter(
    'circuit_breaker_calls_total', 
    'Total circuit breaker calls', 
    ['name', 'state', 'result']
)
CIRCUIT_BREAKER_STATE_CHANGES = Counter(
    'circuit_breaker_state_changes_total', 
    'Circuit breaker state changes', 
    ['name', 'from_state', 'to_state']
)
CIRCUIT_BREAKER_EXECUTION_TIME = Histogram(
    'circuit_breaker_execution_seconds', 
    'Circuit breaker execution time', 
    ['name']
)
CIRCUIT_BREAKER_STATE_GAUGE = Gauge(
    'circuit_breaker_state', 
    'Current circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)', 
    ['name']
)
CIRCUIT_BREAKER_FAILURE_RATE = Gauge(
    'circuit_breaker_failure_rate', 
    'Current failure rate', 
    ['name']
)

class CircuitBreakerState(Enum):
    """Circuit breaker states with integer values for easier comparison."""
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior with sensible defaults."""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 1
    half_open_success_threshold: int = 1
    expected_exception: Optional[type] = None
    call_timeout: Optional[float] = None
    name: str = "default"
    # Memory management settings
    max_state_history_size: int = 50
    state_history_ttl: int = 3600  # 1 hour in seconds
    
    def __post_init__(self):
        """Validate configuration values."""
        if self.failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if self.recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")
        if self.half_open_max_calls <= 0:
            raise ValueError("half_open_max_calls must be positive")
        if self.half_open_success_threshold <= 0:
            raise ValueError("half_open_success_threshold must be positive")

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

@dataclass
class StateChangeEvent:
    """Represents a state change event with timestamp."""
    from_state: CircuitBreakerState
    to_state: CircuitBreakerState
    timestamp: float
    
    def is_expired(self, ttl: int) -> bool:
        """Check if this event has expired based on TTL."""
        return (time.time() - self.timestamp) > ttl

class CircuitBreakerStats:
    """Thread-safe statistics tracking for circuit breaker with memory bounds."""
    
    def __init__(self, max_history_size: int = 50, history_ttl: int = 3600):
        self._lock = threading.Lock()
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.timeout_calls = 0
        self.rejected_calls = 0
        self.last_failure_time = None
        self.last_success_time = None
        
        # Use deque for O(1) operations and automatic size limiting
        self._state_change_history: deque = deque(maxlen=max_history_size)
        self._max_history_size = max_history_size
        self._history_ttl = history_ttl
    
    def record_success(self):
        """Record a successful call."""
        with self._lock:
            self.total_calls += 1
            self.successful_calls += 1
            self.last_success_time = time.time()
    
    def record_failure(self):
        """Record a failed call."""
        with self._lock:
            self.total_calls += 1
            self.failed_calls += 1
            self.last_failure_time = time.time()
    
    def record_timeout(self):
        """Record a timeout call."""
        with self._lock:
            self.total_calls += 1
            self.timeout_calls += 1
            self.failed_calls += 1
            self.last_failure_time = time.time()
    
    def record_rejection(self):
        """Record a rejected call."""
        with self._lock:
            self.rejected_calls += 1
    
    def record_state_change(self, from_state: CircuitBreakerState, to_state: CircuitBreakerState):
        """Record a state change event with automatic cleanup."""
        with self._lock:
            event = StateChangeEvent(from_state, to_state, time.time())
            self._state_change_history.append(event)
            # Cleanup expired events
            self._cleanup_expired_events()
    
    def _cleanup_expired_events(self):
        """Remove expired events from history (called with lock held)."""
        while (self._state_change_history and 
               self._state_change_history[0].is_expired(self._history_ttl)):
            self._state_change_history.popleft()
    
    def get_failure_rate(self) -> float:
        """Calculate the current failure rate."""
        with self._lock:
            if self.total_calls == 0:
                return 0.0
            return self.failed_calls / self.total_calls
    
    def get_state_history(self) -> List[Dict[str, Any]]:
        """Get the state change history as a list of dictionaries."""
        with self._lock:
            self._cleanup_expired_events()
            return [
                {
                    'from': event.from_state.name,
                    'to': event.to_state.name,
                    'timestamp': event.timestamp
                }
                for event in self._state_change_history
            ]

class CircuitBreaker:
    """
    A comprehensive, thread-safe circuit breaker implementation.
    
    Improvements over original:
    - Atomic state transitions with proper locking
    - Memory-bounded state history with TTL
    - Better error handling and validation
    - Comprehensive metrics and monitoring
    - Proper resource cleanup
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        
        # Atomic counters and state
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._state = CircuitBreakerState.CLOSED
        self._last_failure_time = 0.0
        self._last_state_change_time = time.time()
        
        # Async lock for state changes
        self._lock = asyncio.Lock()
        
        # Statistics with memory bounds
        self.stats = CircuitBreakerStats(
            max_history_size=config.max_state_history_size,
            history_ttl=config.state_history_ttl
        )
        
        # State change callbacks
        self._state_change_callbacks: List[Callable] = []
        
        # Initialize metrics
        CIRCUIT_BREAKER_STATE_GAUGE.labels(name=self.config.name).set(self._state.value)
        CIRCUIT_BREAKER_FAILURE_RATE.labels(name=self.config.name).set(0.0)
        
        logger.info(
            f"Circuit breaker '{self.config.name}' initialized",
            extra={
                'circuit_name': self.config.name,
                'failure_threshold': self.config.failure_threshold,
                'recovery_timeout': self.config.recovery_timeout,
                'call_timeout': self.config.call_timeout
            }
        )

    @property
    def state(self) -> CircuitBreakerState:
        """Get current state (thread-safe property)."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count (thread-safe property)."""
        return self._failure_count

    def add_state_change_callback(self, callback: Callable[[CircuitBreakerState, CircuitBreakerState], None]):
        """Add a callback function to be called when state changes."""
        self._state_change_callbacks.append(callback)

    async def _atomic_state_change(self, new_state: CircuitBreakerState):
        """Atomically change state and update all related metrics/stats."""
        # This method should only be called with _lock held
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self._last_state_change_time = time.time()
            
            # Update all metrics atomically
            CIRCUIT_BREAKER_STATE_CHANGES.labels(
                name=self.config.name,
                from_state=old_state.name,
                to_state=new_state.name
            ).inc()
            
            CIRCUIT_BREAKER_STATE_GAUGE.labels(name=self.config.name).set(new_state.value)
            
            # Record in stats
            self.stats.record_state_change(old_state, new_state)
            
            logger.info(
                f"Circuit breaker '{self.config.name}' state changed: {old_state.name} -> {new_state.name}",
                extra={
                    'circuit_name': self.config.name,
                    'old_state': old_state.name,
                    'new_state': new_state.name,
                    'failure_count': self._failure_count
                }
            )
            
            # Trigger callbacks (non-blocking)
            for callback in self._state_change_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        # Schedule async callbacks without awaiting
                        asyncio.create_task(callback(old_state, new_state))
                    else:
                        callback(old_state, new_state)
                except Exception as e:
                    logger.error(
                        f"Error in state change callback: {e}",
                        extra={'circuit_name': self.config.name},
                        exc_info=True
                    )

    async def _can_execute(self) -> bool:
        """
        Check if a call can be executed based on current state.
        Must be called with lock held.
        """
        current_time = time.monotonic()
        
        if self._state == CircuitBreakerState.CLOSED:
            return True
        elif self._state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (current_time - self._last_failure_time) >= self.config.recovery_timeout:
                await self._atomic_state_change(CircuitBreakerState.HALF_OPEN)
                self._success_count = 0
                self._half_open_calls = 0
                return True
            return False
        elif self._state == CircuitBreakerState.HALF_OPEN:
            # Allow limited calls in half-open state
            return self._half_open_calls < self.config.half_open_max_calls
        
        return False

    async def _handle_success(self):
        """Handle successful call execution. Must be called with lock held."""
        self.stats.record_success()
        
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.half_open_success_threshold:
                await self._atomic_state_change(CircuitBreakerState.CLOSED)
                self._failure_count = 0
        elif self._state == CircuitBreakerState.CLOSED:
            # Reset failure count on success in closed state
            self._failure_count = max(0, self._failure_count - 1)
        
        # Update failure rate metric
        CIRCUIT_BREAKER_FAILURE_RATE.labels(name=self.config.name).set(
            self.stats.get_failure_rate()
        )

    async def _handle_failure(self, exception: Exception = None):
        """Handle failed call execution. Must be called with lock held."""
        if isinstance(exception, CircuitBreakerTimeoutError):
            self.stats.record_timeout()
        else:
            self.stats.record_failure()
        
        self._failure_count += 1
        
        # Check if we should open the circuit
        should_open = (
            self._state == CircuitBreakerState.HALF_OPEN or
            self._failure_count >= self.config.failure_threshold
        )
        
        if should_open:
            await self._atomic_state_change(CircuitBreakerState.OPEN)
            self._last_failure_time = time.monotonic()
        
        # Update failure rate metric
        CIRCUIT_BREAKER_FAILURE_RATE.labels(name=self.config.name).set(
            self.stats.get_failure_rate()
        )

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
        
        # Atomic check and execution preparation
        async with self._lock:
            if not await self._can_execute():
                self.stats.record_rejection()
                CIRCUIT_BREAKER_CALLS.labels(
                    name=self.config.name,
                    state=self._state.name,
                    result='rejected'
                ).inc()
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.config.name}' is {self._state.name}",
                    self.config.name
                )
            
            # Track half-open calls
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_calls += 1
            
            # Capture current state for metrics
            current_state = self._state.name

        # Execute the function outside the lock to prevent blocking other operations
        try:
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
                    
                    # Handle timeout failure atomically
                    async with self._lock:
                        await self._handle_failure(timeout_error)
                    
                    CIRCUIT_BREAKER_CALLS.labels(
                        name=self.config.name,
                        state=current_state,
                        result='timeout'
                    ).inc()
                    raise timeout_error
            else:
                result = await func(*args, **kwargs)
            
            # Handle success atomically
            async with self._lock:
                await self._handle_success()
            
            CIRCUIT_BREAKER_CALLS.labels(
                name=self.config.name,
                state=current_state,
                result='success'
            ).inc()
            
            return result
            
        except Exception as e:
            # Check if this is an expected exception
            if (self.config.expected_exception and 
                isinstance(e, self.config.expected_exception)):
                CIRCUIT_BREAKER_CALLS.labels(
                    name=self.config.name,
                    state=current_state,
                    result='expected_error'
                ).inc()
                raise e
            
            # Handle failure atomically
            async with self._lock:
                await self._handle_failure(e)
            
            CIRCUIT_BREAKER_CALLS.labels(
                name=self.config.name,
                state=current_state,
                result='failure'
            ).inc()
            
            raise e
        
        finally:
            # Record execution time
            execution_time = time.time() - start_time
            CIRCUIT_BREAKER_EXECUTION_TIME.labels(name=self.config.name).observe(execution_time)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the circuit breaker."""
        return {
            'name': self.config.name,
            'state': self._state.name,
            'failure_count': self._failure_count,
            'success_count': self._success_count,
            'last_failure_time': self._last_failure_time,
            'last_state_change_time': self._last_state_change_time,
            'failure_rate': self.stats.get_failure_rate(),
            'stats': {
                'total_calls': self.stats.total_calls,
                'successful_calls': self.stats.successful_calls,
                'failed_calls': self.stats.failed_calls,
                'timeout_calls': self.stats.timeout_calls,
                'rejected_calls': self.stats.rejected_calls,
                'last_failure_time': self.stats.last_failure_time,
                'last_success_time': self.stats.last_success_time,
                'state_history_count': len(self.stats._state_change_history)
            },
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'recovery_timeout': self.config.recovery_timeout,
                'half_open_max_calls': self.config.half_open_max_calls,
                'call_timeout': self.config.call_timeout,
                'max_state_history_size': self.config.max_state_history_size
            }
        }

    def get_state_history(self) -> List[Dict[str, Any]]:
        """Get the state change history."""
        return self.stats.get_state_history()

    async def reset(self):
        """Reset the circuit breaker to its initial state."""
        async with self._lock:
            old_state = self._state
            await self._atomic_state_change(CircuitBreakerState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = 0.0
            
            # Reset stats but preserve configuration
            self.stats = CircuitBreakerStats(
                max_history_size=self.config.max_state_history_size,
                history_ttl=self.config.state_history_ttl
            )
            
            # Reset metrics
            CIRCUIT_BREAKER_FAILURE_RATE.labels(name=self.config.name).set(0.0)
            
            logger.info(
                f"Circuit breaker '{self.config.name}' has been reset",
                extra={'circuit_name': self.config.name, 'previous_state': old_state.name}
            )

    async def force_open(self):
        """Force the circuit breaker to open state."""
        async with self._lock:
            await self._atomic_state_change(CircuitBreakerState.OPEN)
            self._last_failure_time = time.monotonic()
            logger.warning(
                f"Circuit breaker '{self.config.name}' has been forced open",
                extra={'circuit_name': self.config.name}
            )

    async def force_close(self):
        """Force the circuit breaker to closed state."""
        async with self._lock:
            await self._atomic_state_change(CircuitBreakerState.CLOSED)
            self._failure_count = 0
            logger.info(
                f"Circuit breaker '{self.config.name}' has been forced closed",
                extra={'circuit_name': self.config.name}
            )

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check and return status information."""
        return {
            'healthy': self._state != CircuitBreakerState.OPEN,
            'state': self._state.name,
            'failure_rate': self.stats.get_failure_rate(),
            'uptime_seconds': time.time() - self._last_state_change_time,
            'total_calls': self.stats.total_calls
        }

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

class CircuitBreakerFactory:
    """Factory for creating pre-configured circuit breakers with improved defaults."""
    
    @staticmethod
    def create_http_client_breaker(name: str, **overrides) -> CircuitBreaker:
        """Create a circuit breaker optimized for HTTP client calls."""
        config = CircuitBreakerConfig(
            name=name,
            failure_threshold=5,
            recovery_timeout=30,
            half_open_max_calls=2,
            half_open_success_threshold=2,
            call_timeout=10.0,
            max_state_history_size=25,
            **overrides
        )
        return CircuitBreaker(config)
    
    @staticmethod
    def create_database_breaker(name: str, **overrides) -> CircuitBreaker:
        """Create a circuit breaker optimized for database calls."""
        config = CircuitBreakerConfig(
            name=name,
            failure_threshold=3,
            recovery_timeout=60,
            half_open_max_calls=1,
            half_open_success_threshold=1,
            call_timeout=5.0,
            max_state_history_size=30,
            **overrides
        )
        return CircuitBreaker(config)
    
    @staticmethod
    def create_external_api_breaker(name: str, **overrides) -> CircuitBreaker:
        """Create a circuit breaker optimized for external API calls."""
        config = CircuitBreakerConfig(
            name=name,
            failure_threshold=10,
            recovery_timeout=120,
            half_open_max_calls=3,
            half_open_success_threshold=2,
            call_timeout=20.0,
            max_state_history_size=40,
            **overrides
        )
        return CircuitBreaker(config)
    
    @staticmethod
    def create_microservice_breaker(name: str, **overrides) -> CircuitBreaker:
        """Create a circuit breaker optimized for microservice calls."""
        config = CircuitBreakerConfig(
            name=name,
            failure_threshold=7,
            recovery_timeout=45,
            half_open_max_calls=2,
            half_open_success_threshold=2,
            call_timeout=15.0,
            max_state_history_size=35,
            **overrides
        )
        return CircuitBreaker(config)

# Singleton registry for managing multiple circuit breakers
class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._breakers = {}
                    cls._instance._registry_lock = asyncio.Lock()
        return cls._instance
    
    async def register(self, name: str, breaker: CircuitBreaker):
        """Register a circuit breaker."""
        async with self._registry_lock:
            self._breakers[name] = breaker
    
    async def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name."""
        async with self._registry_lock:
            return self._breakers.get(name)
    
    async def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all registered circuit breakers."""
        async with self._registry_lock:
            return {
                name: breaker.get_stats()
                for name, breaker in self._breakers.items()
            }
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all registered circuit breakers."""
        async with self._registry_lock:
            results = {}
            for name, breaker in self._breakers.items():
                try:
                    results[name] = await breaker.health_check()
                except Exception as e:
                    results[name] = {
                        'healthy': False,
                        'error': str(e)
                    }
            return results

# Example usage
if __name__ == "__main__":
    import aiohttp
    
    async def example_usage():
        """Example of how to use the improved circuit breaker."""
        
        # Create a circuit breaker for HTTP calls
        http_breaker = CircuitBreakerFactory.create_http_client_breaker("example_api")
        
        async def make_api_call():
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.example.com/data") as response:
                    return await response.json()
        
        # Use the circuit breaker
        try:
            result = await http_breaker.call(make_api_call)
            print(f"Success: {result}")
        except CircuitBreakerOpenError as e:
            print(f"Circuit is open: {e}")
        except Exception as e:
            print(f"Call failed: {e}")
        
        # Check stats
        stats = http_breaker.get_stats()
        print(f"Circuit breaker stats: {stats}")
    
    # asyncio.run(example_usage())