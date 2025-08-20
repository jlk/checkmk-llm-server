"""Tests for MCP server protocol handlers."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import List

from mcp.types import Resource, Prompt, PromptMessage, GetPromptResult, TextContent
from mcp.server import Server
from pydantic import AnyUrl

from checkmk_agent.mcp_server.handlers.protocol import ProtocolHandlers
from checkmk_agent.services.models.services import ServiceState


class TestProtocolHandlers:
    """Test cases for ProtocolHandlers class."""

    @pytest.fixture
    def protocol_handlers(self):
        """Create a ProtocolHandlers instance for testing."""
        return ProtocolHandlers()

    @pytest.fixture
    def mock_service_provider(self):
        """Create a mock service provider."""
        provider = Mock()
        provider._ensure_services = Mock(return_value=True)
        provider._handle_service_result = Mock(return_value='{"success": true}')
        
        # Mock services
        provider.status_service = Mock()
        provider.host_service = Mock()
        provider.service_service = Mock()
        provider.cached_host_service = Mock()
        
        # Mock streaming methods
        provider._stream_hosts_resource = AsyncMock(return_value='{"streaming": "hosts"}')
        provider._stream_services_resource = AsyncMock(return_value='{"streaming": "services"}')
        
        return provider

    def test_protocol_handlers_initialization(self, protocol_handlers):
        """Test protocol handlers initializes correctly."""
        assert protocol_handlers._prompts == {}
        assert protocol_handlers._advanced_resources_registered is False

    def test_register_prompts(self, protocol_handlers):
        """Test prompt registration."""
        mock_prompt = Mock(spec=Prompt)
        mock_prompt.name = "test_prompt"
        
        prompts = {"test_prompt": mock_prompt}
        protocol_handlers.register_prompts(prompts)
        
        assert "test_prompt" in protocol_handlers._prompts
        assert protocol_handlers._prompts["test_prompt"] == mock_prompt

    def test_get_basic_resources(self, protocol_handlers):
        """Test getting basic resource definitions."""
        resources = protocol_handlers.get_basic_resources()
        
        assert len(resources) == 5
        assert all(isinstance(r, Resource) for r in resources)
        
        # Check specific resources
        uris = [str(r.uri) for r in resources]
        assert "checkmk://dashboard/health" in uris
        assert "checkmk://dashboard/problems" in uris
        assert "checkmk://hosts/status" in uris
        assert "checkmk://services/problems" in uris
        assert "checkmk://metrics/performance" in uris

    def test_get_streaming_resources(self, protocol_handlers):
        """Test getting streaming resource definitions."""
        resources = protocol_handlers.get_streaming_resources()
        
        assert len(resources) == 4
        assert all(isinstance(r, Resource) for r in resources)
        
        # Check specific resources
        uris = [str(r.uri) for r in resources]
        assert "checkmk://stream/hosts" in uris
        assert "checkmk://stream/services" in uris
        assert "checkmk://metrics/server" in uris
        assert "checkmk://cache/stats" in uris

    def test_get_all_resources(self, protocol_handlers):
        """Test getting all resource definitions."""
        resources = protocol_handlers.get_all_resources()
        
        # Should include both basic and streaming resources
        assert len(resources) == 9
        
        basic_count = len(protocol_handlers.get_basic_resources())
        streaming_count = len(protocol_handlers.get_streaming_resources())
        assert len(resources) == basic_count + streaming_count

    @pytest.mark.asyncio
    async def test_handle_read_resource_dashboard_health(self, protocol_handlers, mock_service_provider):
        """Test reading dashboard health resource."""
        mock_service_provider.status_service.get_health_dashboard = AsyncMock(return_value=Mock())
        
        uri = AnyUrl("checkmk://dashboard/health")
        result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})
        
        mock_service_provider.status_service.get_health_dashboard.assert_called_once()
        mock_service_provider._handle_service_result.assert_called_once()
        assert result == '{"success": true}'

    @pytest.mark.asyncio
    async def test_handle_read_resource_dashboard_problems(self, protocol_handlers, mock_service_provider):
        """Test reading dashboard problems resource."""
        mock_service_provider.status_service.get_critical_problems = AsyncMock(return_value=Mock())
        
        uri = AnyUrl("checkmk://dashboard/problems")
        result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})
        
        mock_service_provider.status_service.get_critical_problems.assert_called_once()
        assert result == '{"success": true}'

    @pytest.mark.asyncio
    async def test_handle_read_resource_hosts_status(self, protocol_handlers, mock_service_provider):
        """Test reading hosts status resource."""
        mock_service_provider.host_service.list_hosts = AsyncMock(return_value=Mock())
        
        uri = AnyUrl("checkmk://hosts/status")
        result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})
        
        mock_service_provider.host_service.list_hosts.assert_called_once_with(include_status=True)
        assert result == '{"success": true}'

    @pytest.mark.asyncio
    async def test_handle_read_resource_services_problems(self, protocol_handlers, mock_service_provider):
        """Test reading services problems resource."""
        mock_service_provider.service_service.list_all_services = AsyncMock(return_value=Mock())
        
        uri = AnyUrl("checkmk://services/problems")
        result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})
        
        expected_states = [ServiceState.WARNING, ServiceState.CRITICAL, ServiceState.UNKNOWN]
        mock_service_provider.service_service.list_all_services.assert_called_once_with(
            state_filter=expected_states
        )
        assert result == '{"success": true}'

    @pytest.mark.asyncio
    async def test_handle_read_resource_streaming_hosts(self, protocol_handlers, mock_service_provider):
        """Test reading streaming hosts resource."""
        uri = AnyUrl("checkmk://stream/hosts")
        result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})
        
        mock_service_provider._stream_hosts_resource.assert_called_once()
        assert result == '{"streaming": "hosts"}'

    @pytest.mark.asyncio
    async def test_handle_read_resource_streaming_services(self, protocol_handlers, mock_service_provider):
        """Test reading streaming services resource."""
        uri = AnyUrl("checkmk://stream/services")
        result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})
        
        mock_service_provider._stream_services_resource.assert_called_once()
        assert result == '{"streaming": "services"}'

    @pytest.mark.asyncio
    async def test_handle_read_resource_server_metrics(self, protocol_handlers, mock_service_provider):
        """Test reading server metrics resource."""
        mock_stats = {"cpu": 50, "memory": 75}
        
        with patch('checkmk_agent.mcp_server.handlers.protocol.get_metrics_collector') as mock_collector:
            mock_collector.return_value.get_stats = AsyncMock(return_value=mock_stats)
            
            uri = AnyUrl("checkmk://metrics/server")
            result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})
            
            mock_collector.assert_called_once()
            assert '"cpu": 50' in result
            assert '"memory": 75' in result

    @pytest.mark.asyncio
    async def test_handle_read_resource_cache_stats_enabled(self, protocol_handlers, mock_service_provider):
        """Test reading cache stats when cache is enabled."""
        mock_service_provider.cached_host_service.get_cache_stats = AsyncMock(
            return_value={"hits": 100, "misses": 10}
        )
        
        uri = AnyUrl("checkmk://cache/stats")
        result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})
        
        mock_service_provider.cached_host_service.get_cache_stats.assert_called_once()
        assert '"hits": 100' in result
        assert '"misses": 10' in result

    @pytest.mark.asyncio
    async def test_handle_read_resource_cache_stats_disabled(self, protocol_handlers, mock_service_provider):
        """Test reading cache stats when cache is disabled."""
        # Remove cached_host_service to simulate disabled cache
        delattr(mock_service_provider, 'cached_host_service')
        
        uri = AnyUrl("checkmk://cache/stats")
        result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})
        
        assert '"error": "Cache not enabled"' in result

    @pytest.mark.asyncio
    async def test_handle_read_resource_custom_handler(self, protocol_handlers, mock_service_provider):
        """Test reading resource with custom handler."""
        custom_handler = AsyncMock(return_value='{"custom": "data"}')
        resource_handlers = {"checkmk://custom/resource": custom_handler}
        
        uri = AnyUrl("checkmk://custom/resource")
        result = await protocol_handlers.handle_read_resource(uri, mock_service_provider, resource_handlers)
        
        custom_handler.assert_called_once()
        assert result == '{"custom": "data"}'

    @pytest.mark.asyncio
    async def test_handle_read_resource_unknown_uri(self, protocol_handlers, mock_service_provider):
        """Test reading unknown resource URI."""
        uri = AnyUrl("checkmk://unknown/resource")
        
        with pytest.raises(RuntimeError, match="Failed to read resource"):
            await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})

    @pytest.mark.asyncio
    async def test_handle_read_resource_services_not_initialized(self, protocol_handlers, mock_service_provider):
        """Test reading resource when services not initialized."""
        mock_service_provider._ensure_services.return_value = False
        
        uri = AnyUrl("checkmk://dashboard/health")
        
        with pytest.raises(RuntimeError, match="Services not initialized"):
            await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})

    @pytest.mark.asyncio
    async def test_handle_read_resource_exception(self, protocol_handlers, mock_service_provider):
        """Test reading resource with exception."""
        mock_service_provider.status_service.get_health_dashboard = AsyncMock(
            side_effect=Exception("Service error")
        )
        
        uri = AnyUrl("checkmk://dashboard/health")
        
        with pytest.raises(RuntimeError, match="Failed to read resource"):
            await protocol_handlers.handle_read_resource(uri, mock_service_provider, {})

    @pytest.mark.asyncio
    async def test_handle_get_prompt_analyze_host_health(self, protocol_handlers, mock_service_provider):
        """Test handling analyze_host_health prompt."""
        # Mock service responses
        mock_host_data = Mock()
        mock_host_data.model_dump.return_value = {"name": "test_host", "state": "UP"}
        
        mock_host_result = Mock()
        mock_host_result.success = True
        mock_host_result.data = mock_host_data
        
        mock_health_result = Mock()
        mock_health_result.success = True
        mock_health_result.data = {"grade": "B+", "issues": []}
        
        mock_service_provider.host_service.get_host = AsyncMock(return_value=mock_host_result)
        mock_service_provider.status_service.analyze_host_health = AsyncMock(return_value=mock_health_result)
        
        # Test prompt handling
        result = await protocol_handlers.handle_get_prompt(
            "analyze_host_health", 
            {"host_name": "test_host", "include_grade": "true"}, 
            mock_service_provider
        )
        
        assert isinstance(result, GetPromptResult)
        assert result.description == "Analyzing health of host 'test_host'"
        assert len(result.messages) == 1
        
        # Verify service calls
        mock_service_provider.host_service.get_host.assert_called_once_with(
            name="test_host", include_status=True
        )
        mock_service_provider.status_service.analyze_host_health.assert_called_once_with(
            host_name="test_host", include_grade=True, include_recommendations=True
        )

    @pytest.mark.asyncio
    async def test_handle_get_prompt_unknown_prompt(self, protocol_handlers, mock_service_provider):
        """Test handling unknown prompt."""
        result = await protocol_handlers.handle_get_prompt("unknown_prompt", {}, mock_service_provider)
        
        assert isinstance(result, GetPromptResult)
        assert "Error generating prompt" in result.description
        assert len(result.messages) == 1
        assert "unknown_prompt" in result.messages[0].content.text

    @pytest.mark.asyncio
    async def test_handle_get_prompt_services_not_initialized(self, protocol_handlers, mock_service_provider):
        """Test handling prompt when services not initialized."""
        mock_service_provider._ensure_services.return_value = False
        
        with pytest.raises(RuntimeError, match="Services not initialized"):
            await protocol_handlers.handle_get_prompt("analyze_host_health", {}, mock_service_provider)

    def test_register_protocol_handlers(self, protocol_handlers, mock_service_provider):
        """Test registering protocol handlers with MCP server."""
        mock_server = Mock(spec=Server)
        
        # Mock decorators
        mock_server.list_resources.return_value = lambda x: x
        mock_server.read_resource.return_value = lambda x: x
        mock_server.list_prompts.return_value = lambda x: x
        mock_server.get_prompt.return_value = lambda x: x
        
        protocol_handlers.register_protocol_handlers(mock_server, mock_service_provider)
        
        # Verify decorators were called
        mock_server.list_resources.assert_called_once()
        mock_server.read_resource.assert_called_once()
        mock_server.list_prompts.assert_called_once()
        mock_server.get_prompt.assert_called_once()