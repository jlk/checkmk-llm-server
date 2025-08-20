"""
MCP Server Utilities Package

This package contains utility functions and classes used throughout the MCP server.

Modules:
    serialization: JSON serialization utilities including MCPJSONEncoder
    errors: Error handling and sanitization utilities

This module is part of the Phase 1 refactoring to modularize the monolithic
MCP server implementation.
"""

# Import utility functions for easy access
from .serialization import MCPJSONEncoder, safe_json_dumps
from .errors import sanitize_error

__all__ = [
    "MCPJSONEncoder",
    "safe_json_dumps", 
    "sanitize_error"
]