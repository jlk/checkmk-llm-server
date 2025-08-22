"""Unit tests for request tracking middleware."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
import logging
import io
import sys
from datetime import datetime

from checkmk_mcp_server.middleware.request_tracking import (
    track_request,
    RequestTrackingMiddleware,
    with_request_tracking,
    get_request_tracking_metadata,
    propagate_request_context,
    restore_request_context,
)
from checkmk_mcp_server.utils.request_context import (
    generate_request_id,
    set_request_id,
    get_request_id,
    REQUEST_ID_CONTEXT,
)


class TestTrackRequestDecorator:
    """Test the @track_request decorator."""

    def setup_method(self):
        """Clear context before each test."""
        REQUEST_ID_CONTEXT.set(None)

    def test_track_request_generates_id(self):
        """Test that @track_request generates a request ID."""

        @track_request()
        def test_function():
            return get_request_id()

        result = test_function()
        assert result is not None
        assert result.startswith("req_")

    def test_track_request_with_specific_id(self):
        """Test @track_request with a specific request ID."""
        test_id = "req_specific"

        @track_request(request_id=test_id)
        def test_function():
            return get_request_id()

        result = test_function()
        assert result == test_id

    def test_track_request_with_operation_name(self, caplog):
        """Test @track_request with operation name logging."""
        with caplog.at_level(logging.DEBUG):

            @track_request(operation_name="Test Operation")
            def test_function():
                return "success"

            result = test_function()
            assert result == "success"

            # Check that debug logs contain operation name
            log_messages = [record.message for record in caplog.records]
            assert any("Test Operation" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_track_request_async(self):
        """Test @track_request on async functions."""

        @track_request()
        async def test_async_function():
            return get_request_id()

        result = await test_async_function()
        assert result is not None
        assert result.startswith("req_")

    def test_track_request_with_timing(self, caplog):
        """Test @track_request with timing enabled."""
        with caplog.at_level(logging.DEBUG):

            @track_request(include_timing=True)
            def test_function():
                import time

                time.sleep(0.01)  # Small delay
                return "success"

            result = test_function()
            assert result == "success"

            # Check that timing information is logged
            log_messages = [record.message for record in caplog.records]
            assert any("ms" in msg and "Completed" in msg for msg in log_messages)

    def test_track_request_error_handling(self, caplog):
        """Test @track_request error handling and logging."""
        with caplog.at_level(logging.ERROR):

            @track_request(operation_name="Error Test")
            def test_function():
                raise ValueError("Test error")

            with pytest.raises(ValueError, match="Test error"):
                test_function()

            # Check that error is logged with request ID
            log_messages = [record.message for record in caplog.records]
            error_logs = [msg for msg in log_messages if "Failed Error Test" in msg]
            assert len(error_logs) > 0
            assert any("req_" in msg for msg in error_logs)


class TestRequestTrackingMiddleware:
    """Test the RequestTrackingMiddleware class."""

    def setup_method(self):
        """Setup middleware instance for testing."""
        self.middleware = RequestTrackingMiddleware(
            auto_generate=True, log_requests=True, include_timing=True
        )
        REQUEST_ID_CONTEXT.set(None)

    def test_process_request_auto_generate(self):
        """Test request processing with auto-generation."""
        request_context = {}

        request_id = self.middleware.process_request(request_context, "test_operation")

        assert request_id.startswith("req_")
        assert get_request_id() == request_id

    def test_process_request_existing_id(self):
        """Test request processing with existing ID in context."""
        existing_id = "req_existing"
        request_context = {"request_id": existing_id}

        request_id = self.middleware.process_request(request_context, "test_operation")

        assert request_id == existing_id
        assert get_request_id() == existing_id

    def test_process_request_no_auto_generate(self):
        """Test request processing without auto-generation."""
        middleware = RequestTrackingMiddleware(auto_generate=False)
        request_context = {}

        with pytest.raises(ValueError, match="No request ID available"):
            middleware.process_request(request_context, "test_operation")

    def test_complete_request_success(self, caplog):
        """Test successful request completion."""
        with caplog.at_level(logging.INFO):
            request_context = {"_start_time": datetime.now()}

            self.middleware.complete_request(
                "req_test01", request_context, success=True
            )

            log_messages = [record.message for record in caplog.records]
            success_logs = [
                msg for msg in log_messages if "completed successfully" in msg
            ]
            assert len(success_logs) > 0
            assert any("req_test01" in msg for msg in success_logs)

    def test_complete_request_error(self, caplog):
        """Test error request completion."""
        with caplog.at_level(logging.ERROR):
            request_context = {"_start_time": datetime.now()}
            test_error = Exception("Test error")

            self.middleware.complete_request(
                "req_test01", request_context, success=False, error=test_error
            )

            log_messages = [record.message for record in caplog.records]
            error_logs = [msg for msg in log_messages if "Request failed" in msg]
            assert len(error_logs) > 0
            assert any(
                "req_test01" in msg and "Test error" in msg for msg in error_logs
            )

    def test_get_request_headers(self):
        """Test request header generation."""
        set_request_id("req_test01")

        headers = self.middleware.get_request_headers()

        assert headers == {"X-Request-ID": "req_test01"}

    def test_get_request_headers_no_id(self):
        """Test request header generation with no ID."""
        assert get_request_id() is None

        headers = self.middleware.get_request_headers()

        assert headers == {}

    def test_extract_request_id_from_headers(self):
        """Test request ID extraction from headers."""
        headers = {"X-Request-ID": "req_from_header"}

        request_id = self.middleware.extract_request_id_from_headers(headers)

        assert request_id == "req_from_header"

    def test_extract_request_id_various_headers(self):
        """Test request ID extraction from various header formats."""
        header_variants = [
            {"X-Request-ID": "req_test01"},
            {"x-request-id": "req_test02"},
            {"Request-ID": "req_test03"},
            {"request-id": "req_test04"},
        ]

        for headers in header_variants:
            request_id = self.middleware.extract_request_id_from_headers(headers)
            assert request_id is not None
            assert request_id.startswith("req_test")

    def test_extract_request_id_no_header(self):
        """Test request ID extraction with no header."""
        headers = {"Content-Type": "application/json"}

        request_id = self.middleware.extract_request_id_from_headers(headers)

        assert request_id is None


class TestWithRequestTrackingDecorator:
    """Test the @with_request_tracking decorator."""

    def setup_method(self):
        """Clear context before each test."""
        REQUEST_ID_CONTEXT.set(None)

    def test_with_request_tracking_basic(self):
        """Test basic @with_request_tracking functionality."""

        @with_request_tracking("Test Operation")
        def test_function():
            return get_request_id()

        result = test_function()
        assert result is not None
        assert result.startswith("req_")

    @pytest.mark.asyncio
    async def test_with_request_tracking_async(self):
        """Test @with_request_tracking on async functions."""

        @with_request_tracking("Async Test Operation")
        async def test_async_function():
            return get_request_id()

        result = await test_async_function()
        assert result is not None
        assert result.startswith("req_")

    def test_with_request_tracking_error_handling(self, caplog):
        """Test @with_request_tracking error handling."""
        with caplog.at_level(logging.ERROR):

            @with_request_tracking("Error Test")
            def test_function():
                raise ValueError("Test error")

            with pytest.raises(ValueError, match="Test error"):
                test_function()

            # Check error logging
            log_messages = [record.message for record in caplog.records]
            error_logs = [msg for msg in log_messages if "Request failed" in msg]
            assert len(error_logs) > 0


class TestUtilityFunctions:
    """Test utility functions for request tracking."""

    def setup_method(self):
        """Clear context before each test."""
        REQUEST_ID_CONTEXT.set(None)

    def test_get_request_tracking_metadata(self):
        """Test getting request tracking metadata."""
        metadata = get_request_tracking_metadata()

        assert "request_id" in metadata
        assert "formatted_request_id" in metadata
        assert "has_request_id" in metadata
        assert "timestamp" in metadata
        assert metadata["has_request_id"] is False

        # Set request ID and test again
        test_id = "req_test01"
        set_request_id(test_id)

        metadata = get_request_tracking_metadata()
        assert metadata["request_id"] == test_id
        assert metadata["formatted_request_id"] == test_id
        assert metadata["has_request_id"] is True

    def test_propagate_request_context(self):
        """Test request context propagation through headers."""
        test_id = "req_test01"
        set_request_id(test_id)

        headers = propagate_request_context()

        assert headers == {"X-Request-ID": test_id}

    def test_propagate_request_context_existing_headers(self):
        """Test request context propagation with existing headers."""
        test_id = "req_test01"
        set_request_id(test_id)

        existing_headers = {"Content-Type": "application/json"}
        headers = propagate_request_context(existing_headers)

        expected = {"Content-Type": "application/json", "X-Request-ID": test_id}
        assert headers == expected

    def test_propagate_request_context_no_id(self):
        """Test request context propagation with no request ID."""
        assert get_request_id() is None

        headers = propagate_request_context()

        assert headers == {}

    def test_restore_request_context(self):
        """Test request context restoration from headers."""
        headers = {"X-Request-ID": "req_restored"}

        success = restore_request_context(headers)

        assert success is True
        assert get_request_id() == "req_restored"

    def test_restore_request_context_no_header(self):
        """Test request context restoration with no header."""
        headers = {"Content-Type": "application/json"}

        success = restore_request_context(headers)

        assert success is False
        assert get_request_id() is None


class TestMiddlewareIntegration:
    """Test middleware integration scenarios."""

    def setup_method(self):
        """Setup for integration tests."""
        self.middleware = RequestTrackingMiddleware()
        REQUEST_ID_CONTEXT.set(None)

    def test_full_request_lifecycle(self, caplog):
        """Test complete request lifecycle with middleware."""
        with caplog.at_level(logging.INFO):
            request_context = {}

            # Process request
            request_id = self.middleware.process_request(
                request_context, "Integration Test"
            )

            # Simulate some work
            assert get_request_id() == request_id

            # Complete request
            self.middleware.complete_request(request_id, request_context, success=True)

            # Verify logging
            log_messages = [record.message for record in caplog.records]
            assert any("Processing Integration Test" in msg for msg in log_messages)
            assert any("completed successfully" in msg for msg in log_messages)

    def test_request_id_propagation_chain(self):
        """Test request ID propagation through a chain of calls."""

        @with_request_tracking("Parent Operation")
        def parent_function():
            parent_id = get_request_id()

            @track_request()
            def child_function():
                return get_request_id()

            child_id = child_function()

            # Child should have same request ID as parent when not overridden
            return parent_id, child_id

        parent_id, child_id = parent_function()
        assert parent_id == child_id

    @pytest.mark.asyncio
    async def test_async_request_propagation(self):
        """Test request ID propagation in async contexts."""

        @with_request_tracking("Async Parent")
        async def async_parent():
            parent_id = get_request_id()

            async def async_child():
                await asyncio.sleep(0.001)  # Small async operation
                return get_request_id()

            child_id = await async_child()
            return parent_id, child_id

        parent_id, child_id = await async_parent()
        assert parent_id == child_id


class TestPerformanceCharacteristics:
    """Test performance characteristics of request tracking."""

    def test_decorator_overhead(self):
        """Test that decorators have minimal overhead."""
        import time

        def plain_function():
            return "result"

        @track_request()
        def decorated_function():
            return "result"

        # Time plain function
        start_time = time.time()
        for _ in range(1000):
            plain_function()
        plain_time = time.time() - start_time

        # Time decorated function
        start_time = time.time()
        for _ in range(1000):
            decorated_function()
        decorated_time = time.time() - start_time

        # Overhead should be minimal (less than 50% increase)
        overhead_ratio = decorated_time / plain_time
        assert overhead_ratio < 1.5, f"Too much overhead: {overhead_ratio:.2f}x"

    def test_middleware_performance(self):
        """Test middleware performance characteristics."""
        import time

        middleware = RequestTrackingMiddleware()

        start_time = time.time()
        for i in range(1000):
            request_context = {}
            request_id = middleware.process_request(request_context, f"operation_{i}")
            middleware.complete_request(request_id, request_context, success=True)

        duration = time.time() - start_time

        # Should complete 1000 operations in under 1 second
        assert (
            duration < 1.0
        ), f"Middleware too slow: {duration:.2f}s for 1000 operations"


class TestErrorScenarios:
    """Test error handling and edge cases."""

    def setup_method(self):
        """Clear context before each test."""
        REQUEST_ID_CONTEXT.set(None)

    def test_middleware_with_broken_logging(self):
        """Test middleware behavior when logging fails."""
        middleware = RequestTrackingMiddleware(log_requests=True)

        with patch("logging.Logger.info", side_effect=Exception("Logging failed")):
            # Should not raise exception even if logging fails
            request_context = {}
            request_id = middleware.process_request(request_context, "test")

            assert request_id is not None
            assert request_id.startswith("req_")

    def test_decorator_with_generator_function(self):
        """Test decorator behavior with generator functions."""

        @track_request()
        def generator_function():
            yield get_request_id()
            yield "second"
            yield "third"

        gen = generator_function()
        first_value = next(gen)

        assert first_value.startswith("req_")
        assert next(gen) == "second"
        assert next(gen) == "third"

    @pytest.mark.asyncio
    async def test_async_generator_with_decorator(self):
        """Test decorator behavior with async generator functions."""

        @track_request()
        async def async_generator():
            yield get_request_id()
            await asyncio.sleep(0.001)
            yield "async_second"

        gen = async_generator()
        first_value = await gen.__anext__()

        assert first_value.startswith("req_")

        second_value = await gen.__anext__()
        assert second_value == "async_second"
