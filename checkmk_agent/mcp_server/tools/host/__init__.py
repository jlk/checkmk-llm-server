"""Host management tools for the Checkmk MCP server.

This package contains all tools related to host operations including:
- Host CRUD operations (list, create, get, update, delete)
- Host services listing
- Host management utilities

All tools follow the standard MCP tool pattern with proper error handling,
service integration, and response formatting.
"""

from .tools import HostTools

__all__ = ["HostTools"]