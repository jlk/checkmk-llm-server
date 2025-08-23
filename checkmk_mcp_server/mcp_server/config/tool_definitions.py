"""
Tool Definitions Configuration

This module contains the schema definitions and metadata for all MCP server tools.
Each tool category has its own section with input schemas, descriptions, and examples.

Optimized for LLM tool selection with enhanced descriptions, disambiguation guidance,
and "When to Use" context to minimize trial-and-error behavior.

Extracted from the monolithic server.py during Phase 1 refactoring.
This serves as the single source of truth for tool schemas that will be used
when the full tool extraction happens in later phases.
"""

from typing import Dict, Any

# Tool Selection Guidance for LLMs
TOOL_SELECTION_GUIDANCE = {
    "workflow_patterns": {
        "host_management": [
            "list_hosts (discover/search) → create_host/update_host/delete_host (modify) → activate changes",
            "get_host (inspect) → list_host_services (review services)"
        ],
        "service_operations": [
            "list_all_services (discover problems) → acknowledge_service_problem (suppress alerts) OR create_service_downtime (planned maintenance)"
        ],
        "parameter_management": [
            "get_effective_parameters (understand current) → discover_service_ruleset (find correct ruleset) → get_parameter_schema (understand options) → validate_service_parameters (check values) → set_service_parameters (apply changes)",
            "Alternative: get_specialized_defaults (get smart defaults) → validate_with_handler (domain validation) → set_service_parameters"
        ],
        "monitoring_analysis": [
            "get_health_dashboard (overview) → get_critical_problems (prioritize) → analyze_host_health (deep dive)"
        ],
        "event_investigation": [
            "get_recent_critical_events (immediate issues) → search_events (pattern analysis) → list_service_events/list_host_events (detailed history) → acknowledge_event (mark handled)"
        ],
        "performance_analysis": [
            "get_service_metrics (overview) → get_metric_history (detailed trends)"
        ]
    },
    "disambiguation_rules": {
        "when_multiple_tools_apply": {
            "listing_data": {
                "hosts": "Use list_hosts - for host discovery and management",
                "services_all": "Use list_all_services - for infrastructure-wide service overview",
                "services_per_host": "Use list_host_services - for host-specific service listing",
                "events_per_service": "Use list_service_events - for service-specific event history",
                "events_per_host": "Use list_host_events - for host-specific event history",
                "events_critical": "Use get_recent_critical_events - for urgent event overview"
            },
            "service_problems": {
                "known_issues": "Use acknowledge_service_problem - when you know the cause and are working on it",
                "planned_work": "Use create_service_downtime - for scheduled maintenance or expected outages"
            },
            "performance_data": {
                "service_overview": "Use get_service_metrics - for general performance graphs and multiple metrics",
                "specific_metric": "Use get_metric_history - for detailed analysis of one specific metric"
            },
            "system_status": {
                "overall_health": "Use get_health_dashboard - for infrastructure-wide status summary",
                "critical_issues": "Use get_critical_problems - for urgent problems requiring immediate attention",
                "host_specific": "Use analyze_host_health - for detailed analysis of one specific host"
            }
        }
    },
    "common_mistakes": {
        "parameter_management": "Always use get_effective_parameters BEFORE set_service_parameters to understand current state",
        "bulk_operations": "Use batch_create_hosts for multiple hosts, NOT repeated create_host calls",
        "event_vs_monitoring": "Event Console tools (list_*_events) show external events (logs, SNMP), not monitoring check results",
        "validation_first": "Always validate parameters with validate_service_parameters before applying with set_service_parameters"
    }
}

# Host Tools Schemas
HOST_TOOLS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "list_hosts": {
        "name": "list_hosts", 
        "description": "List hosts from Checkmk with filtering options. When to use: First step in host discovery, troubleshooting connectivity issues, or getting an overview of infrastructure. Use this when you need to find specific hosts or get a filtered list of hosts for further operations.",
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
        "description": "Create a new host in Checkmk for monitoring. When to use: Adding new infrastructure to monitoring, after physically deploying new servers or network devices. Prerequisites: Host must be reachable from Checkmk server, appropriate folder permissions required. Workflow: Create host → run service discovery → activate changes.",
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
        "description": "List services across all hosts with optional filtering by state and name patterns. When to use: Getting infrastructure-wide service overview, finding all services in WARNING/CRITICAL states, or identifying specific service types across the environment. Workflow: Use filters to narrow results → investigate specific problems → acknowledge or create downtimes as needed.",
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
        "description": "Acknowledge a service problem to suppress notifications and indicate issue is known. When to use: After identifying the root cause of a service problem, during planned maintenance, or to stop alert noise while working on a fix. Prerequisites: Service must be in WARNING/CRITICAL state. Workflow: Identify problem → acknowledge with descriptive comment → work on resolution → problem automatically clears when fixed.",
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
        "description": "Retrieve the actual monitoring parameters applied to a service, including inherited rules and computed values. When to use: Before modifying service parameters, troubleshooting monitoring thresholds, or understanding current service configuration. Prerequisites: Service must exist and have completed discovery. Workflow: Use this first to understand current settings → then modify with set_service_parameters if needed.",
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
        "description": "Configure monitoring parameters for a service by creating or updating parameter rules. When to use: Adjusting monitoring thresholds (CPU, memory, disk, temperature), customizing check intervals, or setting service-specific limits. Prerequisites: Service must exist, validate parameters first with validate_service_parameters. Workflow: Get current parameters → validate new values → set parameters → activate changes.",
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
        "description": "Get comprehensive infrastructure health dashboard with aggregated status metrics and key performance indicators. When to use: Getting overall system health overview, generating status reports, identifying infrastructure-wide trends or issues. Best for: Daily operational reviews, management reporting, identifying systemic problems across the monitoring environment.",
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
        "description": "Display chronological event history for a specific service from the Event Console. When to use: Investigating service problem patterns, analyzing event frequency, troubleshooting recurring issues. Prerequisites: Service must exist and generate events. Best for: Root cause analysis, understanding event patterns, correlating service problems with system events.", 
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
        "description": "Retrieve historical performance metrics and graph data for a specific service over a defined time period. When to use: Analyzing performance trends, investigating service slowdowns, capacity planning, creating performance reports. Prerequisites: Service must exist and collect performance data (CPU, memory, disk, network metrics). Best for: Performance analysis, trend identification, baseline establishment.",
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
        "description": "Create multiple hosts simultaneously using optimized batch processing with concurrent operations and progress tracking. When to use: Infrastructure automation, bulk host deployment, migrating from other monitoring systems, adding multiple similar hosts. Prerequisites: Valid host data array, appropriate folder permissions. Workflow: Prepare host list → validate data → batch create → activate changes.",
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

# Tool Selection Helper Functions
def get_workflow_guidance(task_type: str) -> str:
    """Get workflow guidance for common task types."""
    workflows = TOOL_SELECTION_GUIDANCE["workflow_patterns"]
    return workflows.get(task_type, "No specific workflow guidance available")

def get_disambiguation_help(category: str, subcategory: str = None) -> str:
    """Get help choosing between similar tools."""
    rules = TOOL_SELECTION_GUIDANCE["disambiguation_rules"]["when_multiple_tools_apply"]
    if category in rules:
        if subcategory and subcategory in rules[category]:
            return rules[category][subcategory]
        return str(rules[category])
    return "No disambiguation guidance available"

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