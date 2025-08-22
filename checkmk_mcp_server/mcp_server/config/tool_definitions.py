"""
Tool Definitions Configuration

This module contains the schema definitions and metadata for all MCP server tools.
Each tool category has its own section with input schemas, descriptions, and examples.

Extracted from the monolithic server.py during Phase 1 refactoring.
This serves as the single source of truth for tool schemas that will be used
when the full tool extraction happens in later phases.
"""

from typing import Dict, Any

# Host Tools Schemas
HOST_TOOLS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "list_hosts": {
        "name": "list_hosts", 
        "description": "List Checkmk hosts with optional filtering",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Search pattern for host names",
                },
                "folder": {
                    "type": "string", 
                    "description": "Filter by Checkmk folder path",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of hosts to return",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 100,
                },
            },
        },
    },
    "create_host": {
        "name": "create_host",
        "description": "Create a new Checkmk host",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host_name": {
                    "type": "string",
                    "description": "Name of the host to create",
                },
                "folder": {
                    "type": "string",
                    "description": "Folder path where to create the host",
                    "default": "/",
                },
                "alias": {
                    "type": "string", 
                    "description": "Human-readable alias for the host",
                },
                "ip_address": {
                    "type": "string",
                    "description": "IP address of the host",
                },
            },
            "required": ["host_name"],
        },
    },
    # Additional host tool schemas will be defined here
}

# Service Tools Schemas
SERVICE_TOOLS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "list_all_services": {
        "name": "list_all_services",
        "description": "List all services across all hosts with optional filtering",
        "inputSchema": {
            "type": "object", 
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Filter services for specific host",
                },
                "service": {
                    "type": "string",
                    "description": "Filter by service name pattern",
                },
                "state": {
                    "type": "string",
                    "enum": ["OK", "WARNING", "CRITICAL", "UNKNOWN"],
                    "description": "Filter by service state",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of services to return",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 100,
                },
            },
        },
    },
    "acknowledge_service_problem": {
        "name": "acknowledge_service_problem", 
        "description": "Acknowledge a service problem",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host_name": {
                    "type": "string",
                    "description": "Host name where service is running",
                },
                "service_name": {
                    "type": "string",
                    "description": "Service name to acknowledge",
                },
                "comment": {
                    "type": "string", 
                    "description": "Comment for the acknowledgment",
                },
                "sticky": {
                    "type": "boolean",
                    "description": "Make acknowledgment sticky",
                    "default": False,
                },
            },
            "required": ["host_name", "service_name", "comment"],
        },
    },
    # Additional service tool schemas will be defined here
}

# Parameter Tools Schemas  
PARAMETER_TOOLS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "get_effective_parameters": {
        "name": "get_effective_parameters",
        "description": "Get effective parameters for a service",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host_name": {
                    "type": "string",
                    "description": "Name of the host",
                },
                "service_name": {
                    "type": "string",
                    "description": "Name of the service",
                },
            },
            "required": ["host_name", "service_name"],
        },
    },
    "set_service_parameters": {
        "name": "set_service_parameters", 
        "description": "Set parameters for a service using intelligent rule creation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host_name": {
                    "type": "string",
                    "description": "Name of the host",
                },
                "service_name": {
                    "type": "string", 
                    "description": "Name of the service",
                },
                "parameters": {
                    "type": "object",
                    "description": "Parameters to set (will be validated against service type)",
                },
            },
            "required": ["host_name", "service_name", "parameters"],
        },
    },
    # Additional parameter tool schemas will be defined here
}

# Status Tools Schemas
STATUS_TOOLS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "get_health_dashboard": {
        "name": "get_health_dashboard",
        "description": "Get comprehensive health dashboard with system metrics",
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_services": {
                    "type": "boolean",
                    "description": "Include service statistics",
                    "default": True,
                },
                "include_hosts": {
                    "type": "boolean", 
                    "description": "Include host statistics",
                    "default": True,
                },
            },
        },
    },
    # Additional status tool schemas will be defined here
}

# Event Tools Schemas
EVENT_TOOLS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "list_service_events": {
        "name": "list_service_events",
        "description": "List service events from Event Console", 
        "inputSchema": {
            "type": "object",
            "properties": {
                "host_name": {
                    "type": "string",
                    "description": "Filter events for specific host",
                },
                "service_name": {
                    "type": "string",
                    "description": "Filter events for specific service",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of events to return",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 100,
                },
            },
        },
    },
    # Additional event tool schemas will be defined here
}

# Metrics Tools Schemas
METRICS_TOOLS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "get_service_metrics": {
        "name": "get_service_metrics",
        "description": "Get performance metrics for a service",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host_name": {
                    "type": "string",
                    "description": "Name of the host",
                },
                "service_name": {
                    "type": "string",
                    "description": "Name of the service",
                },
                "timeframe": {
                    "type": "string", 
                    "enum": ["1h", "4h", "24h", "7d", "30d"],
                    "description": "Timeframe for metrics",
                    "default": "1h",
                },
            },
            "required": ["host_name", "service_name"],
        },
    },
    # Additional metrics tool schemas will be defined here
}

# Advanced Tools Schemas
ADVANCED_TOOLS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "batch_create_hosts": {
        "name": "batch_create_hosts",
        "description": "Create multiple hosts in a single operation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hosts": {
                    "type": "array",
                    "description": "List of hosts to create",
                    "items": {
                        "type": "object",
                        "properties": {
                            "host_name": {"type": "string"},
                            "folder": {"type": "string", "default": "/"},
                            "alias": {"type": "string"},
                            "ip_address": {"type": "string"},
                        },
                        "required": ["host_name"],
                    },
                },
            },
            "required": ["hosts"],
        },
    },
    # Additional advanced tool schemas will be defined here
}

# All tool schemas combined
ALL_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    **HOST_TOOLS_SCHEMAS,
    **SERVICE_TOOLS_SCHEMAS, 
    **PARAMETER_TOOLS_SCHEMAS,
    **STATUS_TOOLS_SCHEMAS,
    **EVENT_TOOLS_SCHEMAS,
    **METRICS_TOOLS_SCHEMAS,
    **ADVANCED_TOOLS_SCHEMAS,
}

# Tool categories for organization
TOOL_CATEGORIES = {
    "host_tools": list(HOST_TOOLS_SCHEMAS.keys()),
    "service_tools": list(SERVICE_TOOLS_SCHEMAS.keys()),
    "parameter_tools": list(PARAMETER_TOOLS_SCHEMAS.keys()),
    "status_tools": list(STATUS_TOOLS_SCHEMAS.keys()),
    "event_tools": list(EVENT_TOOLS_SCHEMAS.keys()),
    "metrics_tools": list(METRICS_TOOLS_SCHEMAS.keys()),
    "advanced_tools": list(ADVANCED_TOOLS_SCHEMAS.keys()),
}

# Validate that all tools are accounted for
def validate_tool_definitions() -> bool:
    """
    Validate that tool definitions are consistent and complete.
    
    Returns:
        True if all definitions are valid
    """
    for category, tools in TOOL_CATEGORIES.items():
        for tool_name in tools:
            if tool_name not in ALL_TOOL_SCHEMAS:
                return False
            
            schema = ALL_TOOL_SCHEMAS[tool_name]
            if "name" not in schema or "description" not in schema:
                return False
                
    return True