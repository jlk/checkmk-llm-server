"""Unit tests for request context utilities."""

import pytest
import asyncio
from unittest.mock import patch

from checkmk_agent.utils.request_context import (
    generate_request_id,
    generate_sub_request_id,
    get_request_id,
    set_request_id,
    with_request_id,
    ensure_request_id,
    format_request_id,
    extract_parent_id,
    validate_request_id,
    is_sub_request_id,
    get_request_context,
    copy_request_context,
    REQUEST_ID_CONTEXT,
)


class TestRequestIDGeneration:
    """Test request ID generation functions."""

    def test_generate_request_id_format(self):
        """Test that generated request IDs follow the correct format."""
        request_id = generate_request_id()

        assert isinstance(request_id, str)
        assert request_id.startswith("req_")
        assert len(request_id) == 9  # 'req_' + 6 hex chars

        # Verify hex format
        hex_part = request_id[4:]
        int(hex_part, 16)  # Should not raise ValueError

    def test_generate_request_id_uniqueness(self):
        """Test that generated request IDs are unique."""
        ids = [generate_request_id() for _ in range(1000)]
        assert len(set(ids)) == 1000  # All should be unique

    def test_generate_sub_request_id(self):
        """Test sub-request ID generation."""
        parent_id = "req_a1b2c3"
        sub_id = generate_sub_request_id(parent_id, 1)

        assert sub_id == "req_a1b2c3.001"
        assert is_sub_request_id(sub_id)

        # Test different sequence numbers
        assert generate_sub_request_id(parent_id, 0) == "req_a1b2c3.000"
        assert generate_sub_request_id(parent_id, 999) == "req_a1b2c3.999"


class TestRequestIDContext:
    """Test request ID context management."""

    def setup_method(self):
        """Clear context before each test."""
        REQUEST_ID_CONTEXT.set(None)

    def test_get_set_request_id(self):
        """Test getting and setting request IDs."""
        assert get_request_id() is None

        test_id = "req_test01"
        set_request_id(test_id)
        assert get_request_id() == test_id

    def test_ensure_request_id_when_none(self):
        """Test ensure_request_id generates ID when none exists."""
        assert get_request_id() is None

        request_id = ensure_request_id()
        assert request_id.startswith("req_")
        assert get_request_id() == request_id

    def test_ensure_request_id_when_exists(self):
        """Test ensure_request_id returns existing ID."""
        existing_id = "req_existing"
        set_request_id(existing_id)

        request_id = ensure_request_id()
        assert request_id == existing_id

    def test_format_request_id(self):
        """Test request ID formatting."""
        assert format_request_id("req_a1b2c3") == "req_a1b2c3"
        assert format_request_id(None) == "req_unknown"
        assert format_request_id("") == "req_unknown"

    def test_extract_parent_id(self):
        """Test parent ID extraction."""
        assert extract_parent_id("req_a1b2c3") == "req_a1b2c3"
        assert extract_parent_id("req_a1b2c3.001") == "req_a1b2c3"
        assert extract_parent_id("req_a1b2c3.999") == "req_a1b2c3"


class TestRequestIDValidation:
    """Test request ID validation functions."""

    def test_validate_request_id_valid_cases(self):
        """Test validation of valid request IDs."""
        valid_ids = [
            "req_a1b2c3",
            "req_000000",
            "req_ffffff",
            "req_123ABC",
            "req_a1b2c3.001",
            "req_a1b2c3.999",
        ]

        for request_id in valid_ids:
            assert validate_request_id(request_id), f"Should be valid: {request_id}"

    def test_validate_request_id_invalid_cases(self):
        """Test validation of invalid request IDs."""
        invalid_ids = [
            "invalid",
            "req_",
            "req_12345",  # Too short
            "req_1234567",  # Too long
            "req_gggggg",  # Invalid hex
            "req_a1b2c3.",  # Invalid sub-request format
            "req_a1b2c3.1000",  # Sub-request too large
            "req_a1b2c3.abc",  # Non-numeric sub-request
            "req_a1b2c3.001.002",  # Too many parts
            None,
            123,
        ]

        for request_id in invalid_ids:
            assert not validate_request_id(
                request_id
            ), f"Should be invalid: {request_id}"

    def test_is_sub_request_id(self):
        """Test sub-request ID detection."""
        assert not is_sub_request_id("req_a1b2c3")
        assert is_sub_request_id("req_a1b2c3.001")
        assert not is_sub_request_id("invalid_id")


class TestRequestIDDecorators:
    """Test request ID decorators and context management."""

    def setup_method(self):
        """Clear context before each test."""
        REQUEST_ID_CONTEXT.set(None)

    def test_with_request_id_decorator_sync(self):
        """Test @with_request_id decorator on sync functions."""

        @with_request_id()
        def test_function():
            return get_request_id()

        result = test_function()
        assert result is not None
        assert result.startswith("req_")

    def test_with_request_id_decorator_specific_id(self):
        """Test @with_request_id decorator with specific ID."""
        test_id = "req_specific"

        @with_request_id(test_id)
        def test_function():
            return get_request_id()

        result = test_function()
        assert result == test_id

    @pytest.mark.asyncio
    async def test_with_request_id_decorator_async(self):
        """Test @with_request_id decorator on async functions."""

        @with_request_id()
        async def test_async_function():
            return get_request_id()

        result = await test_async_function()
        assert result is not None
        assert result.startswith("req_")

    def test_with_request_id_preserves_existing_context(self):
        """Test that decorator preserves existing request ID."""
        existing_id = "req_existing"
        set_request_id(existing_id)

        @with_request_id()
        def test_function():
            return get_request_id()

        result = test_function()
        assert result == existing_id


class TestRequestIDContext:
    """Test request context utilities."""

    def setup_method(self):
        """Clear context before each test."""
        REQUEST_ID_CONTEXT.set(None)

    def test_get_request_context(self):
        """Test getting request context information."""
        context = get_request_context()
        assert "request_id" in context
        assert "formatted_request_id" in context
        assert "has_request_id" in context
        assert context["has_request_id"] is False

        # Set request ID and test again
        test_id = "req_test01"
        set_request_id(test_id)

        context = get_request_context()
        assert context["request_id"] == test_id
        assert context["formatted_request_id"] == test_id
        assert context["has_request_id"] is True

    def test_copy_request_context(self):
        """Test copying request context."""
        assert copy_request_context() is None

        test_id = "req_test01"
        set_request_id(test_id)

        copied = copy_request_context()
        assert copied == test_id


class TestConcurrentRequestIDs:
    """Test request ID handling in concurrent scenarios."""

    def setup_method(self):
        """Clear context before each test."""
        REQUEST_ID_CONTEXT.set(None)

    @pytest.mark.asyncio
    async def test_concurrent_request_ids(self):
        """Test that request IDs are properly isolated in concurrent tasks."""
        results = []

        async def task_with_request_id(task_id: int):
            request_id = f"req_task{task_id:02d}"
            set_request_id(request_id)

            # Simulate some async work
            await asyncio.sleep(0.01)

            current_id = get_request_id()
            results.append((task_id, current_id))

            return current_id

        # Run 10 concurrent tasks
        tasks = [task_with_request_id(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify each task maintained its own request ID
        for task_id, result_id in results:
            expected_id = f"req_task{task_id:02d}"
            assert result_id == expected_id, f"Task {task_id} had wrong ID: {result_id}"

    @pytest.mark.asyncio
    async def test_context_propagation_in_tasks(self):
        """Test request ID propagation within async task contexts."""
        parent_id = "req_parent"
        set_request_id(parent_id)

        async def child_task():
            # Should inherit parent's request ID
            return get_request_id()

        # Create task - should inherit context
        task = asyncio.create_task(child_task())
        result = await task

        assert result == parent_id


class TestRequestIDPerformance:
    """Test performance characteristics of request ID operations."""

    def test_generation_performance(self):
        """Test that request ID generation is performant."""
        import time

        start_time = time.time()
        ids = [generate_request_id() for _ in range(10000)]
        end_time = time.time()

        # Should generate 10,000 IDs in under 1 second
        duration = end_time - start_time
        assert duration < 1.0, f"Generation took too long: {duration}s"

        # All should be unique
        assert len(set(ids)) == 10000

    def test_context_operations_performance(self):
        """Test that context operations are performant."""
        import time

        start_time = time.time()
        for i in range(10000):
            set_request_id(f"req_test{i:04d}")
            current_id = get_request_id()
            assert current_id == f"req_test{i:04d}"
        end_time = time.time()

        # Should complete 10,000 operations in under 1 second
        duration = end_time - start_time
        assert duration < 1.0, f"Context operations took too long: {duration}s"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_request_id_thread_safety(self):
        """Test request ID context variables are thread-safe."""
        import threading
        import queue

        results = queue.Queue()

        def worker(thread_id: int):
            request_id = f"req_thread{thread_id}"
            set_request_id(request_id)

            # Small delay to allow other threads to interfere
            import time

            time.sleep(0.01)

            current_id = get_request_id()
            results.put((thread_id, current_id))

        # Start 10 threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify each thread maintained its own request ID
        thread_results = []
        while not results.empty():
            thread_results.append(results.get())

        assert len(thread_results) == 10

        for thread_id, result_id in thread_results:
            expected_id = f"req_thread{thread_id}"
            assert (
                result_id == expected_id
            ), f"Thread {thread_id} had wrong ID: {result_id}"
