"""Centralized configuration for tool registration and management."""

import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field

from mcp.types import Tool, Prompt, PromptArgument

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """Metadata for a registered tool."""
    category: str
    priority: int = 1
    requires_services: List[str] = field(default_factory=list)
    description: str = ""
    examples: List[str] = field(default_factory=list)


@dataclass
class ServiceDependency:
    """Configuration for service dependencies."""
    name: str
    required: bool = True
    initialization_order: int = 1


class RegistryConfig:
    """
    Centralized configuration for tool registration and service management.
    
    This class provides:
    - Tool configuration management
    - Registration patterns and categories
    - Service dependencies configuration
    - Tool loading and organization strategies
    """

    def __init__(self):
        """Initialize registry configuration."""
        self._tool_categories = {
            "host": "Host management and operations",
            "service": "Service monitoring and management",
            "parameter": "Parameter configuration and optimization",
            "status": "Status monitoring and dashboards",
            "event": "Event and alert management",
            "metrics": "Performance metrics and analytics",
            "business": "Business intelligence and reporting",
            "advanced": "Advanced features and batch operations",
        }
        
        self._service_dependencies = {
            "host_service": ServiceDependency("host_service", required=True, initialization_order=1),
            "service_service": ServiceDependency("service_service", required=True, initialization_order=2),
            "status_service": ServiceDependency("status_service", required=True, initialization_order=3),
            "parameter_service": ServiceDependency("parameter_service", required=True, initialization_order=4),
            "event_service": ServiceDependency("event_service", required=False, initialization_order=5),
            "metrics_service": ServiceDependency("metrics_service", required=False, initialization_order=6),
            "bi_service": ServiceDependency("bi_service", required=False, initialization_order=7),
            "historical_service": ServiceDependency("historical_service", required=False, initialization_order=8),
            "streaming_host_service": ServiceDependency("streaming_host_service", required=False, initialization_order=9),
            "streaming_service_service": ServiceDependency("streaming_service_service", required=False, initialization_order=10),
            "cached_host_service": ServiceDependency("cached_host_service", required=False, initialization_order=11),
        }

        self._tool_registration_patterns = {
            "standard": self._create_standard_tool_pattern,
            "parameter": self._create_parameter_tool_pattern,
            "streaming": self._create_streaming_tool_pattern,
            "batch": self._create_batch_tool_pattern,
        }

    def get_tool_categories(self) -> Dict[str, str]:
        """
        Get available tool categories.
        
        Returns:
            Dict[str, str]: Category names mapped to descriptions
        """
        return self._tool_categories.copy()

    def get_service_dependencies(self) -> Dict[str, ServiceDependency]:
        """
        Get service dependency configuration.
        
        Returns:
            Dict[str, ServiceDependency]: Service dependencies
        """
        return self._service_dependencies.copy()

    def get_required_services(self) -> List[str]:
        """
        Get list of required services.
        
        Returns:
            List[str]: Names of required services
        """
        return [
            name for name, dep in self._service_dependencies.items()
            if dep.required
        ]

    def get_service_initialization_order(self) -> List[str]:
        """
        Get services in initialization order.
        
        Returns:
            List[str]: Service names sorted by initialization order
        """
        return sorted(
            self._service_dependencies.keys(),
            key=lambda name: self._service_dependencies[name].initialization_order
        )

    def create_tool_metadata(
        self,
        category: str,
        priority: int = 1,
        requires_services: Optional[List[str]] = None,
        description: str = "",
        examples: Optional[List[str]] = None
    ) -> ToolMetadata:
        """
        Create tool metadata with validation.
        
        Args:
            category: Tool category
            priority: Tool priority (1-10, higher = more important)
            requires_services: List of required service names
            description: Tool description
            examples: Usage examples
            
        Returns:
            ToolMetadata: Validated tool metadata
            
        Raises:
            ValueError: If category is invalid
        """
        if category not in self._tool_categories:
            raise ValueError(f"Invalid category '{category}'. Valid categories: {list(self._tool_categories.keys())}")

        if priority < 1 or priority > 10:
            raise ValueError("Priority must be between 1 and 10")

        return ToolMetadata(
            category=category,
            priority=priority,
            requires_services=requires_services or [],
            description=description,
            examples=examples or []
        )

    def get_host_tools_config(self) -> Dict[str, Any]:
        """Get configuration for host management tools."""
        return {
            "category": "host",
            "tools": [
                "list_hosts",
                "create_host", 
                "get_host",
                "update_host",
                "delete_host",
                "list_host_services",
                "stream_hosts",
            ],
            "required_services": ["host_service"],
            "optional_services": ["streaming_host_service", "cached_host_service"]
        }

    def get_service_tools_config(self) -> Dict[str, Any]:
        """Get configuration for service management tools."""
        return {
            "category": "service",
            "tools": [
                "list_all_services",
                "acknowledge_service_problem",
                "create_service_downtime",
            ],
            "required_services": ["service_service"],
            "optional_services": ["streaming_service_service"]
        }

    def get_parameter_tools_config(self) -> Dict[str, Any]:
        """Get configuration for parameter management tools."""
        return {
            "category": "parameter",
            "tools": [
                "get_effective_parameters",
                "set_service_parameters",
                "discover_service_ruleset",
                "get_parameter_schema",
                "validate_service_parameters",
                "update_parameter_rule",
                "get_service_handler_info",
                "get_specialized_defaults",
                "validate_with_handler",
                "get_parameter_suggestions",
                "list_parameter_handlers",
                "list_parameter_rules",
                "bulk_set_parameters",
                "search_parameter_rules",
                "validate_specialized_parameters",
                "create_specialized_rule",
                "discover_parameter_handlers",
                "bulk_parameter_operations",
                "get_handler_info",
                "search_services_by_handler",
                "export_parameter_configuration",
            ],
            "required_services": ["parameter_service"],
            "optional_services": []
        }

    def get_status_tools_config(self) -> Dict[str, Any]:
        """Get configuration for status monitoring tools."""
        return {
            "category": "status",
            "tools": [
                "get_health_dashboard",
                "get_critical_problems",
                "analyze_host_health",
            ],
            "required_services": ["status_service"],
            "optional_services": []
        }

    def get_event_tools_config(self) -> Dict[str, Any]:
        """Get configuration for event management tools."""
        return {
            "category": "event",
            "tools": [
                "list_service_events",
                "list_host_events",
                "get_recent_critical_events",
                "acknowledge_event",
                "search_events",
            ],
            "required_services": ["event_service"],
            "optional_services": []
        }

    def get_metrics_tools_config(self) -> Dict[str, Any]:
        """Get configuration for metrics tools."""
        return {
            "category": "metrics",
            "tools": [
                "get_service_metrics",
                "get_metric_history",
                "get_server_metrics",
            ],
            "required_services": ["metrics_service"],
            "optional_services": ["historical_service"]
        }

    def get_business_tools_config(self) -> Dict[str, Any]:
        """Get configuration for business intelligence tools."""
        return {
            "category": "business",
            "tools": [
                "get_business_status_summary",
                "get_critical_business_services",
            ],
            "required_services": ["bi_service"],
            "optional_services": []
        }

    def get_advanced_tools_config(self) -> Dict[str, Any]:
        """Get configuration for advanced feature tools."""
        return {
            "category": "advanced",
            "tools": [
                "batch_create_hosts",
                "get_system_info",
                "clear_cache",
            ],
            "required_services": [],
            "optional_services": ["batch_processor", "cached_host_service"]
        }

    def get_all_tool_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tool configurations by category.
        
        Returns:
            Dict[str, Dict[str, Any]]: All tool configurations
        """
        return {
            "host": self.get_host_tools_config(),
            "service": self.get_service_tools_config(),
            "parameter": self.get_parameter_tools_config(),
            "status": self.get_status_tools_config(),
            "event": self.get_event_tools_config(),
            "metrics": self.get_metrics_tools_config(),
            "business": self.get_business_tools_config(),
            "advanced": self.get_advanced_tools_config(),
        }

    def get_prompt_definitions(self) -> Dict[str, Prompt]:
        """
        Get standard prompt definitions.
        
        Returns:
            Dict[str, Prompt]: Prompt definitions mapped by name
        """
        return {
            "analyze_host_health": Prompt(
                name="analyze_host_health",
                description="Analyze the health of a specific host with detailed recommendations",
                arguments=[
                    PromptArgument(
                        name="host_name",
                        description="Name of the host to analyze",
                        required=True,
                    ),
                    PromptArgument(
                        name="include_grade",
                        description="Include health grade (A+ through F)",
                        required=False,
                    ),
                ],
            ),
            "troubleshoot_service": Prompt(
                name="troubleshoot_service",
                description="Comprehensive troubleshooting analysis for a service problem",
                arguments=[
                    PromptArgument(
                        name="host_name",
                        description="Host name where the service is running",
                        required=True,
                    ),
                    PromptArgument(
                        name="service_name",
                        description="Name of the service to troubleshoot",
                        required=True,
                    ),
                    PromptArgument(
                        name="include_history",
                        description="Include historical performance data",
                        required=False,
                    ),
                ],
            ),
            # Additional prompts would be defined here...
        }

    def validate_tool_registration(self, tool_name: str, category: str, required_services: List[str]) -> bool:
        """
        Validate a tool registration request.
        
        Args:
            tool_name: Name of the tool to register
            category: Tool category
            required_services: List of required services
            
        Returns:
            bool: True if registration is valid
            
        Raises:
            ValueError: If validation fails
        """
        # Validate category
        if category not in self._tool_categories:
            raise ValueError(f"Invalid category '{category}'. Valid categories: {list(self._tool_categories.keys())}")

        # Validate required services
        for service in required_services:
            if service not in self._service_dependencies:
                raise ValueError(f"Unknown service dependency: {service}")

        # Tool name validation
        if not tool_name or not isinstance(tool_name, str):
            raise ValueError("Tool name must be a non-empty string")

        return True

    def _create_standard_tool_pattern(self, **kwargs) -> Dict[str, Any]:
        """Create standard tool registration pattern."""
        return {
            "type": "standard",
            "error_handling": "sanitize",
            "request_tracking": True,
            "caching": False,
        }

    def _create_parameter_tool_pattern(self, **kwargs) -> Dict[str, Any]:
        """Create parameter tool registration pattern."""
        return {
            "type": "parameter",
            "error_handling": "sanitize",
            "request_tracking": True,
            "caching": True,
            "validation": "strict",
        }

    def _create_streaming_tool_pattern(self, **kwargs) -> Dict[str, Any]:
        """Create streaming tool registration pattern."""
        return {
            "type": "streaming", 
            "error_handling": "sanitize",
            "request_tracking": True,
            "caching": False,
            "streaming": True,
        }

    def _create_batch_tool_pattern(self, **kwargs) -> Dict[str, Any]:
        """Create batch tool registration pattern."""
        return {
            "type": "batch",
            "error_handling": "sanitize",
            "request_tracking": True,
            "caching": False,
            "batch_processing": True,
        }