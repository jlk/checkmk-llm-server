"""Event management tools for the Checkmk MCP server.

This module contains all event-related MCP tools extracted from the main server.
"""

import logging
from typing import Any, Dict, Optional, List, TYPE_CHECKING
from mcp.types import Tool

if TYPE_CHECKING:
    pass  # Event service would be imported here

logger = logging.getLogger(__name__)


class EventTools:
    """Event management tools for MCP server."""
    
    def __init__(self, event_service=None, server=None):
        """Initialize event tools with required services.
        
        Args:
            event_service: Event service for event operations (optional for now)
            server: MCP server instance for service access
        """
        self.event_service = event_service
        self.server = server
        self._tool_handlers: Dict[str, Any] = {}
        self._tools: Dict[str, Tool] = {}
        
    def get_tools(self) -> Dict[str, Tool]:
        """Get all event tool definitions."""
        return self._tools.copy()
        
    def get_handlers(self) -> Dict[str, Any]:
        """Get all event tool handlers."""
        return self._tool_handlers.copy()
        
    def _get_service(self, service_name: str):
        """Helper to get service from server."""
        if self.server and hasattr(self.server, '_get_service'):
            return self.server._get_service(service_name)
        return None
        
    def register_tools(self) -> None:
        """Register all event tools and handlers."""
        from ...utils.errors import sanitize_error
        
        # List service events tool
        self._tools["list_service_events"] = Tool(
            name="list_service_events",
            description="Show event history for a specific service",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_name": {"type": "string", "description": "Service name"},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events",
                        "default": 100,
                    },
                    "state_filter": {
                        "type": "string",
                        "description": "Filter by state: ok, warning, critical, unknown",
                    },
                },
                "required": ["host_name", "service_name"],
            },
        )

        async def list_service_events(host_name, service_name, limit=100, state_filter=None):
            # Complex logic from original implementation would go here
            # For this extraction, we'll use a simplified version
            try:
                event_service = self._get_service("event")
                if not event_service:
                    return {
                        "success": False,
                        "error": "Event service not available"
                    }
                    
                result = await event_service.list_service_events(
                    host_name, service_name, limit, state_filter
                )

                if result.success:
                    events_data = []
                    if result.data:
                        for event in result.data:
                            events_data.append({
                                "event_id": event.event_id,
                                "host_name": event.host_name,
                                "service_description": event.service_description,
                                "text": event.text,
                                "state": event.state,
                                "phase": event.phase,
                                "first_time": event.first_time,
                                "last_time": event.last_time,
                                "count": event.count,
                                "comment": event.comment,
                            })
                    message = f"Found {len(events_data)} events for service {service_name} on host {host_name}"
                    if len(events_data) == 0:
                        message += ". Note: Event Console processes external events (syslog, SNMP traps, etc.) and is often empty in installations that only use active service monitoring."
                    return {
                        "success": True,
                        "data_source": "rest_api",
                        "events": events_data,
                        "count": len(events_data),
                        "message": message,
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error or "Event Console operation failed",
                        "data_source": "rest_api"
                    }
            except Exception as e:
                logger.exception(f"Error listing service events: {host_name}/{service_name}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["list_service_events"] = list_service_events

        # List host events tool
        self._tools["list_host_events"] = Tool(
            name="list_host_events",
            description="Show event history for a specific host",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events",
                        "default": 100,
                    },
                    "state_filter": {
                        "type": "string",
                        "description": "Filter by state: ok, warning, critical, unknown",
                    },
                },
                "required": ["host_name"],
            },
        )

        async def list_host_events(host_name, limit=100, state_filter=None):
            try:
                event_service = self._get_service("event")
                if not event_service:
                    return {
                        "success": False,
                        "error": "Event service not available"
                    }
                    
                result = await event_service.list_host_events(
                    host_name, limit, state_filter
                )

                if result.success:
                    events_data = []
                    if result.data:
                        for event in result.data:
                            events_data.append({
                                "event_id": event.event_id,
                                "host_name": event.host_name,
                                "service_description": event.service_description,
                                "text": event.text,
                                "state": event.state,
                                "phase": event.phase,
                                "first_time": event.first_time,
                                "last_time": event.last_time,
                                "count": event.count,
                            })
                    message = f"Found {len(events_data)} events for host {host_name}"
                    if len(events_data) == 0:
                        message += ". Note: Event Console is used for external events (syslog, SNMP traps, etc.) and is often empty in installations that only use active monitoring."
                    return {
                        "success": True,
                        "events": events_data,
                        "count": len(events_data),
                        "message": message,
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error or "Event Console operation failed",
                    }
            except Exception as e:
                logger.exception(f"Error listing host events: {host_name}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["list_host_events"] = list_host_events

        # Get recent critical events tool
        self._tools["get_recent_critical_events"] = Tool(
            name="get_recent_critical_events",
            description="Get recent critical events across all hosts",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events",
                        "default": 20,
                    }
                },
            },
        )

        async def get_recent_critical_events(limit=20):
            try:
                event_service = self._get_service("event")
                if not event_service:
                    return {
                        "success": False,
                        "error": "Event service not available"
                    }
                    
                result = await event_service.get_recent_critical_events(limit)

                if result.success:
                    events_data = []
                    if result.data:
                        for event in result.data:
                            events_data.append({
                                "event_id": event.event_id,
                                "host_name": event.host_name,
                                "service_description": event.service_description,
                                "text": event.text,
                                "state": event.state,
                                "phase": event.phase,
                                "first_time": event.first_time,
                                "last_time": event.last_time,
                                "count": event.count,
                            })
                    message = f"Found {len(events_data)} critical events"
                    if len(events_data) == 0:
                        message += ". Note: Event Console processes external events (syslog, SNMP traps, etc.) and is often empty if not configured for log processing."
                    return {
                        "success": True,
                        "critical_events": events_data,
                        "count": len(events_data),
                        "message": message,
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error or "Event Console operation failed",
                    }
            except Exception as e:
                logger.exception("Error getting recent critical events")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["get_recent_critical_events"] = get_recent_critical_events

        # Acknowledge event tool
        self._tools["acknowledge_event"] = Tool(
            name="acknowledge_event",
            description="Acknowledge an event in the Event Console",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID"},
                    "comment": {
                        "type": "string",
                        "description": "Comment for acknowledgment",
                    },
                    "contact": {"type": "string", "description": "Contact name"},
                    "site_id": {"type": "string", "description": "Site ID"},
                },
                "required": ["event_id", "comment"],
            },
        )

        async def acknowledge_event(event_id, comment, contact=None, site_id=None):
            try:
                event_service = self._get_service("event")
                if not event_service:
                    return {
                        "success": False,
                        "error": "Event service not available"
                    }
                    
                result = await event_service.acknowledge_event(
                    event_id, comment, contact, site_id
                )

                if result.success:
                    return {
                        "success": True,
                        "message": f"Event {event_id} acknowledged successfully",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error or "Event Console operation failed",
                    }
            except Exception as e:
                logger.exception(f"Error acknowledging event: {event_id}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["acknowledge_event"] = acknowledge_event

        # Search events tool
        self._tools["search_events"] = Tool(
            name="search_events",
            description="Search events by text content",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Text to search for",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events",
                        "default": 50,
                    },
                    "state_filter": {
                        "type": "string",
                        "description": "Filter by state: ok, warning, critical, unknown",
                    },
                    "host_filter": {
                        "type": "string",
                        "description": "Filter by host name",
                    },
                },
                "required": ["search_term"],
            },
        )

        async def search_events(
            search_term, limit=50, state_filter=None, host_filter=None
        ):
            try:
                event_service = self._get_service("event")
                if not event_service:
                    return {
                        "success": False,
                        "error": "Event service not available"
                    }
                    
                result = await event_service.search_events(
                    search_term, limit, state_filter, host_filter
                )

                if result.success:
                    events_data = []
                    if result.data:
                        for event in result.data:
                            events_data.append({
                                "event_id": event.event_id,
                                "host_name": event.host_name,
                                "service_description": event.service_description,
                                "text": event.text,
                                "state": event.state,
                                "phase": event.phase,
                                "first_time": event.first_time,
                                "last_time": event.last_time,
                                "count": event.count,
                            })
                    message = f"Found {len(events_data)} events matching '{search_term}'"
                    if len(events_data) == 0:
                        message += ". Note: Event Console searches external events (logs, SNMP traps, etc.) and is often empty in monitoring-only installations."
                    return {
                        "success": True,
                        "events": events_data,
                        "count": len(events_data),
                        "search_term": search_term,
                        "message": message,
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error or "Event Console operation failed",
                    }
            except Exception as e:
                logger.exception(f"Error searching events: {search_term}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["search_events"] = search_events