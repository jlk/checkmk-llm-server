"""Service management tools for the Checkmk MCP server.

This module contains all service-related MCP tools extracted from the main server.
"""

import logging
from typing import Any, Dict, Optional, List, TYPE_CHECKING
from mcp.types import Tool

if TYPE_CHECKING:
    from ...services.service_service import ServiceService

logger = logging.getLogger(__name__)


class ServiceTools:
    """Service management tools for MCP server."""
    
    def __init__(self, service_service: "ServiceService"):
        """Initialize service tools with required services.
        
        Args:
            service_service: Service service for service operations
        """
        self.service_service = service_service
        self._tool_handlers: Dict[str, Any] = {}
        self._tools: Dict[str, Tool] = {}
        
    def get_tools(self) -> Dict[str, Tool]:
        """Get all service tool definitions."""
        return self._tools.copy()
        
    def get_handlers(self) -> Dict[str, Any]:
        """Get all service tool handlers."""
        return self._tool_handlers.copy()
        
    def register_tools(self) -> None:
        """Register all service tools and handlers."""
        from ...utils.errors import sanitize_error
        # Import ServiceState from the correct location
        try:
            from ...models.service_models import ServiceState
        except ImportError:
            # Fallback for testing - define a simple enum
            from enum import Enum
            class ServiceState(Enum):
                OK = "OK"
                WARNING = "WARNING" 
                CRITICAL = "CRITICAL"
                UNKNOWN = "UNKNOWN"
        
        # List all services tool
        self._tools["list_all_services"] = Tool(
            name="list_all_services",
            description="List services across all hosts with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Search pattern for service names",
                    },
                    "state_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by service states (OK, WARNING, CRITICAL, UNKNOWN)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of services to return",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Starting index for pagination",
                        "default": 0,
                    },
                },
            },
        )

        async def list_all_services(
            search=None, state_filter=None, limit=None, offset=0
        ):
            try:

                # Convert string states to enum values
                if state_filter:
                    state_enum_filter = []
                    for state in state_filter:
                        try:
                            state_enum_filter.append(ServiceState[state.upper()])
                        except KeyError:
                            pass
                else:
                    state_enum_filter = None

                # Note: search and offset are not supported by the service layer
                # Use host_filter as search pattern if provided
                result = await self.service_service.list_all_services(
                    host_filter=search, state_filter=state_enum_filter, limit=limit
                )
                if result.success:
                    total_count = result.data.total_count if result.data else 0
                    return {
                        "success": True,
                        "data": result.data.model_dump() if result.data else {},
                        "message": f"Retrieved {total_count} services",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "warnings": result.warnings,
                    }
            except Exception as e:
                logger.exception(f"Error listing all services: search={search}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["list_all_services"] = list_all_services

        # Acknowledge service problem tool
        self._tools["acknowledge_service_problem"] = Tool(
            name="acknowledge_service_problem",
            description="Acknowledge a service problem to suppress notifications and indicate issue is known. When to use: After identifying the root cause of a service problem, during planned maintenance, or to stop alert noise while working on a fix. Prerequisites: Service must be in WARNING/CRITICAL state. Workflow: Identify problem → acknowledge with descriptive comment → work on resolution → problem automatically clears when fixed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_name": {"type": "string", "description": "Service name"},
                    "comment": {
                        "type": "string",
                        "description": "Acknowledgment comment",
                    },
                    "sticky": {
                        "type": "boolean",
                        "description": "Whether acknowledgment persists after recovery",
                        "default": False,
                    },
                    "notify": {
                        "type": "boolean",
                        "description": "Whether to send notifications",
                        "default": True,
                    },
                    "persistent": {
                        "type": "boolean",
                        "description": "Whether acknowledgment survives restarts",
                        "default": False,
                    },
                    "expire_on": {
                        "type": "string",
                        "description": "Expiration time as ISO timestamp (Checkmk 2.4+)",
                    },
                },
                "required": ["host_name", "service_name", "comment"],
            },
        )

        async def acknowledge_service_problem(
            host_name,
            service_name,
            comment,
            sticky=False,
            notify=True,
            persistent=False,
            expire_on=None,
        ):
            try:
                result = await self.service_service.acknowledge_problem(
                    host_name=host_name,
                    service_name=service_name,
                    comment=comment,
                    sticky=sticky,
                    notify=notify,
                    persistent=persistent,
                )
                if result.success:
                    return {
                        "success": True,
                        "data": result.data.model_dump() if result.data else {},
                        "message": f"Acknowledged problem for {service_name} on {host_name}",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "warnings": result.warnings,
                    }
            except Exception as e:
                logger.exception(
                    f"Error acknowledging service problem: {host_name}/{service_name}"
                )
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["acknowledge_service_problem"] = acknowledge_service_problem

        # Create service downtime tool
        self._tools["create_service_downtime"] = Tool(
            name="create_service_downtime",
            description="Schedule planned downtime for a service to suppress notifications during maintenance windows. When to use: Before planned maintenance, system updates, or expected service unavailability. Prerequisites: Service must exist in Checkmk. Workflow: Schedule downtime before maintenance → perform maintenance → downtime automatically expires or can be cancelled early.",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_name": {"type": "string", "description": "Service name"},
                    "start_time": {
                        "type": "string",
                        "description": "Start time (ISO format or 'now')",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time (ISO format)",
                    },
                    "comment": {"type": "string", "description": "Downtime comment"},
                    "duration_hours": {
                        "type": "number",
                        "description": "Duration in hours (alternative to end_time)",
                    },
                    "recur": {"type": "string", "description": "Recurrence rule"},
                },
                "required": ["host_name", "service_name", "comment"],
            },
        )

        async def create_service_downtime(
            host_name,
            service_name,
            comment,
            start_time=None,
            end_time=None,
            duration_hours=None,
            recur=None,
        ):
            try:
                # Default duration to 1 hour if not provided
                if duration_hours is None:
                    duration_hours = 1.0
                elif not isinstance(duration_hours, (int, float)):
                    duration_hours = float(duration_hours)
                
                result = await self.service_service.create_downtime(
                    host_name=host_name,
                    service_name=service_name,
                    comment=comment,
                    start_time=start_time,
                    duration_hours=float(duration_hours),
                )
                if result.success:
                    return {
                        "success": True,
                        "data": result.data.model_dump() if result.data else {},
                        "message": f"Created downtime for {service_name} on {host_name}",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "warnings": result.warnings,
                    }
            except Exception as e:
                logger.exception(
                    f"Error creating service downtime: {host_name}/{service_name}"
                )
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["create_service_downtime"] = create_service_downtime