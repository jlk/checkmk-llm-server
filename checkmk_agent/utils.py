"""Common utilities for Checkmk LLM Agent."""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying functions on failure with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise last_exception
            
            raise last_exception
        return wrapper
    return decorator


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