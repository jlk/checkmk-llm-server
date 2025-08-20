"""MCP Server implementation for Checkmk operations."""

from .server import CheckmkMCPServer

# Backward compatibility imports for extracted utilities
# These can be imported directly from the utils package, but we maintain
# compatibility for any existing code that imports them from the server package
from .utils import (
    MCPJSONEncoder,
    safe_json_dumps,
    sanitize_error
)

# Configuration imports for easy access
from .config import (
    ALL_TOOL_SCHEMAS,
    TOOL_CATEGORIES,
    validate_tool_definitions
)

__all__ = [
    "CheckmkMCPServer",
    # Utility functions (backward compatibility)
    "MCPJSONEncoder",
    "safe_json_dumps", 
    "sanitize_error",
    # Configuration (for future use)
    "ALL_TOOL_SCHEMAS",
    "TOOL_CATEGORIES",
    "validate_tool_definitions",
]
