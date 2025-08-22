"""
Test for async/await coroutine fix in parameter service.

This test reproduces the exact error scenario from the logs:
AttributeError: 'coroutine' object has no attribute 'get'

The error occurred at line 341 in parameter_service.py:
if effective_result.get("status") == "error":

This test verifies that the fix properly awaits the coroutine and returns
a dictionary instead of a coroutine object.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from checkmk_mcp_server.async_api_client import AsyncCheckmkClient
from checkmk_mcp_server.api_client import CheckmkClient
from checkmk_mcp_server.config import AppConfig
from checkmk_mcp_server.services.parameter_service import ParameterService
from checkmk_mcp_server.api_client import CheckmkAPIError


class TestAsyncCoroutineFix:
    """Test cases for the async/await coroutine fix in parameter service."""

    @pytest.fixture
    def mock_sync_client(self):
        """Create a mock synchronous Checkmk client."""
        mock_client = MagicMock(spec=CheckmkClient)

        # Mock the get_service_effective_parameters method
        mock_client.get_service_effective_parameters.return_value = {
            "host_name": "test-host",
            "service_name": "CPU load",
            "parameters": {"levels": (80.0, 90.0)},
            "status": "success",
            "source": "service_discovery",
        }

        return mock_client

    @pytest.fixture
    def mock_async_client(self, mock_sync_client):
        """Create a mock async Checkmk client."""
        return AsyncCheckmkClient(mock_sync_client)

    @pytest.fixture
    def mock_config(self):
        """Create a mock app configuration."""
        config = MagicMock(spec=AppConfig)
        config.checkmk = MagicMock()
        config.checkmk.url = "https://test-checkmk.example.com"
        config.checkmk.username = "test_user"
        config.checkmk.password = "test_password"
        return config

    @pytest.fixture
    def parameter_service(self, mock_async_client, mock_config):
        """Create a parameter service instance."""
        return ParameterService(mock_async_client, mock_config)

    @pytest.mark.asyncio
    async def test_get_effective_parameters_returns_dictionary(
        self, parameter_service, mock_sync_client
    ):
        """Test that get_effective_parameters returns a dictionary, not a coroutine."""
        # Arrange
        host_name = "test-host"
        service_name = "CPU load"

        # Act
        result = await parameter_service.get_effective_parameters(
            host_name, service_name
        )

        # Assert
        assert result.success is True
        assert isinstance(result.data, object)  # ServiceParameterResult object
        assert hasattr(result.data, "host_name")
        assert hasattr(result.data, "service_name")
        assert hasattr(result.data, "parameters")
        assert result.data.host_name == host_name
        assert result.data.service_name == service_name

        # Verify the sync client method was called
        mock_sync_client.get_service_effective_parameters.assert_called_once_with(
            host_name, service_name
        )

    @pytest.mark.asyncio
    async def test_effective_result_get_method_works(
        self, parameter_service, mock_sync_client
    ):
        """Test that effective_result.get() method works (reproduces the original error scenario)."""
        # Arrange - Mock the sync client to return an error status
        mock_sync_client.get_service_effective_parameters.return_value = {
            "host_name": "test-host",
            "service_name": "CPU load",
            "parameters": {"error": "Service not found"},
            "status": "error",
        }

        host_name = "test-host"
        service_name = "CPU load"

        # Act
        result = await parameter_service.get_effective_parameters(
            host_name, service_name
        )

        # Assert
        # The method should handle the error gracefully and return default parameters
        assert result.success is True
        assert result.data.host_name == host_name
        assert result.data.service_name == service_name
        # Should fall back to default parameters when API returns error
        assert len(result.data.warnings) > 0
        assert "Could not retrieve effective parameters" in result.data.warnings[0]

    @pytest.mark.asyncio
    async def test_coroutine_not_returned_from_async_wrapper(
        self, mock_sync_client, mock_config
    ):
        """Test that the async wrapper properly awaits and doesn't return a coroutine."""
        # Arrange
        async_client = AsyncCheckmkClient(mock_sync_client)

        # Act - Call the async method directly
        result = await async_client.get_service_effective_parameters(
            "test-host", "CPU load"
        )

        # Assert
        assert not asyncio.iscoroutine(result)
        assert isinstance(result, dict)
        assert result.get("status") is not None
        assert result.get("host_name") == "test-host"
        assert result.get("service_name") == "CPU load"

    @pytest.mark.asyncio
    async def test_line_341_error_scenario_reproduction(
        self, parameter_service, mock_sync_client
    ):
        """Reproduce the exact error scenario from line 341 in parameter_service.py."""
        # Arrange - Set up the exact conditions that caused the original error
        mock_sync_client.get_service_effective_parameters.return_value = {
            "host_name": "test-host",
            "service_name": "Temperature sensors",
            "parameters": {"error": "API connection failed"},
            "status": "error",
        }

        # Act - This should NOT raise AttributeError: 'coroutine' object has no attribute 'get'
        result = await parameter_service.get_effective_parameters(
            "test-host", "Temperature sensors"
        )

        # Assert
        assert result.success is True
        # Should handle the error and return default parameters
        assert result.data.parameters is not None
        assert len(result.data.warnings) > 0

    @pytest.mark.asyncio
    async def test_api_error_exception_handling(
        self, parameter_service, mock_sync_client
    ):
        """Test that CheckmkAPIError exceptions are properly handled."""
        # Arrange
        mock_sync_client.get_service_effective_parameters.side_effect = CheckmkAPIError(
            "Connection timeout", 408
        )

        # Act
        result = await parameter_service.get_effective_parameters(
            "test-host", "CPU load"
        )

        # Assert
        assert result.success is True  # Should gracefully handle the error
        assert result.data.parameters is not None  # Should return default parameters
        assert len(result.data.warnings) > 0
        assert "Could not retrieve effective parameters" in result.data.warnings[0]

    @pytest.mark.asyncio
    async def test_multiple_status_conditions(
        self, parameter_service, mock_sync_client
    ):
        """Test different status conditions to ensure proper dictionary handling."""
        test_cases = [
            {"status": "success", "expected_success": True},
            {"status": "error", "expected_warnings": True},
            {"status": "partial", "expected_success": True},
            {"status": "not_found", "expected_warnings": True},
        ]

        for case in test_cases:
            # Arrange
            mock_sync_client.get_service_effective_parameters.return_value = {
                "host_name": "test-host",
                "service_name": "Test Service",
                "parameters": {"levels": (70.0, 80.0)},
                "status": case["status"],
            }

            # Act
            result = await parameter_service.get_effective_parameters(
                "test-host", "Test Service"
            )

            # Assert
            assert result.success is True
            assert isinstance(result.data.parameters, dict)

            if case.get("expected_warnings"):
                assert len(result.data.warnings) > 0

    @pytest.mark.asyncio
    async def test_async_wrapper_thread_pool_execution(self, mock_sync_client):
        """Test that the async wrapper properly executes in thread pool."""
        # Arrange
        async_client = AsyncCheckmkClient(mock_sync_client)

        # Mock the sync method to verify it's called
        mock_sync_client.get_service_effective_parameters.return_value = {
            "status": "success",
            "parameters": {"test": "value"},
        }

        # Act
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = AsyncMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = {
                "status": "success",
                "parameters": {"test": "value"},
            }

            result = await async_client.get_service_effective_parameters(
                "host", "service"
            )

            # Assert
            mock_loop.run_in_executor.assert_called_once()
            assert isinstance(result, dict)
            assert not asyncio.iscoroutine(result)

    @pytest.mark.asyncio
    async def test_service_type_determination_with_async_result(
        self, parameter_service, mock_sync_client
    ):
        """Test that service type determination works with properly awaited results."""
        # Arrange
        mock_sync_client.get_service_effective_parameters.return_value = {
            "host_name": "test-host",
            "service_name": "Temperature sensors",
            "parameters": {"levels": (70.0, 80.0)},
            "status": "success",
        }

        # Act
        result = await parameter_service.get_effective_parameters(
            "test-host", "Temperature sensors"
        )

        # Assert
        assert result.success is True
        assert result.data.service_name == "Temperature sensors"
        # Should recognize temperature service type
        assert result.data.ruleset is not None

    @pytest.mark.asyncio
    async def test_concurrent_effective_parameters_calls(
        self, parameter_service, mock_sync_client
    ):
        """Test concurrent calls to get_effective_parameters to ensure thread safety."""
        # Arrange
        mock_sync_client.get_service_effective_parameters.return_value = {
            "status": "success",
            "parameters": {"levels": (80.0, 90.0)},
        }

        # Act - Make multiple concurrent calls
        tasks = [
            parameter_service.get_effective_parameters(f"host-{i}", f"service-{i}")
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == 5
        for result in results:
            assert result.success is True
            assert not asyncio.iscoroutine(result.data)

    @pytest.mark.asyncio
    async def test_error_handling_preserves_dictionary_structure(
        self, parameter_service, mock_sync_client
    ):
        """Test that error handling preserves proper dictionary structure."""
        # Arrange - Test CheckmkAPIError scenarios (should be handled gracefully)
        api_error_scenarios = [
            CheckmkAPIError("Not found", 404),
            CheckmkAPIError("Timeout", 408),
        ]

        for error in api_error_scenarios:
            mock_sync_client.get_service_effective_parameters.side_effect = error

            # Act
            result = await parameter_service.get_effective_parameters(
                "test-host", "CPU load"
            )

            # Assert - CheckmkAPIError should be handled gracefully
            assert result.success is True  # Should handle API errors gracefully
            assert result.data.parameters is not None
            assert isinstance(result.data.parameters, dict)
            assert not asyncio.iscoroutine(result.data.parameters)
            assert len(result.data.warnings) > 0

        # Test generic exception (should fail but not return coroutine)
        mock_sync_client.get_service_effective_parameters.side_effect = Exception(
            "Generic error"
        )
        result = await parameter_service.get_effective_parameters(
            "test-host", "CPU load"
        )

        # Assert - Generic exception should fail but return proper structure
        assert result.success is False  # Generic exceptions should fail
        assert result.error is not None
        assert not asyncio.iscoroutine(
            result
        )  # The important part - no coroutine returned

    def test_sync_method_signature_matches_async(self):
        """Test that sync and async method signatures match for compatibility."""
        from checkmk_mcp_server.config import CheckmkConfig

        # Create a mock config
        mock_config = MagicMock(spec=CheckmkConfig)
        mock_config.server_url = "https://test.com"
        mock_config.username = "user"
        mock_config.password = "pass"
        mock_config.site = "test"

        sync_client = CheckmkClient(mock_config)
        async_client = AsyncCheckmkClient(sync_client)

        # Get method signatures
        import inspect

        sync_sig = inspect.signature(sync_client.get_service_effective_parameters)
        async_sig = inspect.signature(async_client.get_service_effective_parameters)

        # Compare parameters (excluding 'self')
        sync_params = list(sync_sig.parameters.keys())[1:]  # Skip 'self'
        async_params = list(async_sig.parameters.keys())[1:]  # Skip 'self'

        assert sync_params == async_params, "Method signatures should match"
