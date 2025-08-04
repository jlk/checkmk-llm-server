"""Tests for batch operations functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from datetime import datetime

from checkmk_agent.services.batch import (
    BatchProcessor,
    BatchItem,
    BatchProgress,
    BatchResult,
    BatchItemStatus,
    BatchOperationsMixin,
)


@pytest.fixture
def batch_processor():
    """Create a batch processor."""
    return BatchProcessor(max_concurrent=3, max_retries=2, retry_delay=0.01)


class MockBatchService(BatchOperationsMixin):
    """Mock service for testing batch operations."""

    def __init__(self):
        super().__init__()
        self.operation_count = 0

    async def mock_operation(self, item):
        """Mock operation for testing."""
        self.operation_count += 1
        await asyncio.sleep(0.01)

        if item == "fail":
            raise Exception("Simulated failure")

        return f"processed_{item}"


@pytest.fixture
def mock_batch_service():
    """Create a mock batch service."""
    return MockBatchService()


class TestBatchItem:
    """Test BatchItem functionality."""

    def test_batch_item_creation(self):
        """Test creating a batch item."""
        item = BatchItem(id="test_1", data="test_data")

        assert item.id == "test_1"
        assert item.data == "test_data"
        assert item.status == BatchItemStatus.PENDING
        assert item.result is None
        assert item.error is None
        assert item.retry_count == 0

    def test_batch_item_lifecycle(self):
        """Test batch item status transitions."""
        item = BatchItem(id="test_1", data="test_data")

        # Mark as processing
        item.mark_processing()
        assert item.status == BatchItemStatus.PROCESSING
        assert item.started_at is not None

        # Mark as successful
        item.mark_success("result_data")
        assert item.status == BatchItemStatus.SUCCESS
        assert item.result == "result_data"
        assert item.completed_at is not None
        assert item.processing_time is not None

    def test_batch_item_failure(self):
        """Test batch item failure handling."""
        item = BatchItem(id="test_1", data="test_data")

        item.mark_processing()
        item.mark_failed("Error message")

        assert item.status == BatchItemStatus.FAILED
        assert item.error == "Error message"
        assert item.completed_at is not None

    def test_batch_item_skipped(self):
        """Test batch item skipping."""
        item = BatchItem(id="test_1", data="test_data")

        item.mark_skipped("Validation failed")

        assert item.status == BatchItemStatus.SKIPPED
        assert item.error == "Validation failed"
        assert item.completed_at is not None


class TestBatchProgress:
    """Test BatchProgress functionality."""

    def test_batch_progress_creation(self):
        """Test creating batch progress."""
        progress = BatchProgress(total_items=10)

        assert progress.total_items == 10
        assert progress.pending == 0
        assert progress.completed == 0
        assert progress.progress_percent == 0

    def test_batch_progress_calculations(self):
        """Test batch progress calculations."""
        progress = BatchProgress(
            total_items=10, success=6, failed=2, skipped=1, processing=1
        )

        assert progress.completed == 9
        assert progress.progress_percent == 90.0
        assert progress.items_per_second >= 0

    def test_batch_progress_estimated_remaining(self):
        """Test estimated remaining time calculation."""
        progress = BatchProgress(total_items=10, success=5)
        progress.start_time = datetime.now()

        # Mock some duration
        import time

        time.sleep(0.01)

        estimated = progress.estimated_remaining
        assert estimated is None or estimated >= 0  # Should be non-negative or None


class TestBatchProcessor:
    """Test BatchProcessor functionality."""

    @pytest.mark.asyncio
    async def test_process_batch_success(self, batch_processor):
        """Test successful batch processing."""
        items = ["item1", "item2", "item3"]

        async def simple_operation(item):
            await asyncio.sleep(0.01)
            return f"processed_{item}"

        result = await batch_processor.process_batch(
            items=items, operation=simple_operation, batch_id="test_batch"
        )

        assert result.batch_id == "test_batch"
        assert result.progress.total_items == 3
        assert result.progress.success == 3
        assert result.progress.failed == 0
        assert len(result.get_successful_items()) == 3
        assert len(result.get_results()) == 3

    @pytest.mark.asyncio
    async def test_process_batch_with_failures(self, batch_processor):
        """Test batch processing with some failures."""
        items = ["item1", "fail", "item3"]

        async def failing_operation(item):
            await asyncio.sleep(0.01)
            if item == "fail":
                raise Exception("Simulated failure")
            return f"processed_{item}"

        result = await batch_processor.process_batch(
            items=items, operation=failing_operation, batch_id="test_batch"
        )

        assert result.progress.total_items == 3
        assert result.progress.success == 2
        assert result.progress.failed == 1
        assert len(result.get_failed_items()) == 1
        assert result.get_failed_items()[0].error == "Simulated failure"

    @pytest.mark.asyncio
    async def test_process_batch_with_retries(self, batch_processor):
        """Test batch processing with retries."""
        items = ["item1"]
        call_count = 0

        async def retry_operation(item):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)

            if call_count < 2:  # Fail first attempt
                raise Exception("Temporary failure")

            return f"processed_{item}"

        result = await batch_processor.process_batch(
            items=items, operation=retry_operation, batch_id="test_batch"
        )

        assert result.progress.success == 1
        assert call_count == 2  # Should have retried once
        assert result.items[0].retry_count == 1

    @pytest.mark.asyncio
    async def test_process_batch_with_validation(self, batch_processor):
        """Test batch processing with item validation."""
        items = ["valid", "invalid", "also_valid"]

        async def validate_item(item):
            if item == "invalid":
                return False, "Item is invalid"
            return True, None

        async def simple_operation(item):
            return f"processed_{item}"

        result = await batch_processor.process_batch(
            items=items,
            operation=simple_operation,
            batch_id="test_batch",
            validate_item=validate_item,
        )

        assert result.progress.success == 2
        assert result.progress.skipped == 1
        assert result.progress.failed == 0

        skipped_items = [
            item for item in result.items if item.status == BatchItemStatus.SKIPPED
        ]
        assert len(skipped_items) == 1
        assert skipped_items[0].data == "invalid"
        assert skipped_items[0].error == "Item is invalid"

    @pytest.mark.asyncio
    async def test_process_batch_progress_callback(self, batch_processor):
        """Test batch processing with progress callback."""
        items = ["item1", "item2", "item3"]
        progress_updates = []

        async def progress_callback(progress):
            progress_updates.append(
                {
                    "completed": progress.completed,
                    "total": progress.total_items,
                    "percent": progress.progress_percent,
                }
            )

        async def simple_operation(item):
            await asyncio.sleep(0.01)
            return f"processed_{item}"

        await batch_processor.process_batch(
            items=items, operation=simple_operation, progress_callback=progress_callback
        )

        # Should have received progress updates
        assert len(progress_updates) > 0
        final_progress = progress_updates[-1]
        assert final_progress["completed"] == 3
        assert final_progress["percent"] == 100.0

    @pytest.mark.asyncio
    async def test_batch_processor_concurrency_limit(self):
        """Test batch processor respects concurrency limits."""
        processor = BatchProcessor(max_concurrent=2)
        items = ["item1", "item2", "item3", "item4"]
        concurrent_count = 0
        max_concurrent = 0

        async def tracking_operation(item):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)

            await asyncio.sleep(0.05)  # Longer delay to test concurrency

            concurrent_count -= 1
            return f"processed_{item}"

        await processor.process_batch(items=items, operation=tracking_operation)

        # Should not have exceeded concurrency limit
        assert max_concurrent <= 2


class TestBatchOperationsMixin:
    """Test BatchOperationsMixin functionality."""

    @pytest.mark.asyncio
    async def test_batch_create(self, mock_batch_service):
        """Test batch create operation."""
        items = [
            {"name": "host1", "folder": "/"},
            {"name": "host2", "folder": "/servers"},
            {"name": "host3", "folder": "/"},
        ]

        async def mock_create(item_data):
            await asyncio.sleep(0.01)
            return {"id": item_data["name"], "created": True}

        result = await mock_batch_service.batch_create(
            items=items, resource_type="host", create_function=mock_create
        )

        assert result.success is True
        batch_result = result.data
        assert batch_result.progress.total_items == 3
        assert batch_result.progress.success == 3
        assert batch_result.progress.failed == 0

    @pytest.mark.asyncio
    async def test_batch_create_with_failures(self, mock_batch_service):
        """Test batch create with some failures."""
        items = [
            {"name": "host1", "folder": "/"},
            {"name": "fail_host", "folder": "/"},
            {"name": "host3", "folder": "/"},
        ]

        async def mock_create(item_data):
            await asyncio.sleep(0.01)
            if item_data["name"] == "fail_host":
                raise Exception("Host creation failed")
            return {"id": item_data["name"], "created": True}

        result = await mock_batch_service.batch_create(
            items=items, resource_type="host", create_function=mock_create
        )

        assert result.success is True  # Overall operation succeeds
        batch_result = result.data
        assert batch_result.progress.success == 2
        assert batch_result.progress.failed == 1
        assert len(result.warnings) == 1  # Should have warning about failure

    @pytest.mark.asyncio
    async def test_batch_update(self, mock_batch_service):
        """Test batch update operation."""
        updates = [
            ("host1", {"alias": "Updated Host 1"}),
            ("host2", {"alias": "Updated Host 2"}),
            ("host3", {"alias": "Updated Host 3"}),
        ]

        async def mock_update(host_id, **update_data):
            await asyncio.sleep(0.01)
            return {"id": host_id, "updated": True, "changes": update_data}

        result = await mock_batch_service.batch_update(
            updates=updates, resource_type="host", update_function=mock_update
        )

        assert result.success is True
        batch_result = result.data
        assert batch_result.progress.total_items == 3
        assert batch_result.progress.success == 3

    @pytest.mark.asyncio
    async def test_batch_create_with_validation(self, mock_batch_service):
        """Test batch create with validation."""
        items = [
            {"name": "valid_host", "folder": "/"},
            {"name": "", "folder": "/"},  # Invalid - empty name
            {"name": "another_valid", "folder": "/"},
        ]

        async def validate_host(item_data):
            if not item_data.get("name"):
                return False, "Host name is required"
            return True, None

        async def mock_create(item_data):
            return {"id": item_data["name"], "created": True}

        result = await mock_batch_service.batch_create(
            items=items,
            resource_type="host",
            create_function=mock_create,
            validate_function=validate_host,
        )

        assert result.success is True
        batch_result = result.data
        assert batch_result.progress.success == 2
        assert batch_result.progress.skipped == 1
        assert batch_result.progress.failed == 0


@pytest.mark.asyncio
async def test_batch_performance():
    """Test batch processing performance characteristics."""
    processor = BatchProcessor(max_concurrent=5)
    items = [f"item_{i}" for i in range(50)]

    start_time = asyncio.get_event_loop().time()

    async def fast_operation(item):
        await asyncio.sleep(0.001)  # Very fast operation
        return f"processed_{item}"

    result = await processor.process_batch(
        items=items, operation=fast_operation, batch_id="performance_test"
    )

    duration = asyncio.get_event_loop().time() - start_time

    assert result.progress.success == 50
    assert duration < 1.0  # Should complete quickly with concurrency
    assert result.progress.items_per_second > 25  # Should be reasonably fast


@pytest.mark.asyncio
async def test_batch_error_resilience():
    """Test batch processing resilience to various errors."""
    processor = BatchProcessor(max_concurrent=3, max_retries=1)
    items = ["normal", "timeout", "exception", "success"]

    async def unpredictable_operation(item):
        await asyncio.sleep(0.01)

        if item == "timeout":
            await asyncio.sleep(10)  # Simulate timeout
        elif item == "exception":
            raise ValueError("Simulated error")

        return f"processed_{item}"

    # This should handle various types of failures gracefully
    result = await processor.process_batch(
        items=items, operation=unpredictable_operation, batch_id="resilience_test"
    )

    # Should have at least some successes
    assert result.progress.success >= 1
    assert result.progress.total_items == 4

    # Check that failed items have error messages
    failed_items = result.get_failed_items()
    for item in failed_items:
        assert item.error is not None
