"""Utility modules for the Checkmk LLM Agent."""

# Import from request_context module
from .request_context import (
    generate_request_id,
    generate_sub_request_id,
    get_request_id,
    set_request_id,
    with_request_id,
    ensure_request_id,
    format_request_id,
    extract_parent_id,
    REQUEST_ID_CONTEXT,
)

# Import from the common module (excluding setup_logging)
from ..common import (
    retry_on_failure,
    validate_hostname,
    sanitize_folder_path,
    format_host_response,
    extract_error_message,
    safe_get_with_fallback,
    validate_non_empty_string,
    check_connection_health,
    validate_api_response,
    validate_service_data,
)

# Import the proper setup_logging from logging_utils
from ..logging_utils import setup_logging

__all__ = [
    # Request context functions
    "generate_request_id",
    "generate_sub_request_id",
    "get_request_id",
    "set_request_id",
    "with_request_id",
    "ensure_request_id",
    "format_request_id",
    "extract_parent_id",
    "REQUEST_ID_CONTEXT",
    # Utility functions
    "setup_logging",
    "retry_on_failure",
    "validate_hostname",
    "sanitize_folder_path",
    "format_host_response",
    "extract_error_message",
    "safe_get_with_fallback",
    "validate_non_empty_string",
    "check_connection_health",
    "validate_api_response",
    "validate_service_data",
]
