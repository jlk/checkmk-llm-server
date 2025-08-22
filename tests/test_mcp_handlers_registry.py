"""Tests for MCP server tool registry handlers."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any

from mcp.types import Tool
from mcp.server import Server

from checkmk_mcp_server.mcp_server.handlers.registry import ToolRegistry


class TestToolRegistry:
    """Test cases for ToolRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a ToolRegistry instance for testing."""
        return ToolRegistry()

    @pytest.fixture
    def mock_tool(self):
        """Create a mock Tool for testing."""
        return Tool(
            name="test_tool",
            description="A test tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "param": {"type": "string"}
                }
            }
        )

    @pytest.fixture
    def mock_handler(self):
        """Create a mock async handler for testing."""
        handler = AsyncMock()
        handler.return_value = {"success": True, "data": "test result"}
        return handler

    def test_registry_initialization(self, registry):
        """Test registry initializes correctly."""
        assert registry._tools == {}
        assert registry._tool_handlers == {}
        assert registry._tool_metadata == {}

    def test_register_tool_basic(self, registry, mock_tool, mock_handler):
        """Test basic tool registration."""
        metadata = {"category": "test", "priority": 1}
        
        registry.register_tool("test_tool", mock_tool, mock_handler, metadata)
        
        assert "test_tool" in registry._tools
        assert "test_tool" in registry._tool_handlers
        assert "test_tool" in registry._tool_metadata
        assert registry._tools["test_tool"] == mock_tool
        assert registry._tool_handlers["test_tool"] == mock_handler
        assert registry._tool_metadata["test_tool"] == metadata

    def test_register_tool_without_metadata(self, registry, mock_tool, mock_handler):
        """Test tool registration without metadata."""
        registry.register_tool("test_tool", mock_tool, mock_handler)
        
        assert registry._tool_metadata["test_tool"] == {}

    def test_register_tool_overwrite_warning(self, registry, mock_tool, mock_handler, caplog):
        """Test that overwriting a tool generates a warning."""
        registry.register_tool("test_tool", mock_tool, mock_handler)
        
        with caplog.at_level("WARNING"):
            registry.register_tool("test_tool", mock_tool, mock_handler)
        
        assert "Tool 'test_tool' is already registered, overwriting" in caplog.text

    def test_unregister_tool_success(self, registry, mock_tool, mock_handler):
        """Test successful tool unregistration."""
        registry.register_tool("test_tool", mock_tool, mock_handler)
        
        result = registry.unregister_tool("test_tool")
        
        assert result is True
        assert "test_tool" not in registry._tools
        assert "test_tool" not in registry._tool_handlers
        assert "test_tool" not in registry._tool_metadata

    def test_unregister_tool_not_found(self, registry):
        """Test unregistering non-existent tool."""
        result = registry.unregister_tool("nonexistent_tool")
        assert result is False

    def test_get_tool_handler_found(self, registry, mock_tool, mock_handler):
        """Test getting tool handler when tool exists."""
        registry.register_tool("test_tool", mock_tool, mock_handler)
        
        handler = registry.get_tool_handler("test_tool")
        assert handler == mock_handler

    def test_get_tool_handler_not_found(self, registry):
        """Test getting tool handler when tool doesn't exist."""
        handler = registry.get_tool_handler("nonexistent_tool")
        assert handler is None

    def test_get_tool_definition_found(self, registry, mock_tool, mock_handler):
        """Test getting tool definition when tool exists."""
        registry.register_tool("test_tool", mock_tool, mock_handler)
        
        definition = registry.get_tool_definition("test_tool")
        assert definition == mock_tool

    def test_get_tool_definition_not_found(self, registry):
        """Test getting tool definition when tool doesn't exist."""
        definition = registry.get_tool_definition("nonexistent_tool")
        assert definition is None

    def test_get_tool_metadata_found(self, registry, mock_tool, mock_handler):
        """Test getting tool metadata when tool exists."""
        metadata = {"category": "test", "priority": 5}
        registry.register_tool("test_tool", mock_tool, mock_handler, metadata)
        
        result_metadata = registry.get_tool_metadata("test_tool")
        assert result_metadata == metadata

    def test_get_tool_metadata_not_found(self, registry):
        """Test getting tool metadata when tool doesn't exist."""
        metadata = registry.get_tool_metadata("nonexistent_tool")
        assert metadata == {}

    def test_list_tools(self, registry, mock_tool, mock_handler):
        """Test listing all registered tools."""
        registry.register_tool("test_tool", mock_tool, mock_handler)
        
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0] == mock_tool

    def test_list_tool_names(self, registry, mock_tool, mock_handler):
        """Test listing all tool names."""
        registry.register_tool("test_tool", mock_tool, mock_handler)
        
        names = registry.list_tool_names()
        assert names == ["test_tool"]

    def test_get_tools_by_category(self, registry, mock_tool, mock_handler):
        """Test getting tools by category."""
        metadata1 = {"category": "host", "priority": 1}
        metadata2 = {"category": "service", "priority": 1}
        
        registry.register_tool("host_tool", mock_tool, mock_handler, metadata1)
        registry.register_tool("service_tool", mock_tool, mock_handler, metadata2)
        
        host_tools = registry.get_tools_by_category("host")
        service_tools = registry.get_tools_by_category("service")
        empty_tools = registry.get_tools_by_category("nonexistent")
        
        assert host_tools == ["host_tool"]
        assert service_tools == ["service_tool"]
        assert empty_tools == []

    def test_get_tool_count(self, registry, mock_tool, mock_handler):
        """Test getting tool count."""
        assert registry.get_tool_count() == 0
        
        registry.register_tool("test_tool", mock_tool, mock_handler)
        assert registry.get_tool_count() == 1

    def test_has_tool(self, registry, mock_tool, mock_handler):
        """Test checking if tool exists."""
        assert not registry.has_tool("test_tool")
        
        registry.register_tool("test_tool", mock_tool, mock_handler)
        assert registry.has_tool("test_tool")

    def test_get_tool_stats(self, registry, mock_tool, mock_handler):
        """Test getting registry statistics."""
        metadata1 = {"category": "host", "priority": 1}
        metadata2 = {"category": "host", "priority": 2}
        metadata3 = {"category": "service", "priority": 1}
        
        registry.register_tool("host_tool1", mock_tool, mock_handler, metadata1)
        registry.register_tool("host_tool2", mock_tool, mock_handler, metadata2)
        registry.register_tool("service_tool", mock_tool, mock_handler, metadata3)
        
        stats = registry.get_tool_stats()
        
        assert stats["total_tools"] == 3
        assert stats["categories"]["host"] == 2
        assert stats["categories"]["service"] == 1
        assert set(stats["tool_names"]) == {"host_tool1", "host_tool2", "service_tool"}

    @pytest.mark.asyncio
    async def test_register_mcp_handlers_list_tools(self, registry, mock_tool, mock_handler):
        """Test MCP list_tools handler registration."""
        mock_server = Mock(spec=Server)
        mock_services_check = Mock(return_value=True)
        
        # Mock the server decorators
        list_tools_decorator = Mock()
        mock_server.list_tools.return_value = list_tools_decorator
        
        registry.register_tool("test_tool", mock_tool, mock_handler)
        registry.register_mcp_handlers(mock_server, mock_services_check)
        
        # Verify the decorator was called
        mock_server.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_mcp_handlers_call_tool_success(self, registry, mock_tool, mock_handler):
        """Test MCP call_tool handler for successful tool call."""
        mock_server = Mock(spec=Server)
        mock_services_check = Mock(return_value=True)
        
        # Mock the server decorators and capture the handler functions
        call_tool_handler = None
        
        def capture_call_tool_handler(func):
            nonlocal call_tool_handler
            call_tool_handler = func
            return func
        
        mock_server.call_tool.return_value = capture_call_tool_handler
        
        # Register tool and handlers
        registry.register_tool("test_tool", mock_tool, mock_handler)
        registry.register_mcp_handlers(mock_server, mock_services_check)
        
        # Test the call_tool handler
        with patch('checkmk_mcp_server.mcp_server.handlers.registry.generate_request_id', return_value='req_123456'):
            with patch('checkmk_mcp_server.mcp_server.handlers.registry.set_request_id'):
                result = await call_tool_handler("test_tool", {"param": "value"})
        
        # Verify handler was called with correct arguments
        mock_handler.assert_called_once_with(param="value")
        
        # Verify response structure
        assert result["isError"] is False
        assert result["meta"]["request_id"] == "req_123456"
        assert "content" in result

    @pytest.mark.asyncio
    async def test_register_mcp_handlers_call_tool_unknown(self, registry):
        """Test MCP call_tool handler for unknown tool."""
        mock_server = Mock(spec=Server)
        mock_services_check = Mock(return_value=True)
        
        call_tool_handler = None
        
        def capture_call_tool_handler(func):
            nonlocal call_tool_handler
            call_tool_handler = func
            return func
        
        mock_server.call_tool.return_value = capture_call_tool_handler
        
        registry.register_mcp_handlers(mock_server, mock_services_check)
        
        # Test unknown tool
        with pytest.raises(ValueError, match="Unknown tool: unknown_tool"):
            with patch('checkmk_mcp_server.mcp_server.handlers.registry.generate_request_id', return_value='req_123456'):
                with patch('checkmk_mcp_server.mcp_server.handlers.registry.set_request_id'):
                    await call_tool_handler("unknown_tool", {})

    @pytest.mark.asyncio
    async def test_register_mcp_handlers_services_not_initialized(self, registry):
        """Test MCP call_tool handler when services not initialized."""
        mock_server = Mock(spec=Server)
        mock_services_check = Mock(return_value=False)
        
        call_tool_handler = None
        
        def capture_call_tool_handler(func):
            nonlocal call_tool_handler
            call_tool_handler = func
            return func
        
        mock_server.call_tool.return_value = capture_call_tool_handler
        
        registry.register_mcp_handlers(mock_server, mock_services_check)
        
        # Test services not initialized
        with pytest.raises(RuntimeError, match="Services not initialized"):
            with patch('checkmk_mcp_server.mcp_server.handlers.registry.generate_request_id', return_value='req_123456'):
                with patch('checkmk_mcp_server.mcp_server.handlers.registry.set_request_id'):
                    await call_tool_handler("test_tool", {})

    def test_clear_registry(self, registry, mock_tool, mock_handler):
        """Test clearing the registry."""
        registry.register_tool("test_tool", mock_tool, mock_handler)
        assert registry.get_tool_count() == 1
        
        registry.clear_registry()
        assert registry.get_tool_count() == 0
        assert registry._tools == {}
        assert registry._tool_handlers == {}
        assert registry._tool_metadata == {}