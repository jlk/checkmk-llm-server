import logging
from typing import Optional

try:
    from .utils.request_context import get_request_id, format_request_id
except ImportError:
    # Fallback for cases where utils package is not available
    def get_request_id() -> Optional[str]:
        return None

    def format_request_id(request_id: Optional[str]) -> str:
        return request_id or "req_unknown"


class RequestIDFormatter(logging.Formatter):
    """Custom log formatter that includes request ID in log messages.

    This formatter automatically includes the current request ID in all log
    messages, enabling easy filtering and correlation of log entries for
    specific requests.

    Format: timestamp [request_id] level logger_name: message
    Example: 2025-08-07 14:30:15.123 [req_a1b2c3] INFO checkmk_mcp_server.api_client: Fetching host list
    """

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        """Initialize the formatter with request ID support.

        Args:
            fmt: Optional format string (will be modified to include request ID)
            datefmt: Optional date format string
        """
        # Default format with request ID placeholder
        if fmt is None:
            fmt = "%(asctime)s [%(request_id)s] %(levelname)s %(name)s: %(message)s"
        elif "[%(request_id)s]" not in fmt:
            # Insert request ID into existing format if not present
            fmt = fmt.replace("%(levelname)s", "[%(request_id)s] %(levelname)s")

        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with request ID.

        Args:
            record: Log record to format

        Returns:
            str: Formatted log message with request ID
        """
        # Add request ID to the record
        record.request_id = format_request_id(get_request_id())

        return super().format(record)


def setup_logging(log_level: str = "INFO", include_request_id: bool = True):
    """
    Set up logging for the application with optional request ID support.

    Args:
        log_level (str): Logging level as a string (e.g., 'DEBUG', 'INFO').
        include_request_id (bool): Whether to include request IDs in log messages.
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    # Choose formatter based on request ID preference
    if include_request_id:
        formatter = RequestIDFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler with custom formatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)


def get_logger_with_request_id(name: str) -> logging.Logger:
    """Get a logger that automatically includes request IDs in messages.

    This is a convenience function for getting loggers that will automatically
    include request ID context in all log messages.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Logger configured for request ID support

    Examples:
        >>> logger = get_logger_with_request_id(__name__)
        >>> logger.info("This will include request ID")
    """
    logger = logging.getLogger(name)

    # Ensure handler has request ID formatter if not already configured
    if logger.handlers:
        return logger

    # If no handlers, the root logger configuration will be used
    return logger


def log_with_request_id(
    logger: logging.Logger, level: int, message: str, *args, **kwargs
):
    """Log a message with explicit request ID inclusion.

    This function provides explicit request ID logging for cases where
    you need fine-grained control over request ID inclusion.

    Args:
        logger: Logger instance to use
        level: Logging level (e.g., logging.INFO)
        message: Log message format string
        *args: Message format arguments
        **kwargs: Additional logging arguments

    Examples:
        >>> log_with_request_id(logger, logging.INFO, "Processing %s", hostname)
    """
    request_id = format_request_id(get_request_id())

    # Add request ID to the message
    if args:
        formatted_message = message % args
    else:
        formatted_message = message

    logger.log(level, f"[{request_id}] {formatted_message}", **kwargs)


def create_request_aware_logger(
    name: str, request_id: Optional[str] = None
) -> logging.Logger:
    """Create a logger that's bound to a specific request ID.

    This function creates a logger adapter that automatically includes
    a specific request ID in all log messages, useful for long-running
    operations that need consistent request ID correlation.

    Args:
        name: Logger name
        request_id: Optional specific request ID to bind to this logger

    Returns:
        logging.Logger: Logger with bound request ID

    Examples:
        >>> bound_logger = create_request_aware_logger(__name__, "req_a1b2c3")
        >>> bound_logger.info("This message will have req_a1b2c3")
    """
    base_logger = logging.getLogger(name)

    if request_id is None:
        request_id = format_request_id(get_request_id())

    class RequestLoggerAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            return f"[{request_id}] {msg}", kwargs

    return RequestLoggerAdapter(base_logger, {})
