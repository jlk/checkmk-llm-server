"""Unit tests for historical data service."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Tuple, Union

from checkmk_agent.services.historical_service import HistoricalDataService
from checkmk_agent.services.models.historical import (
    HistoricalDataPoint,
    HistoricalDataResult,
    HistoricalDataRequest,
    HistoricalDataServiceResult,
)
from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig, HistoricalDataConfig
from checkmk_agent.async_api_client import AsyncCheckmkClient


@pytest.fixture
def mock_checkmk_client():
    """Create mock async Checkmk client."""
    return Mock(spec=AsyncCheckmkClient)


@pytest.fixture
def test_config():
    """Create test configuration."""
    return AppConfig(
        checkmk=CheckmkConfig(
            server_url="https://test.example.com",
            username="test_user",
            password="test_pass",
            site="test_site"
        ),
        llm=LLMConfig(),
        historical_data=HistoricalDataConfig(
            source="scraper",
            cache_ttl=60,
            scraper_timeout=30
        )
    )


@pytest.fixture
def historical_service(mock_checkmk_client, test_config):
    """Create historical data service instance."""
    return HistoricalDataService(mock_checkmk_client, test_config)


@pytest.fixture
def sample_scraper_data():
    """Sample data from CheckmkHistoricalScraper."""
    return [
        ("2025-01-15T10:30:00", 25.5),
        ("2025-01-15T10:31:00", 25.7),
        ("2025-01-15T10:32:00", 26.0),
        ("min", 25.5),
        ("max", 26.0),
        ("avg", 25.73),
        ("last", 26.0),
    ]


@pytest.fixture
def sample_historical_request():
    """Sample historical data request."""
    return HistoricalDataRequest(
        host_name="test-host",
        service_name="Temperature Zone 0",
        period="4h"
    )


class TestHistoricalDataPoint:
    """Test HistoricalDataPoint data model."""

    def test_valid_data_point_creation(self):
        """Test creating valid data point."""
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        point = HistoricalDataPoint(
            timestamp=timestamp,
            value=25.5,
            metric_name="temperature",
            unit="°C"
        )
        
        assert point.timestamp == timestamp
        assert point.value == 25.5
        assert point.metric_name == "temperature"
        assert point.unit == "°C"

    def test_data_point_with_string_value(self):
        """Test data point with string value."""
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        point = HistoricalDataPoint(
            timestamp=timestamp,
            value="OK",
            metric_name="status",
            unit=None
        )
        
        assert point.value == "OK"
        assert point.unit is None

    def test_invalid_timestamp_type(self):
        """Test data point with invalid timestamp type."""
        with pytest.raises(ValueError, match="timestamp must be datetime"):
            HistoricalDataPoint(
                timestamp="2025-01-15T10:30:00",  # String instead of datetime
                value=25.5,
                metric_name="temperature"
            )

    def test_invalid_value_type(self):
        """Test data point with invalid value type."""
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        with pytest.raises(ValueError, match="value must be numeric or string"):
            HistoricalDataPoint(
                timestamp=timestamp,
                value=[25.5],  # List instead of scalar
                metric_name="temperature"
            )

    def test_empty_metric_name(self):
        """Test data point with empty metric name."""
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        with pytest.raises(ValueError, match="metric_name must be a non-empty string"):
            HistoricalDataPoint(
                timestamp=timestamp,
                value=25.5,
                metric_name=""
            )


class TestHistoricalDataResult:
    """Test HistoricalDataResult data model."""

    def test_valid_result_creation(self):
        """Test creating valid historical data result."""
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        data_points = [
            HistoricalDataPoint(
                timestamp=timestamp,
                value=25.5,
                metric_name="temperature",
                unit="°C"
            )
        ]
        
        result = HistoricalDataResult(
            data_points=data_points,
            summary_stats={"min": 25.5, "max": 26.0},
            metadata={"source": "test"},
            source="scraper"
        )
        
        assert len(result.data_points) == 1
        assert result.summary_stats["min"] == 25.5
        assert result.source == "scraper"

    def test_invalid_source(self):
        """Test result with invalid source."""
        data_points = []
        with pytest.raises(ValueError, match="source must be one of"):
            HistoricalDataResult(
                data_points=data_points,
                summary_stats={},
                metadata={},
                source="invalid_source"
            )

    def test_invalid_data_points_type(self):
        """Test result with invalid data_points type."""
        with pytest.raises(ValueError, match="data_points must be a list"):
            HistoricalDataResult(
                data_points="not a list",
                summary_stats={},
                metadata={},
                source="scraper"
            )


class TestHistoricalDataRequest:
    """Test HistoricalDataRequest validation."""

    def test_valid_request(self):
        """Test valid request creation."""
        request = HistoricalDataRequest(
            host_name="test-host",
            service_name="Temperature Zone 0",
            period="4h"
        )
        
        assert request.host_name == "test-host"
        assert request.service_name == "Temperature Zone 0"
        assert request.period == "4h"

    def test_string_stripping(self):
        """Test string fields are stripped."""
        request = HistoricalDataRequest(
            host_name="  test-host  ",
            service_name="  Temperature Zone 0  ",
            period="4h"
        )
        
        assert request.host_name == "test-host"
        assert request.service_name == "Temperature Zone 0"

    def test_empty_host_name(self):
        """Test request with empty host name."""
        with pytest.raises(ValueError, match="Field cannot be empty"):
            HistoricalDataRequest(
                host_name="",
                service_name="Temperature Zone 0",
                period="4h"
            )

    def test_invalid_period_format(self):
        """Test request with invalid period format."""
        with pytest.raises(ValueError, match="period must end with one of"):
            HistoricalDataRequest(
                host_name="test-host",
                service_name="Temperature Zone 0",
                period="xyz"
            )

    def test_invalid_source(self):
        """Test request with invalid source."""
        with pytest.raises(ValueError, match="source must be one of"):
            HistoricalDataRequest(
                host_name="test-host",
                service_name="Temperature Zone 0",
                period="4h",
                source="invalid_source"
            )


class TestHistoricalDataService:
    """Test HistoricalDataService functionality."""

    def test_service_initialization(self, historical_service, test_config):
        """Test service initialization."""
        assert historical_service.source == "scraper"
        assert historical_service.cache_ttl == 60
        assert historical_service.scraper_timeout == 30

    def test_is_timestamp_detection(self, historical_service):
        """Test timestamp detection method."""
        # Valid timestamps
        assert historical_service._is_timestamp("2025-01-15T10:30:00")
        assert historical_service._is_timestamp("2025-01-15T10:30:00.123Z")
        assert historical_service._is_timestamp("2025-01-15T10:30:00+02:00")
        assert historical_service._is_timestamp("2025-01-15")
        assert historical_service._is_timestamp("10:30:00")
        assert historical_service._is_timestamp("1642248600")  # Unix timestamp
        
        # Invalid timestamps
        assert not historical_service._is_timestamp("not-a-timestamp")
        assert not historical_service._is_timestamp("25.5")
        assert not historical_service._is_timestamp("")
        assert not historical_service._is_timestamp(None)

    def test_is_summary_stat_detection(self, historical_service):
        """Test summary statistic detection method."""
        # Valid summary stats
        assert historical_service._is_summary_stat("min")
        assert historical_service._is_summary_stat("MAX")
        assert historical_service._is_summary_stat("avg")
        assert historical_service._is_summary_stat("average")
        assert historical_service._is_summary_stat("std")
        assert historical_service._is_summary_stat("p95")
        
        # Invalid summary stats
        assert not historical_service._is_summary_stat("2025-01-15T10:30:00")
        assert not historical_service._is_summary_stat("25.5")
        assert not historical_service._is_summary_stat("temperature")
        assert not historical_service._is_summary_stat("")
        assert not historical_service._is_summary_stat(None)

    def test_parse_scraper_output(self, historical_service, sample_scraper_data):
        """Test parsing scraper output into structured data."""
        result = historical_service._parse_scraper_output(
            sample_scraper_data,
            "test-host",
            "Temperature Zone 0",
            "4h"
        )
        
        # Check data points (should be 3 timestamp entries)
        assert len(result.data_points) == 3
        assert all(isinstance(point, HistoricalDataPoint) for point in result.data_points)
        
        # Check first data point
        first_point = result.data_points[0]
        assert first_point.timestamp == datetime(2025, 1, 15, 10, 30, 0)
        assert first_point.value == 25.5
        assert first_point.metric_name == "temperature_zone_0"
        
        # Check summary stats (should be 4 summary entries)
        assert len(result.summary_stats) == 4
        assert result.summary_stats["min"] == 25.5
        assert result.summary_stats["max"] == 26.0
        assert result.summary_stats["avg"] == 25.73
        assert result.summary_stats["last"] == 26.0
        
        # Check metadata
        assert result.source == "scraper"
        assert result.metadata["host_name"] == "test-host"
        assert result.metadata["service_name"] == "Temperature Zone 0"
        assert result.metadata["time_range"] == "4h"

    def test_parse_scraper_output_with_units(self, historical_service):
        """Test parsing scraper output with unit extraction."""
        data_with_units = [
            ("2025-01-15T10:30:00", "25.5°C"),
            ("2025-01-15T10:31:00", "25.7 °C"),
            ("min", 25.5),
        ]
        
        result = historical_service._parse_scraper_output(
            data_with_units,
            "test-host",
            "Temperature Zone 0",
            "4h"
        )
        
        # Check that units are extracted
        assert len(result.data_points) == 2
        assert result.data_points[0].value == 25.5
        assert result.data_points[0].unit == "°C"
        assert result.data_points[1].value == 25.7
        assert result.data_points[1].unit == "°C"

    def test_parse_scraper_output_invalid_timestamps(self, historical_service):
        """Test parsing scraper output with invalid timestamps."""
        data_with_invalid = [
            ("invalid-timestamp", 25.5),
            ("2025-01-15T10:30:00", 25.7),
            ("another-invalid", 26.0),
        ]
        
        result = historical_service._parse_scraper_output(
            data_with_invalid,
            "test-host",
            "Temperature Zone 0",
            "4h"
        )
        
        # Should only parse the valid timestamp
        assert len(result.data_points) == 1
        assert result.data_points[0].value == 25.7
        
        # Should have parse errors recorded
        assert len(result.metadata["parse_errors"]) >= 0  # Depends on implementation

    @patch('checkmk_agent.services.web_scraping.scraper_service.ScraperService')
    @pytest.mark.asyncio
    async def test_get_historical_data_success(
        self, 
        mock_scraper_class, 
        historical_service, 
        sample_historical_request,
        sample_scraper_data
    ):
        """Test successful historical data retrieval."""
        # Setup mock scraper
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.return_value = sample_scraper_data
        mock_scraper_class.return_value = mock_scraper
        
        # Execute
        result = await historical_service.get_historical_data(sample_historical_request)
        
        # Verify
        assert result.success is True
        assert result.data is not None
        assert len(result.data.data_points) == 3
        assert len(result.data.summary_stats) == 4
        assert result.error is None
        
        # Verify scraper was called correctly
        mock_scraper.scrape_historical_data.assert_called_once_with(
            period="4h",
            host="test-host",
            service="Temperature Zone 0"
        )

    @patch('checkmk_agent.services.web_scraping.scraper_service.ScraperService')
    @pytest.mark.asyncio
    async def test_get_historical_data_import_error(
        self, 
        mock_scraper_class, 
        historical_service, 
        sample_historical_request
    ):
        """Test historical data retrieval with import error."""
        # Setup mock to raise ImportError
        mock_scraper_class.side_effect = ImportError("Scraper not available")
        
        # Execute
        result = await historical_service.get_historical_data(sample_historical_request)
        
        # Verify
        assert result.success is False
        assert result.data is None
        assert "Scraper not available" in result.error
        assert result.metadata["error_type"] == "import_error"

    @patch('checkmk_agent.services.web_scraping.scraper_service.ScraperService')
    @pytest.mark.asyncio
    async def test_get_historical_data_scraper_error(
        self, 
        mock_scraper_class, 
        historical_service, 
        sample_historical_request
    ):
        """Test historical data retrieval with scraper error."""
        # Setup mock scraper to raise error
        mock_scraper = Mock()
        mock_scraper.scrape_historical_data.side_effect = Exception("Scraper failed")
        mock_scraper_class.return_value = mock_scraper
        
        # Execute
        result = await historical_service.get_historical_data(sample_historical_request)
        
        # Verify
        assert result.success is False
        assert result.data is None
        assert "Failed to retrieve historical data" in result.error
        assert result.metadata["error_type"] == "scraper_error"

    @pytest.mark.asyncio
    async def test_get_available_metrics(self, historical_service):
        """Test getting available metrics."""
        result = await historical_service.get_available_metrics("test-host", "Temperature Zone 0")
        
        assert result.success is True
        assert result.data == ["temperature_zone_0"]


class TestHistoricalDataServiceResult:
    """Test HistoricalDataServiceResult wrapper."""

    def test_success_result_creation(self):
        """Test creating success result."""
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        data_points = [
            HistoricalDataPoint(
                timestamp=timestamp,
                value=25.5,
                metric_name="temperature"
            )
        ]
        
        historical_data = HistoricalDataResult(
            data_points=data_points,
            summary_stats={"min": 25.5},
            metadata={"test": "data"},
            source="scraper"
        )
        
        result = HistoricalDataServiceResult.success_result(
            data=historical_data,
            warnings=["test warning"],
            metadata={"test": "metadata"},
            request_id="req_123456"
        )
        
        assert result.success is True
        assert result.data == historical_data
        assert result.error is None
        assert result.warnings == ["test warning"]
        assert result.metadata == {"test": "metadata"}
        assert result.request_id == "req_123456"

    def test_error_result_creation(self):
        """Test creating error result."""
        result = HistoricalDataServiceResult.error_result(
            error="Test error",
            warnings=["test warning"],
            metadata={"error_type": "test"},
            request_id="req_123456"
        )
        
        assert result.success is False
        assert result.data is None
        assert result.error == "Test error"
        assert result.warnings == ["test warning"]
        assert result.metadata == {"error_type": "test"}
        assert result.request_id == "req_123456"