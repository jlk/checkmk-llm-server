"""
MCP Server Configuration Package

This package contains configuration definitions and schemas for the MCP server.

Modules:
    tool_definitions: Tool schema definitions, parameter specifications, and documentation
    - Future configuration modules will be added here in later phases

This module is part of the Phase 1 refactoring to modularize the monolithic
MCP server implementation.
"""

# Import configuration definitions
from .tool_definitions import (
    ALL_TOOL_SCHEMAS,
    TOOL_CATEGORIES,
    HOST_TOOLS_SCHEMAS,
    SERVICE_TOOLS_SCHEMAS,
    PARAMETER_TOOLS_SCHEMAS,
    STATUS_TOOLS_SCHEMAS,
    EVENT_TOOLS_SCHEMAS,
    METRICS_TOOLS_SCHEMAS,
    ADVANCED_TOOLS_SCHEMAS,
    validate_tool_definitions,
)

__all__ = [
    "ALL_TOOL_SCHEMAS",
    "TOOL_CATEGORIES",
    "HOST_TOOLS_SCHEMAS",
    "SERVICE_TOOLS_SCHEMAS", 
    "PARAMETER_TOOLS_SCHEMAS",
    "STATUS_TOOLS_SCHEMAS",
    "EVENT_TOOLS_SCHEMAS",
    "METRICS_TOOLS_SCHEMAS",
    "ADVANCED_TOOLS_SCHEMAS",
    "validate_tool_definitions",
]