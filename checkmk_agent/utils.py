"""Common utilities for Checkmk LLM Agent."""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, List


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff_multiplier: float = 2.0):
    """
    Decorator for retrying functions on failure with intelligent retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(func.__module__)
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        logger.info(f"Retry attempt {attempt}/{max_retries} for {func.__name__}")
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    # Don't retry certain types of errors
                    if not _should_retry_error(e):
                        logger.warning(f"Non-retriable error in {func.__name__}: {e}")
                        raise e
                    
                    if attempt < max_retries:
                        wait_time = delay * (backoff_multiplier ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}: {e}")
                        raise last_exception
            
            raise last_exception
        return wrapper
    return decorator


def _should_retry_error(error: Exception) -> bool:
    """
    Determine if an error should be retried.
    
    Args:
        error: The exception to check
        
    Returns:
        True if the error should be retried, False otherwise
    """
    import requests
    
    # Always retry connection errors and timeouts
    if isinstance(error, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    
    # Check for CheckmkAPIError with retriable status codes
    if hasattr(error, 'status_code') and error.status_code:
        # Don't retry client errors (4xx) except for 429 (rate limit) and 408 (timeout)
        if 400 <= error.status_code < 500:
            return error.status_code in [408, 429]
        
        # Retry server errors (5xx)
        if 500 <= error.status_code < 600:
            return True
    
    # Don't retry validation errors or authentication issues
    if isinstance(error, (ValueError, KeyError, TypeError)):
        return False
    
    # Default to retrying other errors (like generic network issues)
    return True


def validate_hostname(hostname: str) -> bool:
    """Validate hostname format according to Checkmk requirements."""
    import re
    pattern = r'^[-0-9a-zA-Z_.]+$'
    return bool(re.match(pattern, hostname))


def sanitize_folder_path(folder: str) -> str:
    """Sanitize folder path for Checkmk API."""
    if not folder:
        return "/"
    
    # Ensure folder starts with /
    if not folder.startswith("/"):
        folder = "/" + folder
    
    # Remove trailing slash unless it's root
    if folder != "/" and folder.endswith("/"):
        folder = folder[:-1]
    
    return folder


def format_host_response(host_data: Dict[str, Any]) -> str:
    """Format host data for human-readable output."""
    if not host_data:
        return "No host data available"
    
    # Extract key information
    host_id = host_data.get("id", "Unknown")
    title = host_data.get("title", "No title")
    
    # Get extensions if available
    extensions = host_data.get("extensions", {})
    folder = extensions.get("folder", "Unknown")
    is_cluster = extensions.get("is_cluster", False)
    is_offline = extensions.get("is_offline", False)
    
    # Get attributes
    attributes = extensions.get("attributes", {})
    ip_address = attributes.get("ipaddress", "Not set")
    alias = attributes.get("alias", "No alias")
    
    # Format output
    output = f"Host: {host_id}\n"
    output += f"  Title: {title}\n"
    output += f"  Folder: {folder}\n"
    output += f"  IP Address: {ip_address}\n"
    output += f"  Alias: {alias}\n"
    output += f"  Cluster: {'Yes' if is_cluster else 'No'}\n"
    output += f"  Offline: {'Yes' if is_offline else 'No'}\n"
    
    return output


def extract_error_message(error_response: Dict[str, Any]) -> str:
    """Extract meaningful error message from API response."""
    if isinstance(error_response, dict):
        # Check for common error fields
        if "detail" in error_response:
            return error_response["detail"]
        elif "message" in error_response:
            return error_response["message"]
        elif "error" in error_response:
            return error_response["error"]
        elif "title" in error_response:
            return error_response["title"]
    
    return str(error_response)


def safe_get_with_fallback(primary_dict: Dict[str, Any], fallback_dict: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get a value from primary dict, then fallback dict, avoiding falsy value issues.
    
    This prevents issues where values like 0, "", or False are incorrectly treated as missing
    when using the 'or' operator.
    
    Args:
        primary_dict: Primary dictionary to check first
        fallback_dict: Fallback dictionary if primary doesn't have the key
        key: Key to look for
        default: Default value if key not found in either dict
        
    Returns:
        Value found or default
    """
    if key in primary_dict and primary_dict[key] is not None:
        return primary_dict[key]
    elif key in fallback_dict and fallback_dict[key] is not None:
        return fallback_dict[key]
    else:
        return default


def validate_non_empty_string(value: Any, field_name: str) -> str:
    """
    Validate that a value is a non-empty string.
    
    Args:
        value: Value to validate
        field_name: Name of the field for error messages
        
    Returns:
        Validated string value
        
    Raises:
        ValueError: If value is not a valid non-empty string
    """
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string, got {type(value)}")
    
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    
    return value.strip()


def check_connection_health(base_url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Check the health of a connection to a Checkmk server.
    
    Args:
        base_url: Base URL of the Checkmk server
        timeout: Timeout in seconds for the connection check
        
    Returns:
        Dictionary with connection health information
    """
    import requests
    from urllib.parse import urljoin
    
    health_info = {
        "url": base_url,
        "reachable": False,
        "response_time_ms": None,
        "status_code": None,
        "error": None,
        "suggestions": []
    }
    
    try:
        # Try to reach the basic server endpoint (not requiring auth)
        start_time = time.time()
        
        # Use a simple GET to the root API endpoint
        test_url = urljoin(base_url, "/")
        response = requests.get(test_url, timeout=timeout, verify=False)  # Skip SSL verification for test
        
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000
        
        health_info.update({
            "reachable": True,
            "response_time_ms": round(response_time_ms, 2),
            "status_code": response.status_code
        })
        
        # Add performance suggestions
        if response_time_ms > 5000:
            health_info["suggestions"].append("Server response time is slow (>5s). Check network connectivity.")
        elif response_time_ms > 2000:
            health_info["suggestions"].append("Server response time is elevated (>2s). Monitor server performance.")
            
    except requests.exceptions.ConnectionError as e:
        health_info["error"] = f"Connection failed: {str(e)}"
        health_info["suggestions"].extend([
            "Check if the server URL is correct",
            "Verify network connectivity to the server",
            "Check if the Checkmk service is running"
        ])
        
    except requests.exceptions.Timeout as e:
        health_info["error"] = f"Connection timeout: {str(e)}"
        health_info["suggestions"].extend([
            "Server may be overloaded or slow to respond",
            "Try increasing the timeout value",
            "Check server performance and load"
        ])
        
    except Exception as e:
        health_info["error"] = f"Unexpected error: {str(e)}"
        health_info["suggestions"].append("Check server configuration and logs")
    
    return health_info


def validate_api_response(response_data: Any, expected_fields: Optional[List[str]] = None, response_type: str = "API response") -> Dict[str, Any]:
    """
    Validate API response data format and content.
    
    Args:
        response_data: The response data to validate
        expected_fields: List of fields that should be present in the response
        response_type: Description of the response type for error messages
        
    Returns:
        Validated response data
        
    Raises:
        ValueError: If the response format is invalid
    """
    if response_data is None:
        raise ValueError(f"{response_type} is None")
    
    # Handle different response formats
    if isinstance(response_data, dict):
        # Check for Checkmk API error format
        if 'error' in response_data:
            error_msg = response_data.get('error', 'Unknown error')
            raise ValueError(f"{response_type} contains error: {error_msg}")
        
        # Validate expected fields if provided
        if expected_fields:
            missing_fields = []
            for field in expected_fields:
                if field not in response_data:
                    missing_fields.append(field)
            
            if missing_fields:
                raise ValueError(f"{response_type} missing required fields: {', '.join(missing_fields)}")
        
        return response_data
    
    elif isinstance(response_data, list):
        # Validate list responses
        if expected_fields and response_data:
            # Check first item for expected structure
            first_item = response_data[0]
            if isinstance(first_item, dict):
                missing_fields = []
                for field in expected_fields:
                    if field not in first_item:
                        missing_fields.append(field)
                
                if missing_fields:
                    raise ValueError(f"{response_type} items missing required fields: {', '.join(missing_fields)}")
        
        return response_data
    
    else:
        # For primitive types, just return as-is
        return response_data


def validate_service_data(service_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate service data from Checkmk API.
    
    Args:
        service_data: Service data from API
        
    Returns:
        Validated service data
        
    Raises:
        ValueError: If service data is invalid
    """
    if not isinstance(service_data, dict):
        raise ValueError(f"Service data must be a dictionary, got {type(service_data)}")
    
    # Check for required fields that should always be present
    required_fields = ['extensions']  # Extensions contain the actual service data
    missing_fields = [field for field in required_fields if field not in service_data]
    
    if missing_fields:
        # Sometimes data comes in different formats, so be more lenient
        # Just log a warning instead of failing
        logger = logging.getLogger(__name__)
        logger.warning(f"Service data missing expected fields: {', '.join(missing_fields)}")
    
    extensions = service_data.get('extensions', {})
    
    # Validate state field if present (should be numeric 0-3 or string)
    if 'state' in extensions:
        state = extensions['state']
        if isinstance(state, int):
            if state not in [0, 1, 2, 3]:
                logger = logging.getLogger(__name__)
                logger.warning(f"Unexpected service state value: {state}")
        elif isinstance(state, str):
            valid_states = ['OK', 'WARNING', 'CRITICAL', 'UNKNOWN', 'WARN', 'CRIT']
            if state.upper() not in valid_states:
                logger = logging.getLogger(__name__)
                logger.warning(f"Unexpected service state string: {state}")
    
    return service_data