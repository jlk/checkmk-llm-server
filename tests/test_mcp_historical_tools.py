"""
Tests for enhanced MCP tools with historical data integration.

This module tests the Phase 3 enhancements to get_metric_history and 
list_service_events tools, focusing on data source selection logic, 
parameter validation, and unified data model formatting.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from checkmk_agent.mcp_server import CheckmkMCPServer
from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig, HistoricalDataConfig
from checkmk_agent.services.models.historical import (
    HistoricalDataRequest,
    HistoricalDataResult,
    HistoricalDataPoint,
    HistoricalDataServiceResult
)


@pytest.fixture
def mock_config():
    """Create mock configuration for testing."""
    return AppConfig(
        checkmk=CheckmkConfig(
            server_url="https://test.checkmk.local",
            username="automation",
            password="test-password",
            site="test-site"
        ),
        llm=LLMConfig(
            provider="anthropic",
            model="claude-3-haiku-20240307"
        ),
        historical_data=HistoricalDataConfig(
            source="rest_api",
            cache_ttl=60,
            scraper_timeout=30
        )
    )


@pytest_asyncio.fixture
async def mcp_server(mock_config):
    """Create MCP server instance for testing."""
    server = CheckmkMCPServer(config=mock_config)
    await server.initialize()
    return server


@pytest.fixture
def sample_historical_data():
    """Create sample historical data for testing."""
    timestamp = datetime.now(timezone.utc)
    
    data_points = [
        HistoricalDataPoint(
            timestamp=timestamp, 
            value=50.0, 
            metric_name="CPU_utilization",
            unit="%"
        ),
        HistoricalDataPoint(
            timestamp=timestamp, 
            value=60.0, 
            metric_name="CPU_utilization",
            unit="%"
        ),
        HistoricalDataPoint(
            timestamp=timestamp, 
            value=55.0, 
            metric_name="CPU_utilization",
            unit="%"
        )
    ]
    
    return HistoricalDataResult(
        data_points=data_points,
        summary_stats={"min": 50.0, "max": 60.0, "avg": 55.0},
        metadata={
            "host": "test-host",
            "service": "CPU utilization",
            "period": "4h",
            "timestamp": timestamp.isoformat()
        },
        source="scraper"
    )


@pytest.fixture
def sample_metrics_graph():
    """Create sample metrics graph for REST API testing."""
    mock_graph = Mock()
    mock_graph.time_range = "4h"
    mock_graph.step = 300
    
    mock_metric = Mock()
    mock_metric.title = "CPU utilization"
    mock_metric.color = "#ff0000"
    mock_metric.line_type = "area"
    mock_metric.data_points = [(1234567890, 50.0), (1234567950, 60.0)]
    
    mock_graph.metrics = [mock_metric]
    return mock_graph


class TestGetMetricHistoryTool:
    """Test enhanced get_metric_history tool with data source selection."""

    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_data_source(self, mcp_server):
        """Test parameter validation rejects invalid data_source values."""
        # Get the tool handler
        handler = mcp_server._tool_handlers["get_metric_history"]
        
        # Test with invalid data_source
        result = await handler(
            host_name="test-host",
            service_description="CPU utilization",
            metric_id="cpu_util",
            data_source="invalid_source"
        )
        
        assert result["success"] is False
        assert "Invalid data_source" in result["error"]
        assert "Must be 'rest_api' or 'scraper'" in result["error"]

    @pytest.mark.asyncio
    async def test_parameter_validation_valid_data_sources(self, mcp_server):
        """Test parameter validation accepts valid data_source values."""
        # Mock the services to avoid actual API calls
        mock_metrics_service = AsyncMock()
        mock_historical_service = AsyncMock()
        
        with patch.object(mcp_server, '_get_service') as mock_get_service:
            # Test with rest_api data_source
            def side_effect(service_name):
                if service_name == "metrics":
                    return mock_metrics_service
                elif service_name == "historical":
                    return mock_historical_service
                raise ValueError(f"Unknown service: {service_name}")
            
            mock_get_service.side_effect = side_effect
            
            # Mock successful result for REST API
            mock_result = Mock()
            mock_result.success = True
            mock_result.data = Mock()
            mock_result.data.time_range = "4h"
            mock_result.data.step = 300
            mock_result.data.metrics = []
            mock_metrics_service.get_metric_history.return_value = mock_result
            
            handler = mcp_server._tool_handlers["get_metric_history"]
            
            # Test rest_api data_source
            result = await handler(
                host_name="test-host",
                service_description="CPU utilization",
                metric_id="cpu_util",
                data_source="rest_api"
            )
            
            assert result["success"] is True
            assert result["data_source"] == "rest_api"

    @pytest.mark.asyncio
    async def test_data_source_selection_uses_config_default(self, mcp_server, sample_historical_data):
        """Test that missing data_source parameter uses config default."""
        # Update config to use scraper as default
        mcp_server.config.historical_data.source = "scraper"
        
        # Mock the historical service
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=True,
            data=sample_historical_data,
            error=None
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["get_metric_history"]
            
            result = await handler(
                host_name="test-host",
                service_description="CPU utilization",
                metric_id="cpu_util"
                # No data_source parameter - should use config default
            )
            
            assert result["success"] is True
            assert result["data_source"] == "scraper"
            assert "unified_data" in result

    @pytest.mark.asyncio
    async def test_scraper_data_source_integration(self, mcp_server, sample_historical_data):
        """Test scraper data source integration with historical service."""
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=True,
            data=sample_historical_data,
            error=None
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["get_metric_history"]
            
            result = await handler(
                host_name="test-host",
                service_description="CPU utilization",
                metric_id="CPU_utilization",  # Match the metric name in test data
                time_range_hours=6,
                data_source="scraper"
            )
            
            # Verify historical service was called correctly
            mock_historical_service.get_historical_data.assert_called_once()
            call_args = mock_historical_service.get_historical_data.call_args[0][0]
            assert isinstance(call_args, HistoricalDataRequest)
            assert call_args.host_name == "test-host"
            assert call_args.service_name == "CPU utilization"
            assert call_args.period == "6h"
            assert call_args.metric_name == "CPU_utilization"
            
            # Verify response format
            assert result["success"] is True
            assert result["data_source"] == "scraper"
            assert "unified_data" in result
            assert "metrics" in result
            assert len(result["metrics"]) == 1
            
            # Verify unified data model
            unified = result["unified_data"]
            assert unified["host"] == "test-host"
            assert unified["service"] == "CPU utilization"
            assert len(unified["metrics"]) == 1
            assert unified["metrics"][0]["name"] == "CPU_utilization"

    @pytest.mark.asyncio
    async def test_rest_api_data_source_integration(self, mcp_server, sample_metrics_graph):
        """Test REST API data source integration with metrics service."""
        mock_metrics_service = AsyncMock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = sample_metrics_graph
        mock_metrics_service.get_metric_history.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_metrics_service):
            handler = mcp_server._tool_handlers["get_metric_history"]
            
            result = await handler(
                host_name="test-host",
                service_description="CPU utilization",
                metric_id="cpu_util",
                time_range_hours=4,
                reduce="average",
                site="test-site",
                data_source="rest_api"
            )
            
            # Verify metrics service was called correctly
            mock_metrics_service.get_metric_history.assert_called_once_with(
                "test-host",
                "CPU utilization",
                "cpu_util",
                4,
                "average",
                "test-site"
            )
            
            # Verify response format
            assert result["success"] is True
            assert result["data_source"] == "rest_api"
            assert result["time_range"] == "4h"
            assert result["step"] == 300
            assert len(result["metrics"]) == 1

    @pytest.mark.asyncio
    async def test_scraper_error_handling(self, mcp_server):
        """Test error handling when scraper data source fails."""
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=False,
            data=None,
            error="Scraper timeout"
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["get_metric_history"]
            
            result = await handler(
                host_name="test-host",
                service_description="CPU utilization",
                metric_id="cpu_util",
                data_source="scraper"
            )
            
            assert result["success"] is False
            assert result["data_source"] == "scraper"
            assert "Scraper timeout" in result["error"]


class TestListServiceEventsTool:
    """Test enhanced list_service_events tool with data source selection."""

    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_data_source(self, mcp_server):
        """Test parameter validation rejects invalid data_source values."""
        handler = mcp_server._tool_handlers["list_service_events"]
        
        result = await handler(
            host_name="test-host",
            service_name="CPU utilization",
            data_source="invalid_source"
        )
        
        assert result["success"] is False
        assert "Invalid data_source" in result["error"]
        assert "Must be 'rest_api' or 'scraper'" in result["error"]

    @pytest.mark.asyncio
    async def test_scraper_data_source_events_generation(self, mcp_server, sample_historical_data):
        """Test scraper data source generates events from metric changes."""
        # Modify sample data to have value changes
        sample_historical_data.data_points = [
            HistoricalDataPoint(timestamp=datetime.now(timezone.utc), value=50.0, metric_name="CPU_utilization", unit="%"),
            HistoricalDataPoint(timestamp=datetime.now(timezone.utc), value=75.0, metric_name="CPU_utilization", unit="%"),  # Change
            HistoricalDataPoint(timestamp=datetime.now(timezone.utc), value=75.0, metric_name="CPU_utilization", unit="%"),  # No change
            HistoricalDataPoint(timestamp=datetime.now(timezone.utc), value=60.0, metric_name="CPU_utilization", unit="%"),  # Change
        ]
        
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=True,
            data=sample_historical_data,
            error=None
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["list_service_events"]
            
            result = await handler(
                host_name="test-host",
                service_name="CPU utilization",
                data_source="scraper"
            )
            
            assert result["success"] is True
            assert result["data_source"] == "scraper"
            assert "unified_data" in result
            
            # Should have 2 events (2 value changes)
            assert len(result["events"]) == 2
            
            # Verify event structure
            event = result["events"][0]
            assert event["host_name"] == "test-host"
            assert event["service_description"] == "CPU utilization"
            assert "50.0 to 75.0" in event["text"]
            assert event["state"] == "INFO"

    @pytest.mark.asyncio
    async def test_scraper_state_filter_application(self, mcp_server, sample_historical_data):
        """Test state filter is applied to scraper-generated events."""
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=True,
            data=sample_historical_data,
            error=None
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["list_service_events"]
            
            # Test with state filter that doesn't match generated events
            result = await handler(
                host_name="test-host",
                service_name="CPU utilization",
                state_filter="WARNING",
                data_source="scraper"
            )
            
            assert result["success"] is True
            assert len(result["events"]) == 0  # No WARNING events generated

    @pytest.mark.asyncio
    async def test_scraper_limit_application(self, mcp_server, sample_historical_data):
        """Test limit parameter is applied to scraper-generated events."""
        # Create data with multiple changes to test limit
        sample_historical_data.data_points = [
            HistoricalDataPoint(timestamp=datetime.now(timezone.utc), value=i * 10.0, metric_name="CPU_utilization", unit="%")
            for i in range(10)  # Creates 9 change events
        ]
        
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=True,
            data=sample_historical_data,
            error=None
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["list_service_events"]
            
            result = await handler(
                host_name="test-host",
                service_name="CPU utilization",
                limit=3,
                data_source="scraper"
            )
            
            assert result["success"] is True
            assert len(result["events"]) == 3  # Limited to 3 events

    @pytest.mark.asyncio
    async def test_rest_api_data_source_passthrough(self, mcp_server):
        """Test REST API data source uses existing event service logic."""
        mock_event_service = AsyncMock()
        mock_event = Mock()
        mock_event.event_id = "event_123"
        mock_event.host_name = "test-host"
        mock_event.service_description = "CPU utilization"
        mock_event.text = "Service state changed"
        mock_event.state = "WARNING"
        mock_event.phase = "open"
        mock_event.first_time = "2024-01-01T00:00:00Z"
        mock_event.last_time = "2024-01-01T00:00:00Z"
        mock_event.count = 1
        mock_event.comment = "Automated detection"
        
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = [mock_event]
        mock_event_service.list_service_events.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_event_service):
            handler = mcp_server._tool_handlers["list_service_events"]
            
            result = await handler(
                host_name="test-host",
                service_name="CPU utilization",
                limit=10,
                state_filter="WARNING",
                data_source="rest_api"
            )
            
            # Verify event service was called correctly
            mock_event_service.list_service_events.assert_called_once_with(
                "test-host", "CPU utilization", 10, "WARNING"
            )
            
            assert result["success"] is True
            assert result["data_source"] == "rest_api"
            assert len(result["events"]) == 1
            assert result["events"][0]["event_id"] == "event_123"

    @pytest.mark.asyncio
    async def test_config_default_source_selection(self, mcp_server):
        """Test that missing data_source parameter uses config default."""
        # Set config to use scraper
        mcp_server.config.historical_data.source = "scraper"
        
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=True,
            data=HistoricalDataResult(
                data_points=[],
                summary_stats={},
                metadata={
                    "host": "test-host",
                    "service": "CPU utilization",
                    "period": "24h",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                source="scraper"
            ),
            error=None
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["list_service_events"]
            
            result = await handler(
                host_name="test-host",
                service_name="CPU utilization"
                # No data_source parameter
            )
            
            assert result["success"] is True
            assert result["data_source"] == "scraper"


class TestUnifiedDataModel:
    """Test unified data model inclusion in tool responses."""

    @pytest.mark.asyncio
    async def test_unified_data_structure_scraper(self, mcp_server, sample_historical_data):
        """Test unified data model structure for scraper data source."""
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=True,
            data=sample_historical_data,
            error=None
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["get_metric_history"]
            
            result = await handler(
                host_name="test-host",
                service_description="CPU utilization",
                metric_id="cpu_util",
                data_source="scraper"
            )
            
            assert "unified_data" in result
            unified = result["unified_data"]
            
            # Verify structure
            assert "host" in unified
            assert "service" in unified
            assert "period" in unified
            assert "timestamp" in unified
            assert "metrics" in unified
            
            # Verify content
            assert unified["host"] == "test-host"
            assert unified["service"] == "CPU utilization"
            assert len(unified["metrics"]) == 1
            
            metric = unified["metrics"][0]
            assert "name" in metric
            assert "unit" in metric
            assert "data_points" in metric
            assert len(metric["data_points"]) == 3

    @pytest.mark.asyncio
    async def test_unified_data_timestamp_formatting(self, mcp_server, sample_historical_data):
        """Test timestamp formatting in unified data model."""
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=True,
            data=sample_historical_data,
            error=None
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["get_metric_history"]
            
            result = await handler(
                host_name="test-host",
                service_description="CPU utilization",
                metric_id="cpu_util",
                data_source="scraper"
            )
            
            unified = result["unified_data"]
            
            # Main timestamp should be ISO format
            assert unified["timestamp"] is not None
            assert "T" in unified["timestamp"]  # ISO format indicator
            
            # Data point timestamps should be ISO format
            for metric in unified["metrics"]:
                for dp in metric["data_points"]:
                    assert "T" in dp["timestamp"]  # ISO format indicator


class TestErrorHandling:
    """Test error handling across enhanced tools."""

    @pytest.mark.asyncio
    async def test_historical_service_error_propagation(self, mcp_server):
        """Test that historical service errors are properly propagated."""
        mock_historical_service = AsyncMock()
        mock_result = HistoricalDataServiceResult(
            success=False,
            data=None,
            error="Connection timeout to scraper"
        )
        mock_historical_service.get_historical_data.return_value = mock_result
        
        with patch.object(mcp_server, '_get_service', return_value=mock_historical_service):
            handler = mcp_server._tool_handlers["get_metric_history"]
            
            result = await handler(
                host_name="test-host",
                service_description="CPU utilization",
                metric_id="cpu_util",
                data_source="scraper"
            )
            
            assert result["success"] is False
            assert result["data_source"] == "scraper"
            assert "Connection timeout to scraper" in result["error"]

    @pytest.mark.asyncio
    async def test_service_not_found_error(self, mcp_server):
        """Test error handling when service is not found."""
        with patch.object(mcp_server, '_get_service', side_effect=ValueError("Unknown service: invalid")):
            handler = mcp_server._tool_handlers["get_metric_history"]
            
            with pytest.raises(ValueError, match="Unknown service"):
                await handler(
                    host_name="test-host",
                    service_description="CPU utilization",
                    metric_id="cpu_util",
                    data_source="scraper"
                )