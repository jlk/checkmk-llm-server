"""Enhanced MCP Server implementation with modular architecture.

This is the main orchestration module that integrates all extracted components
including tools, prompts, handlers, and services in a clean, maintainable way.
"""

import logging
from typing import Dict, Any, List, Optional

from mcp.server import Server
from mcp.types import Resource, Prompt, GetPromptResult
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel.server import NotificationOptions

from ..config import AppConfig
from .container import ServiceContainer
from .handlers.registry import ToolRegistry
from .handlers.protocol import ProtocolHandlers
from .prompts.definitions import PromptDefinitions
from .prompts.handlers import PromptHandlers
from .prompts.validators import PromptValidators

# Import all tool categories
from .tools.host import HostTools
from .tools.service import ServiceTools
from .tools.monitoring import MonitoringTools
from .tools.parameters import ParameterTools
from .tools.events import EventTools
from .tools.metrics import MetricsTools
from .tools.business import BusinessTools
from .tools.advanced import AdvancedTools

# Import utilities
from .utils.serialization import safe_json_dumps
from .utils.errors import sanitize_error

# Import request tracking utilities
try:
    from ..utils.request_context import (
        generate_request_id,
        set_request_id,
    )
except ImportError:
    # Fallback for cases where request tracking is not available
    def generate_request_id() -> str:
        return "req_unknown"

    def set_request_id(request_id: str) -> None:
        pass

logger = logging.getLogger(__name__)


class CheckmkMCPServer:
    """Enhanced Checkmk MCP Server with modular architecture.
    
    This server orchestrates all components including:
    - Service container for dependency injection
    - Tool registry for managing tools
    - Protocol handlers for MCP resources and prompts
    - Tool categories for organized functionality
    - Prompt system for AI interactions
    """

    def __init__(self, config: AppConfig):
        """Initialize the MCP server.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.server: Server = Server("checkmk-agent")
        
        # Core components
        self.container = ServiceContainer(config)
        self.tool_registry = ToolRegistry()
        self.protocol_handlers = ProtocolHandlers()
        self.prompt_handlers = PromptHandlers()
        self.prompt_validators = PromptValidators()
        
        # Tool categories (initialized after services)
        self._tool_categories: Dict[str, Any] = {}
        
        # Track initialization state
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the enhanced MCP server and all components."""
        if self._initialized:
            return
            
        try:
            # Initialize service container first
            await self.container.initialize()
            
            # Initialize tool categories with services
            self._initialize_tool_categories()
            
            # Register all tools and prompts
            self._register_all_tools()
            self._register_all_prompts()
            
            # Register MCP handlers
            self._register_mcp_handlers()
            
            self._initialized = True
            
            tool_count = self.tool_registry.get_tool_count()
            prompt_count = len(self.protocol_handlers._prompts)
            
            logger.info(
                f"Enhanced Checkmk MCP Server initialized successfully with "
                f"{tool_count} tools and {prompt_count} prompts"
            )
            
        except Exception as e:
            logger.exception("Failed to initialize enhanced MCP server")
            raise RuntimeError(f"Initialization failed: {str(e)}")

    def _initialize_tool_categories(self) -> None:
        """Initialize all tool category instances with required services."""
        try:
            # Get services from container
            host_service = self.container.get_service('host_service')
            service_service = self.container.get_service('service_service')
            status_service = self.container.get_service('status_service')
            parameter_service = self.container.get_service('parameter_service')
            event_service = self.container.get_service('event_service')
            metrics_service = self.container.get_service('metrics_service')
            bi_service = self.container.get_service('bi_service')
            historical_service = self.container.get_service('historical_service')
            # Get all services for tool category initialization
            # (some categories may need additional services from container)
            
            # Initialize tool categories with correct constructor arguments
            self._tool_categories['host'] = HostTools(host_service, service_service)
            self._tool_categories['service'] = ServiceTools(service_service)
            self._tool_categories['monitoring'] = MonitoringTools(status_service)
            self._tool_categories['parameters'] = ParameterTools(parameter_service)
            self._tool_categories['events'] = EventTools(event_service)
            self._tool_categories['metrics'] = MetricsTools(metrics_service, historical_service)
            self._tool_categories['business'] = BusinessTools(bi_service, self)
            self._tool_categories['advanced'] = AdvancedTools(self)
            
            logger.info(f"Initialized {len(self._tool_categories)} tool categories")
            
        except Exception as e:
            logger.exception("Failed to initialize tool categories")
            raise RuntimeError(f"Tool category initialization failed: {str(e)}")

    def _register_all_tools(self) -> None:
        """Register all tools from all categories."""
        try:
            for category_name, category_instance in self._tool_categories.items():
                # Register tools in the category
                category_instance.register_tools()
                
                # Get tools and handlers from category
                tools = category_instance.get_tools()
                handlers = category_instance.get_handlers()
                
                # Register each tool with the tool registry
                for tool_name, tool in tools.items():
                    if tool_name in handlers:
                        handler = handlers[tool_name]
                        metadata = {
                            'category': category_name,
                            'source': f'{category_instance.__class__.__module__}.{category_instance.__class__.__name__}'
                        }
                        self.tool_registry.register_tool(tool_name, tool, handler, metadata)
                    else:
                        logger.warning(f"No handler found for tool '{tool_name}' in category '{category_name}'")
            
            # Register MCP handlers with the server
            self.tool_registry.register_mcp_handlers(self.server, lambda: self.container.is_initialized())
            
            logger.info(f"Registered {self.tool_registry.get_tool_count()} tools across all categories")
            
        except Exception as e:
            logger.exception("Failed to register tools")
            raise RuntimeError(f"Tool registration failed: {str(e)}")

    def _register_all_prompts(self) -> None:
        """Register all prompts and their handlers."""
        try:
            # Get prompt definitions
            prompt_definitions = PromptDefinitions.get_all_prompts()
            
            # Register prompts with protocol handlers
            self.protocol_handlers.register_prompts(prompt_definitions)
            
            # Initialize prompt handlers with services
            services = self.container.get_all_services()
            self.prompt_handlers.initialize_services(services)
            
            logger.info(f"Registered {len(prompt_definitions)} prompts")
            
        except Exception as e:
            logger.exception("Failed to register prompts")
            raise RuntimeError(f"Prompt registration failed: {str(e)}")

    def _register_mcp_handlers(self) -> None:
        """Register MCP protocol handlers."""
        try:
            @self.server.list_resources()
            async def handle_list_resources() -> List[Resource]:
                """Handle resource listing requests."""
                request_id = generate_request_id()
                set_request_id(request_id)
                
                try:
                    basic_resources = self.protocol_handlers.get_basic_resources()
                    streaming_resources = self.protocol_handlers.get_streaming_resources()
                    return basic_resources + streaming_resources
                except Exception as e:
                    logger.exception(f"Error listing resources [req={request_id}]")
                    return []

            @self.server.read_resource()
            async def handle_read_resource(uri) -> str:
                """Handle resource content requests."""
                request_id = generate_request_id()
                set_request_id(request_id)
                
                try:
                    # Create a service provider object that the protocol handlers expect
                    class ServiceProvider:
                        def __init__(self, services: Dict[str, Any]):
                            for name, service in services.items():
                                setattr(self, name, service)
                        
                        def _handle_service_result(self, result):
                            if result.success:
                                return safe_json_dumps(result.data.model_dump() if hasattr(result.data, 'model_dump') else result.data)
                            else:
                                return safe_json_dumps({"error": result.error, "warnings": result.warnings})
                    
                    services = self.container.get_all_services()
                    service_provider = ServiceProvider(services)
                    
                    return await self.protocol_handlers.handle_read_resource(uri, service_provider, {})
                except Exception as e:
                    logger.exception(f"Error reading resource {uri} [req={request_id}]")
                    return safe_json_dumps({
                        "error": f"Failed to read resource: {sanitize_error(e)}",
                        "uri": uri
                    })

            @self.server.list_prompts()
            async def handle_list_prompts() -> List[Prompt]:
                """Handle prompt listing requests."""
                request_id = generate_request_id()
                set_request_id(request_id)
                
                try:
                    return list(self.protocol_handlers._prompts.values())
                except Exception as e:
                    logger.exception(f"Error listing prompts [req={request_id}]")
                    return []

            @self.server.get_prompt()
            async def handle_get_prompt(name: str, arguments: Optional[Dict[str, Any]] = None) -> GetPromptResult:
                """Handle individual prompt requests."""
                request_id = generate_request_id()
                set_request_id(request_id)
                
                try:
                    # Validate arguments
                    validated_args = arguments or {}
                    if arguments:
                        validated_args = self.prompt_validators.validate_prompt_arguments(name, arguments)
                    
                    # Generate prompt response
                    return await self.prompt_handlers.handle_prompt(name, validated_args)
                    
                except ValueError as e:
                    logger.warning(f"Invalid arguments for prompt {name}: {str(e)} [req={request_id}]")
                    return GetPromptResult(
                        description=f"Invalid arguments: {str(e)}",
                        messages=[]
                    )
                except Exception as e:
                    logger.exception(f"Error handling prompt {name} [req={request_id}]")
                    return GetPromptResult(
                        description=f"Error processing prompt: {sanitize_error(e)}",
                        messages=[]
                    )

            logger.info("MCP protocol handlers registered successfully")
            
        except Exception as e:
            logger.exception("Failed to register MCP handlers")
            raise RuntimeError(f"MCP handler registration failed: {str(e)}")

    async def run(self, transport_type: str = "stdio") -> None:
        """Run the enhanced MCP server with the specified transport.
        
        Args:
            transport_type: Transport type to use (default: "stdio")
        """
        if not self._initialized:
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
                            experimental_capabilities={},
                        ),
                        instructions="""You are an experienced Senior Network Operations Engineer with 15+ years of expertise in infrastructure monitoring and management. Your role is to provide expert guidance on Checkmk monitoring operations.

Your expertise includes:
- Deep knowledge of network protocols (TCP/IP, SNMP, ICMP, HTTP/HTTPS)
- Infrastructure monitoring best practices and alert optimization
- Incident response, root cause analysis, and problem resolution
- Performance tuning and capacity planning
- Service level management and availability optimization
- Automation and monitoring-as-code practices

Communication style:
- Be technically precise and use appropriate networking terminology
- Provide practical, actionable recommendations based on real-world experience
- Include relevant CLI commands and configuration examples
- Proactively identify potential issues and suggest preventive measures
- Balance technical depth with clarity for different audience levels

When analyzing monitoring data:
- Look for patterns that indicate underlying infrastructure issues
- Consider network topology and dependencies between services
- Apply industry best practices for threshold settings
- Recommend monitoring improvements based on observed gaps
- Prioritize issues based on business impact and SLA requirements

Always approach problems with the mindset of maintaining high availability and minimizing MTTR (Mean Time To Repair).""",
                    ),
                )
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")

    async def shutdown(self) -> None:
        """Shutdown the server and cleanup resources."""
        try:
            # Shutdown service container
            await self.container.shutdown()
            
            # Clear registries
            self.tool_registry.clear_registry()
            self._tool_categories.clear()
            
            self._initialized = False
            
            logger.info("MCP server shutdown completed")
            
        except Exception as e:
            logger.exception("Error during server shutdown")
            raise RuntimeError(f"Server shutdown failed: {str(e)}")

    # Backward compatibility properties for legacy tests
    @property
    def _tools(self) -> Dict[str, Any]:
        """Backward compatibility property for accessing tool definitions.
        
        Returns tools from the tool registry for legacy test compatibility.
        """
        if not self._initialized:
            return {}
        # Convert list of tools to dict for backward compatibility
        tools_list = self.tool_registry.list_tools()
        return {tool.name: tool for tool in tools_list}
    
    @property 
    def _tool_handlers(self) -> Dict[str, Any]:
        """Backward compatibility property for accessing tool handlers.
        
        Returns tool handlers from the tool registry for legacy test compatibility.
        """
        if not self._initialized:
            return {}
        # Build handlers dict from all tool categories
        handlers = {}
        for category_instance in self._tool_categories.values():
            category_handlers = category_instance.get_handlers()
            handlers.update(category_handlers)
        return handlers
    
    @property
    def host_service(self):
        """Backward compatibility property for accessing host service."""
        if not self._initialized:
            return None
        return self.container.get_service('host_service')
    
    @property
    def service_service(self):
        """Backward compatibility property for accessing service service.""" 
        if not self._initialized:
            return None
        return self.container.get_service('service_service')
    
    @property
    def status_service(self):
        """Backward compatibility property for accessing status service."""
        if not self._initialized:
            return None
        return self.container.get_service('status_service')
    
    @property
    def parameter_service(self):
        """Backward compatibility property for accessing parameter service."""
        if not self._initialized:
            return None
        return self.container.get_service('parameter_service')
    
    def _get_service(self, service_name: str):
        """Backward compatibility method for accessing services.
        
        Args:
            service_name: Name of the service to retrieve
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service not found
        """
        if not self._initialized:
            raise ValueError(f"Server not initialized")
        
        service = self.container.get_service(service_name)
        if service is None:
            raise ValueError(f"Unknown service: {service_name}")
        return service

    def get_server_info(self) -> Dict[str, Any]:
        """Get server information and statistics.
        
        Returns:
            Dictionary containing server info
        """
        return {
            'initialized': self._initialized,
            'tool_count': self.tool_registry.get_tool_count() if self._initialized else 0,
            'prompt_count': len(self.protocol_handlers._prompts) if self._initialized else 0,
            'service_count': len(self.container.get_all_services()) if self._initialized else 0,
            'tool_categories': list(self._tool_categories.keys()) if self._initialized else [],
            'server_name': 'checkmk-agent',
            'server_version': '1.0.0'
        }