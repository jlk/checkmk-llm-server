"""Tests for historical data scraping with various service types.

Tests scraping behavior across different service types like CPU, memory, 
network, disk, temperature, etc.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from checkmk_agent.mcp_server import CheckmkMCPServer
from checkmk_agent.config import AppConfig, CheckmkConfig


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


class TestHistoricalServiceTypes:
    """Test historical scraping with various service types."""

    @pytest.mark.asyncio
    async def test_cpu_load_service_scraping(self, mock_config):
        """Test scraping CPU load metrics."""
        cpu_data = [
            ("2025-01-15T10:00:00", 2.5),
            ("2025-01-15T10:05:00", 3.1),
            ("2025-01-15T10:10:00", 2.8),
            ("2025-01-15T10:15:00", 2.3),
            ("avg", 2.675),
            ("max", 3.1),
            ("min", 2.3)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = cpu_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="server01",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify CPU-specific parsing
            assert result["success"] is True
            assert result["metrics"][0]["title"] == "cpu_load"
            assert result["metrics"][0]["data_points_count"] == 4
            
            # Verify CPU load values are properly parsed
            unified_data = result["unified_data"]
            assert unified_data["summary_stats"]["avg"] == 2.675
            assert unified_data["summary_stats"]["max"] == 3.1
            
            # Verify metric name inference
            assert unified_data["metrics"][0]["name"] == "cpu_load"

    @pytest.mark.asyncio
    async def test_memory_usage_service_scraping(self, mock_config):
        """Test scraping memory usage metrics."""
        memory_data = [
            ("2025-01-15T10:00:00", "85.5%"),
            ("2025-01-15T10:05:00", "87.2%"),
            ("2025-01-15T10:10:00", "86.8%"),
            ("2025-01-15T10:15:00", "84.1%"),
            ("avg", 85.9),
            ("max", 87.2),
            ("min", 84.1)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = memory_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="server01",
                service_description="Memory usage",
                metric_id="mem_used_percent",
                data_source="scraper"
            )
            
            # Verify memory-specific parsing
            assert result["success"] is True
            assert result["metrics"][0]["title"] == "memory_usage"
            
            # Verify percentage values are extracted correctly
            data_points = result["unified_data"]["metrics"][0]["data_points"]
            assert data_points[0]["value"] == 85.5  # % extracted from "85.5%"
            assert data_points[1]["value"] == 87.2
            
            # Verify unit extraction
            # Note: Implementation may extract unit from string values
            assert unified_data["summary_stats"]["avg"] == 85.9

    @pytest.mark.asyncio
    async def test_disk_space_service_scraping(self, mock_config):
        """Test scraping disk space metrics."""
        disk_data = [
            ("2025-01-15T10:00:00", "45.2 GB"),
            ("2025-01-15T10:05:00", "45.8 GB"),
            ("2025-01-15T10:10:00", "46.1 GB"),
            ("2025-01-15T10:15:00", "46.3 GB"),
            ("avg", 45.85),
            ("max", 46.3),
            ("min", 45.2)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = disk_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="server01",
                service_description="Disk space /",
                metric_id="disk_used",
                data_source="scraper"
            )
            
            # Verify disk-specific parsing
            assert result["success"] is True
            assert result["metrics"][0]["title"] == "disk_space_/"
            
            # Verify numeric values are extracted from strings with units
            data_points = result["unified_data"]["metrics"][0]["data_points"]
            assert data_points[0]["value"] == 45.2  # GB extracted from "45.2 GB"
            assert data_points[1]["value"] == 45.8

    @pytest.mark.asyncio
    async def test_network_interface_service_scraping(self, mock_config):
        """Test scraping network interface metrics."""
        network_data = [
            ("2025-01-15T10:00:00", "125.4 Mbit/s"),
            ("2025-01-15T10:05:00", "134.7 Mbit/s"),
            ("2025-01-15T10:10:00", "128.9 Mbit/s"),
            ("2025-01-15T10:15:00", "142.1 Mbit/s"),
            ("avg", 132.775),
            ("max", 142.1),
            ("min", 125.4)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = network_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="switch01",
                service_description="Interface eth0",
                metric_id="if_in_octets",
                data_source="scraper"
            )
            
            # Verify network-specific parsing
            assert result["success"] is True
            assert result["metrics"][0]["title"] == "interface_eth0"
            
            # Verify bandwidth values are extracted correctly
            data_points = result["unified_data"]["metrics"][0]["data_points"]
            assert data_points[0]["value"] == 125.4  # Mbit/s extracted
            assert data_points[3]["value"] == 142.1

    @pytest.mark.asyncio
    async def test_temperature_service_scraping(self, mock_config):
        """Test scraping temperature sensor metrics."""
        temperature_data = [
            ("2025-01-15T10:00:00", "75.5°C"),
            ("2025-01-15T10:05:00", "76.2°C"),
            ("2025-01-15T10:10:00", "77.8°C"),
            ("2025-01-15T10:15:00", "78.1°C"),
            ("avg", 76.9),
            ("max", 78.1),
            ("min", 75.5)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = temperature_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="server01",
                service_description="Temperature CPU",
                metric_id="temp_cpu",
                data_source="scraper"
            )
            
            # Verify temperature-specific parsing
            assert result["success"] is True
            assert result["metrics"][0]["title"] == "temperature_cpu"
            
            # Verify temperature values with units are extracted correctly
            data_points = result["unified_data"]["metrics"][0]["data_points"]
            assert data_points[0]["value"] == 75.5  # °C extracted from "75.5°C"
            assert data_points[2]["value"] == 77.8
            
            # Verify temperature summary statistics
            unified_data = result["unified_data"]
            assert unified_data["summary_stats"]["avg"] == 76.9
            assert unified_data["summary_stats"]["max"] == 78.1

    @pytest.mark.asyncio
    async def test_database_service_scraping(self, mock_config):
        """Test scraping database service metrics."""
        db_data = [
            ("2025-01-15T10:00:00", 1250),
            ("2025-01-15T10:05:00", 1347),
            ("2025-01-15T10:10:00", 1289),
            ("2025-01-15T10:15:00", 1421),
            ("avg", 1326.75),
            ("max", 1421),
            ("min", 1250)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = db_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="db01",
                service_description="MySQL Connections",
                metric_id="connections",
                data_source="scraper"
            )
            
            # Verify database-specific parsing
            assert result["success"] is True
            assert result["metrics"][0]["title"] == "mysql_connections"
            
            # Verify integer values are handled correctly
            data_points = result["unified_data"]["metrics"][0]["data_points"]
            assert data_points[0]["value"] == 1250
            assert data_points[3]["value"] == 1421

    @pytest.mark.asyncio
    async def test_service_with_spaces_and_special_chars(self, mock_config):
        """Test scraping services with spaces and special characters."""
        service_data = [
            ("2025-01-15T10:00:00", 42.5),
            ("2025-01-15T10:05:00", 43.1),
            ("avg", 42.8),
            ("max", 43.1)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = service_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="server01",
                service_description="Custom Check: Special/Service (v2.1)",
                metric_id="custom_metric",
                data_source="scraper"
            )
            
            # Verify service name normalization
            assert result["success"] is True
            assert result["metrics"][0]["title"] == "custom_check:_special/service_(v2.1)"
            
            # Verify data is parsed correctly despite special characters
            data_points = result["unified_data"]["metrics"][0]["data_points"]
            assert len(data_points) == 2
            assert data_points[0]["value"] == 42.5

    @pytest.mark.asyncio
    async def test_service_events_with_different_service_types(self, mock_config):
        """Test service events generation for different service types."""
        # Test with varying values that would generate events
        varying_data = [
            ("2025-01-15T10:00:00", 75.0),
            ("2025-01-15T10:05:00", 78.0),  # Change detected
            ("2025-01-15T10:10:00", 78.0),  # No change
            ("2025-01-15T10:15:00", 82.0),  # Change detected
            ("avg", 78.25),
            ("max", 82.0),
            ("min", 75.0)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = varying_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            list_service_events = tool_handlers["list_service_events"]
            
            result = await list_service_events(
                host_name="server01",
                service_name="Temperature CPU",
                data_source="scraper"
            )
            
            # Verify events are generated from value changes
            assert result["success"] is True
            assert result["data_source"] == "scraper"
            
            events = result["events"]
            # Should detect 2 changes: 75->78 and 78->82
            assert len(events) == 2
            
            # Verify event structure
            assert "temperature_cpu changed from 75.0 to 78.0" in events[0]["text"]
            assert "temperature_cpu changed from 78.0 to 82.0" in events[1]["text"]

    @pytest.mark.asyncio
    async def test_mixed_data_types_service_scraping(self, mock_config):
        """Test scraping with mixed data types (strings, numbers, with units)."""
        mixed_data = [
            ("2025-01-15T10:00:00", "45.2 GB"),  # String with unit
            ("2025-01-15T10:05:00", 46.8),       # Pure number
            ("2025-01-15T10:10:00", "48.1GB"),   # String with unit, no space
            ("2025-01-15T10:15:00", "49.5 GB"),  # String with unit and space
            ("avg", 47.4),
            ("max", 49.5),
            ("min", 45.2)
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = mixed_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="server01",
                service_description="Disk usage",
                metric_id="disk_used",
                data_source="scraper"
            )
            
            # Verify mixed data types are handled correctly
            assert result["success"] is True
            
            data_points = result["unified_data"]["metrics"][0]["data_points"]
            assert len(data_points) == 4
            
            # Verify numeric extraction from various formats
            assert data_points[0]["value"] == 45.2  # From "45.2 GB"
            assert data_points[1]["value"] == 46.8  # Pure number
            assert data_points[2]["value"] == 48.1  # From "48.1GB"
            assert data_points[3]["value"] == 49.5  # From "49.5 GB"

    @pytest.mark.asyncio
    async def test_service_with_no_numeric_data(self, mock_config):
        """Test scraping service that returns non-numeric data."""
        text_data = [
            ("2025-01-15T10:00:00", "OK"),
            ("2025-01-15T10:05:00", "WARNING"),
            ("2025-01-15T10:10:00", "CRITICAL"),
            ("2025-01-15T10:15:00", "OK"),
            # No summary stats for text data
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = text_data
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="server01",
                service_description="Service Status",
                metric_id="status",
                data_source="scraper"
            )
            
            # Verify text data is preserved
            assert result["success"] is True
            
            data_points = result["unified_data"]["metrics"][0]["data_points"]
            assert len(data_points) == 4
            
            # Verify text values are kept as-is
            assert data_points[0]["value"] == "OK"
            assert data_points[1]["value"] == "WARNING"
            assert data_points[2]["value"] == "CRITICAL"
            assert data_points[3]["value"] == "OK"
            
            # No summary stats expected for text data
            assert result["unified_data"]["summary_stats"] == {}

    @pytest.mark.asyncio
    async def test_service_metric_name_inference(self, mock_config):
        """Test metric name inference from different service descriptions."""
        test_cases = [
            ("CPU load", "cpu_load"),
            ("Memory usage", "memory_usage"),
            ("Disk space /var", "disk_space_/var"),
            ("Interface eth0", "interface_eth0"),
            ("Temperature Sensor 1", "temperature_sensor_1"),
            ("MySQL Connections", "mysql_connections"),
            ("Apache HTTP Server", "apache_http_server"),
            ("Check_MK Discovery", "check_mk_discovery"),
        ]
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = [
            ("2025-01-15T10:00:00", 42.0),
            ("avg", 42.0)
        ]
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_agent.api_client.CheckmkClient"):
            await server.initialize()

        with patch('checkmk_scraper.CheckmkHistoricalScraper', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            for service_description, expected_metric_name in test_cases:
                result = await get_metric_history(
                    host_name="server01",
                    service_description=service_description,
                    metric_id="test_metric",
                    data_source="scraper"
                )
                
                # Verify metric name inference
                assert result["success"] is True
                assert result["metrics"][0]["title"] == expected_metric_name
                assert result["unified_data"]["metrics"][0]["name"] == expected_metric_name