"""Monitoring and status tools for the Checkmk MCP server.

This package contains all tools related to system monitoring and status operations including:
- Health dashboard and system overview
- Critical problems identification 
- Host health analysis and recommendations
- Status monitoring and reporting

All tools follow the standard MCP tool pattern with proper error handling,
service integration, and response formatting.
"""

from .tools import MonitoringTools

__all__ = ["MonitoringTools"]