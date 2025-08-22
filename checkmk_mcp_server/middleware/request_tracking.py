"""Request tracking middleware for automatic request ID generation and propagation.

This module provides middleware components that automatically generate and track
request IDs throughout the system. It includes decorators, context managers,
and utility classes for seamless request ID integration.

Key features:
- Automatic request ID generation for entry points
- Context-aware request ID propagation
- Support for both sync and async operations
- Integration with logging and error handling
- Minimal performance overhead
"""

import logging
import asyncio
from typing import Optional, Callable, TypeVar, Any, Dict, Union
from functools import wraps
from datetime import datetime

from ..utils.request_context import (
    generate_request_id,
    get_request_id,
    set_request_id,
    with_request_id,
    ensure_request_id,
    format_request_id,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)


def track_request(
    request_id: Optional[str] = None,
    operation_name: Optional[str] = None,
    include_timing: bool = False,
):
    """Decorator to automatically track requests with unique IDs.

    This decorator provides automatic request ID generation and propagation
    for any function or method. It can be used on entry points to ensure
    all operations have proper request tracing.

    Args:
        request_id: Optional specific request ID to use
        operation_name: Optional name for the operation (for logging)
        include_timing: Whether to include execution timing in logs

    Returns:
        Decorator function

    Examples:
        @track_request()
        def cli_command():
            # Request ID automatically generated and propagated
            pass

        @track_request(operation_name="MCP Tool Execution")
        async def mcp_tool():
            # Request ID generated with custom operation name
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                # Determine request ID
                # Always generate new ID if no specific request_id provided
                current_id = request_id or generate_request_id()

                # Set up operation context
                op_name = operation_name or f"{func.__name__}"
                start_time = datetime.now() if include_timing else None

                # Set request ID context
                set_request_id(current_id)

                try:
                    logger.debug(f"[{current_id}] Starting {op_name}")
                    result = await func(*args, **kwargs)

                    if include_timing and start_time:
                        duration_ms = (
                            datetime.now() - start_time
                        ).total_seconds() * 1000
                        logger.debug(
                            f"[{current_id}] Completed {op_name} in {duration_ms:.2f}ms"
                        )
                    else:
                        logger.debug(f"[{current_id}] Completed {op_name}")

                    return result

                except Exception as e:
                    if include_timing and start_time:
                        duration_ms = (
                            datetime.now() - start_time
                        ).total_seconds() * 1000
                        logger.error(
                            f"[{current_id}] Failed {op_name} after {duration_ms:.2f}ms: {e}"
                        )
                    else:
                        logger.error(f"[{current_id}] Failed {op_name}: {e}")
                    raise

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                # Determine request ID
                # Always generate new ID if no specific request_id provided
                current_id = request_id or generate_request_id()

                # Set up operation context
                op_name = operation_name or f"{func.__name__}"
                start_time = datetime.now() if include_timing else None

                # Set request ID context
                set_request_id(current_id)

                try:
                    logger.debug(f"[{current_id}] Starting {op_name}")
                    result = func(*args, **kwargs)

                    if include_timing and start_time:
                        duration_ms = (
                            datetime.now() - start_time
                        ).total_seconds() * 1000
                        logger.debug(
                            f"[{current_id}] Completed {op_name} in {duration_ms:.2f}ms"
                        )
                    else:
                        logger.debug(f"[{current_id}] Completed {op_name}")

                    return result

                except Exception as e:
                    if include_timing and start_time:
                        duration_ms = (
                            datetime.now() - start_time
                        ).total_seconds() * 1000
                        logger.error(
                            f"[{current_id}] Failed {op_name} after {duration_ms:.2f}ms: {e}"
                        )
                    else:
                        logger.error(f"[{current_id}] Failed {op_name}: {e}")
                    raise

            return sync_wrapper

    return decorator


class RequestTrackingMiddleware:
    """Middleware class for request tracking in various contexts.

    This class provides middleware functionality that can be integrated
    into different parts of the system (CLI, MCP server, API client, etc.)
    to ensure consistent request ID tracking.
    """

    def __init__(
        self,
        auto_generate: bool = True,
        log_requests: bool = True,
        include_timing: bool = False,
    ):
        """Initialize request tracking middleware.

        Args:
            auto_generate: Whether to auto-generate request IDs
            log_requests: Whether to log request start/completion
            include_timing: Whether to include timing information
        """
        self.auto_generate = auto_generate
        self.log_requests = log_requests
        self.include_timing = include_timing
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def process_request(
        self, request_context: Dict[str, Any], operation_name: str = "request"
    ) -> str:
        """Process incoming request and ensure request ID tracking.

        Args:
            request_context: Request context information
            operation_name: Name of the operation being processed

        Returns:
            str: Request ID for this request
        """
        # Check for existing request ID in context (don't reuse thread context)
        existing_id = request_context.get("request_id")

        if existing_id:
            request_id = existing_id
        elif self.auto_generate:
            request_id = generate_request_id()
        else:
            raise ValueError("No request ID available and auto-generation disabled")

        # Set request context
        set_request_id(request_id)

        # Log request start
        if self.log_requests:
            self.logger.info(f"[{request_id}] Processing {operation_name}")

        # Add timing start if enabled
        if self.include_timing:
            request_context["_start_time"] = datetime.now()

        return request_id

    def complete_request(
        self,
        request_id: str,
        request_context: Dict[str, Any],
        success: bool = True,
        error: Optional[Exception] = None,
    ) -> None:
        """Complete request processing and log results.

        Args:
            request_id: Request ID for this request
            request_context: Request context information
            success: Whether the request completed successfully
            error: Exception if request failed
        """
        if not self.log_requests:
            return

        # Calculate timing if enabled
        duration_str = ""
        if self.include_timing and "_start_time" in request_context:
            start_time = request_context["_start_time"]
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            duration_str = f" in {duration_ms:.2f}ms"

        # Log completion
        if success:
            self.logger.info(
                f"[{request_id}] Request completed successfully{duration_str}"
            )
        else:
            error_msg = str(error) if error else "Unknown error"
            self.logger.error(
                f"[{request_id}] Request failed{duration_str}: {error_msg}"
            )

    def get_request_headers(self) -> Dict[str, str]:
        """Get HTTP headers including request ID.

        Returns:
            Dict[str, str]: HTTP headers with request ID
        """
        request_id = get_request_id()
        if request_id:
            return {"X-Request-ID": request_id}
        return {}

    def extract_request_id_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """Extract request ID from HTTP headers.

        Args:
            headers: HTTP headers dictionary

        Returns:
            Optional[str]: Request ID if found in headers
        """
        # Check various header formats
        for header_name in ["X-Request-ID", "x-request-id", "Request-ID", "request-id"]:
            if header_name in headers:
                return headers[header_name]
        return None


def with_request_tracking(
    operation_name: Optional[str] = None, include_timing: bool = False
):
    """Decorator that provides full request tracking with middleware integration.

    This is a higher-level decorator that combines request ID generation
    with comprehensive request tracking and logging.

    Args:
        operation_name: Optional name for the operation
        include_timing: Whether to include execution timing

    Returns:
        Decorator function

    Examples:
        @with_request_tracking("CLI Command")
        def handle_cli_command():
            pass

        @with_request_tracking("MCP Tool", include_timing=True)
        async def handle_mcp_tool():
            pass
    """
    middleware = RequestTrackingMiddleware(include_timing=include_timing)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                op_name = operation_name or func.__name__
                request_context = {}

                # Process request and get request ID
                request_id = middleware.process_request(request_context, op_name)

                try:
                    result = await func(*args, **kwargs)
                    middleware.complete_request(
                        request_id, request_context, success=True
                    )
                    return result
                except Exception as e:
                    middleware.complete_request(
                        request_id, request_context, success=False, error=e
                    )
                    raise

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                op_name = operation_name or func.__name__
                request_context = {}

                # Process request and get request ID
                request_id = middleware.process_request(request_context, op_name)

                try:
                    result = func(*args, **kwargs)
                    middleware.complete_request(
                        request_id, request_context, success=True
                    )
                    return result
                except Exception as e:
                    middleware.complete_request(
                        request_id, request_context, success=False, error=e
                    )
                    raise

            return sync_wrapper

    return decorator


def get_request_tracking_metadata() -> Dict[str, Any]:
    """Get current request tracking metadata.

    Returns comprehensive information about the current request context
    for debugging and monitoring purposes.

    Returns:
        Dict[str, Any]: Request tracking metadata
    """
    return {
        "request_id": get_request_id(),
        "formatted_request_id": format_request_id(get_request_id()),
        "has_request_id": get_request_id() is not None,
        "timestamp": datetime.now().isoformat(),
    }


def propagate_request_context(
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Propagate request context through HTTP headers or other mechanisms.

    Args:
        headers: Existing headers to add request ID to

    Returns:
        Dict[str, str]: Headers with request ID propagation
    """
    result_headers = headers.copy() if headers else {}

    request_id = get_request_id()
    if request_id:
        result_headers["X-Request-ID"] = request_id

    return result_headers


def restore_request_context(headers: Dict[str, str]) -> bool:
    """Restore request context from HTTP headers or other sources.

    Args:
        headers: Headers potentially containing request ID

    Returns:
        bool: True if request context was restored
    """
    middleware = RequestTrackingMiddleware()
    request_id = middleware.extract_request_id_from_headers(headers)

    if request_id:
        set_request_id(request_id)
        return True

    return False
