"""Tests for streaming functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from datetime import datetime

from checkmk_mcp_server.services.streaming import (
    StreamingMixin,
    StreamBatch,
    StreamingHostService,
    StreamingServiceService,
)
from checkmk_mcp_server.services.models.hosts import HostInfo
from checkmk_mcp_server.services.models.services import ServiceInfo, ServiceState
from checkmk_mcp_server.config import AppConfig


class MockStreamingService(StreamingMixin):
    """Mock service for testing streaming functionality."""

    def __init__(self):
        super().__init__()
        self.checkmk = AsyncMock()


@pytest.fixture
def mock_streaming_service():
    """Create a mock streaming service."""
    return MockStreamingService()


@pytest.fixture
def sample_hosts():
    """Sample host data for testing."""
    return [
        {"id": "host1", "folder": "/", "attributes": {"alias": "Host 1"}},
        {"id": "host2", "folder": "/", "attributes": {"alias": "Host 2"}},
        {"id": "host3", "folder": "/servers", "attributes": {"alias": "Host 3"}},
    ]


@pytest.fixture
def mock_config():
    """Mock configuration."""
    return Mock(spec=AppConfig)


class TestStreamBatch:
    """Test StreamBatch functionality."""

    def test_stream_batch_creation(self):
        """Test creating a stream batch."""
        items = [HostInfo(name="host1", folder="/"), HostInfo(name="host2", folder="/")]
        batch = StreamBatch(items=items, batch_number=1, has_more=True)

        assert batch.batch_number == 1
        assert len(batch.items) == 2
        assert batch.has_more is True
        assert isinstance(batch.timestamp, datetime)

    def test_stream_batch_metadata(self):
        """Test stream batch with metadata."""
        items = []
        metadata = {"source": "test", "total_count": 100}
        batch = StreamBatch(
            items=items, batch_number=0, has_more=False, metadata=metadata
        )

        assert batch.metadata["source"] == "test"
        assert batch.metadata["total_count"] == 100


class TestStreamingMixin:
    """Test StreamingMixin functionality."""

    @pytest.mark.asyncio
    async def test_stream_paginated_data(self, mock_streaming_service):
        """Test streaming paginated data."""

        # Mock fetch function
        async def mock_fetch(limit, offset):
            if offset == 0:
                return type(
                    "Result", (), {"items": ["item1", "item2"], "total_count": 5}
                )()
            elif offset == 2:
                return type(
                    "Result", (), {"items": ["item3", "item4"], "total_count": 5}
                )()
            else:
                return type("Result", (), {"items": ["item5"], "total_count": 5})()

        # Test streaming
        batches = []
        async for batch in mock_streaming_service._stream_paginated_data(
            mock_fetch, batch_size=2
        ):
            batches.append(batch)
            if len(batches) >= 3:  # Prevent infinite loop
                break

        assert len(batches) == 3
        assert batches[0].batch_number == 0
        assert len(batches[0].items) == 2
        assert batches[0].has_more is True

        assert batches[1].batch_number == 1
        assert len(batches[1].items) == 2
        assert batches[1].has_more is True

        assert batches[2].batch_number == 2
        assert len(batches[2].items) == 1
        assert batches[2].has_more is False

    @pytest.mark.asyncio
    async def test_process_stream_with_callback(self, mock_streaming_service):
        """Test processing stream with callback."""

        # Create test stream
        async def test_stream():
            yield StreamBatch(items=["item1", "item2"], batch_number=0, has_more=True)
            yield StreamBatch(items=["item3"], batch_number=1, has_more=False)

        # Track processed items
        processed_items = []

        async def process_callback(item):
            processed_items.append(item)
            await asyncio.sleep(0.01)  # Simulate processing time

        # Process stream
        result = await mock_streaming_service._process_stream_with_callback(
            test_stream(), process_callback
        )

        assert result.success is True
        assert result.data["processed_count"] == 3
        assert result.data["error_count"] == 0
        assert len(processed_items) == 3
        assert processed_items == ["item1", "item2", "item3"]


class TestStreamingHostService:
    """Test StreamingHostService functionality."""

    @pytest.fixture
    def streaming_host_service(self, mock_config):
        """Create streaming host service."""
        mock_client = AsyncMock()
        return StreamingHostService(mock_client, mock_config)

    @pytest.mark.asyncio
    async def test_list_hosts_streamed(self, streaming_host_service, sample_hosts):
        """Test streaming hosts."""
        # Mock the checkmk client
        streaming_host_service.checkmk.list_hosts = AsyncMock()

        # First call returns 2 hosts
        streaming_host_service.checkmk.list_hosts.side_effect = [
            {"value": sample_hosts[:2], "total_count": 3},
            {"value": sample_hosts[2:], "total_count": 3},
        ]

        # Test streaming
        batches = []
        async for batch in streaming_host_service.list_hosts_streamed(batch_size=2):
            batches.append(batch)
            if len(batches) >= 2:  # Prevent infinite loop
                break

        assert len(batches) == 2
        assert len(batches[0].items) == 2
        assert len(batches[1].items) == 1

        # Check that HostInfo objects were created
        assert isinstance(batches[0].items[0], HostInfo)
        assert batches[0].items[0].name == "host1"
        assert batches[0].items[1].name == "host2"
        assert batches[1].items[0].name == "host3"


class TestStreamingServiceService:
    """Test StreamingServiceService functionality."""

    @pytest.fixture
    def streaming_service_service(self, mock_config):
        """Create streaming service service."""
        mock_client = AsyncMock()
        return StreamingServiceService(mock_client, mock_config)

    @pytest.mark.asyncio
    async def test_list_all_services_streamed(self, streaming_service_service):
        """Test streaming all services."""
        # Mock data
        hosts_data = [{"id": "host1"}, {"id": "host2"}]

        services_host1 = [
            {"description": "CPU", "state": 0, "plugin_output": "OK"},
            {"description": "Memory", "state": 1, "plugin_output": "Warning"},
        ]

        services_host2 = [
            {"description": "Disk", "state": 2, "plugin_output": "Critical"}
        ]

        # Mock the checkmk client
        streaming_service_service.checkmk.list_hosts = AsyncMock(
            return_value={"value": hosts_data}
        )
        streaming_service_service.checkmk.list_host_services = AsyncMock()
        streaming_service_service.checkmk.list_host_services.side_effect = [
            {"value": services_host1},
            {"value": services_host2},
        ]

        # Test streaming
        batches = []
        async for batch in streaming_service_service.list_all_services_streamed(
            batch_size=2
        ):
            batches.append(batch)
            if not batch.has_more:
                break

        # Should have all 3 services in batches
        total_services = sum(len(batch.items) for batch in batches)
        assert total_services == 3

        # Check ServiceInfo objects were created
        first_batch = batches[0]
        assert isinstance(first_batch.items[0], ServiceInfo)
        assert first_batch.items[0].host_name == "host1"
        assert first_batch.items[0].service_name == "CPU"
        assert first_batch.items[0].state == ServiceState.OK

    @pytest.mark.asyncio
    async def test_list_services_streamed_with_filter(self, streaming_service_service):
        """Test streaming services with state filter."""
        # Mock data with different states
        hosts_data = [{"id": "host1"}]
        services_data = [
            {"description": "CPU", "state": 0, "plugin_output": "OK"},
            {"description": "Memory", "state": 1, "plugin_output": "Warning"},
            {"description": "Disk", "state": 2, "plugin_output": "Critical"},
        ]

        # Mock the checkmk client
        streaming_service_service.checkmk.list_hosts = AsyncMock(
            return_value={"value": hosts_data}
        )
        streaming_service_service.checkmk.list_host_services = AsyncMock(
            return_value={"value": services_data}
        )

        # Test streaming with state filter (only non-OK states)
        batches = []
        async for batch in streaming_service_service.list_all_services_streamed(
            batch_size=10, state_filter=[ServiceState.WARNING, ServiceState.CRITICAL]
        ):
            batches.append(batch)
            if not batch.has_more:
                break

        # Should only have 2 services (Warning and Critical)
        total_services = sum(len(batch.items) for batch in batches)
        assert total_services == 2

        # Check filtered services
        all_services = []
        for batch in batches:
            all_services.extend(batch.items)

        states = [service.state for service in all_services]
        assert ServiceState.OK not in states
        assert ServiceState.WARNING in states
        assert ServiceState.CRITICAL in states


@pytest.mark.asyncio
async def test_streaming_error_handling():
    """Test streaming with errors."""
    service = MockStreamingService()

    # Mock fetch function that raises error
    async def failing_fetch(limit, offset):
        if offset == 0:
            return type("Result", (), {"items": ["item1"], "total_count": 2})()
        else:
            raise Exception("API Error")

    # Test streaming with error
    batches = []
    async for batch in service._stream_paginated_data(failing_fetch, batch_size=1):
        batches.append(batch)
        if len(batches) >= 2:  # Should get error batch
            break

    assert len(batches) == 2
    assert len(batches[0].items) == 1  # First batch succeeds
    assert len(batches[1].items) == 0  # Second batch fails
    assert "error" in batches[1].metadata


@pytest.mark.asyncio
async def test_streaming_performance():
    """Test streaming performance characteristics."""
    service = MockStreamingService()

    # Mock fetch function with consistent data
    async def mock_fetch(limit, offset):
        items = [f"item_{i}" for i in range(offset, min(offset + limit, 1000))]
        return type("Result", (), {"items": items, "total_count": 1000})()

    # Measure streaming performance
    import time

    start_time = time.time()

    batch_count = 0
    item_count = 0

    async for batch in service._stream_paginated_data(mock_fetch, batch_size=100):
        batch_count += 1
        item_count += len(batch.items)
        if batch_count >= 5:  # Process 5 batches
            break

    duration = time.time() - start_time

    assert batch_count == 5
    assert item_count == 500
    assert duration < 1.0  # Should be fast

    # Verify batch metadata
    assert all(hasattr(batch, "timestamp") for batch in [batch])
    assert all(hasattr(batch, "metadata") for batch in [batch])
