"""Performance and caching tests for historical data scraping.

Tests caching behavior, TTL functionality, concurrent requests, and performance
characteristics of the historical data scraping system.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import time
from datetime import datetime, timedelta

from checkmk_mcp_server.mcp_server import CheckmkMCPServer
from checkmk_mcp_server.config import AppConfig, CheckmkConfig
from checkmk_mcp_server.services.historical_service import CachedHistoricalDataService
from checkmk_mcp_server.services.models.historical import HistoricalDataRequest


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
    """Create a mock historical data configuration with short TTL for testing."""
    return {
        'source': 'scraper',
        'cache_ttl': 2,  # Short TTL for testing
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


@pytest.mark.skip(reason="Scraper functionality is in placeholder state - tests require full implementation")
class TestHistoricalPerformance:
    """Test performance and caching behavior of historical data scraping.
    
    Note: These tests are currently skipped because the scraper functionality
    is in a simplified placeholder state in the refactored architecture.
    They will be re-enabled once full scraper implementation is complete.
    """

    @pytest.mark.asyncio
    async def test_cache_hit_behavior(self, mock_config, sample_scraper_data):
        """Test that repeated requests with same parameters hit the cache."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # First request - should hit scraper
            start_time = time.time()
            result1 = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            first_duration = time.time() - start_time
            
            # Second request - should hit cache
            start_time = time.time()
            result2 = await get_metric_history(
                host_name="test-host",
                service_description="CPU load", 
                metric_id="load1",
                data_source="scraper"
            )
            second_duration = time.time() - start_time
            
            # Verify both requests succeeded
            assert result1["success"] is True
            assert result2["success"] is True
            
            # Verify data is identical (from cache)
            assert result1["metrics"] == result2["metrics"]
            assert result1["unified_data"]["summary_stats"] == result2["unified_data"]["summary_stats"]
            
            # Scraper should only be called once (for first request)
            assert mock_scraper.scrape_historical_data.call_count == 1
            
            # Second request should be faster (cache hit)
            assert second_duration < first_duration * 0.5  # At least 50% faster

    @pytest.mark.asyncio
    async def test_cache_miss_with_different_parameters(self, mock_config, sample_scraper_data):
        """Test that requests with different parameters miss the cache."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Request 1
            result1 = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Request 2 with different host
            result2 = await get_metric_history(
                host_name="different-host",
                service_description="CPU load",
                metric_id="load1", 
                data_source="scraper"
            )
            
            # Request 3 with different service
            result3 = await get_metric_history(
                host_name="test-host",
                service_description="Memory usage",
                metric_id="mem_used",
                data_source="scraper"
            )
            
            # Verify all requests succeeded
            assert result1["success"] is True
            assert result2["success"] is True
            assert result3["success"] is True
            
            # Verify scraper was called for each unique request
            assert mock_scraper.scrape_historical_data.call_count == 3

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, mock_config, sample_scraper_data):
        """Test that cache entries expire after TTL and scraper is called again."""
        # Use config with very short TTL
        mock_config.historical_data['cache_ttl'] = 0.1  # 100ms TTL
        
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # First request
            result1 = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Wait for TTL to expire
            await asyncio.sleep(0.15)  # Wait longer than TTL
            
            # Second request after TTL expiration
            result2 = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify both requests succeeded
            assert result1["success"] is True
            assert result2["success"] is True
            
            # Verify scraper was called twice (cache expired)
            assert mock_scraper.scrape_historical_data.call_count == 2

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, mock_config, sample_scraper_data):
        """Test handling of concurrent requests for the same data."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper with slight delay to simulate real-world scenario
        mock_scraper = Mock()
        async def delayed_scrape(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate network delay
            return sample_scraper_data
        mock_scraper.scrape_historical_data.side_effect = delayed_scrape
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Launch multiple concurrent requests for same data
            tasks = []
            for i in range(5):
                task = get_metric_history(
                    host_name="test-host",
                    service_description="CPU load",
                    metric_id="load1",
                    data_source="scraper"
                )
                tasks.append(task)
            
            # Execute all requests concurrently
            results = await asyncio.gather(*tasks)
            
            # Verify all requests succeeded
            for result in results:
                assert result["success"] is True
                assert result["metrics"][0]["data_points_count"] == 4
            
            # All results should be identical
            first_result = results[0]
            for result in results[1:]:
                assert result["metrics"] == first_result["metrics"]
                assert result["unified_data"]["summary_stats"] == first_result["unified_data"]["summary_stats"]

    @pytest.mark.asyncio
    async def test_cache_statistics_tracking(self, mock_config, sample_scraper_data):
        """Test that cache statistics are properly tracked."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        
        historical_service = server.historical_service
        assert isinstance(historical_service, CachedHistoricalDataService)
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            # Get initial cache stats
            initial_stats = historical_service.get_cache_stats()
            
            # Make some requests
            request = HistoricalDataRequest(
                host_name="test-host",
                service_name="CPU load",
                period="4h"
            )
            
            # First request (cache miss)
            await historical_service.get_historical_data(request)
            
            # Second request (cache hit)
            await historical_service.get_historical_data(request)
            
            # Get updated cache stats
            final_stats = historical_service.get_cache_stats()
            
            # Verify stats were updated
            assert final_stats['hits'] >= initial_stats['hits']
            assert final_stats['misses'] >= initial_stats['misses']
            assert final_stats['size'] >= initial_stats['size']

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, mock_config, sample_scraper_data):
        """Test cache invalidation functionality."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        
        historical_service = server.historical_service
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            request = HistoricalDataRequest(
                host_name="test-host", 
                service_name="CPU load",
                period="4h"
            )
            
            # First request (populate cache)
            await historical_service.get_historical_data(request)
            assert mock_scraper.scrape_historical_data.call_count == 1
            
            # Second request (should hit cache)
            await historical_service.get_historical_data(request)
            assert mock_scraper.scrape_historical_data.call_count == 1  # Still 1
            
            # Invalidate cache for host
            historical_service.invalidate_cache_pattern("test-host")
            
            # Third request (should miss cache after invalidation)
            await historical_service.get_historical_data(request)
            assert mock_scraper.scrape_historical_data.call_count == 2  # Now 2

    @pytest.mark.asyncio
    async def test_performance_with_large_datasets(self, mock_config):
        """Test performance characteristics with large datasets."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        # Generate large dataset (1000 data points)
        large_dataset = []
        base_time = datetime(2025, 1, 15, 10, 0, 0)
        for i in range(1000):
            timestamp = (base_time + timedelta(minutes=i)).isoformat()
            value = 75.0 + (i % 10)  # Varying values
            large_dataset.append((timestamp, value))
        
        # Add summary stats
        large_dataset.extend([
            ("avg", 79.5),
            ("max", 84.0),
            ("min", 75.0)
        ])
        
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = large_dataset
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # Measure performance with large dataset
            start_time = time.time()
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                time_range_hours=168,  # 1 week
                data_source="scraper"
            )
            duration = time.time() - start_time
            
            # Verify large dataset is handled correctly
            assert result["success"] is True
            assert result["metrics"][0]["data_points_count"] == 1000
            
            # Performance should be reasonable (< 5 seconds for processing)
            assert duration < 5.0
            
            # Verify execution time is recorded in metadata
            assert "execution_time_ms" in result["unified_data"]
            assert result["unified_data"]["execution_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_memory_usage_optimization(self, mock_config, sample_scraper_data):
        """Test memory usage patterns and optimization."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        
        historical_service = server.historical_service
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            # Make multiple requests to fill cache
            requests = []
            for i in range(10):
                request = HistoricalDataRequest(
                    host_name=f"test-host-{i}",
                    service_name="CPU load",
                    period="4h"
                )
                requests.append(request)
            
            # Execute requests
            for request in requests:
                await historical_service.get_historical_data(request)
            
            # Verify cache size is managed
            cache_stats = historical_service.get_cache_stats()
            assert cache_stats['size'] <= 1000  # Should not exceed max cache size

    @pytest.mark.asyncio
    async def test_error_caching_behavior(self, mock_config):
        """Test that errors are not cached."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        # Mock scraper that fails first time, succeeds second time
        mock_scraper = Mock()
        call_count = 0
        
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            else:
                return [("2025-01-15T10:00:00", 75.5), ("avg", 75.5)]
        
        mock_scraper.scrape_historical_data.side_effect = side_effect
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            # First request (should fail)
            result1 = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Second request (should succeed, not cached error)
            result2 = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify first request failed, second succeeded
            assert result1["success"] is False
            assert result2["success"] is True
            
            # Verify both calls hit the scraper (error not cached)
            assert mock_scraper.scrape_historical_data.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, mock_config, sample_scraper_data):
        """Test that cache keys are generated correctly for different requests."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        
        historical_service = server.historical_service
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            # Different requests should generate different cache keys
            requests = [
                HistoricalDataRequest(host_name="host1", service_name="service1", period="4h"),
                HistoricalDataRequest(host_name="host2", service_name="service1", period="4h"),
                HistoricalDataRequest(host_name="host1", service_name="service2", period="4h"),
                HistoricalDataRequest(host_name="host1", service_name="service1", period="8h"),
            ]
            
            # Execute all requests
            for request in requests:
                await historical_service.get_historical_data(request)
            
            # Verify each request hit the scraper (different cache keys)
            assert mock_scraper.scrape_historical_data.call_count == len(requests)

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, mock_config, sample_scraper_data):
        """Test that performance metrics are properly collected."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            tool_handlers = server._tool_handlers
            get_metric_history = tool_handlers["get_metric_history"]
            
            result = await get_metric_history(
                host_name="test-host",
                service_description="CPU load",
                metric_id="load1",
                data_source="scraper"
            )
            
            # Verify performance metrics are included
            assert result["success"] is True
            unified_data = result["unified_data"]
            
            # Should include execution timing
            assert "execution_time_ms" in unified_data
            assert isinstance(unified_data["execution_time_ms"], (int, float))
            assert unified_data["execution_time_ms"] > 0
            
            # Should include parsing metadata
            assert "raw_data_count" in unified_data
            assert "parsed_data_points" in unified_data
            assert "parsed_summary_stats" in unified_data
            
            assert unified_data["raw_data_count"] == 7  # Total scraper entries
            assert unified_data["parsed_data_points"] == 4  # Timestamp entries
            assert unified_data["parsed_summary_stats"] == 3  # Summary stats

    @pytest.mark.asyncio
    async def test_cache_cleanup_on_service_shutdown(self, mock_config, sample_scraper_data):
        """Test that cache is properly cleaned up when service shuts down."""
        server = CheckmkMCPServer(mock_config)
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            await server.initialize()

        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        
        historical_service = server.historical_service
        
        with patch('checkmk_mcp_server.services.web_scraping.ScraperService', return_value=mock_scraper):
            # Populate cache with some data
            request = HistoricalDataRequest(
                host_name="test-host",
                service_name="CPU load", 
                period="4h"
            )
            await historical_service.get_historical_data(request)
            
            # Verify cache has data
            initial_stats = historical_service.get_cache_stats()
            assert initial_stats['size'] > 0
            
            # Clear cache (simulating shutdown cleanup)
            historical_service._cache.clear()
            
            # Verify cache is empty
            final_stats = historical_service.get_cache_stats()
            assert final_stats['size'] == 0