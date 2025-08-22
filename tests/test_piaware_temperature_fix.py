"""
Specific test for the exact "piaware/Temperature Zone 0" error scenario.

This test recreates the exact conditions that caused the original error:
'list' object has no attribute 'get' when calling get_service_effective_parameters
for "piaware/Temperature Zone 0".
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from checkmk_mcp_server.api_client import CheckmkClient, CheckmkAPIError
from checkmk_mcp_server.config import CheckmkConfig


class TestPiawareTemperatureFix:
    """Test the specific piaware temperature sensor error fix."""

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
        with patch("checkmk_mcp_server.api_client.requests.Session"), patch(
            "checkmk_mcp_server.api_client.logging.getLogger"
        ):
            return CheckmkClient(config)

    def create_piaware_discovery_data(self) -> Dict[str, Any]:
        """
        Create discovery data that simulates the actual piaware temperature sensor scenario.

        Based on the error logs, the issue occurred when temperature sensors were returned
        as lists instead of dictionaries in the service discovery data.
        """
        return {
            "extensions": {
                "services": {
                    "monitored": [
                        # Other services as dictionaries (working correctly)
                        {
                            "service_name": "PiAware Process",
                            "parameters": {"process": "piaware"},
                            "check_plugin_name": "ps",
                        },
                        {
                            "service_name": "Interface eth0",
                            "parameters": {"state": ["1"], "speed": 1000000000},
                            "check_plugin_name": "interfaces",
                        },
                        # Temperature sensors as lists (the problematic data structure)
                        # This is what caused the original 'list' object has no attribute 'get' error
                        [
                            "Temperature Zone 0",
                            "lm_sensors",
                            {
                                "device": "/sys/class/thermal/thermal_zone0/temp",
                                "levels": (60000, 70000),  # Temperature in millidegrees
                                "sensor_type": "thermal_zone",
                            },
                        ],
                        [
                            "Temperature Zone 1",
                            "lm_sensors",
                            {
                                "device": "/sys/class/thermal/thermal_zone1/temp",
                                "levels": (55000, 65000),
                                "sensor_type": "thermal_zone",
                            },
                        ],
                        # More temperature sensors as lists
                        [
                            "Temperature CPU",
                            "lm_sensors",
                            {
                                "device": "/sys/class/hwmon/hwmon0/temp1_input",
                                "levels": (75000, 85000),
                                "sensor_type": "cpu_thermal",
                            },
                        ],
                        # Regular services continue as dictionaries
                        {
                            "service_name": "Disk IO",
                            "parameters": {"average": 300},
                            "check_plugin_name": "diskstat",
                        },
                    ],
                    "ignored": [],
                    "undecided": [
                        # Some undecided temperature sensors also as lists
                        [
                            "Temperature GPU",
                            "lm_sensors",
                            {
                                "device": "/sys/class/hwmon/hwmon1/temp1_input",
                                "levels": (80000, 90000),
                                "sensor_type": "gpu_thermal",
                            },
                        ]
                    ],
                    "vanished": [],
                }
            }
        }

    def test_piaware_temperature_zone_0_no_attribute_error(self, client):
        """
        Test the exact error scenario: get_service_effective_parameters for "piaware/Temperature Zone 0".

        Before the fix: AttributeError: 'list' object has no attribute 'get'
        After the fix: Should handle gracefully without error
        """
        # Arrange - Use the exact problematic data structure
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = self.create_piaware_discovery_data()
            mock_monitoring.return_value = [
                {
                    "extensions": {
                        "check_command": "check_lm_sensors!temperature!thermal_zone0"
                    }
                }
            ]

            # Act - This exact call caused the original error
            # The service name "Temperature Zone 0" exists as a list entry, not a dictionary
            result = client.get_service_effective_parameters(
                "piaware", "Temperature Zone 0"
            )

            # Assert - The key test: no AttributeError should be raised
            assert isinstance(result, dict), "Result should be a dictionary"
            assert result["host_name"] == "piaware"
            assert result["service_name"] == "Temperature Zone 0"
            assert "status" in result

            # The temperature sensor is in list format, so won't be found by dictionary lookup
            # Should fall back to monitoring endpoint
            assert result["status"] in ["partial", "not_found"]

            # Should include check command from monitoring fallback
            if "check_command" in result:
                assert "lm_sensors" in result["check_command"]

    def test_all_temperature_sensors_handled_correctly(self, client):
        """
        Test that all temperature sensors in list format are handled without errors.
        """
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = self.create_piaware_discovery_data()
            mock_monitoring.return_value = [
                {"extensions": {"check_command": "mock_temp_check"}}
            ]

            # Test all temperature sensors that are in list format
            temperature_sensors = [
                "Temperature Zone 0",
                "Temperature Zone 1",
                "Temperature CPU",
                "Temperature GPU",  # This is in undecided phase
            ]

            for sensor in temperature_sensors:
                # Act - None of these should raise AttributeError
                result = client.get_service_effective_parameters("piaware", sensor)

                # Assert
                assert isinstance(result, dict), f"Failed for sensor: {sensor}"
                assert result["service_name"] == sensor
                assert "status" in result
                # All should fall back since they're in list format, not searchable by dict keys
                assert result["status"] in [
                    "partial",
                    "not_found",
                ], f"Unexpected status for {sensor}"

    def test_mixed_dictionary_and_list_services_processing(self, client):
        """
        Test that the system correctly processes both dictionary and list services.

        Dictionary services should be found normally, list services should be skipped gracefully.
        """
        with patch.object(client, "get_service_discovery_result") as mock_discovery:
            mock_discovery.return_value = self.create_piaware_discovery_data()

            # Test dictionary services (should be found)
            dict_result = client.get_service_effective_parameters(
                "piaware", "PiAware Process"
            )
            assert dict_result["status"] == "success"
            assert dict_result["parameters"]["process"] == "piaware"
            assert dict_result["check_plugin"] == "ps"

            interface_result = client.get_service_effective_parameters(
                "piaware", "Interface eth0"
            )
            assert interface_result["status"] == "success"
            assert interface_result["parameters"]["speed"] == 1000000000
            assert interface_result["check_plugin"] == "interfaces"

    def test_type_checking_prevents_list_get_calls(self, client):
        """
        Test that the type checking specifically prevents .get() calls on list objects.

        This is the core of the fix: isinstance(service, dict) check before service.get().
        """
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring, patch.object(
            client, "logger"
        ) as mock_logger:

            mock_discovery.return_value = self.create_piaware_discovery_data()
            mock_monitoring.return_value = [{"extensions": {"check_command": "mock"}}]

            # Act
            client.get_service_effective_parameters("piaware", "Temperature Zone 0")

            # Assert - Should have logged warnings about non-dictionary services
            warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "Expected service dictionary but got" in str(call)
            ]

            # Should have warnings for the list entries (temperature sensors)
            assert (
                len(warnings) >= 3
            ), "Should warn about list entries in monitored services"

            # Verify the warning mentions list type
            list_warnings = [w for w in warnings if "<class 'list'>" in str(w)]
            assert (
                len(list_warnings) >= 3
            ), "Should specifically warn about list objects"

    def test_logging_provides_debugging_information(self, client):
        """
        Test that the enhanced logging provides useful debugging information.

        The fix includes better logging to help diagnose similar issues.
        """
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring, patch.object(
            client, "logger"
        ) as mock_logger:

            mock_discovery.return_value = self.create_piaware_discovery_data()
            mock_monitoring.return_value = [
                {"extensions": {"check_command": "debug_check"}}
            ]

            # Act
            client.get_service_effective_parameters("piaware", "Temperature Zone 0")

            # Assert - Check for debug logging
            debug_calls = mock_logger.debug.call_args_list

            # Should log discovery result structure
            structure_logs = [
                call
                for call in debug_calls
                if "Service discovery result structure" in str(call)
            ]
            assert len(structure_logs) > 0, "Should log discovery structure"

            # Should log phases available
            phases_logs = [
                call
                for call in debug_calls
                if "Services data phases available" in str(call)
            ]
            assert len(phases_logs) > 0, "Should log available phases"

    def test_error_resilience_extreme_cases(self, client):
        """
        Test error resilience with extreme temperature sensor data variations.
        """
        # Create extreme variations of temperature sensor data
        extreme_discovery = {
            "extensions": {
                "services": {
                    "monitored": [
                        # Normal list temperature sensor
                        [
                            "Temperature Normal",
                            "lm_sensors",
                            {"levels": (60000, 70000)},
                        ],
                        # Deeply nested list
                        [
                            ["Temperature Nested"],
                            "lm_sensors",
                            {"levels": (50000, 60000)},
                        ],
                        # List with None elements
                        ["Temperature None", None, {"levels": (40000, 50000)}],
                        # List with missing parameters
                        ["Temperature Incomplete", "lm_sensors"],
                        # Empty list
                        [],
                        # List with wrong number of elements
                        [
                            "Temperature Wrong Count",
                            "lm_sensors",
                            {"param": "value"},
                            "extra",
                        ],
                        # Mixed with valid dictionary
                        {
                            "service_name": "Temperature Valid Dict",
                            "parameters": {"levels": (65000, 75000)},
                            "check_plugin_name": "lm_sensors",
                        },
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

            # All of these should work without AttributeError
            test_cases = [
                "Temperature Normal",
                "Temperature Nested",
                "Temperature None",
                "Temperature Incomplete",
                "Temperature Wrong Count",
                "Temperature Valid Dict",  # This should be found
                "Nonexistent Temperature",
            ]

            for temp_service in test_cases:
                result = client.get_service_effective_parameters(
                    "piaware", temp_service
                )
                assert isinstance(result, dict), f"Failed for: {temp_service}"
                assert "status" in result

                if temp_service == "Temperature Valid Dict":
                    # Only the valid dictionary should be found
                    assert result["status"] == "success"
                    assert result["parameters"]["levels"] == (65000, 75000)
                else:
                    # All others should fall back gracefully
                    assert result["status"] in ["partial", "not_found", "error"]

    def test_original_stacktrace_scenario_reproduction(self, client):
        """
        Reproduce the exact scenario from the original error stacktrace.

        This test simulates the exact call chain that led to the error.
        """
        # This discovery data mimics what would cause the original error
        original_error_discovery = {
            "extensions": {
                "services": {
                    "monitored": [
                        # The exact problematic entry that caused 'list' object has no attribute 'get'
                        [
                            "Temperature Zone 0",
                            "lm_sensors",
                            {
                                "device": "/sys/class/thermal/thermal_zone0/temp",
                                "levels": (60000, 70000),
                                "sensor_type": "thermal_zone",
                                "factor": 0.001,
                                "unit": "C",
                            },
                        ]
                    ],
                    "ignored": [],
                    "undecided": [],
                    "vanished": [],
                }
            }
        }

        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = original_error_discovery
            mock_monitoring.return_value = [
                {
                    "extensions": {
                        "check_command": "check_lm_sensors!temperature!thermal_zone0!60000!70000"
                    }
                }
            ]

            # This is the exact call that failed in the original error
            # Before fix: AttributeError: 'list' object has no attribute 'get'
            # After fix: Should work without error
            result = client.get_service_effective_parameters(
                "piaware", "Temperature Zone 0"
            )

            # Verify the fix worked
            assert isinstance(result, dict)
            assert result["host_name"] == "piaware"
            assert result["service_name"] == "Temperature Zone 0"
            assert result["status"] in [
                "partial",
                "not_found",
            ]  # Falls back since it's a list

            # Should contain monitoring information
            if "check_command" in result:
                assert "lm_sensors" in result["check_command"]
                assert "thermal_zone0" in result["check_command"]
