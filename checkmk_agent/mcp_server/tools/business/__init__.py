"""Business Intelligence tools for the Checkmk MCP server.

This package contains all tools related to business intelligence operations including:
- Business status summaries
- Critical business services monitoring
- BI aggregation analysis

All tools follow the standard MCP tool pattern with proper error handling,
service integration, and response formatting.
"""

from .tools import BusinessTools

__all__ = ["BusinessTools"]