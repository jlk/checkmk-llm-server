"""Integration tests for Phase 2 MCP server refactoring components."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any

from mcp.types import Tool, Resource, Prompt
from mcp.server import Server
from pydantic import AnyUrl

from checkmk_agent.mcp_server.handlers.registry import ToolRegistry
from checkmk_agent.mcp_server.handlers.protocol import ProtocolHandlers
from checkmk_agent.mcp_server.config.registry import RegistryConfig


class TestPhase2Integration:
    """Integration tests for Phase 2 extracted components."""

    @pytest.fixture
    def registry_config(self):
        """Create registry configuration."""
        return RegistryConfig()

    @pytest.fixture
    def tool_registry(self):
        """Create tool registry."""
        return ToolRegistry()

    @pytest.fixture
    def protocol_handlers(self):
        """Create protocol handlers."""
        return ProtocolHandlers()

    @pytest.fixture
    def mock_service_provider(self):
        """Create a comprehensive mock service provider."""
        provider = Mock()
        provider._ensure_services = Mock(return_value=True)
        provider._handle_service_result = Mock(return_value='{"success": true}')
        
        # Mock all required services
        provider.host_service = Mock()
        provider.service_service = Mock()
        provider.status_service = Mock()
        provider.parameter_service = Mock()
        provider.event_service = Mock()
        provider.metrics_service = Mock()
        provider.bi_service = Mock()
        provider.historical_service = Mock()
        provider.streaming_host_service = Mock()
        provider.streaming_service_service = Mock()
        provider.cached_host_service = Mock()
        
        # Mock streaming methods
        provider._stream_hosts_resource = AsyncMock(return_value='{"streaming": "hosts"}')
        provider._stream_services_resource = AsyncMock(return_value='{"streaming": "services"}')
        
        return provider

    @pytest.fixture
    def mock_server(self):
        """Create a mock MCP server."""
        server = Mock(spec=Server)
        server.list_resources = Mock(return_value=lambda x: x)
        server.read_resource = Mock(return_value=lambda x: x)
        server.list_tools = Mock(return_value=lambda x: x)
        server.call_tool = Mock(return_value=lambda x: x)
        server.list_prompts = Mock(return_value=lambda x: x)
        server.get_prompt = Mock(return_value=lambda x: x)
        return server

    def test_registry_config_tool_categories_comprehensive(self, registry_config):
        """Test that registry config provides comprehensive tool categorization."""
        categories = registry_config.get_tool_categories()
        all_configs = registry_config.get_all_tool_configs()
        
        # Verify all categories have configurations
        assert set(categories.keys()) == set(all_configs.keys())
        
        # Verify each category has expected structure
        for category, config in all_configs.items():
            assert config["category"] == category
            assert isinstance(config["tools"], list)
            assert len(config["tools"]) > 0
            assert isinstance(config["required_services"], list)
            assert isinstance(config["optional_services"], list)

    def test_tool_registry_and_config_integration(self, registry_config, tool_registry):
        """Test integration between tool registry and configuration."""
        # Create tool metadata using config
        metadata = registry_config.create_tool_metadata(
            category="host",
            priority=5,
            requires_services=["host_service"],
            description="Test host tool"
        )
        
        # Create mock tool and handler
        mock_tool = Tool(
            name="test_host_tool",
            description="Test host management tool",
            inputSchema={"type": "object", "properties": {}}
        )
        mock_handler = AsyncMock()
        
        # Register tool in registry
        tool_registry.register_tool("test_host_tool", mock_tool, mock_handler, metadata.__dict__)
        
        # Verify registration
        assert tool_registry.has_tool("test_host_tool")
        assert tool_registry.get_tool_handler("test_host_tool") == mock_handler
        assert tool_registry.get_tool_definition("test_host_tool") == mock_tool
        
        # Verify metadata is preserved
        retrieved_metadata = tool_registry.get_tool_metadata("test_host_tool")
        assert retrieved_metadata["category"] == "host"
        assert retrieved_metadata["priority"] == 5

    def test_protocol_handlers_resource_integration(self, protocol_handlers, mock_service_provider):
        """Test protocol handlers resource management integration."""
        # Test resource definitions
        basic_resources = protocol_handlers.get_basic_resources()
        streaming_resources = protocol_handlers.get_streaming_resources()
        all_resources = protocol_handlers.get_all_resources()
        
        # Verify resource structure
        assert len(all_resources) == len(basic_resources) + len(streaming_resources)
        
        # Verify all resources are properly formed
        for resource in all_resources:
            assert isinstance(resource, Resource)
            assert resource.name
            assert resource.description
            assert resource.mimeType

    @pytest.mark.asyncio
    async def test_full_mcp_server_integration(self, registry_config, tool_registry, protocol_handlers, mock_service_provider, mock_server):
        """Test full integration of all Phase 2 components."""
        # 1. Setup configuration-driven tool registration
        host_config = registry_config.get_host_tools_config()
        
        # Create mock tools for host category
        for tool_name in host_config["tools"][:3]:  # Test first 3 tools
            mock_tool = Tool(
                name=tool_name,
                description=f"Mock {tool_name} tool",
                inputSchema={"type": "object", "properties": {}}
            )
            mock_handler = AsyncMock(return_value={"success": True, "tool": tool_name})
            
            metadata = registry_config.create_tool_metadata(
                category=host_config["category"],
                requires_services=host_config["required_services"]
            )
            
            tool_registry.register_tool(tool_name, mock_tool, mock_handler, metadata.__dict__)
        
        # 2. Register prompts with protocol handlers
        prompt_definitions = registry_config.get_prompt_definitions()
        protocol_handlers.register_prompts(prompt_definitions)
        
        # 3. Register MCP handlers with server
        tool_registry.register_mcp_handlers(mock_server, mock_service_provider._ensure_services)
        protocol_handlers.register_protocol_handlers(mock_server, mock_service_provider)
        
        # 4. Verify all handlers were registered
        mock_server.list_resources.assert_called_once()
        mock_server.read_resource.assert_called_once()
        mock_server.list_tools.assert_called_once()
        mock_server.call_tool.assert_called_once()
        mock_server.list_prompts.assert_called_once()
        mock_server.get_prompt.assert_called_once()
        
        # 5. Verify tool registry state
        assert tool_registry.get_tool_count() == 3
        host_tools = tool_registry.get_tools_by_category("host")
        assert len(host_tools) == 3

    @pytest.mark.asyncio
    async def test_service_dependency_validation(self, registry_config, tool_registry, mock_service_provider):
        """Test service dependency validation across components."""
        # Get service dependencies from config
        dependencies = registry_config.get_service_dependencies()
        required_services = registry_config.get_required_services()
        
        # Verify required services are available in mock service provider
        for service_name in required_services:
            assert hasattr(mock_service_provider, service_name)
        
        # Test tool registration with valid dependencies
        valid_metadata = registry_config.create_tool_metadata(
            category="host",
            requires_services=["host_service"]  # Valid service
        )
        
        # Should not raise exception
        registry_config.validate_tool_registration(
            "valid_tool",
            "host", 
            ["host_service"]
        )
        
        # Test tool registration with invalid dependencies
        with pytest.raises(ValueError, match="Unknown service dependency"):
            registry_config.validate_tool_registration(
                "invalid_tool",
                "host",
                ["nonexistent_service"]
            )

    def test_configuration_completeness(self, registry_config):
        """Test that configuration covers all expected tool categories."""
        categories = registry_config.get_tool_categories()
        all_configs = registry_config.get_all_tool_configs()
        
        # Verify expected categories exist
        expected_categories = {
            "host", "service", "parameter", "status",
            "event", "metrics", "business", "advanced"
        }
        assert set(categories.keys()) == expected_categories
        
        # Verify each category has tools defined
        total_tools = 0
        for config in all_configs.values():
            assert len(config["tools"]) > 0
            total_tools += len(config["tools"])
        
        # Should have reasonable number of tools (Phase 0 analysis found 44+ tools)
        assert total_tools >= 40

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, tool_registry, protocol_handlers, mock_service_provider):
        """Test error handling across all components."""
        # Test tool registry error handling - get_tool_handler returns None for unknown tools
        handler = tool_registry.get_tool_handler("nonexistent_tool")
        assert handler is None  # This is the correct behavior
        
        # Test protocol handlers error handling
        with pytest.raises(RuntimeError, match="Failed to read resource"):
            await protocol_handlers.handle_read_resource(
                AnyUrl("checkmk://invalid/resource"), 
                mock_service_provider, 
                {}
            )
        
        # Test service not initialized error handling
        mock_service_provider._ensure_services.return_value = False
        
        with pytest.raises(RuntimeError, match="Services not initialized"):
            await protocol_handlers.handle_read_resource(
                AnyUrl("checkmk://dashboard/health"),
                mock_service_provider,
                {}
            )

    def test_registry_statistics_and_monitoring(self, registry_config, tool_registry):
        """Test registry statistics and monitoring capabilities."""
        # Register tools from multiple categories
        categories_configs = registry_config.get_all_tool_configs()
        
        for category, config in list(categories_configs.items())[:3]:  # Test first 3 categories
            tool_name = config["tools"][0]  # Take first tool from each category
            
            mock_tool = Tool(
                name=tool_name,
                description=f"Mock {tool_name}",
                inputSchema={"type": "object", "properties": {}}
            )
            mock_handler = AsyncMock()
            
            metadata = registry_config.create_tool_metadata(category=category)
            tool_registry.register_tool(tool_name, mock_tool, mock_handler, metadata.__dict__)
        
        # Get registry statistics
        stats = tool_registry.get_tool_stats()
        
        assert stats["total_tools"] == 3
        assert len(stats["categories"]) <= 3  # At most 3 categories
        assert len(stats["tool_names"]) == 3
        
        # Test category-specific queries
        for category in stats["categories"]:
            category_tools = tool_registry.get_tools_by_category(category)
            assert len(category_tools) >= 1

    @pytest.mark.asyncio
    async def test_backward_compatibility_imports(self):
        """Test that Phase 2 components maintain backward compatibility."""
        # Test imports work as expected
        try:
            from checkmk_agent.mcp_server.handlers.registry import ToolRegistry
            from checkmk_agent.mcp_server.handlers.protocol import ProtocolHandlers
            from checkmk_agent.mcp_server.config.registry import RegistryConfig
            
            # Verify classes can be instantiated
            registry = ToolRegistry()
            handlers = ProtocolHandlers()
            config = RegistryConfig()
            
            assert isinstance(registry, ToolRegistry)
            assert isinstance(handlers, ProtocolHandlers)
            assert isinstance(config, RegistryConfig)
            
        except ImportError as e:
            pytest.fail(f"Import failed, backward compatibility broken: {e}")

    def test_registry_clear_and_reset(self, tool_registry):
        """Test registry clearing and reset functionality."""
        # Add some tools
        mock_tool = Tool(
            name="test_tool",
            description="Test tool",
            inputSchema={"type": "object", "properties": {}}
        )
        mock_handler = AsyncMock()
        
        tool_registry.register_tool("test_tool", mock_tool, mock_handler)
        assert tool_registry.get_tool_count() == 1
        
        # Clear registry
        tool_registry.clear_registry()
        assert tool_registry.get_tool_count() == 0
        assert not tool_registry.has_tool("test_tool")
        
        # Verify registry can be used again after clearing
        tool_registry.register_tool("new_tool", mock_tool, mock_handler)
        assert tool_registry.get_tool_count() == 1
        assert tool_registry.has_tool("new_tool")