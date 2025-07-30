"""Main MCP Server implementation for Checkmk operations."""

import logging
import asyncio
import json
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List

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
from ..services.metrics_service import MetricsService
from ..services.bi_service import BIService


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


class CheckmkMCPServer:
    """Checkmk MCP Server implementation with comprehensive monitoring capabilities."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.server = Server("checkmk-agent")
        self.checkmk_client: Optional[AsyncCheckmkClient] = None
        
        # Services
        self.host_service: Optional[HostService] = None
        self.status_service: Optional[StatusService] = None
        self.service_service: Optional[ServiceService] = None
        self.parameter_service: Optional[ParameterService] = None
        self.metrics_service: Optional[MetricsService] = None
        self.bi_service: Optional[BIService] = None
        
        # Tool definitions
        self._tools = {}
        
        # Register handlers
        self._register_handlers()
        self._register_tool_handlers()
    
    def _register_handlers(self):
        """Register MCP server handlers."""
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available MCP resources for real-time monitoring data."""
            return [
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
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read MCP resource content for real-time data."""
            if not self._ensure_services():
                raise RuntimeError("Services not initialized")
            
            try:
                if uri == "checkmk://dashboard/health":
                    result = await self.status_service.get_health_dashboard()
                    if result.success:
                        return result.data.model_dump_json()
                    else:
                        raise RuntimeError(f"Failed to get health dashboard: {result.error}")
                
                elif uri == "checkmk://dashboard/problems":
                    result = await self.status_service.get_critical_problems()
                    if result.success:
                        return result.data.model_dump_json()
                    else:
                        raise RuntimeError(f"Failed to get critical problems: {result.error}")
                
                elif uri == "checkmk://hosts/status":
                    result = await self.host_service.list_hosts(include_status=True)
                    if result.success:
                        return result.data.model_dump_json()
                    else:
                        raise RuntimeError(f"Failed to get host status: {result.error}")
                
                elif uri == "checkmk://services/problems":
                    # Get services with problems (non-OK states)
                    from ..services.models.services import ServiceState
                    result = await self.service_service.list_all_services(
                        state_filter=[ServiceState.WARNING, ServiceState.CRITICAL, ServiceState.UNKNOWN]
                    )
                    if result.success:
                        return result.data.model_dump_json()
                    else:
                        raise RuntimeError(f"Failed to get service problems: {result.error}")
                
                elif uri == "checkmk://metrics/performance":
                    result = await self.status_service.get_performance_metrics()
                    if result.success:
                        return result.data.model_dump_json()
                    else:
                        raise RuntimeError(f"Failed to get performance metrics: {result.error}")
                
                else:
                    raise ValueError(f"Unknown resource URI: {uri}")
            
            except Exception as e:
                logger.exception(f"Error reading resource {uri}")
                raise RuntimeError(f"Failed to read resource {uri}: {str(e)}")
        
        @self.server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            """List available MCP prompt templates."""
            return [
                Prompt(
                    name="analyze_host_health",
                    description="Analyze the health of a specific host with detailed recommendations",
                    arguments=[
                        {
                            "name": "host_name",
                            "description": "Name of the host to analyze",
                            "required": True
                        },
                        {
                            "name": "include_grade",
                            "description": "Include health grade (A+ through F)",
                            "required": False
                        }
                    ]
                ),
                Prompt(
                    name="troubleshoot_service",
                    description="Comprehensive troubleshooting analysis for a service problem",
                    arguments=[
                        {
                            "name": "host_name", 
                            "description": "Host name where the service is running",
                            "required": True
                        },
                        {
                            "name": "service_name",
                            "description": "Name of the service with problems",
                            "required": True
                        }
                    ]
                ),
                Prompt(
                    name="infrastructure_overview",
                    description="Get a comprehensive overview of infrastructure health and trends",
                    arguments=[
                        {
                            "name": "time_range_hours",
                            "description": "Time range for trend analysis (default: 24)",
                            "required": False
                        }
                    ]
                ),
                Prompt(
                    name="optimize_parameters",
                    description="Get parameter optimization recommendations for a service",
                    arguments=[
                        {
                            "name": "host_name",
                            "description": "Host name",
                            "required": True
                        },
                        {
                            "name": "service_name", 
                            "description": "Service name to optimize",
                            "required": True
                        }
                    ]
                )
            ]
        
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: Optional[Dict[str, str]]) -> PromptMessage:
            """Get MCP prompt template content."""
            if not self._ensure_services():
                raise RuntimeError("Services not initialized")
            
            args = arguments or {}
            
            if name == "analyze_host_health":
                host_name = args.get("host_name")
                if not host_name:
                    raise ValueError("host_name argument is required")
                
                include_grade = args.get("include_grade", "true").lower() == "true"
                
                # Get comprehensive host health data
                health_result = await self.status_service.analyze_host_health(
                    host_name=host_name,
                    include_grade=include_grade,
                    include_recommendations=True,
                    compare_to_peers=True
                )
                
                if not health_result.success:
                    raise RuntimeError(f"Failed to analyze host health: {health_result.error}")
                
                return PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Please analyze the health of host '{host_name}' based on this comprehensive monitoring data:

{health_result.data.model_dump_json(indent=2)}

Provide a detailed analysis including:
1. Overall health assessment and grade explanation
2. Critical issues requiring immediate attention
3. Performance trends and patterns
4. Specific maintenance recommendations with priorities
5. Comparison to infrastructure peers if available

Focus on actionable insights and prioritize by business impact."""
                    )
                )
            
            elif name == "troubleshoot_service":
                host_name = args.get("host_name")
                service_name = args.get("service_name")
                
                if not host_name or not service_name:
                    raise ValueError("Both host_name and service_name arguments are required")
                
                # Get comprehensive service troubleshooting data
                status_result = await self.service_service.get_service_status(
                    host_name=host_name,
                    service_name=service_name,
                    include_related=True
                )
                
                problems_result = await self.status_service.get_host_problems(
                    host_name=host_name,
                    include_services=True
                )
                
                params_result = await self.parameter_service.get_effective_parameters(
                    host_name=host_name,
                    service_name=service_name
                )
                
                troubleshooting_data = {
                    "service_status": status_result.data.model_dump() if status_result.success else {"error": status_result.error},
                    "host_problems": (problems_result.data.model_dump() if hasattr(problems_result.data, 'model_dump') else problems_result.data) if problems_result.success else {"error": problems_result.error},
                    "parameters": params_result.data.model_dump() if params_result.success else {"error": params_result.error}
                }
                
                return PromptMessage(
                    role="user", 
                    content=TextContent(
                        type="text",
                        text=f"""Please provide comprehensive troubleshooting analysis for the service problem:

Host: {host_name}
Service: {service_name}

Monitoring Data:
{troubleshooting_data}

Please provide:
1. Root cause analysis based on the service status and error messages
2. Impact assessment on related services and host health  
3. Step-by-step troubleshooting recommendations
4. Parameter tuning suggestions if applicable
5. Prevention measures to avoid similar issues

Focus on specific, actionable steps prioritized by urgency."""
                    )
                )
            
            elif name == "infrastructure_overview":
                time_range = int(args.get("time_range_hours", "24"))
                
                # Get comprehensive infrastructure data
                summary_result = await self.status_service.get_infrastructure_summary(
                    include_trends=True,
                    time_range_hours=time_range
                )
                
                dashboard_result = await self.status_service.get_health_dashboard(
                    include_services=True,
                    include_metrics=True
                )
                
                trends_result = await self.status_service.get_problem_trends(
                    time_range_hours=time_range,
                    category_breakdown=True
                )
                
                infrastructure_data = {
                    "summary": (summary_result.data.model_dump() if hasattr(summary_result.data, 'model_dump') else summary_result.data) if summary_result.success else {"error": summary_result.error},
                    "dashboard": (dashboard_result.data.model_dump() if hasattr(dashboard_result.data, 'model_dump') else dashboard_result.data) if dashboard_result.success else {"error": dashboard_result.error},
                    "trends": (trends_result.data.model_dump() if hasattr(trends_result.data, 'model_dump') else trends_result.data) if trends_result.success else {"error": trends_result.error}
                }
                
                return PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text", 
                        text=f"""Please provide a comprehensive infrastructure overview and analysis based on {time_range} hours of monitoring data:

{infrastructure_data}

Please provide:
1. Executive summary of infrastructure health and status
2. Key performance indicators and trends
3. Critical issues requiring immediate attention
4. Capacity planning insights and growth trends
5. Operational recommendations for optimization
6. Risk assessment and mitigation strategies

Focus on strategic insights for infrastructure management and operations."""
                    )
                )
            
            elif name == "optimize_parameters":
                host_name = args.get("host_name")
                service_name = args.get("service_name")
                
                if not host_name or not service_name:
                    raise ValueError("Both host_name and service_name arguments are required")
                
                # Get parameter optimization data
                recommendations_result = await self.parameter_service.get_parameter_recommendations(
                    host_name=host_name,
                    service_name=service_name
                )
                
                effective_result = await self.parameter_service.get_effective_parameters(
                    host_name=host_name,
                    service_name=service_name
                )
                
                optimization_data = {
                    "recommendations": recommendations_result.data if recommendations_result.success else {"error": recommendations_result.error},
                    "current_parameters": effective_result.data.model_dump() if effective_result.success else {"error": effective_result.error}
                }
                
                return PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Please provide parameter optimization recommendations for:

Host: {host_name}
Service: {service_name}

Current Configuration and Recommendations:
{optimization_data}

Please provide:
1. Analysis of current parameter settings vs. best practices
2. Specific optimization recommendations with rationale
3. Expected impact of proposed changes
4. Implementation plan with rollback considerations
5. Monitoring strategy to validate improvements

Focus on evidence-based recommendations that improve reliability and performance."""
                    )
                )
            
            else:
                raise ValueError(f"Unknown prompt: {name}")
    
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
    
    async def initialize(self):
        """Initialize the MCP server and its dependencies."""
        try:
            # Initialize the async Checkmk client
            from ..api_client import CheckmkClient
            sync_client = CheckmkClient(self.config.checkmk)
            self.checkmk_client = AsyncCheckmkClient(sync_client)
            
            # Initialize services
            self.host_service = HostService(self.checkmk_client, self.config)
            self.status_service = StatusService(self.checkmk_client, self.config)
            self.service_service = ServiceService(self.checkmk_client, self.config)
            self.parameter_service = ParameterService(self.checkmk_client, self.config)
            self.metrics_service = MetricsService(self.checkmk_client, self.config)
            self.bi_service = BIService(self.checkmk_client, self.config)
            
            # Initialize tool handlers
            self._tool_handlers = {}
            
            # Register tools from each module
            self._register_host_tools()
            self._register_service_tools()
            self._register_status_tools()
            self._register_parameter_tools()
            self._register_event_console_tools()
            self._register_metrics_tools()
            self._register_bi_tools()
            
            logger.info("Checkmk MCP Server initialized successfully")
            logger.info(f"Registered {len(self._tools)} tools")
            
        except Exception as e:
            logger.exception("Failed to initialize MCP server")
            raise RuntimeError(f"Initialization failed: {str(e)}")
    
    def _ensure_services(self) -> bool:
        """Ensure all services are initialized."""
        return all([
            self.checkmk_client,
            self.host_service,
            self.status_service, 
            self.service_service,
            self.parameter_service
        ])
    
    def _register_host_tools(self):
        """Register host operation tools."""
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
        """Register service operation tools."""
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
        
        async def acknowledge_service_problem(arguments: dict) -> dict:
            try:
                host_name = arguments["host_name"]
                service_name = arguments["service_name"]
                comment = arguments["comment"]
                sticky = arguments.get("sticky", False)
                notify = arguments.get("notify", True)
                persistent = arguments.get("persistent", False)
                expire_on = arguments.get("expire_on")
                
                result = await self.service_service.acknowledge_service_problems(
                    host_name=host_name, service_name=service_name, comment=comment, 
                    sticky=sticky, notify=notify, persistent=persistent, expire_on=expire_on
                )
                if result.success:
                    return {"success": True, "data": result.data.model_dump(), "message": f"Acknowledged problem for {service_name} on {host_name}"}
                else:
                    return {"success": False, "error": result.error, "warnings": result.warnings}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
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
        """Register status monitoring tools."""
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
                return {"success": False, "error": result.error}
        
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
                # result.data is already a dict, no need to call model_dump()
                return {"success": True, "data": result.data}
            else:
                return {"success": False, "error": result.error}
        
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
                # result.data is already a dict, no need to call model_dump()
                return {"success": True, "data": result.data}
            else:
                return {"success": False, "error": result.error}
        
        self._tool_handlers["analyze_host_health"] = analyze_host_health
    
    def _register_parameter_tools(self):
        """Register parameter management tools."""
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
                return {"success": False, "error": result.error}
        
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
                return {"success": False, "error": result.error}
        
        self._tool_handlers["set_service_parameters"] = set_service_parameters
    
    def _register_event_console_tools(self):
        """Register Event Console tools for service history and event management."""
        
        # List service events tool
        self._tools["list_service_events"] = Tool(
            name="list_service_events",
            description="Show event history for a specific service",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_name": {"type": "string", "description": "Service name"},
                    "limit": {"type": "integer", "description": "Maximum number of events to return", "default": 50},
                    "state_filter": {"type": "string", "description": "Filter by state (ok, warning, critical, unknown)", "enum": ["ok", "warning", "critical", "unknown"]}
                },
                "required": ["host_name", "service_name"]
            }
        )
        
        async def list_service_events(host_name, service_name, limit=50, state_filter=None):
            # Use the sync client Event Console methods
            try:
                # Build query for this service
                query = {
                    "op": "and",
                    "expr": [
                        {"op": "=", "left": "eventconsoleevents.event_host", "right": host_name}
                    ]
                }
                if service_name and service_name.strip():
                    query["expr"].append({
                        "op": "~", "left": "eventconsoleevents.event_text", "right": service_name
                    })
                
                # Add state filter if provided
                if state_filter:
                    state_map = {"ok": "0", "warning": "1", "critical": "2", "unknown": "3"}
                    if state_filter.lower() in state_map:
                        query["expr"].append({
                            "op": "=", "left": "eventconsoleevents.event_state", "right": state_map[state_filter.lower()]
                        })
                
                events = self.api_client.list_events(query=query, host=host_name)
                
                # Sort by time and limit
                events.sort(key=lambda e: e.get('extensions', {}).get('last', ''), reverse=True)
                if limit > 0:
                    events = events[:limit]
                
                return {"success": True, "events": events, "count": len(events)}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self._tool_handlers["list_service_events"] = list_service_events
        
        # List host events tool
        self._tools["list_host_events"] = Tool(
            name="list_host_events", 
            description="Show event history for a specific host",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "limit": {"type": "integer", "description": "Maximum number of events to return", "default": 100},
                    "state_filter": {"type": "string", "description": "Filter by state (ok, warning, critical, unknown)", "enum": ["ok", "warning", "critical", "unknown"]}
                },
                "required": ["host_name"]
            }
        )
        
        async def list_host_events(host_name, limit=100, state_filter=None):
            try:
                # Build query for this host
                query = {"op": "=", "left": "eventconsoleevents.event_host", "right": host_name}
                
                # Add state filter if provided
                if state_filter:
                    state_map = {"ok": "0", "warning": "1", "critical": "2", "unknown": "3"}
                    if state_filter.lower() in state_map:
                        query = {
                            "op": "and",
                            "expr": [
                                query,
                                {"op": "=", "left": "eventconsoleevents.event_state", "right": state_map[state_filter.lower()]}
                            ]
                        }
                
                events = self.api_client.list_events(query=query, host=host_name)
                
                # Sort by time and limit
                events.sort(key=lambda e: e.get('extensions', {}).get('last', ''), reverse=True)
                if limit > 0:
                    events = events[:limit]
                
                return {"success": True, "events": events, "count": len(events)}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self._tool_handlers["list_host_events"] = list_host_events
        
        # Get recent critical events tool
        self._tools["get_recent_critical_events"] = Tool(
            name="get_recent_critical_events",
            description="Show recent critical events across all hosts", 
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of events to return", "default": 20}
                }
            }
        )
        
        async def get_recent_critical_events(limit=20):
            try:
                # Query for critical events
                query = {"op": "=", "left": "eventconsoleevents.event_state", "right": "2"}
                events = self.api_client.list_events(query=query, state="critical")
                
                # Sort by time and limit
                events.sort(key=lambda e: e.get('extensions', {}).get('last', ''), reverse=True)
                if limit > 0:
                    events = events[:limit]
                
                return {"success": True, "events": events, "count": len(events)}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self._tool_handlers["get_recent_critical_events"] = get_recent_critical_events
        
        # Acknowledge event tool
        self._tools["acknowledge_event"] = Tool(
            name="acknowledge_event",
            description="Acknowledge a specific event in the Event Console",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID to acknowledge"},
                    "comment": {"type": "string", "description": "Comment for the acknowledgment"},
                    "contact": {"type": "string", "description": "Contact name (optional)"},
                    "site_id": {"type": "string", "description": "Site ID (optional)"}
                },
                "required": ["event_id", "comment"]
            }
        )
        
        async def acknowledge_event(event_id, comment, contact=None, site_id=None):
            try:
                response = self.api_client.acknowledge_event(
                    event_id=event_id,
                    comment=comment,
                    contact=contact,
                    site_id=site_id
                )
                return {"success": True, "response": response}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self._tool_handlers["acknowledge_event"] = acknowledge_event
        
        # Search events tool
        self._tools["search_events"] = Tool(
            name="search_events",
            description="Search events by text content across all hosts",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "Text to search for in event messages"},
                    "limit": {"type": "integer", "description": "Maximum number of events to return", "default": 50},
                    "state_filter": {"type": "string", "description": "Filter by state (ok, warning, critical, unknown)", "enum": ["ok", "warning", "critical", "unknown"]},
                    "host_filter": {"type": "string", "description": "Filter by host name (optional)"}
                },
                "required": ["search_term"]
            }
        )
        
        async def search_events(search_term, limit=50, state_filter=None, host_filter=None):
            try:
                # Build text search query
                query_parts = [
                    {"op": "~", "left": "eventconsoleevents.event_text", "right": search_term}
                ]
                
                # Add state filter if provided
                if state_filter:
                    state_map = {"ok": "0", "warning": "1", "critical": "2", "unknown": "3"}
                    if state_filter.lower() in state_map:
                        query_parts.append({
                            "op": "=", "left": "eventconsoleevents.event_state", "right": state_map[state_filter.lower()]
                        })
                
                # Add host filter if provided
                if host_filter:
                    query_parts.append({
                        "op": "=", "left": "eventconsoleevents.event_host", "right": host_filter
                    })
                
                # Combine query parts
                if len(query_parts) == 1:
                    query = query_parts[0]
                else:
                    query = {"op": "and", "expr": query_parts}
                
                events = self.api_client.list_events(query=query, host=host_filter, state=state_filter)
                
                # Sort by time and limit
                events.sort(key=lambda e: e.get('extensions', {}).get('last', ''), reverse=True)
                if limit > 0:
                    events = events[:limit]
                
                return {"success": True, "events": events, "count": len(events), "search_term": search_term}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
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
        
        async def get_service_metrics(arguments: dict) -> dict:
            try:
                host_name = arguments["host_name"]
                service_description = arguments["service_description"]
                time_range_hours = arguments.get("time_range_hours", 24)
                reduce = arguments.get("reduce", "average")
                site = arguments.get("site")
                
                result = await self.metrics_service.get_service_metrics(
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
                    return {"success": False, "error": result.error}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
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
        
        async def get_metric_history(arguments: dict) -> dict:
            try:
                host_name = arguments["host_name"]
                service_description = arguments["service_description"]
                metric_id = arguments["metric_id"]
                time_range_hours = arguments.get("time_range_hours", 168)
                reduce = arguments.get("reduce", "average")
                site = arguments.get("site")
                
                result = await self.metrics_service.get_metric_history(
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
                    return {"success": False, "error": result.error}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
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
        
        async def get_business_status_summary(arguments: dict) -> dict:
            try:
                filter_groups = arguments.get("filter_groups")
                
                result = await self.bi_service.get_business_status_summary(filter_groups)
                
                if result.success:
                    return {"success": True, "business_summary": result.data}
                else:
                    return {"success": False, "error": result.error}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
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
        
        async def get_critical_business_services(arguments: dict) -> dict:
            try:
                result = await self.bi_service.get_critical_business_services()
                
                if result.success:
                    return {"success": True, "critical_services": result.data, "count": len(result.data)}
                else:
                    return {"success": False, "error": result.error}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
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
        
        async def get_system_info(arguments: dict) -> dict:
            try:
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
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self._tool_handlers["get_system_info"] = get_system_info
    
    async def run(self, transport_type: str = "stdio"):
        """Run the MCP server with the specified transport."""
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
                        server_name="checkmk-agent",
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
    """Main entry point for running the MCP server standalone."""
    import sys
    from pathlib import Path
    
    # Add the project root to the path so we can import modules
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    # Load configuration
    from ..config import load_config
    config = load_config()
    
    # Create and run the server with proper error handling
    server = CheckmkMCPServer(config)
    
    try:
        logger.info("Starting Checkmk MCP Server...")
        logger.info("  - ✓ Configuration loaded")
        logger.info("  - ✓ Core monitoring capabilities")
        logger.info("  - ✓ Host and service management")
        logger.info("  - ✓ Event Console integration")
        logger.info("  - ✓ Metrics and BI support")
        
        await server.run()
        
    except BrokenPipeError:
        # This is expected when the client disconnects - don't log as error
        logger.info("MCP server connection closed by client")
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in MCP server: {e}")
        logger.debug("Exception details:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Configure logging with better format
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP server interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in MCP server: {e}")
        sys.exit(1)