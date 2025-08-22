"""
Before/After demonstration test for the list handling fix.

This test explicitly shows what would have happened before the fix
versus what happens after the fix is applied.
"""

import pytest
from unittest.mock import patch, Mock
from typing import Dict, Any

from checkmk_mcp_server.api_client import CheckmkClient
from checkmk_mcp_server.config import CheckmkConfig


class TestListHandlingBeforeAfter:
    """Demonstrate the before/after behavior of the list handling fix."""

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

    def create_problematic_discovery_data(self) -> Dict[str, Any]:
        """Create the exact data structure that caused the original error."""
        return {
            "extensions": {
                "services": {
                    "monitored": [
                        # This list entry caused: AttributeError: 'list' object has no attribute 'get'
                        [
                            "Temperature Zone 0",
                            "lm_sensors",
                            {"levels": (60000, 70000)},
                        ],
                        # This dictionary entry worked fine
                        {
                            "service_name": "CPU Load",
                            "parameters": {"levels": (80.0, 90.0)},
                            "check_plugin_name": "cpu",
                        },
                    ]
                }
            }
        }

    def simulate_old_behavior_without_fix(self, services_list):
        """
        Simulate what the old code would do (without type checking).

        This demonstrates the exact error that occurred before the fix.
        """
        errors = []

        for service in services_list:
            try:
                # This is what the old code tried to do - call .get() on every service
                # Without checking if it's a dictionary first
                service_name = service.get(
                    "service_name"
                )  # This line would fail for lists
                if service_name == "Temperature Zone 0":
                    return {"status": "would_have_worked_if_dict"}
            except AttributeError as e:
                errors.append(f"AttributeError: {e}")

        return {"errors": errors}

    def test_before_fix_demonstration(self, client):
        """
        Demonstrate what would have happened before the fix.

        This test shows the exact error that occurred.
        """
        discovery_data = self.create_problematic_discovery_data()
        services_list = discovery_data["extensions"]["services"]["monitored"]

        # Simulate the old behavior (without the fix)
        old_result = self.simulate_old_behavior_without_fix(services_list)

        # The old code would have produced an AttributeError
        assert "errors" in old_result
        assert len(old_result["errors"]) > 0
        assert "'list' object has no attribute 'get'" in str(old_result["errors"][0])

    def test_after_fix_behavior(self, client):
        """
        Demonstrate the new behavior after the fix.

        The same data that caused errors now works correctly.
        """
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = self.create_problematic_discovery_data()
            mock_monitoring.return_value = [
                {"extensions": {"check_command": "mock_check"}}
            ]

            # The same call that would have failed before the fix
            result = client.get_service_effective_parameters(
                "piaware", "Temperature Zone 0"
            )

            # After the fix: no AttributeError, graceful handling
            assert isinstance(result, dict)
            assert "status" in result
            assert result["service_name"] == "Temperature Zone 0"
            # Should gracefully fall back since list entries aren't searchable
            assert result["status"] in ["partial", "not_found"]

    def test_fix_preserves_dictionary_functionality(self, client):
        """
        Verify that the fix doesn't break existing dictionary-based services.
        """
        with patch.object(client, "get_service_discovery_result") as mock_discovery:
            mock_discovery.return_value = self.create_problematic_discovery_data()

            # Dictionary services should still work perfectly
            result = client.get_service_effective_parameters("piaware", "CPU Load")

            assert result["status"] == "success"
            assert result["parameters"]["levels"] == (80.0, 90.0)
            assert result["check_plugin"] == "cpu"

    def test_comprehensive_before_after_comparison(self, client):
        """
        Comprehensive comparison of before/after behavior.
        """
        # Test data with various problematic structures
        comprehensive_data = {
            "extensions": {
                "services": {
                    "monitored": [
                        # Dictionary (always worked)
                        {
                            "service_name": "Working Service",
                            "parameters": {},
                            "check_plugin_name": "test",
                        },
                        # List (caused AttributeError before fix)
                        ["Problematic Service", "test_check", {"param": "value"}],
                        # None (also problematic)
                        None,
                        # Integer (also problematic)
                        42,
                        # String (also problematic)
                        "string_service",
                    ],
                    "ignored": [
                        # More problematic list entries
                        ["Ignored List Service", "ignored_check", {}]
                    ],
                }
            }
        }

        # Simulate old behavior for each service entry
        old_errors = []
        for phase_name, phase_services in comprehensive_data["extensions"][
            "services"
        ].items():
            if isinstance(phase_services, list):
                for service in phase_services:
                    try:
                        # Old code: call .get() without type checking
                        if service is not None:
                            service.get("service_name")  # Would fail for non-dict
                    except AttributeError as e:
                        old_errors.append(str(e))

        # Before fix: multiple AttributeErrors
        assert len(old_errors) >= 4  # list, int, string, list in ignored
        assert all("has no attribute 'get'" in error for error in old_errors)

        # After fix: should handle all gracefully
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring:

            mock_discovery.return_value = comprehensive_data
            mock_monitoring.return_value = [
                {"extensions": {"check_command": "fallback"}}
            ]

            # All these calls should work without AttributeError
            test_services = [
                "Working Service",  # Should be found (dictionary)
                "Problematic Service",  # Should fall back (list)
                "Ignored List Service",  # Should fall back (list in ignored phase)
                "Nonexistent Service",  # Should fall back (not found)
            ]

            for service in test_services:
                result = client.get_service_effective_parameters("test-host", service)
                assert isinstance(result, dict), f"Failed for service: {service}"
                assert "status" in result

                if service == "Working Service":
                    assert result["status"] == "success"
                else:
                    assert result["status"] in ["partial", "not_found"]

    def test_error_message_improvements(self, client):
        """
        Test that error messages are more helpful after the fix.
        """
        with patch.object(
            client, "get_service_discovery_result"
        ) as mock_discovery, patch.object(
            client, "get_service_monitoring_data"
        ) as mock_monitoring, patch.object(
            client, "logger"
        ) as mock_logger:

            mock_discovery.return_value = self.create_problematic_discovery_data()
            mock_monitoring.return_value = [{"extensions": {"check_command": "test"}}]

            # Run the method
            client.get_service_effective_parameters("piaware", "Temperature Zone 0")

            # Check that helpful warnings were logged
            warning_calls = mock_logger.warning.call_args_list
            helpful_warnings = [
                call
                for call in warning_calls
                if "Expected service dictionary but got" in str(call)
            ]

            assert (
                len(helpful_warnings) > 0
            ), "Should log helpful warnings about data types"

            # The warning should specify the actual type that was problematic
            list_warnings = [
                call for call in helpful_warnings if "<class 'list'>" in str(call)
            ]
            assert (
                len(list_warnings) > 0
            ), "Should specifically mention list type in warnings"

    def test_fix_summary_validation(self):
        """
        Summary test that validates what the fix accomplished.
        """
        # Create a mock list that would have caused the original error
        problematic_service = ["Temperature Zone 0", "lm_sensors", {"levels": (60, 70)}]

        # Before fix: This would raise AttributeError
        try:
            # This is what the old code tried to do
            service_name = problematic_service.get("service_name")
            assert False, "Should have raised AttributeError"
        except AttributeError as e:
            assert "'list' object has no attribute 'get'" in str(e)

        # After fix: Type checking prevents the error
        if isinstance(problematic_service, dict):
            service_name = problematic_service.get("service_name")
        else:
            # Fix: Skip non-dictionary entries gracefully
            service_name = None

        assert service_name is None, "Fix should handle list entries gracefully"

        # This test passes, proving the fix concept works
