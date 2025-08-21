"""Tests for historical data scraping error handling scenarios.

Tests authentication failures, timeouts, network issues, and other error
conditions in the scraping pipeline.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from datetime import datetime

from checkmk_agent.mcp_server import CheckmkMCPServer
from checkmk_agent.config import AppConfig, CheckmkConfig
from checkmk_agent.services.historical_service import HistoricalDataService


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


class TestHistoricalErrorScenarios:
    """Test error handling in historical data scraping."""

    @pytest.mark.asyncio
    async def test_authentication_failure(self, mock_config):
        """Test handling of authentication failures."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises authentication error
        mock_scraper = Mock()
        auth_error = Exception("401 Unauthorized: Invalid credentials")
        mock_scraper.scrape_historical_data.side_effect = auth_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            # Test direct service call
            historical_service = server.historical_service
            
            from checkmk_agent.services.models.historical import HistoricalDataRequest
            request = HistoricalDataRequest(
                host_name="test-host",
                service_name="CPU load",
                period="4h"
            )
            
            result = await historical_service.get_historical_data(request)
            
            # Verify authentication error is handled
            assert result.success is False
            assert "Failed to retrieve historical data" in result.error
            assert result.metadata["error_type"] == "scraper_error"

    @pytest.mark.asyncio
    async def test_network_timeout_error(self, mock_config):
        """Test handling of network timeout errors."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises timeout error
        mock_scraper = Mock()
        timeout_error = asyncio.TimeoutError("Request timeout after 30 seconds")
        mock_scraper.scrape_historical_data.side_effect = timeout_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify timeout error is handled
            assert result["success"] is False
            assert result["data_source"] == "scraper"
            assert "Failed to retrieve historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_connection_refused_error(self, mock_config):
        """Test handling of connection refused errors."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises connection error
        mock_scraper = Mock()
        connection_error = ConnectionRefusedError("Connection refused to test.checkmk.com:80")
        mock_scraper.scrape_historical_data.side_effect = connection_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            list_service_events = tool_handlers["list_service_events"]
            
            result = await list_service_events(
                host_name="test-host",
                service_name="Temperature",
                data_source="scraper"
            )
            
            # Verify connection error is handled
            assert result["success"] is False
            assert result["data_source"] == "scraper"
            assert "Historical data retrieval failed" in result["error"]

    @pytest.mark.asyncio
    async def test_ssl_certificate_error(self, mock_config):
        """Test handling of SSL certificate verification errors."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises SSL error
        import ssl
        mock_scraper = Mock()
        ssl_error = ssl.SSLCertVerificationError("certificate verify failed: self signed certificate")
        mock_scraper.scrape_historical_data.side_effect = ssl_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify SSL error is handled
            assert result["success"] is False
            assert "Failed to retrieve historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_scraper_import_failure(self, mock_config):
        """Test handling when scraper module cannot be imported."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock import failure
        with patch('checkmk_agent.services.web_scraping.ScraperService', side_effect=ImportError("No module named 'web_scraping'")):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify import error is handled
            assert result["success"] is False
            assert result["data_source"] == "scraper"
            assert "Historical service not available" in result["error"] or "Scraper data source implementation" in result["error"]

    @pytest.mark.asyncio
    async def test_scraper_initialization_failure(self, mock_config):
        """Test handling when scraper initialization fails."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper class that fails during initialization
        with patch('checkmk_agent.services.web_scraping.ScraperService', side_effect=ValueError("Invalid configuration")):
            historical_service = server.historical_service
            
            # Test direct service method
            with pytest.raises(ValueError, match="Failed to create scraper instance"):
                historical_service._create_scraper_instance()

    @pytest.mark.asyncio
    async def test_malformed_server_response(self, mock_config):
        """Test handling of malformed responses from Checkmk server."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that returns malformed data
        mock_scraper = Mock()
        malformed_response = "HTTP/1.1 500 Internal Server Error\nContent-Type: text/html\n\n<html><body>Server Error</body></html>"
        mock_scraper.scrape_historical_data.side_effect = ValueError(f"Failed to parse response: {malformed_response}")
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify malformed response error is handled
            assert result["success"] is False
            assert "Failed to retrieve historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_host_not_found_error(self, mock_config):
        """Test handling when requested host is not found."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises host not found error
        mock_scraper = Mock()
        host_error = Exception("404 Not Found: Host 'nonexistent-host' not found")
        mock_scraper.scrape_historical_data.side_effect = host_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            list_service_events = tool_handlers["list_service_events"]
            
            result = await list_service_events(
                host_name="nonexistent-host",
                service_name="CPU load",
                data_source="scraper"
            )
            
            # Verify host not found error is handled
            assert result["success"] is False
            assert "Historical data retrieval failed" in result["error"]

    @pytest.mark.asyncio
    async def test_service_not_found_error(self, mock_config):
        """Test handling when requested service is not found."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises service not found error
        mock_scraper = Mock()
        service_error = Exception("404 Not Found: Service 'nonexistent-service' not found on host 'test-host'")
        mock_scraper.scrape_historical_data.side_effect = service_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="nonexistent-service",
                metric_id="metric1",
                data_source="scraper"
            )
            
            # Verify service not found error is handled
            assert result["success"] is False
            assert "Failed to retrieve historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_insufficient_permissions_error(self, mock_config):
        """Test handling of insufficient permissions errors."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises permission error
        mock_scraper = Mock()
        permission_error = PermissionError("403 Forbidden: Insufficient permissions to access historical data")
        mock_scraper.scrape_historical_data.side_effect = permission_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify permission error is handled
            assert result["success"] is False
            assert "Failed to retrieve historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_scraping_error_with_custom_exception(self, mock_config):
        """Test handling of custom ScrapingError exceptions."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises custom ScrapingError
        mock_scraper = Mock()
        
        # Create a mock ScrapingError class and instance
        with patch('checkmk_agent.services.web_scraping.ScrapingError') as mock_scraping_error_class:
            scraping_error = Exception("Authentication failed: Invalid API key")
            scraping_error.__class__ = mock_scraping_error_class
            mock_scraper.scrape_historical_data.side_effect = scraping_error
            
            # Mock isinstance check to return True for ScrapingError
            def mock_isinstance(obj, cls):
                if cls == mock_scraping_error_class:
                    return obj == scraping_error
                return isinstance(obj, cls)
            
            with patch('builtins.isinstance', side_effect=mock_isinstance):
                with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
                    tool_handlers = server._tool_handlers
                    get_metric_history = tool_handlers["get_metric_history"]
                    
                    result = await get_metric_history(
                        host_name="test-host",
                        service_description="CPU load",
                        metric_id="load1",
                        data_source="scraper"
                    )
                    
                    # Verify ScrapingError is handled specifically
                    assert result["success"] is False
                    assert result["data_source"] == "scraper"
                    assert "Scraping failed" in result["error"]

    @pytest.mark.asyncio
    async def test_data_parsing_error(self, mock_config):
        """Test handling of data parsing errors in the historical service."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that returns data that causes parsing errors
        mock_scraper = Mock()
        problematic_data = [
            (None, "invalid"),  # None timestamp
            ("", ""),  # Empty strings
            ("not-a-timestamp", float('inf')),  # Invalid timestamp and infinite value
            ("2025-01-15T10:00:00", complex(1, 2)),  # Complex number
        ]
        mock_scraper.scrape_historical_data.return_value = problematic_data
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify parsing errors are handled gracefully
            assert result["success"] is True  # Should succeed despite parsing errors
            assert result["metrics"] == []  # But no valid data points
            assert "parse_errors" in result["unified_data"]["metrics"] or len(result["metrics"]) == 0

    @pytest.mark.asyncio
    async def test_memory_error_during_scraping(self, mock_config):
        """Test handling of memory errors during large data scraping."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises memory error
        mock_scraper = Mock()
        memory_error = MemoryError("Unable to allocate memory for large dataset")
        mock_scraper.scrape_historical_data.side_effect = memory_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                time_range_hours=8760,  # 1 year of data
                data_source="scraper"
            )
            
            # Verify memory error is handled
            assert result["success"] is False
            assert "Failed to retrieve historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_configuration_error(self, mock_config):
        """Test handling of configuration errors."""
        # Modify config to have invalid settings
        mock_config.checkmk.server_url = "invalid-url"
        mock_config.checkmk.username = None
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises configuration error
        mock_scraper = Mock()
        config_error = ValueError("Invalid server URL: 'invalid-url' is not a valid URL")
        mock_scraper.scrape_historical_data.side_effect = config_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify configuration error is handled
            assert result["success"] is False
            assert "Failed to retrieve historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_concurrent_access_error(self, mock_config):
        """Test handling of concurrent access issues."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that occasionally fails due to concurrent access
        mock_scraper = Mock()
        concurrent_error = Exception("429 Too Many Requests: Rate limit exceeded")
        mock_scraper.scrape_historical_data.side_effect = concurrent_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Test multiple concurrent requests
            tasks = []
            for i in range(5):
                task = get_metric_history(
                    host_name=f"test-host-{i}",
                    service_description="CPU load",
                    metric_id="load1",
                    data_source="scraper"
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify all requests handle rate limiting gracefully
            for result in results:
                if isinstance(result, dict):
                    assert result["success"] is False
                    assert "Failed to retrieve historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_fallback_to_rest_api_on_scraper_failure(self, mock_config):
        """Test that system doesn't automatically fallback to REST API on scraper failure."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that fails
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.side_effect = Exception("Scraper failed")
        
        # Mock REST API service
        mock_rest_result = Mock()
        mock_rest_result.success = True
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            with patch.object(server.metrics_service, 'get_metric_history', return_value=mock_rest_result) as mock_rest_api:
                tool_handlers = server._tool_handlers
                get_metric_history = tool_handlers["get_metric_history"]
                
                result = await get_metric_history(
                    host_name="test-host",
                    service_description="CPU load",
                    metric_id="load1",
                    data_source="scraper"  # Explicitly request scraper
                )
                
                # Verify scraper failure is reported, no fallback to REST API
                assert result["success"] is False
                assert result["data_source"] == "scraper"
                mock_rest_api.assert_not_called()  # Should not fallback automatically

    @pytest.mark.asyncio
    async def test_error_metadata_collection(self, mock_config):
        """Test that error metadata is properly collected and reported."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper with detailed error
        mock_scraper = Mock()
        detailed_error = Exception("Connection timeout after 30.5 seconds to test.checkmk.com:80")
        mock_scraper.scrape_historical_data.side_effect = detailed_error
        
        with patch('checkmk_agent.services.web_scraping.ScraperService', return_value=mock_scraper):
            historical_service = server.historical_service
            
            from checkmk_agent.services.models.historical import HistoricalDataRequest
            request = HistoricalDataRequest(
                host_name="test-host",
                service_name="CPU load",
                period="4h"
            )
            
            result = await historical_service.get_historical_data(request)
            
            # Verify error metadata is collected
            assert result.success is False
            assert result.metadata is not None
            assert "error_type" in result.metadata
            assert result.metadata["error_type"] == "scraper_error"
            
            # Verify request ID is included in error response
            assert result.request_id is not None
            assert result.request_id.startswith("req_")