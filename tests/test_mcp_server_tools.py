"""Test MCP server tool registration after fixes."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from checkmk_agent.mcp_server.server import CheckmkMCPServer
from checkmk_agent.mcp_server.enhanced_server import EnhancedCheckmkMCPServer
from checkmk_agent.config import AppConfig


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock(spec=AppConfig)
    config.checkmk = Mock()
    config.checkmk.server_url = "http://test.checkmk.com"
    config.checkmk.username = "test_user"
    config.checkmk.password = "test_pass"
    config.checkmk.site = "test_site"
    return config


class TestMCPServerTools:
    """Test MCP server tool registration."""
    
    @pytest.mark.asyncio
    async def test_basic_server_tool_registration(self, mock_config):
        """Test that basic server registers tools correctly."""
        server = CheckmkMCPServer(mock_config)
        
        with patch('checkmk_agent.api_client.CheckmkClient'):
            await server.initialize()
        
        # Check tools are registered
        assert len(server._tools) == 14
        assert len(server._tool_handlers) == 14
        
        # Check essential tools
        assert "list_hosts" in server._tools
        assert "create_host" in server._tools
        assert "get_health_dashboard" in server._tools
        assert "list_all_services" in server._tools
        
        # Check tool/handler consistency
        assert set(server._tools.keys()) == set(server._tool_handlers.keys())
    
    @pytest.mark.asyncio
    async def test_enhanced_server_tool_registration(self, mock_config):
        """Test that enhanced server registers all tools correctly."""
        server = EnhancedCheckmkMCPServer(mock_config)
        
        with patch('checkmk_agent.api_client.CheckmkClient'):
            await server.initialize()
        
        # Check tools are registered
        assert len(server._tools) == 18
        assert len(server._tool_handlers) == 18
        
        # Check standard tools
        assert "list_hosts" in server._tools
        assert "create_host" in server._tools
        assert "get_health_dashboard" in server._tools
        
        # Check advanced tools
        assert "stream_hosts" in server._tools
        assert "batch_create_hosts" in server._tools
        assert "get_server_metrics" in server._tools
        assert "clear_cache" in server._tools
        
        # Check tool/handler consistency
        assert set(server._tools.keys()) == set(server._tool_handlers.keys())
    
    @pytest.mark.asyncio
    async def test_tool_handlers_callable(self, mock_config):
        """Test that tool handlers are properly callable."""
        server = CheckmkMCPServer(mock_config)
        
        with patch('checkmk_agent.api_client.CheckmkClient'):
            await server.initialize()
        
        # Mock the host service
        server.host_service.list_hosts = AsyncMock(
            return_value=Mock(
                success=True,
                data=Mock(
                    model_dump=lambda: {"hosts": []},
                    total_count=0
                ),
                error=None,
                warnings=[]
            )
        )
        
        # Test calling a handler
        list_hosts_handler = server._tool_handlers["list_hosts"]
        result = await list_hosts_handler()
        
        assert result["success"] is True
        assert "data" in result
        assert "message" in result