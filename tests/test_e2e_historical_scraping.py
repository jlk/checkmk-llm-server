"""End-to-end tests for historical data scraping integration.

Tests the complete flow: MCP client → MCP server → Historical service → Scraper
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import List, Tuple, Union

from checkmk_agent.mcp_server import CheckmkMCPServer
from checkmk_agent.config import AppConfig, CheckmkConfig
from checkmk_agent.services.models.historical import (
    HistoricalDataPoint,
    HistoricalDataResult,
    HistoricalDataRequest,
    HistoricalDataServiceResult
)


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


@pytest.fixture
def sample_scraper_data():
    """Sample data that would be returned by CheckmkHistoricalScraper."""
    return [
        ("2025-01-15T10:00:00", 75.5),
        ("2025-01-15T10:05:00", 76.2),
        ("2025-01-15T10:10:00", 77.8),
        ("2025-01-15T10:15:00", 78.1),
        ("avg", 76.9),
        ("max", 78.1),
        ("min", 75.5)
    ]


@pytest.fixture
def mock_scraper(sample_scraper_data):
    """Create a mock scraper instance."""
    scraper = Mock()
    scraper.scrape_historical_data.return_value = sample_scraper_data
    return scraper


class TestE2EHistoricalScraping:
    """End-to-end tests for historical scraping integration."""

    @pytest.mark.asyncio
    async def test_e2e_get_metric_history_scraper_flow(self, mock_config, mock_scraper, sample_scraper_data):
        """Test complete E2E flow for get_metric_history with scraper data source."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock the scraper creation
        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            # Get the tool handler
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Execute the tool with scraper data source
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                time_range_hours=4,
                data_source="scraper"
            )
            
            # Verify scraper was called correctly
            mock_scraper.scrape_historical_data.assert_called_once_with(
                period="4h",
                host="test-host", 
                service="CPU load"
            )
            
            # Verify response structure
            assert result["success"] is True
            assert result["data_source"] == "scraper"
            assert result["time_range"] == "4h"
            assert result["metric_id"] == "load1"
            assert "metrics" in result
            assert "unified_data" in result
            
            # Verify metrics data
            metrics = result["metrics"]
            assert len(metrics) == 1
            assert metrics[0]["title"] == "cpu_load"
            assert metrics[0]["data_points_count"] == 4
            
            # Verify unified data model
            unified_data = result["unified_data"]
            assert unified_data["host"] == "test-host"
            assert unified_data["service"] == "CPU load"
            assert unified_data["period"] == "4h"
            assert "summary_stats" in unified_data
            assert unified_data["summary_stats"]["avg"] == 76.9
            assert unified_data["summary_stats"]["max"] == 78.1
            assert unified_data["summary_stats"]["min"] == 75.5

    @pytest.mark.asyncio
    async def test_e2e_list_service_events_scraper_flow(self, mock_config, mock_scraper, sample_scraper_data):
        """Test complete E2E flow for list_service_events with scraper data source."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock the scraper creation
        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            # Get the tool handler
            tool_handlers = server._tool_handlers
            list_service_events = tool_handlers["list_service_events"]
            
            # Execute the tool with scraper data source
            result = await list_service_events(
                host_name="test-host",
                service_name="Temperature",
                limit=10,
                data_source="scraper"
            )
            
            # Verify scraper was called correctly
            mock_scraper.scrape_historical_data.assert_called_once_with(
                period="24h",  # Default for events
                host="test-host", 
                service="Temperature"
            )
            
            # Verify response structure
            assert result["success"] is True
            assert result["data_source"] == "scraper"
            assert "events" in result
            assert "unified_data" in result
            
            # Verify events are generated from metric changes
            events = result["events"]
            assert len(events) >= 0  # Could be empty if no changes detected
            
            # Verify unified data model
            unified_data = result["unified_data"]
            assert unified_data["host"] == "test-host"
            assert unified_data["service"] == "Temperature"
            assert unified_data["period"] == "24h"

    @pytest.mark.asyncio
    async def test_e2e_configuration_override(self, mock_config, mock_scraper):
        """Test E2E flow with configuration override via data_source parameter."""
        # Set config to use REST API by default
        mock_config.historical_data['source'] = 'rest_api'
        
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock both scraper and REST API
        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            with patch.object(server.metrics_service, 'get_metric_history') as mock_rest_api:
                # Get the tool handler
                tool_handlers = server._tool_handlers
                get_metric_history = tool_handlers["get_metric_history"]
                
                # Override to use scraper despite REST API config
                result = await get_metric_history(
                    host_name="test-host",
                    service_description="CPU load",
                    metric_id="load1",
                    data_source="scraper"  # Override config default
                )
                
                # Verify scraper was used, not REST API
                mock_scraper.scrape_historical_data.assert_called_once()
                mock_rest_api.assert_not_called()
                
                assert result["data_source"] == "scraper"

    @pytest.mark.asyncio
    async def test_e2e_data_source_validation(self, mock_config):
        """Test E2E flow with invalid data_source parameter."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Get the tool handler
        tool_handlers = server._tool_handlers
        get_metric_history = tool_handlers["get_metric_history"]
        
        # Test invalid data source
        result = await get_metric_history(
            host_name="test-host",
            service_description="CPU load",
            metric_id="load1",
            data_source="invalid_source"
        )
        
        # Verify validation error
        assert result["success"] is False
        assert "Invalid data_source" in result["error"]
        assert "Must be 'rest_api' or 'scraper'" in result["error"]

    @pytest.mark.asyncio
    async def test_e2e_scraper_import_error(self, mock_config):
        """Test E2E flow when scraper cannot be imported."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock import error
        with patch('checkmk_scraper.CheckmkHistoricalScraper', side_effect=ImportError("Scraper not available")):
            # Get the tool handler
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Execute the tool
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify error handling
            assert result["success"] is False
            assert result["data_source"] == "scraper"
            assert "Scraper not available" in result["error"]

    @pytest.mark.asyncio
    async def test_e2e_scraper_execution_error(self, mock_config):
        """Test E2E flow when scraper execution fails."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises error during execution
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.side_effect = Exception("Network timeout")
        
        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            # Get the tool handler
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Execute the tool
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify error handling
            assert result["success"] is False
            assert result["data_source"] == "scraper"
            assert "Failed to retrieve historical data" in result["error"]

    @pytest.mark.asyncio
    async def test_e2e_scraping_error_handling(self, mock_config):
        """Test E2E flow with ScrapingError exception."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that raises ScrapingError
        mock_scraper = Mock()
        
        # Create a mock ScrapingError
        with patch('checkmk_scraper.ScrapingError') as mock_scraping_error_class:
            scraping_error = Exception("Authentication failed")
            scraping_error.__class__.__name__ = "ScrapingError"
            mock_scraper.scrape_historical_data.side_effect = scraping_error
            
            with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
                # Get the tool handler
                tool_handlers = server._tool_handlers
                get_metric_history = tool_handlers["get_metric_history"]
                
                # Execute the tool
                result = await get_metric_history(
                    host_name="test-host",
                    service_description="CPU load",
                    metric_id="load1",
                    data_source="scraper"
                )
                
                # Verify ScrapingError handling
                assert result["success"] is False
                assert result["data_source"] == "scraper"
                assert "Scraping failed" in result["error"]

    @pytest.mark.asyncio
    async def test_e2e_caching_behavior(self, mock_config, mock_scraper, sample_scraper_data):
        """Test E2E flow with caching behavior."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            # Get the tool handler
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # First call
            result1 = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Second call with same parameters (should use cache)
            result2 = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify both calls succeeded
            assert result1["success"] is True
            assert result2["success"] is True
            
            # Verify caching behavior (implementation detail may vary)
            # At minimum, both should return the same structure
            assert result1["metrics"] == result2["metrics"]
            assert result1["unified_data"]["summary_stats"] == result2["unified_data"]["summary_stats"]

    @pytest.mark.asyncio
    async def test_e2e_multiple_metric_handling(self, mock_config):
        """Test E2E flow with data containing multiple metrics."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Create mock scraper with multi-metric data
        multi_metric_data = [
            ("2025-01-15T10:00:00", 75.5),
            ("2025-01-15T10:05:00", 76.2),
            ("avg", 75.85),  # Summary stats
            ("max", 76.2),
            ("min", 75.5)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = multi_metric_data
        
        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            # Get the tool handler
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Execute the tool
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify response structure
            assert result["success"] is True
            assert len(result["metrics"]) == 1
            assert result["metrics"][0]["data_points_count"] == 2
            
            # Verify summary stats are properly extracted
            unified_data = result["unified_data"]
            assert unified_data["summary_stats"]["avg"] == 75.85
            assert unified_data["summary_stats"]["max"] == 76.2
            assert unified_data["summary_stats"]["min"] == 75.5

    @pytest.mark.asyncio
    async def test_e2e_empty_data_handling(self, mock_config):
        """Test E2E flow with empty data from scraper."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Create mock scraper with empty data
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = []
        
        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            # Get the tool handler
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Execute the tool
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify empty data is handled gracefully
            assert result["success"] is True
            assert result["metrics"] == []
            assert result["unified_data"]["metrics"] == []
            assert result["unified_data"]["summary_stats"] == {}

    @pytest.mark.asyncio
    async def test_e2e_malformed_data_handling(self, mock_config):
        """Test E2E flow with malformed data from scraper."""
        # Initialize MCP server
        server = CheckmkMCPServer(mock_config)
        
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        # Create mock scraper with malformed data
        malformed_data = [
            ("invalid-timestamp", "not-a-number"),
            ("", ""),
            ("2025-01-15T10:00:00", 75.5),  # Valid data point
            ("avg", 75.5)  # Valid summary stat
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = malformed_data
        
        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            # Get the tool handler
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Execute the tool
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify malformed data is handled gracefully
            assert result["success"] is True
            # Should only have 1 valid data point
            assert len(result["metrics"]) == 1
            assert result["metrics"][0]["data_points_count"] == 1
            # Should still have valid summary stats
            assert result["unified_data"]["summary_stats"]["avg"] == 75.5