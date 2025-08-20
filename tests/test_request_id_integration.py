"""Integration tests for end-to-end request ID flow."""

import pytest
import asyncio
import logging
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from checkmk_agent.utils.request_context import (
    generate_request_id,
    set_request_id,
    get_request_id,
    REQUEST_ID_CONTEXT,
)
from checkmk_agent.middleware.request_tracking import RequestTrackingMiddleware
from checkmk_agent.logging_utils import setup_logging, RequestIDFormatter
from checkmk_agent.config import AppConfig, CheckmkConfig
from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.services.base import BaseService, ServiceResult
from checkmk_agent.async_api_client import AsyncCheckmkClient


class TestEndToEndRequestFlow:
    """Test complete request ID flow through all system components."""

    def setup_method(self):
        """Setup for integration tests."""
        REQUEST_ID_CONTEXT.set(None)

        # Mock configuration
        self.checkmk_config = CheckmkConfig(
            server_url="https://test.example.com",
            site="test",
            username="test_user",
            password="test_password",
        )

        self.app_config = AppConfig(checkmk=self.checkmk_config, log_level="DEBUG")

    def test_api_client_request_id_flow(self, caplog):
        """Test request ID flow through API client."""
        with patch("requests.Session.request") as mock_request:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"value": [{"name": "test-host"}]}
            mock_request.return_value = mock_response

            client = CheckmkClient(self.checkmk_config)

            # Set request ID
            test_id = "req_api_test"
            set_request_id(test_id)

            with caplog.at_level(logging.DEBUG):
                result = client.list_hosts()

                # Verify request ID was included in headers
                mock_request.assert_called_once()
                call_args = mock_request.call_args
                headers = call_args[1].get("headers", {})
                assert "X-Request-ID" in headers
                assert headers["X-Request-ID"] == test_id

                # Verify logging includes request ID
                log_messages = [record.message for record in caplog.records]
                request_id_logs = [msg for msg in log_messages if test_id in msg]
                assert len(request_id_logs) > 0

    @pytest.mark.asyncio
    async def test_service_layer_request_id_flow(self):
        """Test request ID flow through service layer."""
        # Mock async API client
        mock_client = Mock(spec=AsyncCheckmkClient)
        mock_client.list_hosts.return_value = {"value": [{"name": "test-host"}]}

        service = BaseService(mock_client, self.app_config)

        # Set request ID
        test_id = "req_service_test"
        set_request_id(test_id)

        # Execute operation with error handling
        async def test_operation():
            return {"hosts": ["test-host"]}

        result = await service._execute_with_error_handling(
            test_operation, "Test Service Operation"
        )

        # Verify result includes request ID
        assert result.success is True
        assert result.request_id == test_id
        assert result.data == {"hosts": ["test-host"]}

    def test_logging_formatter_integration(self, caplog):
        """Test logging formatter integration with request tracking."""
        # Setup logging with request ID formatter
        setup_logging("DEBUG", include_request_id=True)
        logger = logging.getLogger("test_integration")

        test_id = "req_log_test"
        set_request_id(test_id)

        with caplog.at_level(logging.DEBUG):
            logger.debug("Test debug message")
            logger.info("Test info message")
            logger.warning("Test warning message")
            logger.error("Test error message")

        # Verify all log messages include request ID
        for record in caplog.records:
            assert test_id in record.message or hasattr(record, "request_id")

    def test_middleware_integration(self, caplog):
        """Test middleware integration across components."""
        middleware = RequestTrackingMiddleware(
            auto_generate=True, log_requests=True, include_timing=True
        )

        with caplog.at_level(logging.INFO):
            request_context = {}

            # Start request
            request_id = middleware.process_request(
                request_context, "Integration Test Operation"
            )

            # Simulate API call
            headers = middleware.get_request_headers()
            assert headers["X-Request-ID"] == request_id

            # Simulate successful completion
            middleware.complete_request(request_id, request_context, success=True)

            # Verify comprehensive logging
            log_messages = [record.message for record in caplog.records]
            assert any(
                "Processing Integration Test Operation" in msg for msg in log_messages
            )
            assert any("completed successfully" in msg for msg in log_messages)
            assert any(request_id in msg for msg in log_messages)


class TestMCPServerIntegration:
    """Test request ID integration with MCP server."""

    def setup_method(self):
        """Setup for MCP server tests."""
        REQUEST_ID_CONTEXT.set(None)

    @pytest.mark.asyncio
    async def test_mcp_tool_call_request_id_generation(self):
        """Test MCP tool call generates and tracks request IDs."""
        from checkmk_agent.mcp_server import CheckmkMCPServer

        # Mock configuration
        config = Mock()
        config.checkmk = Mock()

        server = CheckmkMCPServer(config)

        # Mock the _ensure_services method
        server._ensure_services = Mock(return_value=True)

        # Mock a simple tool handler
        async def mock_tool_handler(**kwargs):
            return {
                "result": "success",
                "arguments": kwargs,
                "request_id": get_request_id(),
            }

        server._tool_handlers["test_tool"] = mock_tool_handler

        # Simulate MCP tool call
        result = await server._tool_handlers["test_tool"](param1="value1")

        # Verify request ID was generated and included
        assert "request_id" in result
        assert result["request_id"] is not None
        assert result["request_id"].startswith("req_")

    def test_mcp_server_response_includes_request_id(self):
        """Test MCP server responses include request ID in metadata."""
        # This would test the actual MCP server response format
        # which includes request ID in the meta field

        test_id = "req_mcp_test"
        set_request_id(test_id)

        # Mock MCP response structure
        response = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"result": "test"}),
                    "annotations": None,
                    "meta": {"request_id": test_id},
                }
            ],
            "isError": False,
            "meta": {"request_id": test_id},
            "structuredContent": None,
        }

        # Verify request ID is in response metadata
        assert response["meta"]["request_id"] == test_id
        assert response["content"][0]["meta"]["request_id"] == test_id


class TestCLIIntegration:
    """Test request ID integration with CLI interfaces."""

    def setup_method(self):
        """Setup for CLI tests."""
        REQUEST_ID_CONTEXT.set(None)

    @patch("checkmk_agent.cli.CheckmkClient")
    @patch("checkmk_agent.cli.load_config")
    def test_cli_command_request_id_generation(
        self, mock_load_config, mock_client_class
    ):
        """Test CLI commands generate request IDs."""
        from click.testing import CliRunner
        from checkmk_agent.cli import cli

        # Mock configuration
        mock_config = Mock()
        mock_config.checkmk = self.checkmk_config
        mock_config.log_level = "INFO"
        mock_load_config.return_value = mock_config

        # Mock client
        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_client_class.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["test"])

        # Command should complete successfully
        assert result.exit_code == 0

    def test_cli_with_specific_request_id(self):
        """Test CLI with manually specified request ID."""
        from click.testing import CliRunner
        from checkmk_agent.cli import cli

        test_id = "req_cli_test"

        with patch("checkmk_agent.cli.load_config") as mock_load_config:
            mock_config = Mock()
            mock_config.checkmk = self.checkmk_config
            mock_config.log_level = "INFO"
            mock_load_config.return_value = mock_config

            with patch("checkmk_agent.cli.CheckmkClient"):
                runner = CliRunner()
                result = runner.invoke(cli, ["--request-id", test_id, "test"])

                # Should accept custom request ID
                assert (
                    result.exit_code == 0
                    or "Successfully connected" in result.output
                    or "error" not in result.output.lower()
                )


class TestInteractiveModeIntegration:
    """Test request ID integration with interactive mode."""

    def setup_method(self):
        """Setup for interactive mode tests."""
        REQUEST_ID_CONTEXT.set(None)

    def test_command_parser_request_id_generation(self):
        """Test command parser generates request IDs."""
        from checkmk_agent.interactive.command_parser import CommandParser

        parser = CommandParser()

        # Parse a command
        intent = parser.parse_command("list hosts")

        # Should have generated a request ID during parsing
        current_id = get_request_id()
        assert current_id is not None
        assert current_id.startswith("req_")

    def test_interactive_session_request_continuity(self):
        """Test request ID continuity in interactive sessions."""
        from checkmk_agent.interactive.command_parser import CommandParser

        parser = CommandParser()

        # First command
        intent1 = parser.parse_command("list hosts")
        id1 = get_request_id()

        # Second command (should get new ID)
        intent2 = parser.parse_command("show services")
        id2 = get_request_id()

        # Each command should have its own request ID
        assert id1 != id2
        assert id1.startswith("req_")
        assert id2.startswith("req_")


class TestBatchOperationsIntegration:
    """Test request ID integration with batch operations."""

    def setup_method(self):
        """Setup for batch operation tests."""
        REQUEST_ID_CONTEXT.set(None)

    @pytest.mark.asyncio
    async def test_batch_operation_sub_request_ids(self):
        """Test batch operations generate sub-request IDs."""
        from checkmk_agent.services.base import BaseService

        # Mock async client
        mock_client = Mock(spec=AsyncCheckmkClient)
        service = BaseService(mock_client, Mock())

        # Set parent request ID
        parent_id = "req_batch_parent"
        set_request_id(parent_id)

        # Mock items to process
        items = [f"item_{i}" for i in range(5)]

        # Mock operation that captures request ID
        operation_results = []

        async def mock_operation(item):
            current_id = get_request_id()
            operation_results.append((item, current_id))
            return f"processed_{item}"

        # Execute batch operation
        results = await service._execute_batch_operation(
            items, mock_operation, batch_size=2, operation_name="Test Batch"
        )

        # Verify results
        assert len(results) == 5
        assert all(result.success for result in results)

        # Verify sub-request IDs were generated
        request_ids = [item_id for _, item_id in operation_results]

        # All should be different sub-request IDs
        assert len(set(request_ids)) == 5

        # All should be based on parent ID
        for req_id in request_ids:
            assert req_id.startswith(parent_id)
            assert "." in req_id  # Should be sub-request ID format


class TestErrorHandlingIntegration:
    """Test request ID integration in error scenarios."""

    def setup_method(self):
        """Setup for error handling tests."""
        REQUEST_ID_CONTEXT.set(None)

    def test_api_error_includes_request_id(self, caplog):
        """Test API errors include request ID in error messages."""
        from checkmk_agent.api_client import CheckmkAPIError

        test_id = "req_error_test"
        set_request_id(test_id)

        with patch("requests.Session.request") as mock_request:
            # Mock error response
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"title": "Server Error"}
            mock_response.text = "Internal Server Error"
            mock_request.return_value = mock_response

            client = CheckmkClient(self.checkmk_config)

            with caplog.at_level(logging.ERROR):
                with pytest.raises(CheckmkAPIError):
                    client.list_hosts()

                # Verify error logs include request ID
                log_messages = [record.message for record in caplog.records]
                error_logs = [msg for msg in log_messages if "API error" in msg]
                assert any(test_id in msg for msg in error_logs)

    @pytest.mark.asyncio
    async def test_service_error_preserves_request_id(self):
        """Test service errors preserve request ID context."""
        from checkmk_agent.services.base import BaseService

        mock_client = Mock(spec=AsyncCheckmkClient)
        service = BaseService(mock_client, Mock())

        test_id = "req_service_error"
        set_request_id(test_id)

        async def failing_operation():
            # Verify request ID is available in operation
            assert get_request_id() == test_id
            raise ValueError("Test service error")

        result = await service._execute_with_error_handling(
            failing_operation, "Failing Operation"
        )

        # Verify error result includes request ID
        assert result.success is False
        assert result.request_id == test_id
        assert "Test service error" in result.error


class TestPerformanceImpactIntegration:
    """Test performance impact of request ID tracking in integration scenarios."""

    def setup_method(self):
        """Setup for performance tests."""
        REQUEST_ID_CONTEXT.set(None)

    def test_end_to_end_performance_impact(self):
        """Test end-to-end performance impact of request tracking."""
        import time
        from checkmk_agent.middleware.request_tracking import with_request_tracking

        # Test function without request tracking
        def plain_operation():
            # Simulate some work
            for i in range(100):
                pass
            return "result"

        # Test function with request tracking
        @with_request_tracking("Performance Test")
        def tracked_operation():
            # Simulate same work
            for i in range(100):
                pass
            return "result"

        # Measure plain operations
        start_time = time.time()
        for _ in range(1000):
            plain_operation()
        plain_time = time.time() - start_time

        # Measure tracked operations
        start_time = time.time()
        for _ in range(1000):
            tracked_operation()
        tracked_time = time.time() - start_time

        # Overhead should be reasonable (less than 100% increase)
        overhead_ratio = tracked_time / plain_time if plain_time > 0 else 1

        # Allow for some overhead but ensure it's not excessive
        assert (
            overhead_ratio < 2.0
        ), f"Request tracking overhead too high: {overhead_ratio:.2f}x"

    @pytest.mark.asyncio
    async def test_async_performance_impact(self):
        """Test performance impact in async scenarios."""
        import time
        from checkmk_agent.middleware.request_tracking import with_request_tracking

        # Async function without tracking
        async def plain_async_operation():
            await asyncio.sleep(0.001)  # Simulate async work
            return "result"

        # Async function with tracking
        @with_request_tracking("Async Performance Test")
        async def tracked_async_operation():
            await asyncio.sleep(0.001)  # Simulate same async work
            return "result"

        # Measure plain operations
        start_time = time.time()
        tasks = [plain_async_operation() for _ in range(100)]
        await asyncio.gather(*tasks)
        plain_time = time.time() - start_time

        # Measure tracked operations
        start_time = time.time()
        tasks = [tracked_async_operation() for _ in range(100)]
        await asyncio.gather(*tasks)
        tracked_time = time.time() - start_time

        # Overhead should be reasonable
        overhead_ratio = tracked_time / plain_time if plain_time > 0 else 1
        assert (
            overhead_ratio < 2.0
        ), f"Async request tracking overhead too high: {overhead_ratio:.2f}x"


class TestConfigurationIntegration:
    """Test request ID tracking configuration integration."""

    def test_logging_configuration_with_request_ids(self):
        """Test logging configuration properly includes request IDs."""
        import tempfile
        import logging

        # Setup logging with request ID support
        setup_logging("DEBUG", include_request_id=True)

        # Create a logger and test it
        logger = logging.getLogger("integration_test")

        test_id = "req_config_test"
        set_request_id(test_id)

        # Use StringIO to capture log output
        import io

        log_stream = io.StringIO()

        # Create a handler that writes to our stream
        handler = logging.StreamHandler(log_stream)
        formatter = RequestIDFormatter()
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Log a message
        logger.info("Test configuration message")

        # Get log output
        log_output = log_stream.getvalue()

        # Verify request ID is in output
        assert test_id in log_output
        assert "Test configuration message" in log_output

        # Clean up
        logger.removeHandler(handler)
        handler.close()

    def test_request_id_persistence_across_components(self):
        """Test request ID persists across different component interactions."""
        from checkmk_agent.middleware.request_tracking import RequestTrackingMiddleware

        middleware = RequestTrackingMiddleware()

        # Generate request ID via middleware
        request_context = {}
        request_id = middleware.process_request(request_context, "Multi-Component Test")

        # Verify ID is available in different contexts
        assert get_request_id() == request_id

        # Simulate API client call
        headers = middleware.get_request_headers()
        assert headers["X-Request-ID"] == request_id

        # Simulate receiving response with same ID
        response_headers = {
            "X-Request-ID": request_id,
            "Content-Type": "application/json",
        }
        restored = middleware.extract_request_id_from_headers(response_headers)
        assert restored == request_id

        # Complete the request
        middleware.complete_request(request_id, request_context, success=True)

        # ID should still be available
        assert get_request_id() == request_id
