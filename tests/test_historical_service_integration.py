"""Integration tests for historical service registration in MCP server."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from checkmk_agent.mcp_server import CheckmkMCPServer
from checkmk_agent.config import AppConfig, CheckmkConfig
from checkmk_agent.services.historical_service import HistoricalDataService, CachedHistoricalDataService
from checkmk_agent.services.models.historical import HistoricalDataRequest


@pytest.fixture
def mock_checkmk_config():
    """Create a mock Checkmk configuration."""
    return Mock(spec=CheckmkConfig, 
                server_url="http://test.checkmk.com",
                username="test_user", 
                password="test_pass",
                site="test_site",
                max_retries=3,
                request_timeout=30)


@pytest.fixture  
def mock_historical_config():
    """Create a mock historical data configuration."""
    return {
        'source': 'scraper',
        'cache_ttl': 60,
        'scraper_timeout': 30
    }


@pytest.fixture
def mock_config(mock_checkmk_config, mock_historical_config):
    """Create a mock application configuration."""
    config = Mock(spec=AppConfig)
    config.checkmk = mock_checkmk_config
    config.historical_data = mock_historical_config
    return config


class TestHistoricalServiceIntegration:
    """Test historical service integration with MCP server."""

    @pytest.mark.asyncio
    async def test_historical_service_registration(self, mock_config):
        """Test that historical service is properly registered in MCP server."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Verify historical service is initialized
        assert server.historical_service is not None
        assert isinstance(server.historical_service, CachedHistoricalDataService)
        
        # Verify historical service is in _ensure_services check
        assert server._ensure_services() == True
        
        # Verify historical service is in service registry
        historical_service = server._get_service("historical")
        assert historical_service is server.historical_service

    @pytest.mark.asyncio
    async def test_historical_service_initialization_with_config(self, mock_config):
        """Test historical service initialization with configuration values."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Verify service configuration
        historical_service = server.historical_service
        assert historical_service.source == "scraper"
        assert historical_service.cache_ttl == 60
        assert historical_service.scraper_timeout == 30

    @pytest.mark.asyncio
    async def test_historical_service_registry_lookup(self, mock_config):
        """Test service registry lookup for historical service."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Test service lookup by name
        service = server._get_service("historical")
        assert service is not None
        assert isinstance(service, CachedHistoricalDataService)

        # Test invalid service name raises error
        with pytest.raises(ValueError, match="Unknown service"):
            server._get_service("nonexistent")

    @pytest.mark.asyncio
    async def test_historical_service_caching_capabilities(self, mock_config):
        """Test that historical service has caching capabilities."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        historical_service = server.historical_service
        
        # Verify it's a cached service
        assert isinstance(historical_service, CachedHistoricalDataService)
        
        # Verify it has cache methods
        assert hasattr(historical_service, '_cache')
        assert hasattr(historical_service, 'cached')
        assert hasattr(historical_service, 'get_cache_stats')
        assert hasattr(historical_service, 'invalidate_cache_pattern')

    @pytest.mark.asyncio
    async def test_historical_service_factory_pattern(self, mock_config):
        """Test that historical service implements scraper factory pattern."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        historical_service = server.historical_service
        
        # Verify factory method exists
        assert hasattr(historical_service, '_create_scraper_instance')
        
        # Test factory method with mock scraper
        with patch('checkmk_agent.services.historical_service.ScraperService') as mock_scraper_class:
            mock_scraper = Mock()
            mock_scraper_class.return_value = mock_scraper
            
            scraper = historical_service._create_scraper_instance()
            assert scraper is mock_scraper
            mock_scraper_class.assert_called_once_with(mock_config.checkmk)

    @pytest.mark.asyncio
    async def test_historical_service_error_handling(self, mock_config):
        """Test historical service error handling patterns."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        historical_service = server.historical_service
        
        # Test handling when scraper import fails
        with patch('checkmk_agent.services.historical_service.ScraperService', side_effect=ImportError("Scraper not available")):
            with pytest.raises(ImportError, match="Failed to import CheckmkHistoricalScraper"):
                historical_service._create_scraper_instance()

    @pytest.mark.asyncio
    async def test_historical_data_request_handling(self, mock_config):
        """Test historical data request model integration."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Test that request model validation works
        request = HistoricalDataRequest(
            host_name="test-host",
            service_name="CPU load",
            period="4h"
        )
        
        assert request.host_name == "test-host"
        assert request.service_name == "CPU load"
        assert request.period == "4h"
        assert request.metric_name is None
        assert request.source is None

    @pytest.mark.asyncio 
    async def test_historical_service_multiple_inheritance(self, mock_config):
        """Test that CachedHistoricalDataService properly inherits from both classes."""
        server = CheckmkMCPServer(mock_config)

        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        historical_service = server.historical_service
        
        # Verify multiple inheritance
        assert isinstance(historical_service, CachedHistoricalDataService)
        assert isinstance(historical_service, HistoricalDataService)
        
        # Verify it has methods from both parent classes
        assert hasattr(historical_service, 'get_historical_data')  # From HistoricalDataService
        assert hasattr(historical_service, 'get_available_metrics')  # From HistoricalDataService
        assert hasattr(historical_service, '_cache')  # From CachingService
        assert hasattr(historical_service, 'cached')  # From CachingService

    @pytest.mark.asyncio
    async def test_service_initialization_order(self, mock_config):
        """Test that historical service is initialized in correct order."""
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            await server.initialize()
            
            # Verify all standard services are initialized
            assert server.host_service is not None
            assert server.status_service is not None
            assert server.service_service is not None
            assert server.parameter_service is not None
            assert server.event_service is not None
            assert server.metrics_service is not None
            assert server.bi_service is not None
            assert server.historical_service is not None  # Our new service
            
            # Verify enhanced services are also initialized
            assert server.streaming_host_service is not None
            assert server.streaming_service_service is not None
            assert server.cached_host_service is not None

    def test_historical_config_defaults(self, mock_checkmk_config):
        """Test historical service handles missing configuration gracefully."""
        # Create config without historical_data section
        config = Mock(spec=AppConfig)
        config.checkmk = mock_checkmk_config
        # No historical_data attribute
        
        with patch("checkmk_agent.async_api_client.AsyncCheckmkClient"):
            service = CachedHistoricalDataService(Mock(), config)
            
            # Should use defaults
            assert service.source == "scraper"
            assert service.cache_ttl == 60  
            assert service.scraper_timeout == 30