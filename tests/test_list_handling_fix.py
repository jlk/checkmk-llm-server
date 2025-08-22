"""
Comprehensive test suite for verifying the 'list' object has no attribute 'get' fix.

This test file specifically addresses the error that occurred when the API returned
lists instead of dictionaries, causing AttributeError when .get() was called on list objects.

Original error scenario:
- get_service_effective_parameters was called for "piaware/Temperature Zone 0"
- Service discovery API returned lists in some contexts where dictionaries were expected
- Code attempted to call .get() method on list objects
- Result: AttributeError: 'list' object has no attribute 'get'

The fix implemented proper type checking to handle both lists and dictionaries gracefully.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, List, Any

from checkmk_mcp_server.api_client import CheckmkClient, CheckmkAPIError
from checkmk_mcp_server.config import CheckmkConfig


class TestListHandlingFix:
    """Test suite for verifying the list handling fix in get_service_effective_parameters."""

    @pytest.fixture
    def config(self):
        """Create a real Checkmk configuration."""
        return CheckmkConfig(
            server_url="https://test-checkmk.com",
            username="test_user",
            password="test_password",
            site="test_site",
            max_retries=3,
            request_timeout=30,
        )

    @pytest.fixture
    def client(self, config):
        """Create CheckmkClient instance with mocked dependencies."""
        with patch("checkmk_mcp_server.api_client.requests.Session"), patch(
            "checkmk_mcp_server.api_client.logging.getLogger"
        ):
            return CheckmkClient(config)

    def create_discovery_result_with_lists(self) -> Dict[str, Any]:
        """
        Create a service discovery result that contains lists instead of dictionaries
        in problematic locations. This simulates the exact scenario that caused the error.
        """
        return {
            "extensions": {
                "services": {
                    "monitored": [
                        # Valid dictionary service - should work
                        {
                            "service_name": "CPU load",
                            "parameters": {"levels": (80.0, 90.0)},
                            "check_plugin_name": "cpu",
                        },
                        # This is the problematic case: list instead of dict
                        ["Temperature Zone 0", "temperature", {"levels": (30.0, 35.0)}],
                        # Another problematic case: nested lists
                        [
                            "Disk IO",
                            "disk_io",
                            [{"read_throughput": 100}, {"write_throughput": 50}],
                        ],
                    ],
                    "ignored": [
                        # Mixed content: some dicts, some lists
                        {"service_name": "Valid ignored service", "parameters": {}},
                        ["Invalid list service", "check_type", {}],
                    ],
                    "undecided": [
                        # All list entries (problematic)
                        ["Service A", "check_a", {"param1": "value1"}],
                        ["Service B", "check_b", {"param2": "value2"}],
                    ],
                    "vanished": "this_is_not_even_a_list_or_dict",  # Completely wrong type
                }
            }
        }

    def create_discovery_result_with_mixed_types(self) -> Dict[str, Any]:
        """Create discovery result with various problematic data types."""
        return {
            "extensions": {
                "services": {
                    "monitored": [
                        # Valid cases
                        {
                            "service_name": "piaware/Temperature Zone 0",
                            "parameters": {
                                "device": "/dev/temperature0",
                                "levels": (30.0, 35.0),
                            },
                            "check_plugin_name": "temperature",
                        },
                        # Invalid cases that should be handled gracefully
                        None,  # None value
                        42,  # Integer instead of dict
                        "string_instead_of_dict",  # String
                        [],  # Empty list
                        {},  # Empty dict (valid but no service_name)
                        {
                            # Dict without service_name
                            "parameters": {"some": "params"},
                            "check_plugin_name": "unknown",
                        },
                    ]
                }
            }
        }

    @pytest.mark.parametrize(
        "service_name,expected_found",
        [
            ("CPU load", True),
            (
                "Temperature Zone 0",
                False,
            ),  # List format, won't be found with current logic
            ("piaware/Temperature Zone 0", False),  # Not in this discovery data
            ("Nonexistent Service", False),
        ],
    )
    def test_list_handling_in_service_discovery(
        self, client, service_name, expected_found
    ):
        """
        Test that the method handles lists in service discovery data without errors.

        This tests the core fix: proper type checking before calling .get() on objects.
        """
        # Arrange
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = self.create_discovery_result_with_lists()
            # Mock monitoring endpoint to return expected structure
            mock_monitoring.return_value = [
                {
                    "extensions": {
                        "check_command": f"check_mock --service='{service_name}'"
                    }
                }
            ]

            # Act - This should not raise AttributeError even with problematic data
            result = client.get_service_effective_parameters("test-host", service_name)

            # Assert
            assert isinstance(result, dict), "Result should always be a dictionary"
            assert "status" in result, "Result should have status field"
            assert result["host_name"] == "test-host"
            assert result["service_name"] == service_name

            if expected_found:
                assert result["status"] == "success"
                assert "parameters" in result
            else:
                # Service not found in discovery, should fall back to monitoring endpoint
                assert result["status"] in ["partial", "not_found"]

    def test_original_error_scenario_piaware_temperature(self, client):
        """
        Test the exact scenario that caused the original error:
        get_service_effective_parameters for "piaware/Temperature Zone 0"
        """
        # Arrange - Use mixed types that include the problematic service
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = (
                self.create_discovery_result_with_mixed_types()
            )
            mock_monitoring.return_value = [
                {"extensions": {"check_command": "check_temperature_piaware"}}
            ]

            # Act - This was the exact call that failed before the fix
            result = client.get_service_effective_parameters(
                "piaware", "Temperature Zone 0"
            )

            # Assert - Should not raise 'list' object has no attribute 'get'
            assert isinstance(result, dict)
            assert result["host_name"] == "piaware"
            assert result["service_name"] == "Temperature Zone 0"
            assert "status" in result
            # The "piaware/Temperature Zone 0" service should be found in mixed types
            if result["status"] == "success":
                assert "parameters" in result
            else:
                # If not found, should fall back gracefully
                assert result["status"] in ["partial", "not_found"]

    def test_type_validation_and_error_handling(self, client):
        """
        Test that all type validation and error handling works correctly.

        This verifies the fix handles all the problematic data types gracefully.
        """
        # Arrange
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = (
                self.create_discovery_result_with_mixed_types()
            )
            mock_monitoring.return_value = [
                {"extensions": {"check_command": "check_mock_service"}}
            ]

            # Act & Assert - None of these should raise AttributeError
            test_cases = [
                ("host1", "piaware/Temperature Zone 0"),  # Should be found
                ("host2", "Nonexistent Service"),  # Should not be found
                ("host3", ""),  # Empty service name
                ("", "Some Service"),  # Empty host name
            ]

            for host, service in test_cases:
                result = client.get_service_effective_parameters(host, service)

                # Verify basic result structure
                assert isinstance(
                    result, dict
                ), f"Result should be dict for {host}/{service}"
                assert "status" in result, f"Status missing for {host}/{service}"
                assert "host_name" in result, f"Host name missing for {host}/{service}"
                assert (
                    "service_name" in result
                ), f"Service name missing for {host}/{service}"

    def test_list_entries_are_skipped_gracefully(self, client):
        """
        Test that list entries in service discovery are skipped without causing errors.

        The fix should log warnings about unexpected data types but continue processing.
        """
        # Arrange
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(client, "logger") as mock_logger:

            mock_discovery.return_value = self.create_discovery_result_with_lists()

            # Act
            result = client.get_service_effective_parameters("test-host", "CPU load")

            # Assert - Should find the valid dictionary service
            assert result["status"] == "success"
            assert result["service_name"] == "CPU load"
            assert result["parameters"]["levels"] == (80.0, 90.0)

            # Verify warnings were logged for problematic entries
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "Expected service dictionary but got" in str(call)
            ]
            assert (
                len(warning_calls) > 0
            ), "Should have logged warnings about non-dict services"

    def test_phase_services_type_validation(self, client):
        """
        Test validation of phase services data structure.

        The fix includes checking that phase_services is actually a list.
        """
        # Arrange - Problematic discovery result where phases contain non-lists
        problematic_discovery = {
            "extensions": {
                "services": {
                    "monitored": "this_should_be_a_list",  # Wrong type
                    "ignored": None,  # Wrong type
                    "undecided": 42,  # Wrong type
                    "vanished": {},  # Wrong type (dict instead of list)
                }
            }
        }

        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(client, "logger") as mock_logger:

            mock_discovery.return_value = problematic_discovery

            # Act
            result = client.get_service_effective_parameters("test-host", "Any Service")

            # Assert - Should handle gracefully and fall back to monitoring endpoint
            assert result["status"] in ["partial", "not_found"]

            # Verify warnings were logged for problematic phase data
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "Expected list for phase" in str(call)
            ]
            assert (
                len(warning_calls) >= 4
            ), "Should have logged warnings for all 4 problematic phases"

    def test_backward_compatibility_with_valid_data(self, client):
        """
        Test that the fix maintains backward compatibility with properly formatted data.
        """
        # Arrange - Valid discovery result (the expected format)
        valid_discovery = {
            "extensions": {
                "services": {
                    "monitored": [
                        {
                            "service_name": "Test Service",
                            "parameters": {"threshold": 100, "units": "MB"},
                            "check_plugin_name": "test_check",
                        },
                        {
                            "service_name": "Another Service",
                            "parameters": {"enabled": True},
                            "check_plugin_name": "another_check",
                        },
                    ],
                    "ignored": [],
                    "undecided": [],
                    "vanished": [],
                }
            }
        }

        with patch.object(client, "get_service_discovery_result") as mock_discovery:
            mock_discovery.return_value = valid_discovery

            # Act
            result = client.get_service_effective_parameters(
                "test-host", "Test Service"
            )

            # Assert - Should work exactly as before
            assert result["status"] == "success"
            assert result["service_name"] == "Test Service"
            assert result["parameters"]["threshold"] == 100
            assert result["parameters"]["units"] == "MB"
            assert result["check_plugin"] == "test_check"
            assert result["discovery_phase"] == "monitored"

    def test_fallback_to_monitoring_endpoint_with_list_data(self, client):
        """
        Test fallback to monitoring endpoint when service not found in discovery.

        This tests the secondary code path that also needed list handling.
        """
        # Arrange
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            # Empty discovery result
            mock_discovery.return_value = {
                "extensions": {"services": {"monitored": []}}
            }

            # Monitoring endpoint returns list (this is expected behavior)
            mock_monitoring.return_value = [
                {
                    "extensions": {
                        "check_command": "check_piaware_temperature --device=/dev/temp0"
                    }
                }
            ]

            # Act
            result = client.get_service_effective_parameters(
                "piaware", "Temperature Zone 0"
            )

            # Assert - Should handle list from monitoring endpoint correctly
            assert result["status"] == "partial"
            assert (
                result["check_command"]
                == "check_piaware_temperature --device=/dev/temp0"
            )
            assert (
                "Parameters not available in discovery data"
                in result["parameters"]["note"]
            )

    def test_exception_handling_preserves_error_information(self, client):
        """
        Test that the improved exception handling preserves error information.
        """
        # Arrange
        with patch.object(client, "get_service_discovery_result") as mock_discovery:
            mock_discovery.side_effect = CheckmkAPIError("API Error", status_code=500)

            # Act
            result = client.get_service_effective_parameters(
                "test-host", "test-service"
            )

            # Assert - Should handle API errors gracefully
            assert result["status"] == "error"
            assert result["error_type"] == "CheckmkAPIError"
            assert "API Error" in result["parameters"]["error"]

    def test_comprehensive_error_scenarios(self, client):
        """
        Test various error scenarios to ensure robust error handling.
        """
        error_scenarios = [
            # Discovery returns completely invalid data
            ({"invalid": "structure"}, "Invalid discovery structure"),
            # Discovery returns None
            (None, "None discovery result"),
            # Discovery returns list instead of dict
            ([], "List instead of dict"),
            # Discovery missing extensions
            ({"no_extensions": True}, "Missing extensions"),
            # Discovery missing services in extensions
            ({"extensions": {"no_services": True}}, "Missing services"),
        ]

        for discovery_data, scenario_name in error_scenarios:
            with patch.object(
                client, "get_service_discovery_result"
            ) as mock_discovery, patch.object(
                client, "get_service_monitoring_data"
            ) as mock_monitoring:

                mock_discovery.return_value = discovery_data
                mock_monitoring.side_effect = CheckmkAPIError(
                    "Service not found", status_code=404
                )

                # Act - Should not raise exceptions
                result = client.get_service_effective_parameters(
                    "test-host", "test-service"
                )

                # Assert
                assert isinstance(result, dict), f"Failed for scenario: {scenario_name}"
                assert (
                    "status" in result
                ), f"Missing status for scenario: {scenario_name}"
                assert result["status"] in [
                    "error",
                    "not_found",
                ], f"Unexpected status for scenario: {scenario_name}"

    def test_debug_logging_for_data_structure_analysis(self, client):
        """
        Test that debug logging provides useful information about data structures.

        The fix includes enhanced logging to help debug similar issues in the future.
        """
        # Arrange
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(client, "logger") as mock_logger:

            mock_discovery.return_value = self.create_discovery_result_with_lists()

            # Act
            client.get_service_effective_parameters("test-host", "CPU load")

            # Assert - Verify debug logging was called
            debug_calls = mock_logger.debug.call_args_list

            # Should log discovery result structure
            structure_logs = [
                call
                for call in debug_calls
                if "Service discovery result structure" in str(call)
            ]
            assert len(structure_logs) > 0, "Should log discovery result structure"

            # Should log services data phases
            phases_logs = [
                call
                for call in debug_calls
                if "Services data phases available" in str(call)
            ]
            assert len(phases_logs) > 0, "Should log available phases"

    def test_performance_with_large_problematic_dataset(self, client):
        """
        Test performance and stability with large datasets containing problematic entries.
        """
        # Arrange - Create large dataset with mixed valid/invalid entries
        large_discovery = {"extensions": {"services": {"monitored": []}}}

        # Add 1000 entries with mixed types (some valid, some problematic)
        for i in range(1000):
            if i % 5 == 0:  # Every 5th entry is problematic
                large_discovery["extensions"]["services"]["monitored"].append(
                    ["List service", f"check_{i}", {"param": f"value_{i}"}]
                )
            elif i % 7 == 0:  # Some are completely invalid
                large_discovery["extensions"]["services"]["monitored"].append(i)
            else:  # Most are valid
                large_discovery["extensions"]["services"]["monitored"].append(
                    {
                        "service_name": f"Service {i}",
                        "parameters": {"index": i},
                        "check_plugin_name": f"check_{i}",
                    }
                )

        with patch.object(client, "get_service_discovery_result") as mock_discovery:
            mock_discovery.return_value = large_discovery

            # Act - Should complete without timeout or memory issues
            import time

            start_time = time.time()

            result = client.get_service_effective_parameters("test-host", "Service 10")

            execution_time = time.time() - start_time

            # Assert
            assert execution_time < 5.0, "Should complete within reasonable time"
            assert result["status"] == "success"
            assert result["service_name"] == "Service 10"
