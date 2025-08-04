"""
Core tests for the 'list' object has no attribute 'get' fix.

This focused test suite demonstrates that the key fix works:
- Lists in service discovery data are handled without AttributeError
- Type checking prevents calling .get() on non-dictionary objects
- The method returns meaningful results even with problematic data
"""

import pytest
from unittest.mock import patch
from typing import Dict, Any

from checkmk_agent.api_client import CheckmkClient, CheckmkAPIError
from checkmk_agent.config import CheckmkConfig


class TestCoreListHandlingFix:
    """Core tests for the list handling fix."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
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
        """Create CheckmkClient instance."""
        with patch("checkmk_agent.api_client.requests.Session"), patch(
            "checkmk_agent.api_client.logging.getLogger"
        ):
            return CheckmkClient(config)

    def test_original_error_fixed_no_attribute_error(self, client):
        """
        Prove that the original 'list' object has no attribute 'get' error is fixed.

        The original error occurred when service discovery returned lists instead of
        dictionaries, and the code tried to call .get() on list objects.
        """
        # Create discovery data with problematic list entries
        problematic_discovery = {
            "extensions": {
                "services": {
                    "monitored": [
                        # Valid dictionary entry - this works
                        {
                            "service_name": "Valid Service",
                            "parameters": {"param1": "value1"},
                            "check_plugin_name": "valid_check",
                        },
                        # Problematic list entry - this used to cause AttributeError
                        ["List Service", "list_check", {"param2": "value2"}],
                        # Mixed invalid types
                        None,
                        42,
                        "string_entry",
                    ]
                }
            }
        }

        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = problematic_discovery
            mock_monitoring.return_value = [
                {"extensions": {"check_command": "mock_check"}}
            ]

            # Act - This should NOT raise AttributeError: 'list' object has no attribute 'get'
            # Before the fix, calling .get() on the list entry would cause this error
            result = client.get_service_effective_parameters("test-host", "Any Service")

            # Assert - The key proof: no AttributeError was raised
            assert isinstance(result, dict)
            assert "status" in result
            assert result["host_name"] == "test-host"
            assert result["service_name"] == "Any Service"
            # Should handle the error gracefully and fall back to monitoring endpoint
            assert result["status"] in ["partial", "not_found"]

    def test_list_type_checking_prevents_get_calls(self, client):
        """
        Test that the type checking prevents calling .get() on list objects.

        This is the core of the fix: checking isinstance(service, dict) before
        calling service.get().
        """
        # Discovery data where ALL services are lists (worst case scenario)
        all_lists_discovery = {
            "extensions": {
                "services": {
                    "monitored": [
                        ["Service A", "check_a", {"param": "a"}],
                        ["Service B", "check_b", {"param": "b"}],
                        ["Service C", "check_c", {"param": "c"}],
                    ],
                    "ignored": [["Ignored Service", "ignored_check", {}]],
                    "undecided": [["Undecided Service", "undecided_check", {}]],
                    "vanished": [["Vanished Service", "vanished_check", {}]],
                }
            }
        }

        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = all_lists_discovery
            mock_monitoring.return_value = [
                {"extensions": {"check_command": "fallback_check"}}
            ]

            # Act - Should handle all list entries without error
            result = client.get_service_effective_parameters("test-host", "Service A")

            # Assert - No AttributeError, graceful fallback
            assert isinstance(result, dict)
            assert result["status"] in ["partial", "not_found"]

    def test_mixed_valid_invalid_data_processing(self, client):
        """
        Test processing of mixed valid/invalid data types.

        This ensures valid dictionary entries still work while invalid ones are skipped.
        """
        mixed_discovery = {
            "extensions": {
                "services": {
                    "monitored": [
                        # Valid entry - should be found
                        {
                            "service_name": "Temperature Sensor",
                            "parameters": {
                                "device": "/dev/temp0",
                                "levels": (30.0, 35.0),
                            },
                            "check_plugin_name": "temperature",
                        },
                        # Invalid list - should be skipped
                        ["Invalid List Entry", "temp_check", {"levels": (25.0, 30.0)}],
                        # Another valid entry
                        {
                            "service_name": "CPU Load",
                            "parameters": {"levels": (80.0, 90.0)},
                            "check_plugin_name": "cpu_load",
                        },
                        # More invalid types - should be skipped
                        None,
                        "string",
                        123,
                    ]
                }
            }
        }

        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = mixed_discovery
            mock_monitoring.return_value = [{"extensions": {"check_command": "mock"}}]

            # Test finding valid services
            result1 = client.get_service_effective_parameters(
                "test-host", "Temperature Sensor"
            )
            assert result1["status"] == "success"
            assert result1["parameters"]["device"] == "/dev/temp0"
            assert result1["check_plugin"] == "temperature"

            result2 = client.get_service_effective_parameters("test-host", "CPU Load")
            assert result2["status"] == "success"
            assert result2["parameters"]["levels"] == (80.0, 90.0)

            # Test handling non-existent service (falls back to monitoring)
            result3 = client.get_service_effective_parameters(
                "test-host", "Non-existent"
            )
            assert result3["status"] in ["partial", "not_found"]

    def test_backward_compatibility_valid_data_unchanged(self, client):
        """
        Test that the fix doesn't break existing functionality with valid data.

        This ensures backward compatibility is maintained.
        """
        valid_discovery = {
            "extensions": {
                "services": {
                    "monitored": [
                        {
                            "service_name": "Disk Space /",
                            "parameters": {"levels": (80.0, 90.0), "magic": 1.0},
                            "check_plugin_name": "df",
                        },
                        {
                            "service_name": "Memory",
                            "parameters": {"levels": (80.0, 90.0)},
                            "check_plugin_name": "mem",
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

            # Test - Should work exactly as before the fix
            result = client.get_service_effective_parameters(
                "test-host", "Disk Space /"
            )

            assert result["status"] == "success"
            assert result["service_name"] == "Disk Space /"
            assert result["parameters"]["levels"] == (80.0, 90.0)
            assert result["parameters"]["magic"] == 1.0
            assert result["check_plugin"] == "df"
            assert result["discovery_phase"] == "monitored"

    def test_error_logging_for_invalid_types(self, client):
        """
        Test that appropriate warnings are logged for invalid data types.

        The fix includes enhanced logging to help debug similar issues.
        """
        problematic_discovery = {
            "extensions": {
                "services": {
                    "monitored": [
                        ["List entry", "check", {}],  # Should log warning
                        None,  # Should log warning
                        42,  # Should log warning
                        "string",  # Should log warning
                        {"service_name": "Valid"},  # Should NOT log warning
                    ]
                }
            }
        }

        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring, patch.object(
            client, "logger"
        ) as mock_logger:

            mock_discovery.return_value = problematic_discovery
            mock_monitoring.return_value = [{"extensions": {"check_command": "mock"}}]

            # Act
            client.get_service_effective_parameters("test-host", "Valid")

            # Assert - Should have logged warnings for non-dict services
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "Expected service dictionary but got" in str(call)
            ]
            # Should have 4 warnings: list, None, int, string (but not for valid dict)
            assert len(warning_calls) >= 4

    def test_phase_validation_prevents_errors(self, client):
        """
        Test that phase validation prevents errors when phases contain non-lists.

        Another part of the fix: ensuring phase_services is actually a list.
        """
        invalid_phases_discovery = {
            "extensions": {
                "services": {
                    "monitored": "should_be_list",  # Wrong type
                    "ignored": None,  # Wrong type
                    "undecided": 42,  # Wrong type
                    "vanished": {"not": "a_list"},  # Wrong type
                }
            }
        }

        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring, patch.object(
            client, "logger"
        ) as mock_logger:

            mock_discovery.return_value = invalid_phases_discovery
            mock_monitoring.return_value = [{"extensions": {"check_command": "mock"}}]

            # Act - Should not crash despite invalid phase data
            result = client.get_service_effective_parameters("test-host", "Any Service")

            # Assert
            assert isinstance(result, dict)
            assert result["status"] in ["partial", "not_found"]

            # Should have logged warnings about invalid phase types
            phase_warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "Expected list for phase" in str(call)
            ]
            assert len(phase_warnings) >= 4  # One for each invalid phase

    def test_comprehensive_error_resilience(self, client):
        """
        Test comprehensive error resilience with extreme edge cases.

        This ensures the fix handles even the most pathological data.
        """
        extreme_discovery = {
            "extensions": {
                "services": {
                    "monitored": [
                        # Nested complexity
                        {
                            "service_name": "Complex Service",
                            "parameters": {
                                "nested": {"deep": {"value": 123}},
                                "list_param": [1, 2, 3],
                                "mixed": {"a": [1, 2], "b": {"c": 3}},
                            },
                            "check_plugin_name": "complex",
                        },
                        # Pathological cases
                        [[[["deeply_nested_list"]]]],
                        {"no_service_name": "missing_key"},
                        {"service_name": "", "parameters": {}},  # Empty name
                        {"service_name": None, "parameters": {}},  # None name
                    ]
                }
            }
        }

        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = extreme_discovery
            mock_monitoring.return_value = [
                {"extensions": {"check_command": "extreme_mock"}}
            ]

            # Should handle all edge cases without crashing
            test_services = [
                "Complex Service",  # Should be found
                "Nonexistent",  # Should fall back
                "",  # Empty string
                None,  # This would cause other errors, but not AttributeError
            ]

            for service in test_services:
                if service is None:
                    continue  # Skip None test as it would fail type checking elsewhere

                result = client.get_service_effective_parameters("test-host", service)
                assert isinstance(result, dict)
                assert "status" in result

                if service == "Complex Service":
                    assert result["status"] == "success"
                    assert result["parameters"]["nested"]["deep"]["value"] == 123
