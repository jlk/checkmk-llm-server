"""Host management tools for the Checkmk MCP server.

This module contains all host-related MCP tools extracted from the main server.
"""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING
from mcp.types import Tool

if TYPE_CHECKING:
    from ...services.host_service import HostService
    from ...services.service_service import ServiceService

logger = logging.getLogger(__name__)


class HostTools:
    """Host management tools for MCP server."""
    
    def __init__(self, host_service: "HostService", service_service: "ServiceService"):
        """Initialize host tools with required services.
        
        Args:
            host_service: Host service for host operations
            service_service: Service service for host services listing
        """
        self.host_service = host_service
        self.service_service = service_service
        self._tool_handlers: Dict[str, Any] = {}
        self._tools: Dict[str, Tool] = {}
        
    def get_tools(self) -> Dict[str, Tool]:
        """Get all host tool definitions."""
        return self._tools.copy()
        
    def get_handlers(self) -> Dict[str, Any]:
        """Get all host tool handlers."""
        return self._tool_handlers.copy()
        
    def register_tools(self) -> None:
        """Register all host tools and handlers."""
        from ...utils.errors import sanitize_error
        
        # List hosts tool
        self._tools["list_hosts"] = Tool(
            name="list_hosts",
            description="List hosts from Checkmk with filtering options. When to use: First step in host discovery, troubleshooting connectivity issues, or getting an overview of infrastructure. Use this when you need to find specific hosts or get a filtered list of hosts for further operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Search pattern for host names",
                    },
                    "folder": {
                        "type": "string",
                        "description": "Folder path to filter hosts",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of hosts to return",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Starting index for pagination",
                        "default": 0,
                    },
                    "include_status": {
                        "type": "boolean",
                        "description": "Whether to include status information",
                        "default": False,
                    },
                    "effective_attributes": {
                        "type": "boolean",
                        "description": "Include inherited folder attributes and computed parameters (permissions enforced by Checkmk server)",
                        "default": False,
                    },
                },
            },
        )

        async def list_hosts(
            search=None,
            folder=None,
            limit=None,
            offset=0,
            include_status=False,
            effective_attributes=False,
        ):
            try:
                result = await self.host_service.list_hosts(
                    search=search,
                    folder=folder,
                    limit=limit,
                    offset=offset,
                    include_status=include_status,
                    effective_attributes=effective_attributes,
                )
                if result.success:
                    return {
                        "success": True,
                        "data": result.data.model_dump() if result.data else {},
                        "message": f"Retrieved {result.data.total_count if result.data else 0} hosts",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "warnings": result.warnings,
                    }
            except Exception as e:
                logger.exception(
                    f"Error listing hosts: search={search}, folder={folder}"
                )
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["list_hosts"] = list_hosts

        # Create host tool
        self._tools["create_host"] = Tool(
            name="create_host",
            description="Create a new host in Checkmk for monitoring. When to use: Adding new infrastructure to monitoring, after physically deploying new servers or network devices. Prerequisites: Host must be reachable from Checkmk server, appropriate folder permissions required. Workflow: Create host → run service discovery → activate changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Host name"},
                    "folder": {
                        "type": "string",
                        "description": "Checkmk folder path",
                        "default": "/",
                    },
                    "ip_address": {"type": "string", "description": "Host IP address"},
                    "attributes": {
                        "type": "object",
                        "description": "Host attributes dictionary",
                    },
                    "labels": {
                        "type": "object",
                        "description": "Host labels dictionary",
                    },
                },
                "required": ["name"],
            },
        )

        async def create_host(
            name, folder="/", ip_address=None, attributes=None, labels=None
        ):
            try:
                result = await self.host_service.create_host(
                    name=name,
                    folder=folder,
                    ip_address=ip_address,
                    attributes=attributes,
                    labels=labels,
                )
                if result.success:
                    return {
                        "success": True,
                        "data": result.data.model_dump() if result.data else {},
                        "message": f"Successfully created host {name}",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "warnings": result.warnings,
                    }
            except Exception as e:
                logger.exception(f"Error creating host: {name}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["create_host"] = create_host

        # Get host tool
        self._tools["get_host"] = Tool(
            name="get_host",
            description="Get detailed configuration and status information about a specific host. When to use: Investigating host-specific issues, reviewing host configuration before making changes, or checking host attributes and labels. Prerequisites: Host name must exist in Checkmk.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Host name"},
                    "include_status": {
                        "type": "boolean",
                        "description": "Whether to include status information",
                        "default": True,
                    },
                    "effective_attributes": {
                        "type": "boolean",
                        "description": "Include inherited folder attributes and computed parameters (permissions enforced by Checkmk server)",
                        "default": False,
                    },
                },
                "required": ["name"],
            },
        )

        async def get_host(name, include_status=True, effective_attributes=False):
            try:
                result = await self.host_service.get_host(
                    name=name,
                    include_status=include_status,
                    effective_attributes=effective_attributes,
                )
                if result.success:
                    return {
                        "success": True,
                        "data": result.data.model_dump() if result.data else {},
                        "message": f"Retrieved details for host {name}",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "warnings": result.warnings,
                    }
            except Exception as e:
                logger.exception(f"Error getting host: {name}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["get_host"] = get_host

        # Update host tool
        self._tools["update_host"] = Tool(
            name="update_host",
            description="Modify configuration of an existing host including IP address, folder location, attributes, and labels. When to use: Host has moved to different network segment, changing host attributes, or relocating host to different folder. Prerequisites: Host must exist, appropriate permissions for target folder. Workflow: Get current host info → make changes → activate changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Host name"},
                    "folder": {"type": "string", "description": "New folder path"},
                    "ip_address": {"type": "string", "description": "New IP address"},
                    "attributes": {
                        "type": "object",
                        "description": "Updated attributes",
                    },
                    "labels": {"type": "object", "description": "Updated labels"},
                    "etag": {
                        "type": "string",
                        "description": "ETag for optimistic locking",
                    },
                },
                "required": ["name"],
            },
        )

        async def update_host(
            name, folder=None, ip_address=None, attributes=None, labels=None, etag=None
        ):
            try:
                result = await self.host_service.update_host(
                    name=name,
                    folder=folder,
                    ip_address=ip_address,
                    attributes=attributes,
                    labels=labels,
                    etag=etag,
                )
                if result.success:
                    return {
                        "success": True,
                        "data": result.data.model_dump() if result.data else {},
                        "message": f"Successfully updated host {name}",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "warnings": result.warnings,
                    }
            except Exception as e:
                logger.exception(f"Error updating host: {name}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["update_host"] = update_host

        # Delete host tool
        self._tools["delete_host"] = Tool(
            name="delete_host",
            description="Remove a host completely from Checkmk monitoring. When to use: Hardware decommissioned, server permanently offline, or cleaning up test/temporary hosts. WARNING: This removes all historical data and cannot be undone. Prerequisites: Confirm host is no longer needed, backup historical data if required.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Host name to delete"}
                },
                "required": ["name"],
            },
        )

        async def delete_host(name):
            try:
                result = await self.host_service.delete_host(name=name)
                if result.success:
                    return {
                        "success": True,
                        "data": result.data.model_dump() if result.data else {},
                        "message": f"Successfully deleted host {name}",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "warnings": result.warnings,
                    }
            except Exception as e:
                logger.exception(f"Error deleting host: {name}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["delete_host"] = delete_host

        # List host services tool
        self._tools["list_host_services"] = Tool(
            name="list_host_services",
            description="List all monitored services for a specific host with current status. When to use: Investigating host-specific service problems, getting overview of services on a particular host, or before making service-level changes. Prerequisites: Host must exist and have completed service discovery.",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Name of the host"},
                    "include_downtimes": {
                        "type": "boolean",
                        "description": "Include downtime information",
                        "default": False,
                    },
                    "include_acknowledged": {
                        "type": "boolean",
                        "description": "Include acknowledgment information",
                        "default": False,
                    },
                },
                "required": ["host_name"],
            },
        )

        async def list_host_services(
            host_name, include_downtimes=False, include_acknowledged=False
        ):
            try:
                # Note: include_downtimes and include_acknowledged are accepted by tool but not used by service
                # This maintains backward compatibility with tool schema
                result = await self.service_service.list_host_services(
                    host_name=host_name
                )
                if result.success:
                    total_count = result.data.total_count if result.data else 0
                    return {
                        "success": True,
                        "data": result.data.model_dump() if result.data else {},
                        "message": f"Retrieved {total_count} services for host {host_name}",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "warnings": result.warnings,
                    }
            except Exception as e:
                logger.exception(f"Error listing host services: {host_name}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["list_host_services"] = list_host_services