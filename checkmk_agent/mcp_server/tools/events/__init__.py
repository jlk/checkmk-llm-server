"""Event management tools for the Checkmk MCP server.

This package contains all tools related to event operations including:
- Service and host event listing
- Critical event monitoring  
- Event acknowledgment
- Event search and filtering

All tools follow the standard MCP tool pattern with proper error handling,
service integration, and response formatting.
"""

from .tools import EventTools

__all__ = ["EventTools"]