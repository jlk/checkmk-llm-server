"""Request context management for tracing requests through the system.

This module provides utilities for generating, tracking, and propagating unique request IDs
throughout the Checkmk LLM Agent system. Request IDs enable efficient log filtering,
debugging, and request tracing across all system components.

Key features:
- Thread-safe request ID propagation using contextvars
- High-performance 6-digit hex ID generation
- Support for sub-request IDs for batch operations
- Automatic fallback for orphaned operations
- Comprehensive request ID formatting and validation
"""

import secrets
import asyncio
from contextvars import ContextVar
from typing import Optional, Callable, TypeVar, Any, Dict, Union
from functools import wraps

# Global context variable for request ID - thread-safe and async-safe
REQUEST_ID_CONTEXT: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

T = TypeVar("T")


def generate_request_id() -> str:
    """Generate a unique 6-digit hex request ID with req_ prefix.

    Uses cryptographically secure random number generation to create
    request IDs with high probability of uniqueness (16.7M combinations).

    Performance: ~10-50ns per call with minimal memory overhead.

    Returns:
        str: Request ID in format 'req_a1b2c3'

    Examples:
        >>> request_id = generate_request_id()
        >>> request_id.startswith('req_')
        True
        >>> len(request_id) == 9  # 'req_' + 6 hex chars
        True
    """
    return f"req_{secrets.token_hex(3)}"  # 3 bytes = 6 hex chars


def generate_sub_request_id(parent_id: str, sequence: int) -> str:
    """Generate sub-request ID for batch operations and nested calls.

    Creates hierarchical request IDs that maintain parent-child relationships
    while preserving the ability to trace back to the original request.

    Args:
        parent_id: Parent request ID (e.g., 'req_a1b2c3')
        sequence: Sequential number for this sub-request (0-999)

    Returns:
        str: Sub-request ID in format 'req_a1b2c3.001'

    Examples:
        >>> parent_id = 'req_a1b2c3'
        >>> sub_id = generate_sub_request_id(parent_id, 1)
        >>> sub_id
        'req_a1b2c3.001'
    """
    return f"{parent_id}.{sequence:03d}"


def get_request_id() -> Optional[str]:
    """Get the current request ID from context.

    Returns the request ID set in the current execution context, or None
    if no request ID has been set. This is thread-safe and async-safe.

    Returns:
        Optional[str]: Current request ID or None

    Examples:
        >>> get_request_id()  # Before setting
        None
        >>> set_request_id('req_a1b2c3')
        >>> get_request_id()
        'req_a1b2c3'
    """
    return REQUEST_ID_CONTEXT.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in the current context.

    Sets the request ID for the current execution context. This will
    propagate to all function calls within the same context.

    Args:
        request_id: Request ID to set (e.g., 'req_a1b2c3')

    Examples:
        >>> set_request_id('req_a1b2c3')
        >>> get_request_id()
        'req_a1b2c3'
    """
    REQUEST_ID_CONTEXT.set(request_id)


def format_request_id(request_id: Optional[str]) -> str:
    """Format request ID for logging and display.

    Provides consistent formatting of request IDs with fallback for
    cases where no request ID is available.

    Args:
        request_id: Request ID to format, or None

    Returns:
        str: Formatted request ID with fallback

    Examples:
        >>> format_request_id('req_a1b2c3')
        'req_a1b2c3'
        >>> format_request_id(None)
        'req_unknown'
    """
    return request_id or "req_unknown"


def extract_parent_id(request_id: str) -> str:
    """Extract parent request ID from sub-request ID.

    Extracts the root request ID from hierarchical request IDs,
    enabling correlation of related operations.

    Args:
        request_id: Request ID that may be a sub-request ID

    Returns:
        str: Parent request ID

    Examples:
        >>> extract_parent_id('req_a1b2c3.001')
        'req_a1b2c3'
        >>> extract_parent_id('req_a1b2c3')
        'req_a1b2c3'
    """
    return request_id.split(".")[0] if "." in request_id else request_id


def ensure_request_id() -> str:
    """Ensure a request ID exists, generating one if necessary.

    Gets the current request ID from context, or generates a new one
    if none exists. Useful for orphaned operations that need traceability.

    Returns:
        str: Current or newly generated request ID

    Examples:
        >>> # Without existing request ID
        >>> request_id = ensure_request_id()
        >>> request_id.startswith('req_')
        True
        >>> # With existing request ID
        >>> set_request_id('req_existing')
        >>> ensure_request_id()
        'req_existing'
    """
    current_id = get_request_id()
    if current_id:
        return current_id

    new_id = generate_request_id()
    set_request_id(new_id)
    return new_id


def with_request_id(request_id: Optional[str] = None):
    """Decorator to automatically manage request ID context for functions.

    This decorator ensures that a function executes with a request ID context.
    If no request ID is provided, it will generate one. If one already exists
    in the context, it will use that instead.

    Args:
        request_id: Optional specific request ID to use

    Returns:
        Decorator function

    Examples:
        @with_request_id()
        def my_function():
            return get_request_id()

        @with_request_id('req_specific')
        async def async_function():
            return get_request_id()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                # Use provided request_id, current context, or generate new one
                current_id = request_id or get_request_id()
                if not current_id:
                    current_id = generate_request_id()

                # Execute function with request ID context
                token = REQUEST_ID_CONTEXT.set(current_id)
                try:
                    return await func(*args, **kwargs)
                finally:
                    REQUEST_ID_CONTEXT.reset(token)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                # Use provided request_id, current context, or generate new one
                current_id = request_id or get_request_id()
                if not current_id:
                    current_id = generate_request_id()

                # Execute function with request ID context
                token = REQUEST_ID_CONTEXT.set(current_id)
                try:
                    return func(*args, **kwargs)
                finally:
                    REQUEST_ID_CONTEXT.reset(token)

            return sync_wrapper

    return decorator


def get_request_context() -> Dict[str, Any]:
    """Get current request context information.

    Returns a dictionary containing current request context information
    useful for debugging and monitoring.

    Returns:
        Dict[str, Any]: Request context information

    Examples:
        >>> set_request_id('req_a1b2c3')
        >>> context = get_request_context()
        >>> context['request_id']
        'req_a1b2c3'
    """
    return {
        "request_id": get_request_id(),
        "formatted_request_id": format_request_id(get_request_id()),
        "has_request_id": get_request_id() is not None,
    }


def copy_request_context() -> Optional[str]:
    """Copy the current request context for manual propagation.

    Useful when you need to manually propagate request context across
    boundaries where context variables don't automatically propagate.

    Returns:
        Optional[str]: Current request ID for manual propagation

    Examples:
        >>> set_request_id('req_a1b2c3')
        >>> context = copy_request_context()
        >>> # Later, in different context:
        >>> set_request_id(context)
    """
    return get_request_id()


def validate_request_id(request_id: str) -> bool:
    """Validate request ID format.

    Validates that a request ID follows the expected format:
    - Starts with 'req_'
    - Contains 6 hexadecimal characters
    - May have sub-request suffix (.001, .002, etc.)

    Args:
        request_id: Request ID to validate

    Returns:
        bool: True if valid, False otherwise

    Examples:
        >>> validate_request_id('req_a1b2c3')
        True
        >>> validate_request_id('req_a1b2c3.001')
        True
        >>> validate_request_id('invalid_id')
        False
    """
    if not isinstance(request_id, str):
        return False

    # Split on '.' to handle sub-request IDs
    parts = request_id.split(".")
    main_id = parts[0]

    # Validate main ID format
    if not main_id.startswith("req_"):
        return False

    hex_part = main_id[4:]  # Remove 'req_' prefix
    if len(hex_part) != 6:
        return False

    try:
        int(hex_part, 16)  # Validate hex format
    except ValueError:
        return False

    # Validate sub-request suffix if present
    if len(parts) == 2:
        try:
            sub_num = int(parts[1])
            if sub_num < 0 or sub_num > 999:
                return False
        except ValueError:
            return False
    elif len(parts) > 2:
        return False

    return True


def is_sub_request_id(request_id: str) -> bool:
    """Check if request ID is a sub-request ID.

    Args:
        request_id: Request ID to check

    Returns:
        bool: True if this is a sub-request ID

    Examples:
        >>> is_sub_request_id('req_a1b2c3.001')
        True
        >>> is_sub_request_id('req_a1b2c3')
        False
    """
    return "." in request_id and validate_request_id(request_id)
