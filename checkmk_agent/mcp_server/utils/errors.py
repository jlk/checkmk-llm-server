"""
Error Handling Utilities

This module provides utilities for sanitizing error messages to prevent
information disclosure while maintaining useful debugging information.

Extracted from the monolithic server.py during Phase 1 refactoring.
"""

import re
from pathlib import Path


def sanitize_error(error: Exception) -> str:
    """
    Sanitize error messages to prevent information disclosure.
    
    This function removes sensitive information from error messages while
    preserving useful debugging context. It removes full file paths,
    replaces home directory references, and truncates overly long messages.
    
    Args:
        error: The exception to sanitize
        
    Returns:
        Sanitized error message string
        
    Example:
        >>> error = FileNotFoundError("/home/user/secret/file.txt not found")
        >>> sanitize_error(error)
        "file.txt not found"
        
    Security Note:
        This function is designed to prevent accidental disclosure of:
        - Full file system paths
        - Home directory locations  
        - Overly verbose error details
    """
    try:
        error_str = str(error)
        
        # Remove sensitive path information
        sanitized = error_str.replace(str(Path.home()), "~")
        
        # Remove full file paths, keep only filename
        sanitized = re.sub(r"/[a-zA-Z0-9_/.-]*/", "", sanitized)
        
        # Truncate overly long error messages
        if len(sanitized) > 200:
            sanitized = sanitized[:200] + "..."
            
        return sanitized
        
    except Exception:
        # If sanitization itself fails, return a generic message
        return "Internal server error occurred"