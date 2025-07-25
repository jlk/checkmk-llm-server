"""Advanced error recovery and resilience patterns."""

import asyncio
import logging
import random
import time
from typing import Optional, Dict, Any, Callable, TypeVar, Union, List, Type
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum

from pydantic import BaseModel, Field

from .metrics import get_metrics_collector, timed_context


T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


class RetryStrategy(str, Enum):
    """Retry strategies."""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    JITTERED_EXPONENTIAL = "jittered_exponential"


class FailureType(str, Enum):
    """Types of failures that can be recovered from."""
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    AUTHENTICATION = "authentication"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"


class RecoveryAction(str, Enum):
    """Recovery actions to take."""
    RETRY = "retry"
    CIRCUIT_BREAK = "circuit_break"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    FAIL_FAST = "fail_fast"


class ErrorPattern(BaseModel):
    """Configuration for handling specific error patterns."""
    exception_types: List[Type[Exception]] = Field(default_factory=list)
    error_codes: List[int] = Field(default_factory=list)
    error_messages: List[str] = Field(default_factory=list)
    failure_type: FailureType
    recovery_action: RecoveryAction
    max_retries: int = 3
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    circuit_break_threshold: int = 5
    circuit_break_timeout: int = 60


class CircuitBreaker:
    """Circuit breaker implementation for service protection."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            expected_exception: Exception type that triggers circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._successful_calls = 0
        self.logger = logging.getLogger(__name__)
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset circuit."""
        if self._state != CircuitState.OPEN:
            return False
        
        if self._last_failure_time is None:
            return False
        
        return time.time() - self._last_failure_time >= self.recovery_timeout
    
    async def call(self, func: Callable[[], T]) -> T:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        # Check if we should attempt reset
        if self._should_attempt_reset():
            self._state = CircuitState.HALF_OPEN
            self.logger.info("Circuit breaker moving to HALF_OPEN state")
        
        # Reject if circuit is open
        if self._state == CircuitState.OPEN:
            await get_metrics_collector().increment_counter("circuit_breaker.rejected")
            raise Exception("Circuit breaker is OPEN")
        
        try:
            # Execute function
            async with timed_context("circuit_breaker.call"):
                result = await func()
            
            # Handle success
            await self._on_success()
            return result
            
        except self.expected_exception as e:
            # Handle expected failure
            await self._on_failure()
            raise
        except Exception as e:
            # Handle unexpected failure
            await self._on_failure()
            raise
    
    async def _on_success(self):
        """Handle successful call."""
        self._successful_calls += 1
        
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self.logger.info("Circuit breaker reset to CLOSED state")
            await get_metrics_collector().increment_counter("circuit_breaker.reset")
        
        await get_metrics_collector().increment_counter("circuit_breaker.success")
    
    async def _on_failure(self):
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self.logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )
            await get_metrics_collector().increment_counter("circuit_breaker.opened")
        
        await get_metrics_collector().increment_counter("circuit_breaker.failure")


class RetryPolicy:
    """Configurable retry policy with different strategies."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter: bool = True
    ):
        """
        Initialize retry policy.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
            strategy: Retry strategy to use
            jitter: Whether to add jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.strategy = strategy
        self.jitter = jitter
        self.logger = logging.getLogger(__name__)
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        if self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.base_delay * attempt
        elif self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.base_delay * (2 ** (attempt - 1))
        elif self.strategy == RetryStrategy.JITTERED_EXPONENTIAL:
            delay = self.base_delay * (2 ** (attempt - 1))
            if self.jitter:
                delay *= (0.5 + random.random() * 0.5)  # Add 0-50% jitter
        else:
            delay = self.base_delay
        
        # Apply jitter if enabled
        if self.jitter and self.strategy != RetryStrategy.JITTERED_EXPONENTIAL:
            jitter_factor = 0.1 * random.random()  # ±10% jitter
            delay *= (1 + jitter_factor)
        
        return min(delay, self.max_delay)
    
    async def execute(
        self,
        func: Callable[[], T],
        retryable_exceptions: tuple = (Exception,),
        operation_name: str = "operation"
    ) -> T:
        """
        Execute function with retry policy.
        
        Args:
            func: Async function to execute
            retryable_exceptions: Tuple of exception types to retry on
            operation_name: Name for logging and metrics
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None
        
        for attempt in range(1, self.max_retries + 2):  # +1 for initial attempt
            try:
                async with timed_context(f"retry.{operation_name}.attempt_{attempt}"):
                    result = await func()
                
                if attempt > 1:
                    self.logger.info(
                        f"Operation {operation_name} succeeded on attempt {attempt}"
                    )
                    await get_metrics_collector().increment_counter(
                        f"retry.{operation_name}.success_after_retry",
                        attempt=str(attempt)
                    )
                
                return result
                
            except retryable_exceptions as e:
                last_exception = e
                
                if attempt <= self.max_retries:
                    delay = self.calculate_delay(attempt)
                    self.logger.warning(
                        f"Attempt {attempt} failed for {operation_name}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    
                    await get_metrics_collector().increment_counter(
                        f"retry.{operation_name}.attempt",
                        attempt=str(attempt)
                    )
                    
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"All {self.max_retries} retries exhausted for {operation_name}"
                    )
                    await get_metrics_collector().increment_counter(
                        f"retry.{operation_name}.exhausted"
                    )
                    break
            
            except Exception as e:
                # Non-retryable exception
                self.logger.error(f"Non-retryable error in {operation_name}: {e}")
                await get_metrics_collector().increment_counter(
                    f"retry.{operation_name}.non_retryable"
                )
                raise
        
        # If we get here, all retries were exhausted
        raise last_exception


class FallbackHandler:
    """Handler for fallback operations when primary operation fails."""
    
    def __init__(self):
        self.fallback_functions: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_fallback(self, operation_name: str, fallback_func: Callable):
        """Register a fallback function for an operation."""
        self.fallback_functions[operation_name] = fallback_func
    
    async def execute_with_fallback(
        self,
        primary_func: Callable[[], T],
        operation_name: str,
        fallback_args: tuple = (),
        fallback_kwargs: Optional[Dict[str, Any]] = None
    ) -> T:
        """
        Execute primary function with fallback on failure.
        
        Args:
            primary_func: Primary function to execute
            operation_name: Operation name for fallback lookup
            fallback_args: Arguments for fallback function
            fallback_kwargs: Keyword arguments for fallback function
            
        Returns:
            Result from primary or fallback function
        """
        try:
            return await primary_func()
        except Exception as e:
            self.logger.warning(f"Primary operation {operation_name} failed: {e}")
            await get_metrics_collector().increment_counter(f"fallback.{operation_name}.triggered")
            
            fallback_func = self.fallback_functions.get(operation_name)
            if not fallback_func:
                self.logger.error(f"No fallback registered for {operation_name}")
                await get_metrics_collector().increment_counter(f"fallback.{operation_name}.missing")
                raise
            
            try:
                self.logger.info(f"Executing fallback for {operation_name}")
                result = await fallback_func(*(fallback_args or ()), **(fallback_kwargs or {}))
                await get_metrics_collector().increment_counter(f"fallback.{operation_name}.success")
                return result
            except Exception as fallback_error:
                self.logger.error(f"Fallback also failed for {operation_name}: {fallback_error}")
                await get_metrics_collector().increment_counter(f"fallback.{operation_name}.failed")
                raise


class RecoveryMixin:
    """Mixin to add advanced error recovery capabilities to services."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_policies: Dict[str, RetryPolicy] = {}
        self.fallback_handler = FallbackHandler()
        self.error_patterns: List[ErrorPattern] = []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_circuit_breaker(self, name: str, **kwargs) -> CircuitBreaker:
        """Get or create circuit breaker for operation."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(**kwargs)
        return self.circuit_breakers[name]
    
    def get_retry_policy(self, name: str, **kwargs) -> RetryPolicy:
        """Get or create retry policy for operation."""
        if name not in self.retry_policies:
            self.retry_policies[name] = RetryPolicy(**kwargs)
        return self.retry_policies[name]
    
    def resilient(
        self,
        operation_name: Optional[str] = None,
        circuit_breaker: bool = True,
        retry_policy: bool = True,
        fallback: bool = False,
        **kwargs
    ):
        """
        Decorator to add resilience patterns to methods.
        
        Args:
            operation_name: Name for the operation (defaults to method name)
            circuit_breaker: Enable circuit breaker
            retry_policy: Enable retry policy
            fallback: Enable fallback handling
            **kwargs: Additional configuration for patterns
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **func_kwargs):
                name = operation_name or func.__name__
                
                async def execute():
                    if retry_policy:
                        retry = self.get_retry_policy(f"{name}_retry", **kwargs.get('retry_config', {}))
                        return await retry.execute(
                            lambda: func(*args, **func_kwargs),
                            operation_name=name
                        )
                    else:
                        return await func(*args, **func_kwargs)
                
                if circuit_breaker:
                    cb = self.get_circuit_breaker(f"{name}_circuit", **kwargs.get('circuit_config', {}))
                    return await cb.call(execute)
                else:
                    return await execute()
            
            return wrapper
        return decorator
    
    async def execute_with_recovery(
        self,
        func: Callable[[], T],
        operation_name: str,
        enable_circuit_breaker: bool = True,
        enable_retry: bool = True,
        enable_fallback: bool = False,
        fallback_args: tuple = (),
        fallback_kwargs: Optional[Dict[str, Any]] = None
    ) -> T:
        """
        Execute function with full recovery capabilities.
        
        Args:
            func: Function to execute
            operation_name: Name for tracking and configuration
            enable_circuit_breaker: Use circuit breaker
            enable_retry: Use retry policy
            enable_fallback: Use fallback handling
            fallback_args: Arguments for fallback
            fallback_kwargs: Keyword arguments for fallback
            
        Returns:
            Function result
        """
        async def execute():
            if enable_retry:
                retry = self.get_retry_policy(f"{operation_name}_retry")
                return await retry.execute(func, operation_name=operation_name)
            else:
                return await func()
        
        if enable_circuit_breaker:
            cb = self.get_circuit_breaker(f"{operation_name}_circuit")
            if enable_fallback:
                return await self.fallback_handler.execute_with_fallback(
                    lambda: cb.call(execute),
                    operation_name,
                    fallback_args,
                    fallback_kwargs
                )
            else:
                return await cb.call(execute)
        else:
            if enable_fallback:
                return await self.fallback_handler.execute_with_fallback(
                    execute,
                    operation_name,
                    fallback_args,
                    fallback_kwargs
                )
            else:
                return await execute()
    
    async def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        return {
            'circuit_breakers': {
                name: {
                    'state': cb.state,
                    'failure_count': cb._failure_count,
                    'successful_calls': cb._successful_calls
                }
                for name, cb in self.circuit_breakers.items()
            },
            'retry_policies_count': len(self.retry_policies),
            'error_patterns_count': len(self.error_patterns),
            'fallback_functions_count': len(self.fallback_handler.fallback_functions)
        }