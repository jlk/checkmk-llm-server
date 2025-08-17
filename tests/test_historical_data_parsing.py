"""Comprehensive tests for historical data parsing from scraper output."""

import pytest
from datetime import datetime
from typing import List, Tuple, Union

from checkmk_agent.services.historical_service import HistoricalDataService
from checkmk_agent.services.models.historical import HistoricalDataPoint, HistoricalDataResult
from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig, HistoricalDataConfig
from checkmk_agent.async_api_client import AsyncCheckmkClient
from unittest.mock import Mock


@pytest.fixture
def historical_service():
    """Create historical data service for testing."""
    config = AppConfig(
        checkmk=CheckmkConfig(
            server_url="https://test.example.com",
            username="test_user",
            password="test_pass",
            site="test_site"
        ),
        llm=LLMConfig(),
        historical_data=HistoricalDataConfig()
    )
    mock_client = Mock(spec=AsyncCheckmkClient)
    return HistoricalDataService(mock_client, config)


class TestTimestampDetection:
    """Test timestamp detection in various formats."""

    def test_iso_timestamp_formats(self, historical_service):
        """Test detection of ISO 8601 timestamp formats."""
        valid_iso_timestamps = [
            "2025-01-15T10:30:00",
            "2025-01-15T10:30:00.123",
            "2025-01-15T10:30:00Z",
            "2025-01-15T10:30:00+02:00",
            "2025-01-15T10:30:00-05:00",
            "2025-12-31T23:59:59.999Z"
        ]
        
        for timestamp in valid_iso_timestamps:
            assert historical_service._is_timestamp(timestamp), f"Failed to detect: {timestamp}"

    def test_date_only_formats(self, historical_service):
        """Test detection of date-only formats."""
        valid_dates = [
            "2025-01-15",
            "2025-12-31",
            "2024-02-29"  # Leap year
        ]
        
        for date in valid_dates:
            assert historical_service._is_timestamp(date), f"Failed to detect: {date}"

    def test_time_only_formats(self, historical_service):
        """Test detection of time-only formats."""
        valid_times = [
            "10:30:00",
            "00:00:00",
            "23:59:59"
        ]
        
        for time in valid_times:
            assert historical_service._is_timestamp(time), f"Failed to detect: {time}"

    def test_unix_timestamp_formats(self, historical_service):
        """Test detection of Unix timestamps."""
        valid_unix_timestamps = [
            "1642248600",    # 10 digits
            "164224860000",  # 12 digits (milliseconds)
            "1000000000",    # 10 digits (edge case)
        ]
        
        for timestamp in valid_unix_timestamps:
            assert historical_service._is_timestamp(timestamp), f"Failed to detect: {timestamp}"

    def test_invalid_timestamp_formats(self, historical_service):
        """Test rejection of invalid timestamp formats."""
        invalid_timestamps = [
            "not-a-timestamp",
            "25.5",
            "temperature",
            "2025-13-01",      # Invalid month
            "2025-01-32",      # Invalid day
            "25:61:00",        # Invalid time
            "2025/01/15",      # Wrong separator
            "15-01-2025",      # Wrong order
            "",
            "123",             # Too short for Unix timestamp
            "abc123",          # Mixed letters and numbers
        ]
        
        for timestamp in invalid_timestamps:
            assert not historical_service._is_timestamp(timestamp), f"Incorrectly detected: {timestamp}"

    def test_non_string_inputs(self, historical_service):
        """Test timestamp detection with non-string inputs."""
        non_string_inputs = [
            None,
            123,
            25.5,
            [],
            {},
            datetime.now()
        ]
        
        for input_val in non_string_inputs:
            assert not historical_service._is_timestamp(input_val), f"Incorrectly detected: {input_val}"


class TestSummaryStatDetection:
    """Test summary statistic detection."""

    def test_basic_summary_stats(self, historical_service):
        """Test detection of basic summary statistics."""
        basic_stats = [
            "min", "MIN", "Min",
            "max", "MAX", "Max",
            "avg", "AVG", "Avg",
            "average", "AVERAGE", "Average",
            "mean", "MEAN", "Mean",
            "median", "MEDIAN", "Median",
            "sum", "SUM", "Sum",
            "count", "COUNT", "Count",
            "last", "LAST", "Last",
            "first", "FIRST", "First"
        ]
        
        for stat in basic_stats:
            assert historical_service._is_summary_stat(stat), f"Failed to detect: {stat}"

    def test_variance_and_deviation_stats(self, historical_service):
        """Test detection of variance and standard deviation stats."""
        variance_stats = [
            "std", "STD", "Std",
            "stddev", "STDDEV", "StdDev",
            "stdev", "STDEV", "StDev",
            "variance", "VARIANCE", "Variance",
            "var", "VAR", "Var"
        ]
        
        for stat in variance_stats:
            assert historical_service._is_summary_stat(stat), f"Failed to detect: {stat}"

    def test_percentile_stats(self, historical_service):
        """Test detection of percentile statistics."""
        percentile_stats = [
            "p50", "P50",
            "p90", "P90", 
            "p95", "P95",
            "p99", "P99"
        ]
        
        for stat in percentile_stats:
            assert historical_service._is_summary_stat(stat), f"Failed to detect: {stat}"

    def test_quartile_stats(self, historical_service):
        """Test detection of quartile statistics."""
        quartile_stats = [
            "q1", "Q1",
            "q2", "Q2", 
            "q3", "Q3"
        ]
        
        for stat in quartile_stats:
            assert historical_service._is_summary_stat(stat), f"Failed to detect: {stat}"

    def test_range_stats(self, historical_service):
        """Test detection of range statistics."""
        range_stats = [
            "range", "RANGE", "Range",
            "iqr", "IQR", "Iqr"
        ]
        
        for stat in range_stats:
            assert historical_service._is_summary_stat(stat), f"Failed to detect: {stat}"

    def test_invalid_summary_stats(self, historical_service):
        """Test rejection of invalid summary statistics."""
        invalid_stats = [
            "2025-01-15T10:30:00",  # Timestamp
            "25.5",                 # Numeric string
            "temperature",          # Metric name
            "status",               # Status value
            "error",                # Error value
            "",                     # Empty string
            "minimum",              # Similar but not exact
            "maximum",              # Similar but not exact
            "p100",                 # Invalid percentile
            "q4",                   # Invalid quartile
            "abc123",               # Mixed content
        ]
        
        for stat in invalid_stats:
            assert not historical_service._is_summary_stat(stat), f"Incorrectly detected: {stat}"

    def test_non_string_summary_inputs(self, historical_service):
        """Test summary stat detection with non-string inputs."""
        non_string_inputs = [
            None,
            123,
            25.5,
            [],
            {},
            datetime.now()
        ]
        
        for input_val in non_string_inputs:
            assert not historical_service._is_summary_stat(input_val), f"Incorrectly detected: {input_val}"


class TestScraperOutputParsing:
    """Test parsing of various scraper output formats."""

    def test_mixed_timestamp_and_summary_data(self, historical_service):
        """Test parsing mixed timestamp and summary data."""
        mixed_data = [
            ("2025-01-15T10:30:00", 25.5),
            ("2025-01-15T10:31:00", 25.7),
            ("2025-01-15T10:32:00", 26.0),
            ("min", 25.5),
            ("max", 26.0),
            ("avg", 25.73),
            ("count", 3)
        ]
        
        result = historical_service._parse_scraper_output(
            mixed_data, "test-host", "Temperature Zone 0", "4h"
        )
        
        # Should have 3 data points and 4 summary stats
        assert len(result.data_points) == 3
        assert len(result.summary_stats) == 4
        
        # Verify data points
        assert result.data_points[0].timestamp == datetime(2025, 1, 15, 10, 30, 0)
        assert result.data_points[0].value == 25.5
        assert result.data_points[1].value == 25.7
        assert result.data_points[2].value == 26.0
        
        # Verify summary stats
        assert result.summary_stats["min"] == 25.5
        assert result.summary_stats["max"] == 26.0
        assert result.summary_stats["avg"] == 25.73
        assert result.summary_stats["count"] == 3.0

    def test_unix_timestamp_parsing(self, historical_service):
        """Test parsing Unix timestamps."""
        unix_data = [
            ("1642248600", 25.5),   # 2022-01-15 10:30:00 UTC
            ("1642248660", 25.7),   # 2022-01-15 10:31:00 UTC
            ("min", 25.5),
            ("max", 25.7)
        ]
        
        result = historical_service._parse_scraper_output(
            unix_data, "test-host", "Temperature Zone 0", "1h"
        )
        
        # Should parse Unix timestamps correctly
        assert len(result.data_points) == 2
        # Note: fromtimestamp() uses local timezone, so exact time may vary
        # Just check that we got reasonable timestamps
        assert result.data_points[0].timestamp.year == 2022
        assert result.data_points[0].timestamp.month == 1
        assert result.data_points[0].timestamp.day == 15
        assert result.data_points[1].timestamp > result.data_points[0].timestamp

    def test_data_with_units(self, historical_service):
        """Test parsing data with units."""
        data_with_units = [
            ("2025-01-15T10:30:00", "25.5°C"),
            ("2025-01-15T10:31:00", "25.7 °C"),
            ("2025-01-15T10:32:00", "26.0 degrees"),
            ("2025-01-15T10:33:00", "85%"),
            ("min", 25.5),
            ("max", 26.0)
        ]
        
        result = historical_service._parse_scraper_output(
            data_with_units, "test-host", "Temperature Zone 0", "4h"
        )
        
        # Should extract values and units
        assert len(result.data_points) == 4
        
        # Check unit extraction
        assert result.data_points[0].value == 25.5
        assert result.data_points[0].unit == "°C"
        assert result.data_points[1].value == 25.7
        assert result.data_points[1].unit == "°C"
        assert result.data_points[2].value == 26.0
        assert result.data_points[2].unit == "degrees"
        assert result.data_points[3].value == 85.0
        assert result.data_points[3].unit == "%"

    def test_string_values_parsing(self, historical_service):
        """Test parsing string values that aren't numeric."""
        string_data = [
            ("2025-01-15T10:30:00", "OK"),
            ("2025-01-15T10:31:00", "WARNING"),
            ("2025-01-15T10:32:00", "CRITICAL"),
            ("2025-01-15T10:33:00", "UNKNOWN"),
            ("mode", "OK")
        ]
        
        result = historical_service._parse_scraper_output(
            string_data, "test-host", "Service Status", "1h"
        )
        
        # Should preserve string values
        assert len(result.data_points) == 4
        assert result.data_points[0].value == "OK"
        assert result.data_points[1].value == "WARNING"
        assert result.data_points[2].value == "CRITICAL"
        assert result.data_points[3].value == "UNKNOWN"

    def test_invalid_data_handling(self, historical_service):
        """Test handling of invalid data in scraper output."""
        invalid_data = [
            ("invalid-timestamp", 25.5),     # Invalid timestamp
            ("2025-01-15T10:30:00", 25.7),   # Valid entry
            ("another-invalid", "value"),     # Invalid timestamp
            ("not-timestamp-or-stat", 26.0), # Neither timestamp nor stat
            ("min", 25.5),                   # Valid summary stat
            ("invalid-stat", "badvalue")     # Invalid stat name
        ]
        
        result = historical_service._parse_scraper_output(
            invalid_data, "test-host", "Test Service", "1h"
        )
        
        # Should only parse valid entries
        assert len(result.data_points) == 1  # Only one valid timestamp
        assert result.data_points[0].value == 25.7
        
        assert len(result.summary_stats) == 1  # Only one valid summary stat
        assert result.summary_stats["min"] == 25.5

    def test_empty_data_parsing(self, historical_service):
        """Test parsing empty scraper output."""
        empty_data = []
        
        result = historical_service._parse_scraper_output(
            empty_data, "test-host", "Test Service", "1h"
        )
        
        # Should handle empty data gracefully
        assert len(result.data_points) == 0
        assert len(result.summary_stats) == 0
        assert result.source == "scraper"
        assert result.metadata["raw_data_count"] == 0

    def test_only_summary_stats(self, historical_service):
        """Test parsing data with only summary statistics."""
        stats_only = [
            ("min", 10.5),
            ("max", 50.3),
            ("avg", 30.2),
            ("std", 12.8),
            ("count", 100)
        ]
        
        result = historical_service._parse_scraper_output(
            stats_only, "test-host", "Test Service", "24h"
        )
        
        # Should have no data points but all summary stats
        assert len(result.data_points) == 0
        assert len(result.summary_stats) == 5
        assert result.summary_stats["min"] == 10.5
        assert result.summary_stats["max"] == 50.3
        assert result.summary_stats["avg"] == 30.2
        assert result.summary_stats["std"] == 12.8
        assert result.summary_stats["count"] == 100.0

    def test_only_timestamp_data(self, historical_service):
        """Test parsing data with only timestamp entries."""
        timestamps_only = [
            ("2025-01-15T10:30:00", 25.5),
            ("2025-01-15T10:31:00", 25.7),
            ("2025-01-15T10:32:00", 26.0)
        ]
        
        result = historical_service._parse_scraper_output(
            timestamps_only, "test-host", "Test Service", "30m"
        )
        
        # Should have data points but no summary stats
        assert len(result.data_points) == 3
        assert len(result.summary_stats) == 0

    def test_metric_name_generation(self, historical_service):
        """Test metric name generation from service names."""
        test_cases = [
            ("Temperature Zone 0", "temperature_zone_0"),
            ("CPU Load", "cpu_load"),
            ("Disk Space /var", "disk_space_/var"),
            ("Network Interface eth0", "network_interface_eth0"),
            ("Memory Usage", "memory_usage")
        ]
        
        for service_name, expected_metric in test_cases:
            data = [("2025-01-15T10:30:00", 25.5)]
            result = historical_service._parse_scraper_output(
                data, "test-host", service_name, "1h"
            )
            
            assert len(result.data_points) == 1
            assert result.data_points[0].metric_name == expected_metric

    def test_metadata_population(self, historical_service):
        """Test that metadata is properly populated."""
        test_data = [
            ("2025-01-15T10:30:00", 25.5),
            ("min", 25.5)
        ]
        
        result = historical_service._parse_scraper_output(
            test_data, "test-host", "Test Service", "2h"
        )
        
        # Check metadata fields
        metadata = result.metadata
        assert metadata["source"] == "scraper"
        assert metadata["time_range"] == "2h"
        assert metadata["host_name"] == "test-host"
        assert metadata["service_name"] == "Test Service"
        assert metadata["raw_data_count"] == 2
        assert metadata["parsed_data_points"] == 1
        assert metadata["parsed_summary_stats"] == 1
        assert "parse_errors" in metadata
        assert "request_id" in metadata

    def test_complex_mixed_data_scenario(self, historical_service):
        """Test complex scenario with mixed data types and edge cases."""
        complex_data = [
            # Valid timestamps with various value types
            ("2025-01-15T10:30:00", 25.5),
            ("2025-01-15T10:31:00", "26.2°C"),
            ("2025-01-15T10:32:00", "CRITICAL"),
            
            # Unix timestamps
            ("1642248780", 27.1),
            
            # Date-only timestamps
            ("2025-01-15", 25.0),
            
            # Summary statistics
            ("min", 25.0),
            ("max", 27.1),
            ("avg", 25.96),
            ("std", 0.89),
            ("count", 5),
            
            # Invalid entries (should be skipped)
            ("invalid-timestamp", 30.0),
            ("not-a-stat", "somevalue"),
            
            # Edge cases
            ("", 0.0),  # Empty timestamp
            ("null", None),  # Null value
        ]
        
        result = historical_service._parse_scraper_output(
            complex_data, "production-server", "Temperature Sensor", "6h"
        )
        
        # Should parse valid entries and skip invalid ones
        # Expected valid timestamps: ISO timestamps (3) + Unix timestamp (1) + date-only (1) = 5
        assert len(result.data_points) == 5  # Valid timestamps only
        assert len(result.summary_stats) == 5  # Valid summary stats only
        
        # Verify data diversity
        values = [point.value for point in result.data_points]
        assert 25.5 in values  # Numeric value
        assert 26.2 in values  # Extracted from string with unit
        assert "CRITICAL" in values  # String value
        assert 27.1 in values  # Unix timestamp value
        
        # Verify summary stats
        expected_stats = ["min", "max", "avg", "std", "count"]
        for stat in expected_stats:
            assert stat in result.summary_stats