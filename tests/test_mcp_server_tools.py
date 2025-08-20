"""Test MCP server tool registration after fixes."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from checkmk_agent.mcp_server.server import CheckmkMCPServer
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
    async def test_server_tool_registration(self, mock_config):
        """Test that the consolidated server registers all tools correctly."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Check tools are registered (refactored architecture has 37 tools)
        assert len(server._tools) == 37
        assert len(server._tool_handlers) == 37

        # Check host tools
        assert "list_hosts" in server._tools
        assert "create_host" in server._tools
        assert "get_host" in server._tools
        assert "update_host" in server._tools
        assert "delete_host" in server._tools
        assert "list_host_services" in server._tools

        # Check service tools
        assert "list_all_services" in server._tools
        assert "acknowledge_service_problem" in server._tools
        assert "create_service_downtime" in server._tools

        # Check monitoring tools
        assert "get_health_dashboard" in server._tools
        assert "get_critical_problems" in server._tools
        assert "analyze_host_health" in server._tools

        # Check parameter tools
        assert "get_effective_parameters" in server._tools
        assert "set_service_parameters" in server._tools
        assert "validate_service_parameters" in server._tools
        assert "update_parameter_rule" in server._tools

        # Check event tools
        assert "list_service_events" in server._tools
        assert "list_host_events" in server._tools
        assert "acknowledge_event" in server._tools

        # Check metrics tools
        assert "get_service_metrics" in server._tools
        assert "get_metric_history" in server._tools

        # Check business tools
        assert "get_business_status_summary" in server._tools
        assert "get_critical_business_services" in server._tools

        # Check advanced tools
        assert "stream_hosts" in server._tools
        assert "batch_create_hosts" in server._tools
        assert "get_server_metrics" in server._tools
        assert "clear_cache" in server._tools
        assert "get_system_info" in server._tools

        # Check tool/handler consistency
        assert set(server._tools.keys()) == set(server._tool_handlers.keys())

    @pytest.mark.asyncio
    async def test_tool_handlers_callable(self, mock_config):
        """Test that tool handlers are properly callable."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock the host service
        server.host_service.list_hosts = AsyncMock(
            return_value=Mock(
                success=True,
                data=Mock(model_dump=lambda: {"hosts": []}, total_count=0),
                error=None,
                warnings=[],
            )
        )

        # Test calling a handler
        list_hosts_handler = server._tool_handlers["list_hosts"]
        result = await list_hosts_handler()

        assert result["success"] is True
        assert "data" in result
        assert "message" in result
