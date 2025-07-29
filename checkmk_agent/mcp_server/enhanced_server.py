"""Enhanced MCP Server implementation with advanced features."""

import logging
import asyncio
import json
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime

from mcp.server import Server
from mcp.types import (
    Resource, TextContent, EmbeddedResource, Tool,
    Prompt, PromptMessage, CallToolResult
)
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel.server import NotificationOptions

from ..config import AppConfig
from ..async_api_client import AsyncCheckmkClient
from ..services import HostService, StatusService, ServiceService, ParameterService
from ..services.event_service import EventService
from ..services.metrics_service import MetricsService
from ..services.bi_service import BIService
from ..services.streaming import StreamingHostService, StreamingServiceService
from ..services.cache import CachedHostService
from ..services.metrics import MetricsMixin, get_metrics_collector
from ..services.recovery import RecoveryMixin
from ..services.batch import BatchProcessor, BatchOperationsMixin


logger = logging.getLogger(__name__)


class MCPJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime, Decimal, and Enum objects."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif hasattr(obj, 'model_dump'):
            return obj.model_dump()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


def safe_json_dumps(obj):
    """Safely serialize object to JSON, handling datetime and other non-serializable types."""
    try:
        return json.dumps(obj, cls=MCPJSONEncoder, ensure_ascii=False)
    except Exception as e:
        # Fallback: convert to string representation
        return json.dumps({"error": f"Serialization failed: {str(e)}", "data": str(obj)})


class EnhancedCheckmkMCPServer:
    """Enhanced Checkmk MCP Server with advanced features."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.server = Server("checkmk-agent-enhanced")
        self.checkmk_client: Optional[AsyncCheckmkClient] = None
        
        # Standard services
        self.host_service: Optional[HostService] = None
        self.status_service: Optional[StatusService] = None
        self.service_service: Optional[ServiceService] = None
        self.parameter_service: Optional[ParameterService] = None
        self.event_service: Optional[EventService] = None
        self.metrics_service: Optional[MetricsService] = None
        self.bi_service: Optional[BIService] = None
        
        # Enhanced services
        self.streaming_host_service: Optional[StreamingHostService] = None
        self.streaming_service_service: Optional[StreamingServiceService] = None
        self.cached_host_service: Optional[CachedHostService] = None
        
        # Advanced features
        self.batch_processor = BatchProcessor()
        
        # Tool definitions
        self._tools = {}
        self._tool_handlers = {}
        
        # Register handlers
        self._register_handlers()
        self._register_tool_handlers()
        self._register_advanced_resources()
    
    def _register_handlers(self):
        """Register standard MCP server handlers."""
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available MCP resources including streaming and performance data."""
            basic_resources = [
                Resource(
                    uri="checkmk://dashboard/health",
                    name="Health Dashboard",
                    description="Real-time infrastructure health dashboard",
                    mimeType="application/json"
                ),
                Resource(
                    uri="checkmk://dashboard/problems",
                    name="Critical Problems",
                    description="Current critical problems across infrastructure",
                    mimeType="application/json"
                ),
                Resource(
                    uri="checkmk://hosts/status",
                    name="Host Status Overview",
                    description="Current status of all monitored hosts",
                    mimeType="application/json"
                ),
                Resource(
                    uri="checkmk://services/problems",
                    name="Service Problems",
                    description="Current service problems requiring attention",
                    mimeType="application/json"
                ),
                Resource(
                    uri="checkmk://metrics/performance",
                    name="Performance Metrics",
                    description="Real-time performance metrics and trends",
                    mimeType="application/json"
                )
            ]
            
            # Add streaming resources
            streaming_resources = [
                Resource(
                    uri="checkmk://stream/hosts",
                    name="Host Stream",
                    description="Streaming host data for large environments",
                    mimeType="application/x-ndjson"
                ),
                Resource(
                    uri="checkmk://stream/services",
                    name="Service Stream", 
                    description="Streaming service data for large environments",
                    mimeType="application/x-ndjson"
                ),
                Resource(
                    uri="checkmk://metrics/server",
                    name="Server Metrics",
                    description="MCP server performance metrics",
                    mimeType="application/json"
                ),
                Resource(
                    uri="checkmk://cache/stats",
                    name="Cache Statistics",
                    description="Cache performance and statistics",
                    mimeType="application/json"
                )
            ]
            
            return basic_resources + streaming_resources
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read MCP resource content including advanced features."""
            if not self._ensure_services():
                raise RuntimeError("Services not initialized")
            
            try:
                # Standard resources
                if uri == "checkmk://dashboard/health":
                    result = await self.status_service.get_health_dashboard()
                    return self._handle_service_result(result)
                
                elif uri == "checkmk://dashboard/problems":
                    result = await self.status_service.get_critical_problems()
                    return self._handle_service_result(result)
                
                elif uri == "checkmk://hosts/status":
                    result = await self.host_service.list_hosts(include_status=True)
                    return self._handle_service_result(result)
                
                elif uri == "checkmk://services/problems":
                    from ..services.models.services import ServiceState
                    result = await self.service_service.list_all_services(
                        state_filter=[ServiceState.WARNING, ServiceState.CRITICAL, ServiceState.UNKNOWN]
                    )
                    return self._handle_service_result(result)
                
                elif uri == "checkmk://metrics/performance":
                    result = await self.status_service.get_performance_metrics()
                    return self._handle_service_result(result)
                
                # Streaming resources
                elif uri == "checkmk://stream/hosts":
                    return await self._stream_hosts_resource()
                
                elif uri == "checkmk://stream/services":
                    return await self._stream_services_resource()
                
                # Advanced metrics
                elif uri == "checkmk://metrics/server":
                    stats = await get_metrics_collector().get_stats()
                    return safe_json_dumps(stats)
                
                elif uri == "checkmk://cache/stats":
                    if self.cached_host_service:
                        cache_stats = await self.cached_host_service.get_cache_stats()
                        return safe_json_dumps(cache_stats)
                    else:
                        return safe_json_dumps({"error": "Cache not enabled"})
                
                else:
                    raise ValueError(f"Unknown resource URI: {uri}")
            
            except Exception as e:
                logger.exception(f"Error reading resource {uri}")
                raise RuntimeError(f"Failed to read resource {uri}: {str(e)}")
    
    def _register_tool_handlers(self):
        """Register MCP tool handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available MCP tools."""
            return list(self._tools.values())
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """Handle MCP tool calls."""
            if not self._ensure_services():
                raise RuntimeError("Services not initialized")
            
            handler = self._tool_handlers.get(name)
            if not handler:
                raise ValueError(f"Unknown tool: {name}")
            
            try:
                result = await handler(**arguments)
                # Return raw dict to avoid MCP framework tuple construction bug
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": safe_json_dumps(result),
                            "annotations": None,
                            "meta": None
                        }
                    ],
                    "isError": False,
                    "meta": None,
                    "structuredContent": None
                }
            except Exception as e:
                logger.exception(f"Error calling tool {name}")
                # Return raw dict for error case too
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": str(e),
                            "annotations": None,
                            "meta": None
                        }
                    ],
                    "isError": True,
                    "meta": None,
                    "structuredContent": None
                }
    
    def _register_advanced_resources(self):
        """Register advanced resource handlers."""
        pass  # Resources are handled in the main read_resource handler
    
    def _register_all_tools(self):
        """Register all tools including standard and advanced."""
        # First register all standard tools
        self._register_host_tools()
        self._register_service_tools()
        self._register_status_tools()
        self._register_parameter_tools()
        self._register_event_console_tools()
        self._register_metrics_tools()
        self._register_bi_tools()
        
        # Then register advanced tools
        self._register_advanced_tools()
    
    def _register_host_tools(self):
        """Register host operation tools - same as basic server."""
        # List hosts tool
        self._tools["list_hosts"] = Tool(
            name="list_hosts",
            description="List Checkmk hosts with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Search pattern for host names"},
                    "folder": {"type": "string", "description": "Filter by Checkmk folder path"},
                    "limit": {"type": "integer", "description": "Maximum number of hosts to return"},
                    "offset": {"type": "integer", "description": "Starting index for pagination", "default": 0},
                    "include_status": {"type": "boolean", "description": "Whether to include status information", "default": False}
                }
            }
        )
        
        async def list_hosts(search=None, folder=None, limit=None, offset=0, include_status=False):
            result = await self.host_service.list_hosts(
                search=search, folder=folder, limit=limit, offset=offset, include_status=include_status
            )
            if result.success:
                return {"success": True, "data": result.data.model_dump(), "message": f"Retrieved {result.data.total_count} hosts"}
            else:
                return {"success": False, "error": result.error, "warnings": result.warnings}
        
        self._tool_handlers["list_hosts"] = list_hosts
        
        # Create host tool
        self._tools["create_host"] = Tool(
            name="create_host",
            description="Create a new host in Checkmk",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Host name"},
                    "folder": {"type": "string", "description": "Checkmk folder path", "default": "/"},
                    "ip_address": {"type": "string", "description": "Host IP address"},
                    "attributes": {"type": "object", "description": "Host attributes dictionary"},
                    "labels": {"type": "object", "description": "Host labels dictionary"}
                },
                "required": ["name"]
            }
        )
        
        async def create_host(name, folder="/", ip_address=None, attributes=None, labels=None):
            result = await self.host_service.create_host(
                name=name, folder=folder, ip_address=ip_address, attributes=attributes, labels=labels
            )
            if result.success:
                return {"success": True, "data": result.data.model_dump(), "message": f"Successfully created host {name}"}
            else:
                return {"success": False, "error": result.error, "warnings": result.warnings}
        
        self._tool_handlers["create_host"] = create_host
        
        # Get host tool
        self._tools["get_host"] = Tool(
            name="get_host",
            description="Get detailed information about a specific host",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Host name"},
                    "include_status": {"type": "boolean", "description": "Whether to include status information", "default": True}
                },
                "required": ["name"]
            }
        )
        
        async def get_host(name, include_status=True):
            result = await self.host_service.get_host(name=name, include_status=include_status)
            if result.success:
                return {"success": True, "data": result.data.model_dump(), "message": f"Retrieved details for host {name}"}
            else:
                return {"success": False, "error": result.error, "warnings": result.warnings}
        
        self._tool_handlers["get_host"] = get_host
        
        # Update host tool
        self._tools["update_host"] = Tool(
            name="update_host",
            description="Update an existing host",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Host name"},
                    "folder": {"type": "string", "description": "New folder path"},
                    "ip_address": {"type": "string", "description": "New IP address"},
                    "attributes": {"type": "object", "description": "Updated attributes"},
                    "labels": {"type": "object", "description": "Updated labels"},
                    "etag": {"type": "string", "description": "ETag for optimistic locking"}
                },
                "required": ["name"]
            }
        )
        
        async def update_host(name, folder=None, ip_address=None, attributes=None, labels=None, etag=None):
            result = await self.host_service.update_host(
                name=name, folder=folder, ip_address=ip_address, attributes=attributes, labels=labels, etag=etag
            )
            if result.success:
                return {"success": True, "data": result.data.model_dump(), "message": f"Successfully updated host {name}"}
            else:
                return {"success": False, "error": result.error, "warnings": result.warnings}
        
        self._tool_handlers["update_host"] = update_host
        
        # Delete host tool
        self._tools["delete_host"] = Tool(
            name="delete_host",
            description="Delete a host from Checkmk",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Host name to delete"}
                },
                "required": ["name"]
            }
        )
        
        async def delete_host(name):
            result = await self.host_service.delete_host(name=name)
            if result.success:
                return {"success": True, "data": result.data.model_dump(), "message": f"Successfully deleted host {name}"}
            else:
                return {"success": False, "error": result.error, "warnings": result.warnings}
        
        self._tool_handlers["delete_host"] = delete_host
    
    def _register_service_tools(self):
        """Register service operation tools - same as basic server."""
        # List host services tool
        self._tools["list_host_services"] = Tool(
            name="list_host_services",
            description="List all services for a specific host",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Name of the host"},
                    "include_downtimes": {"type": "boolean", "description": "Include downtime information", "default": False},
                    "include_acknowledged": {"type": "boolean", "description": "Include acknowledgment information", "default": False}
                },
                "required": ["host_name"]
            }
        )
        
        async def list_host_services(host_name, include_downtimes=False, include_acknowledged=False):
            # Note: include_downtimes and include_acknowledged are accepted by tool but not used by service
            # This maintains backward compatibility with tool schema
            result = await self.service_service.list_host_services(
                host_name=host_name
            )
            if result.success:
                return {"success": True, "data": result.data.model_dump(), "message": f"Retrieved {result.data.total_count} services for host {host_name}"}
            else:
                return {"success": False, "error": result.error, "warnings": result.warnings}
        
        self._tool_handlers["list_host_services"] = list_host_services
        
        # List all services tool
        self._tools["list_all_services"] = Tool(
            name="list_all_services",
            description="List services across all hosts with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Search pattern for service names"},
                    "state_filter": {"type": "array", "items": {"type": "string"}, "description": "Filter by service states (OK, WARNING, CRITICAL, UNKNOWN)"},
                    "limit": {"type": "integer", "description": "Maximum number of services to return"},
                    "offset": {"type": "integer", "description": "Starting index for pagination", "default": 0}
                }
            }
        )
        
        async def list_all_services(search=None, state_filter=None, limit=None, offset=0):
            from ..services.models.services import ServiceState
            
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
                return {"success": True, "data": result.data.model_dump(), "message": f"Retrieved {result.data.total_count} services"}
            else:
                return {"success": False, "error": result.error, "warnings": result.warnings}
        
        self._tool_handlers["list_all_services"] = list_all_services
        
        # Acknowledge service problem tool
        self._tools["acknowledge_service_problem"] = Tool(
            name="acknowledge_service_problem",
            description="Acknowledge a service problem",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_name": {"type": "string", "description": "Service name"},
                    "comment": {"type": "string", "description": "Acknowledgment comment"},
                    "sticky": {"type": "boolean", "description": "Whether acknowledgment persists after recovery", "default": False},
                    "notify": {"type": "boolean", "description": "Whether to send notifications", "default": True},
                    "persistent": {"type": "boolean", "description": "Whether acknowledgment survives restarts", "default": False},
                    "expire_on": {"type": "string", "description": "Expiration time as ISO timestamp (Checkmk 2.4+)"}
                },
                "required": ["host_name", "service_name", "comment"]
            }
        )
        
        async def acknowledge_service_problem(host_name, service_name, comment, sticky=False, notify=True, persistent=False, expire_on=None):
            
            result = await self.service_service.acknowledge_service_problems(
                host_name=host_name, service_name=service_name, comment=comment, 
                sticky=sticky, notify=notify, persistent=persistent, expire_on=expire_on
            )
            if result.success:
                return {"success": True, "data": result.data.model_dump(), "message": f"Acknowledged problem for {service_name} on {host_name}"}
            else:
                return {"success": False, "error": result.error, "warnings": result.warnings}
        
        self._tool_handlers["acknowledge_service_problem"] = acknowledge_service_problem
        
        # Create service downtime tool
        self._tools["create_service_downtime"] = Tool(
            name="create_service_downtime",
            description="Create downtime for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_name": {"type": "string", "description": "Service name"},
                    "start_time": {"type": "string", "description": "Start time (ISO format or 'now')"},
                    "end_time": {"type": "string", "description": "End time (ISO format)"},
                    "comment": {"type": "string", "description": "Downtime comment"},
                    "duration_hours": {"type": "number", "description": "Duration in hours (alternative to end_time)"},
                    "recur": {"type": "string", "description": "Recurrence rule"}
                },
                "required": ["host_name", "service_name", "comment"]
            }
        )
        
        async def create_service_downtime(host_name, service_name, comment, start_time=None, end_time=None, duration_hours=None, recur=None):
            result = await self.service_service.create_service_downtime(
                host_name=host_name, service_name=service_name, comment=comment,
                start_time=start_time, end_time=end_time, duration_hours=duration_hours, recur=recur
            )
            if result.success:
                return {"success": True, "data": result.data.model_dump(), "message": f"Created downtime for {service_name} on {host_name}"}
            else:
                return {"success": False, "error": result.error, "warnings": result.warnings}
        
        self._tool_handlers["create_service_downtime"] = create_service_downtime
    
    def _register_status_tools(self):
        """Register status monitoring tools - same as basic server."""
        # Get health dashboard tool
        self._tools["get_health_dashboard"] = Tool(
            name="get_health_dashboard",
            description="Get comprehensive infrastructure health dashboard",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_services": {"type": "boolean", "description": "Include service statistics", "default": True},
                    "include_metrics": {"type": "boolean", "description": "Include performance metrics", "default": True}
                }
            }
        )
        
        async def get_health_dashboard(**kwargs):
            # Note: The service method doesn't accept parameters, ignore any passed
            result = await self.status_service.get_health_dashboard()
            if result.success:
                # Handle both dict and Pydantic model data
                data = result.data.model_dump() if hasattr(result.data, 'model_dump') else result.data
                return {"success": True, "data": data}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["get_health_dashboard"] = get_health_dashboard
        
        # Get critical problems tool
        self._tools["get_critical_problems"] = Tool(
            name="get_critical_problems",
            description="Get current critical problems requiring immediate attention",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity_filter": {"type": "array", "items": {"type": "string"}, "description": "Filter by severity levels"},
                    "category_filter": {"type": "array", "items": {"type": "string"}, "description": "Filter by problem categories"},
                    "include_acknowledged": {"type": "boolean", "description": "Include acknowledged problems", "default": False}
                }
            }
        )
        
        async def get_critical_problems(severity_filter=None, category_filter=None, include_acknowledged=False):
            result = await self.status_service.get_critical_problems(
                severity_filter=severity_filter, category_filter=category_filter, 
                include_acknowledged=include_acknowledged
            )
            if result.success:
                # Handle both dict and Pydantic model data
                data = result.data.model_dump() if hasattr(result.data, 'model_dump') else result.data
                return {"success": True, "data": data}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["get_critical_problems"] = get_critical_problems
        
        # Analyze host health tool
        self._tools["analyze_host_health"] = Tool(
            name="analyze_host_health",
            description="Analyze the health of a specific host with recommendations",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Name of the host to analyze"},
                    "include_grade": {"type": "boolean", "description": "Include health grade (A+ through F)", "default": True},
                    "include_recommendations": {"type": "boolean", "description": "Include maintenance recommendations", "default": True},
                    "compare_to_peers": {"type": "boolean", "description": "Compare to infrastructure peers", "default": False}
                },
                "required": ["host_name"]
            }
        )
        
        async def analyze_host_health(host_name, include_grade=True, include_recommendations=True, compare_to_peers=False):
            result = await self.status_service.analyze_host_health(
                host_name=host_name, include_grade=include_grade, 
                include_recommendations=include_recommendations, compare_to_peers=compare_to_peers
            )
            if result.success:
                return {"success": True, "data": result.data}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["analyze_host_health"] = analyze_host_health
    
    def _register_parameter_tools(self):
        """Register parameter management tools - same as basic server."""
        # Get effective parameters tool
        self._tools["get_effective_parameters"] = Tool(
            name="get_effective_parameters",
            description="Get effective monitoring parameters for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_name": {"type": "string", "description": "Service name"}
                },
                "required": ["host_name", "service_name"]
            }
        )
        
        async def get_effective_parameters(host_name, service_name):
            result = await self.parameter_service.get_effective_parameters(
                host_name=host_name, service_name=service_name
            )
            if result.success:
                return {"success": True, "data": result.data.model_dump()}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["get_effective_parameters"] = get_effective_parameters
        
        # Set service parameters tool
        self._tools["set_service_parameters"] = Tool(
            name="set_service_parameters",
            description="Set monitoring parameters for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_name": {"type": "string", "description": "Service name"},
                    "parameters": {"type": "object", "description": "Parameter values to set"},
                    "rule_properties": {"type": "object", "description": "Rule properties like description and folder"}
                },
                "required": ["host_name", "service_name", "parameters"]
            }
        )
        
        async def set_service_parameters(host_name, service_name, parameters, rule_properties=None):
            result = await self.parameter_service.set_service_parameters(
                host_name=host_name, service_name=service_name, 
                parameters=parameters, rule_properties=rule_properties
            )
            if result.success:
                return {"success": True, "data": result.data.model_dump(), "message": f"Updated parameters for {service_name} on {host_name}"}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["set_service_parameters"] = set_service_parameters
    
    def _register_event_console_tools(self):
        """Register Event Console MCP tools."""
        
        # List service events tool
        self._tools["list_service_events"] = Tool(
            name="list_service_events",
            description="Show event history for a specific service",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_name": {"type": "string", "description": "Service name"},
                    "limit": {"type": "integer", "description": "Maximum number of events", "default": 50},
                    "state_filter": {"type": "string", "description": "Filter by state: ok, warning, critical, unknown"}
                },
                "required": ["host_name", "service_name"]
            }
        )
        
        async def list_service_events(host_name, service_name, limit=50, state_filter=None):
            
            event_service = self._get_service("event")
            result = await event_service.list_service_events(host_name, service_name, limit, state_filter)
            
            if result.success:
                events_data = []
                if result.data:  # result.data could be an empty list, which is still success
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
                        "comment": event.comment
                    })
                message = f"Found {len(events_data)} events for service {service_name} on host {host_name}"
                if len(events_data) == 0:
                    message += ". Note: Event Console processes external events (syslog, SNMP traps, etc.) and is often empty in installations that only use active service monitoring."
                return {"success": True, "events": events_data, "count": len(events_data), "message": message}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["list_service_events"] = list_service_events
        
        # List host events tool
        self._tools["list_host_events"] = Tool(
            name="list_host_events",
            description="Show event history for a specific host",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "limit": {"type": "integer", "description": "Maximum number of events", "default": 100},
                    "state_filter": {"type": "string", "description": "Filter by state: ok, warning, critical, unknown"}
                },
                "required": ["host_name"]
            }
        )
        
        async def list_host_events(host_name, limit=100, state_filter=None):
            
            event_service = self._get_service("event")
            result = await event_service.list_host_events(host_name, limit, state_filter)
            
            if result.success:
                events_data = []
                if result.data:  # result.data could be an empty list, which is still success
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
                            "count": event.count
                        })
                message = f"Found {len(events_data)} events for host {host_name}"
                if len(events_data) == 0:
                    message += ". Note: Event Console is used for external events (syslog, SNMP traps, etc.) and is often empty in installations that only use active monitoring."
                return {"success": True, "events": events_data, "count": len(events_data), "message": message}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["list_host_events"] = list_host_events
        
        # Get recent critical events tool
        self._tools["get_recent_critical_events"] = Tool(
            name="get_recent_critical_events",
            description="Get recent critical events across all hosts",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of events", "default": 20}
                }
            }
        )
        
        async def get_recent_critical_events(limit=20):
            
            event_service = self._get_service("event")
            result = await event_service.get_recent_critical_events(limit)
            
            if result.success:
                events_data = []
                if result.data:  # result.data could be an empty list, which is still success
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
                        "count": event.count
                    })
                message = f"Found {len(events_data)} critical events"
                if len(events_data) == 0:
                    message += ". Note: Event Console processes external events (syslog, SNMP traps, etc.) and is often empty if not configured for log processing."
                return {"success": True, "critical_events": events_data, "count": len(events_data), "message": message}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["get_recent_critical_events"] = get_recent_critical_events
        
        # Acknowledge event tool
        self._tools["acknowledge_event"] = Tool(
            name="acknowledge_event",
            description="Acknowledge an event in the Event Console",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID"},
                    "comment": {"type": "string", "description": "Comment for acknowledgment"},
                    "contact": {"type": "string", "description": "Contact name"},
                    "site_id": {"type": "string", "description": "Site ID"}
                },
                "required": ["event_id", "comment"]
            }
        )
        
        async def acknowledge_event(event_id, comment, contact=None, site_id=None):
            
            event_service = self._get_service("event")
            result = await event_service.acknowledge_event(event_id, comment, contact, site_id)
            
            if result.success:
                return {"success": True, "message": f"Event {event_id} acknowledged successfully"}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["acknowledge_event"] = acknowledge_event
        
        # Search events tool
        self._tools["search_events"] = Tool(
            name="search_events",
            description="Search events by text content",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "Text to search for"},
                    "limit": {"type": "integer", "description": "Maximum number of events", "default": 50},
                    "state_filter": {"type": "string", "description": "Filter by state: ok, warning, critical, unknown"},
                    "host_filter": {"type": "string", "description": "Filter by host name"}
                },
                "required": ["search_term"]
            }
        )
        
        async def search_events(search_term, limit=50, state_filter=None, host_filter=None):
            
            event_service = self._get_service("event")
            result = await event_service.search_events(search_term, limit, state_filter, host_filter)
            
            if result.success:
                events_data = []
                if result.data:  # result.data could be an empty list, which is still success
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
                        "count": event.count
                    })
                message = f"Found {len(events_data)} events matching '{search_term}'"
                if len(events_data) == 0:
                    message += ". Note: Event Console searches external events (logs, SNMP traps, etc.) and is often empty in monitoring-only installations."
                return {"success": True, "events": events_data, "count": len(events_data), "search_term": search_term, "message": message}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["search_events"] = search_events
    
    def _register_metrics_tools(self):
        """Register Metrics MCP tools."""
        
        # Get service metrics tool
        self._tools["get_service_metrics"] = Tool(
            name="get_service_metrics",
            description="Get performance metrics/graphs for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_description": {"type": "string", "description": "Service description"},
                    "time_range_hours": {"type": "integer", "description": "Hours of data to retrieve", "default": 24},
                    "reduce": {"type": "string", "description": "Data reduction method", "enum": ["min", "max", "average"], "default": "average"},
                    "site": {"type": "string", "description": "Site name for performance optimization"}
                },
                "required": ["host_name", "service_description"]
            }
        )
        
        async def get_service_metrics(host_name, service_description, time_range_hours=24, reduce="average"):
            site = arguments.get("site")
            
            metrics_service = self._get_service("metrics")
            result = await metrics_service.get_service_metrics(
                host_name, service_description, time_range_hours, reduce, site
            )
            
            if result.success:
                metrics_data = []
                for graph in result.data:
                    graph_info = {
                        "time_range": graph.time_range,
                        "step": graph.step,
                        "metrics": []
                    }
                    for metric in graph.metrics:
                        metric_info = {
                            "title": metric.title,
                            "color": metric.color,
                            "line_type": metric.line_type,
                            "data_points_count": len(metric.data_points),
                            "latest_value": metric.data_points[-1] if metric.data_points else None
                        }
                        graph_info["metrics"].append(metric_info)
                    metrics_data.append(graph_info)
                
                return {"success": True, "graphs": metrics_data, "count": len(metrics_data)}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["get_service_metrics"] = get_service_metrics
        
        # Get metric history tool
        self._tools["get_metric_history"] = Tool(
            name="get_metric_history",
            description="Get historical data for a specific metric",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_description": {"type": "string", "description": "Service description"},
                    "metric_id": {"type": "string", "description": "Metric ID (enable 'Show internal IDs' in Checkmk UI)"},
                    "time_range_hours": {"type": "integer", "description": "Hours of data to retrieve", "default": 168},
                    "reduce": {"type": "string", "description": "Data reduction method", "enum": ["min", "max", "average"], "default": "average"},
                    "site": {"type": "string", "description": "Site name for performance optimization"}
                },
                "required": ["host_name", "service_description", "metric_id"]
            }
        )
        
        async def get_metric_history(host_name, service_description, metric_id, time_range_hours=168):
            reduce = arguments.get("reduce", "average")
            site = arguments.get("site")
            
            metrics_service = self._get_service("metrics")
            result = await metrics_service.get_metric_history(
                host_name, service_description, metric_id, time_range_hours, reduce, site
            )
            
            if result.success:
                graph = result.data
                metrics_data = []
                for metric in graph.metrics:
                    metric_info = {
                        "title": metric.title,
                        "color": metric.color,
                        "line_type": metric.line_type,
                        "data_points": metric.data_points,
                        "data_points_count": len(metric.data_points)
                    }
                    metrics_data.append(metric_info)
                
                return {
                    "success": True,
                    "time_range": graph.time_range,
                    "step": graph.step,
                    "metrics": metrics_data,
                    "metric_id": metric_id
                }
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["get_metric_history"] = get_metric_history
    
    def _register_bi_tools(self):
        """Register Business Intelligence MCP tools."""
        
        # Get business status summary tool
        self._tools["get_business_status_summary"] = Tool(
            name="get_business_status_summary",
            description="Get business-level status summary from BI aggregations",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_groups": {"type": "array", "items": {"type": "string"}, "description": "Filter by group names"}
                }
            }
        )
        
        async def get_business_status_summary(filter_groups=None):
            
            bi_service = self._get_service("bi")
            result = await bi_service.get_business_status_summary(filter_groups)
            
            if result.success:
                return {"success": True, "business_summary": result.data}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["get_business_status_summary"] = get_business_status_summary
        
        # Get critical business services tool
        self._tools["get_critical_business_services"] = Tool(
            name="get_critical_business_services",
            description="Get list of critical business services from BI aggregations",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
        
        async def get_critical_business_services():
            bi_service = self._get_service("bi")
            result = await bi_service.get_critical_business_services()
            
            if result.success:
                return {"success": True, "critical_services": result.data, "count": len(result.data)}
            else:
                return {"success": False, "error": result.error or "Event Console operation failed"}
        
        self._tool_handlers["get_critical_business_services"] = get_critical_business_services
        
        # Get system version info tool
        self._tools["get_system_info"] = Tool(
            name="get_system_info",
            description="Get Checkmk system version and basic information",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
        
        async def get_system_info():
            # Use the direct async client method for this simple operation
            version_info = await self.checkmk_client.get_version_info()
            
            # Extract key information
            versions = version_info.get('versions', {})
            site_info = version_info.get('site', 'unknown')
            edition = version_info.get('edition', 'unknown')
            
            return {
                "success": True,
                "checkmk_version": versions.get('checkmk', 'unknown'),
                "edition": edition,
                "site": site_info,
                "python_version": versions.get('python', 'unknown'),
                "apache_version": versions.get('apache', 'unknown')
            }
        
        self._tool_handlers["get_system_info"] = get_system_info
    
    def _register_advanced_tools(self):
        """Register advanced MCP tools."""
        
        # Stream hosts tool
        self._tools["stream_hosts"] = Tool(
            name="stream_hosts",
            description="Stream hosts in batches for large environments",
            inputSchema={
                "type": "object",
                "properties": {
                    "batch_size": {"type": "integer", "description": "Number of hosts per batch", "default": 100},
                    "search": {"type": "string", "description": "Optional search filter"},
                    "folder": {"type": "string", "description": "Optional folder filter"}
                }
            }
        )
        
        async def stream_hosts(batch_size=100, search=None, folder=None):
            try:
                if not self.streaming_host_service:
                    return {"success": False, "error": "Streaming not enabled"}
                
                batches = []
                async for batch in self.streaming_host_service.list_hosts_streamed(
                    batch_size=batch_size, search=search, folder=folder
                ):
                    batch_data = batch.model_dump()
                    batches.append({
                        "batch_number": batch_data["batch_number"],
                        "items_count": len(batch_data["items"]),
                        "has_more": batch_data["has_more"],
                        "timestamp": batch_data["timestamp"]
                    })
                    
                    # Limit to prevent overwhelming response
                    if len(batches) >= 10:
                        break
                
                return {
                    "success": True,
                    "data": {
                        "total_batches_processed": len(batches),
                        "batches": batches,
                        "message": f"Processed {len(batches)} batches with {batch_size} items each"
                    }
                }
                
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self._tool_handlers["stream_hosts"] = stream_hosts
        
        # Batch create hosts tool
        self._tools["batch_create_hosts"] = Tool(
            name="batch_create_hosts",
            description="Create multiple hosts in a batch operation",
            inputSchema={
                "type": "object",
                "properties": {
                    "hosts_data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of host creation data"
                    },
                    "max_concurrent": {
                        "type": "integer",
                        "description": "Maximum concurrent operations",
                        "default": 5
                    }
                },
                "required": ["hosts_data"]
            }
        )
        
        async def batch_create_hosts(hosts_data, max_concurrent=5):
            try:
                # Use batch processor for efficient creation
                self.batch_processor.max_concurrent = max_concurrent
                
                async def create_single_host(host_data: Dict[str, Any]):
                    return await self.host_service.create_host(**host_data)
                
                result = await self.batch_processor.process_batch(
                    items=hosts_data,
                    operation=create_single_host,
                    batch_id=f"create_hosts_{datetime.now().timestamp()}"
                )
                
                return {
                    "success": True,
                    "data": {
                        "batch_id": result.batch_id,
                        "total_items": result.progress.total_items,
                        "successful": result.progress.success,
                        "failed": result.progress.failed,
                        "skipped": result.progress.skipped,
                        "duration_seconds": result.progress.duration,
                        "items_per_second": result.progress.items_per_second
                    },
                    "message": f"Batch completed: {result.progress.success} created, {result.progress.failed} failed"
                }
                
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self._tool_handlers["batch_create_hosts"] = batch_create_hosts
        
        # Get server metrics tool
        self._tools["get_server_metrics"] = Tool(
            name="get_server_metrics",
            description="Get comprehensive server performance metrics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
        
        async def get_server_metrics():
            try:
                # Get metrics from various sources
                server_stats = await get_metrics_collector().get_stats()
                
                # Add service-specific metrics if available
                service_metrics = {}
                if hasattr(self.host_service, 'get_service_metrics'):
                    service_metrics['host_service'] = await self.host_service.get_service_metrics()
                if hasattr(self.service_service, 'get_service_metrics'):
                    service_metrics['service_service'] = await self.service_service.get_service_metrics()
                
                # Add cache stats if available
                cache_stats = {}
                if self.cached_host_service:
                    cache_stats = await self.cached_host_service.get_cache_stats()
                
                # Add recovery stats if available
                recovery_stats = {}
                if hasattr(self.host_service, 'get_recovery_stats'):
                    recovery_stats = await self.host_service.get_recovery_stats()
                
                return {
                    "success": True,
                    "data": {
                        "server_metrics": server_stats,
                        "service_metrics": service_metrics,
                        "cache_metrics": cache_stats,
                        "recovery_metrics": recovery_stats,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self._tool_handlers["get_server_metrics"] = get_server_metrics
        
        # Clear cache tool
        self._tools["clear_cache"] = Tool(
            name="clear_cache",
            description="Clear cache entries",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Optional pattern to match cache keys"
                    }
                }
            }
        )
        
        async def clear_cache(pattern=None):
            try:
                if not self.cached_host_service:
                    return {"success": False, "error": "Cache not enabled"}
                
                if pattern:
                    cleared = await self.cached_host_service.invalidate_cache_pattern(pattern)
                    message = f"Cleared {cleared} cache entries matching '{pattern}'"
                else:
                    await self.cached_host_service._cache.clear()
                    message = "Cleared all cache entries"
                
                return {
                    "success": True,
                    "data": {"cleared_entries": cleared if pattern else "all"},
                    "message": message
                }
                
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self._tool_handlers["clear_cache"] = clear_cache
    
    async def _stream_hosts_resource(self) -> str:
        """Generate streaming hosts resource content."""
        if not self.streaming_host_service:
            return safe_json_dumps({"error": "Streaming not enabled"})
        
        lines = []
        batch_count = 0
        
        try:
            async for batch in self.streaming_host_service.list_hosts_streamed(batch_size=50):
                # Convert each host in batch to JSON line
                for host in batch.items:
                    lines.append(host.model_dump_json())
                
                batch_count += 1
                # Limit output to prevent overwhelming
                if batch_count >= 5:
                    break
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.exception("Error streaming hosts")
            return safe_json_dumps({"error": str(e)})
    
    async def _stream_services_resource(self) -> str:
        """Generate streaming services resource content."""
        if not self.streaming_service_service:
            return safe_json_dumps({"error": "Streaming not enabled"})
        
        lines = []
        batch_count = 0
        
        try:
            async for batch in self.streaming_service_service.list_all_services_streamed(batch_size=100):
                # Convert each service in batch to JSON line
                for service in batch.items:
                    lines.append(service.model_dump_json())
                
                batch_count += 1
                # Limit output to prevent overwhelming
                if batch_count >= 3:
                    break
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.exception("Error streaming services")
            return safe_json_dumps({"error": str(e)})
    
    def _handle_service_result(self, result) -> str:
        """Handle service result and return appropriate JSON."""
        if result.success:
            return result.data.model_dump_json() if hasattr(result.data, 'model_dump_json') else safe_json_dumps(result.data)
        else:
            raise RuntimeError(f"Service operation failed: {result.error}")
    
    async def initialize(self):
        """Initialize the enhanced MCP server and its dependencies."""
        try:
            # Initialize the async Checkmk client
            from ..api_client import CheckmkClient
            sync_client = CheckmkClient(self.config.checkmk)
            self.checkmk_client = AsyncCheckmkClient(sync_client)
            
            # Initialize standard services
            self.host_service = HostService(self.checkmk_client, self.config)
            self.status_service = StatusService(self.checkmk_client, self.config)
            self.service_service = ServiceService(self.checkmk_client, self.config)
            self.parameter_service = ParameterService(self.checkmk_client, self.config)
            self.event_service = EventService(self.checkmk_client, self.config)
            self.metrics_service = MetricsService(self.checkmk_client, self.config)
            self.bi_service = BIService(self.checkmk_client, self.config)
            
            # Initialize enhanced services
            self.streaming_host_service = StreamingHostService(self.checkmk_client, self.config)
            self.streaming_service_service = StreamingServiceService(self.checkmk_client, self.config)
            self.cached_host_service = CachedHostService(self.checkmk_client, self.config)
            
            # Register all tools (standard + advanced)
            self._register_all_tools()
            
            logger.info("Enhanced Checkmk MCP Server initialized successfully with advanced features")
            logger.info(f"Registered {len(self._tools)} tools (standard + advanced)")
            
        except Exception as e:
            logger.exception("Failed to initialize enhanced MCP server")
            raise RuntimeError(f"Initialization failed: {str(e)}")
    
    def _ensure_services(self) -> bool:
        """Ensure all services are initialized."""
        return all([
            self.checkmk_client,
            self.host_service,
            self.status_service, 
            self.service_service,
            self.parameter_service,
            self.event_service,
            self.metrics_service,
            self.bi_service
        ])
    
    def _get_service(self, service_name: str):
        """Get service instance by name."""
        service_map = {
            "host": self.host_service,
            "status": self.status_service,
            "service": self.service_service,
            "parameter": self.parameter_service,
            "event": self.event_service,
            "metrics": self.metrics_service,
            "bi": self.bi_service
        }
        
        service = service_map.get(service_name)
        if service is None:
            raise ValueError(f"Unknown service: {service_name}")
        return service
    
    async def run(self, transport_type: str = "stdio"):
        """Run the enhanced MCP server with the specified transport."""
        if not self._ensure_services():
            await self.initialize()
        
        if transport_type == "stdio":
            # For stdio transport (most common for MCP)
            from mcp.server.stdio import stdio_server
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream, 
                    InitializationOptions(
                        server_name="checkmk-agent-enhanced",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")


async def main():
    """Main entry point for running the enhanced MCP server standalone."""
    import sys
    from pathlib import Path
    
    # Add the project root to the path so we can import modules
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    # Load configuration
    from ..config import load_config
    config = load_config()
    
    # Create and run the enhanced server
    server = EnhancedCheckmkMCPServer(config)
    await server.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())