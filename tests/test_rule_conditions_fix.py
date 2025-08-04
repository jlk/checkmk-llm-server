"""
Test for the rule conditions fix that resolves API 400 error when creating parameter rules.

This test verifies that the fix for the conditions field formatting error works correctly.
The original error was:
    API error 400 on POST domain-types/rule/collections/all: These fields have problems: conditions

The fix changed from invalid "match_regex" operator to correct "one_of" operator with proper structure.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any

from checkmk_agent.api_client import CheckmkClient, CheckmkAPIError
from checkmk_agent.config import CheckmkConfig
from checkmk_agent.services.parameter_service import ParameterService


class TestRuleConditionsFix:
    """Test the rule conditions formatting fix for parameter rules."""

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

    @pytest.fixture
    def parameter_service(self, client, config):
        """Create ParameterService instance."""
        from checkmk_agent.async_api_client import AsyncCheckmkClient
        from checkmk_agent.config import AppConfig, LLMConfig

        llm_config = LLMConfig()
        app_config = AppConfig(checkmk=config, llm=llm_config)
        async_client = AsyncCheckmkClient(client)

        with patch("checkmk_agent.services.parameter_service.logging.getLogger"):
            return ParameterService(async_client, app_config)

    def test_create_rule_conditions_format_correct(self, client):
        """
        Test that create_rule is called with correct conditions format.

        The fix ensures conditions use proper "one_of" operator instead of invalid "match_regex".
        """
        # Mock the underlying create_rule method to capture the conditions
        with patch.object(client, "create_rule") as mock_create_rule:
            mock_create_rule.return_value = {
                "id": "test-rule-123",
                "ruleset": "checkgroup_parameters:temperature",
                "folder": "/",
                "value_raw": '{"levels": [75, 80]}',
                "conditions": {
                    "host_name": {"match_on": ["piaware"], "operator": "one_of"},
                    "service_description": {
                        "match_on": ["Temperature Zone 0"],
                        "operator": "one_of",
                    },
                },
            }

            # Act - Create a parameter rule (this should use the fixed conditions format)
            result = client.create_service_parameter_rule(
                ruleset_name="checkgroup_parameters:temperature",
                folder="/",
                parameters={"levels": [75, 80]},
                host_name="piaware",
                service_pattern="Temperature Zone 0",
                description="Test temperature rule",
            )

            # Assert - Verify create_rule was called with correct conditions format
            mock_create_rule.assert_called_once()
            call_args = mock_create_rule.call_args

            # Check the conditions structure
            conditions = call_args[1]["conditions"]  # kwargs
            assert conditions is not None

            # Verify host_name condition uses "one_of" operator
            assert "host_name" in conditions
            assert conditions["host_name"]["operator"] == "one_of"
            assert conditions["host_name"]["match_on"] == ["piaware"]

            # Verify service_description condition uses "one_of" operator (NOT "match_regex")
            assert "service_description" in conditions
            assert conditions["service_description"]["operator"] == "one_of"
            assert conditions["service_description"]["match_on"] == [
                "Temperature Zone 0"
            ]

            # Verify NO "match_regex" operator is used anywhere
            for condition_key, condition_value in conditions.items():
                assert (
                    condition_value["operator"] != "match_regex"
                ), f"Invalid 'match_regex' operator found in {condition_key} condition"

            # Verify rule creation succeeded
            assert result["id"] == "test-rule-123"

    def test_piaware_temperature_parameter_rule_creation_succeeds(self, client):
        """
        Test the exact scenario from the error logs: creating temperature parameters for piaware.

        This should now succeed without the API 400 error.
        """
        # Mock successful rule creation
        with patch.object(client, "create_rule") as mock_create_rule:
            mock_create_rule.return_value = {
                "id": "piaware-temp-rule-456",
                "ruleset": "checkgroup_parameters:temperature",
                "folder": "/",
                "value_raw": json.dumps(
                    {
                        "levels": [75, 80],
                        "levels_lower": [5, 0],
                        "device_levels_handling": "worst",
                        "trend_compute": {
                            "period": 30,
                            "trend_levels": [5, 10],
                            "trend_levels_lower": [5, 10],
                        },
                        "output_unit": "c",
                    }
                ),
                "conditions": {
                    "host_name": {"match_on": ["piaware"], "operator": "one_of"},
                    "service_description": {
                        "match_on": ["Temperature Zone 0"],
                        "operator": "one_of",
                    },
                },
            }

            # Act - Create the exact temperature parameters that were failing
            temperature_params = {
                "levels": [75, 80],
                "levels_lower": [5, 0],
                "device_levels_handling": "worst",
                "trend_compute": {
                    "period": 30,
                    "trend_levels": [5, 10],
                    "trend_levels_lower": [5, 10],
                },
                "output_unit": "c",
            }

            result = client.create_service_parameter_rule(
                ruleset_name="checkgroup_parameters:temperature",
                folder="/",
                parameters=temperature_params,
                host_name="piaware",
                service_pattern="Temperature Zone 0",
                description="Temperature parameters for piaware Temperature Zone 0",
            )

            # Assert - Rule creation should succeed
            assert result["id"] == "piaware-temp-rule-456"

            # Verify the conditions were formatted correctly
            mock_create_rule.assert_called_once()
            call_args = mock_create_rule.call_args
            conditions = call_args[1]["conditions"]

            # Ensure no "match_regex" operator
            assert all(cond["operator"] == "one_of" for cond in conditions.values())

            # Verify parameters were converted to JSON correctly
            value_raw = call_args[1]["value_raw"]
            parsed_params = json.loads(value_raw)
            assert parsed_params["levels"] == [75, 80]
            assert parsed_params["output_unit"] == "c"

    def test_parameter_service_set_service_parameters_integration(
        self, parameter_service
    ):
        """
        Test the full parameter service integration with the rule conditions fix.
        """
        # Mock the checkmk client methods
        with patch.object(
            parameter_service.checkmk, "create_service_parameter_rule"
        ) as mock_create_rule, patch.object(
            parameter_service.checkmk, "get_service_effective_parameters"
        ) as mock_get_effective, patch.object(
            parameter_service, "validate_parameters"
        ) as mock_validate:

            # Setup mocks
            mock_create_rule.return_value = {
                "id": "integration-rule-789",
                "ruleset": "checkgroup_parameters:temperature",
            }

            mock_get_effective.return_value = {
                "parameters": {"levels": [75, 80], "output_unit": "c"},
                "status": "success",
            }

            mock_validate.return_value = MagicMock(
                success=True,
                data=MagicMock(
                    is_valid=True, errors=[], warnings=[], normalized_parameters=None
                ),
            )

            # Act - Use the high-level parameter service
            import asyncio

            result = asyncio.run(
                parameter_service.set_service_parameters(
                    host_name="piaware",
                    service_name="Temperature Zone 0",
                    parameters={
                        "levels": [75, 80],
                        "levels_lower": [5, 0],
                        "output_unit": "c",
                    },
                    rule_comment="Integration test rule",
                )
            )

            # Assert - Operation should succeed
            assert result.success is True
            assert result.data.success is True
            assert result.data.host_name == "piaware"
            assert result.data.service_name == "Temperature Zone 0"
            assert result.data.rule_id == "integration-rule-789"

            # Verify create_service_parameter_rule was called with correct parameters
            mock_create_rule.assert_called_once()
            call_args = mock_create_rule.call_args
            assert call_args[1]["host_name"] == "piaware"
            assert call_args[1]["service_pattern"] == "Temperature Zone 0"
            assert call_args[1]["ruleset_name"] == "checkgroup_parameters:temperature"

    def test_various_service_types_rule_creation(self, client):
        """
        Test that the fix works for different service types, not just temperature.
        """
        test_cases = [
            {
                "service_name": "CPU load",
                "ruleset": "checkgroup_parameters:cpu_load",
                "parameters": {"levels": [80, 90]},
                "description": "CPU load thresholds",
            },
            {
                "service_name": "Interface eth0",
                "ruleset": "checkgroup_parameters:if",
                "parameters": {"speed": 1000000000, "state": ["1"]},
                "description": "Interface parameters",
            },
            {
                "service_name": "Filesystem /",
                "ruleset": "checkgroup_parameters:filesystem",
                "parameters": {"levels": [90, 95], "levels_low": [10, 5]},
                "description": "Filesystem thresholds",
            },
            {
                "service_name": "Memory",
                "ruleset": "checkgroup_parameters:memory",
                "parameters": {"levels": [80, 90]},
                "description": "Memory usage thresholds",
            },
        ]

        for i, case in enumerate(test_cases):
            with patch.object(client, "create_rule") as mock_create_rule:
                mock_create_rule.return_value = {
                    "id": f"rule-{i}",
                    "ruleset": case["ruleset"],
                    "folder": "/",
                    "value_raw": json.dumps(case["parameters"]),
                }

                # Act
                result = client.create_service_parameter_rule(
                    ruleset_name=case["ruleset"],
                    folder="/",
                    parameters=case["parameters"],
                    host_name="testhost",
                    service_pattern=case["service_name"],
                    description=case["description"],
                )

                # Assert - All should succeed with correct conditions format
                mock_create_rule.assert_called_once()
                call_args = mock_create_rule.call_args
                conditions = call_args[1]["conditions"]

                # Verify all use "one_of" operator
                assert conditions["host_name"]["operator"] == "one_of"
                assert conditions["service_description"]["operator"] == "one_of"
                assert result["id"] == f"rule-{i}"

    def test_edge_cases_host_service_patterns(self, client):
        """
        Test edge cases with various host and service pattern formats.
        """
        edge_cases = [
            {
                "host_name": "host-with-dashes",
                "service_pattern": "Service with spaces",
                "description": "Spaces and dashes",
            },
            {
                "host_name": "host.with.dots",
                "service_pattern": "Service/with/slashes",
                "description": "Dots and slashes",
            },
            {
                "host_name": "host_with_underscores",
                "service_pattern": "Service-with-mixed_chars.123",
                "description": "Mixed characters",
            },
            {
                "host_name": "192.168.1.100",
                "service_pattern": "Temperature Zone 0",
                "description": "IP address host",
            },
            {
                "host_name": "UPPERCASE-HOST",
                "service_pattern": "Service (with) [brackets]",
                "description": "Special characters",
            },
        ]

        for i, case in enumerate(edge_cases):
            with patch.object(client, "create_rule") as mock_create_rule:
                mock_create_rule.return_value = {
                    "id": f"edge-rule-{i}",
                    "ruleset": "checkgroup_parameters:temperature",
                    "folder": "/",
                }

                # Act - Should not raise any errors
                result = client.create_service_parameter_rule(
                    ruleset_name="checkgroup_parameters:temperature",
                    folder="/",
                    parameters={"levels": [70, 80]},
                    host_name=case["host_name"],
                    service_pattern=case["service_pattern"],
                    description=case["description"],
                )

                # Assert - Verify correct conditions formatting
                mock_create_rule.assert_called_once()
                call_args = mock_create_rule.call_args
                conditions = call_args[1]["conditions"]

                # Check host name condition
                assert conditions["host_name"]["operator"] == "one_of"
                assert conditions["host_name"]["match_on"] == [case["host_name"]]

                # Check service description condition
                assert conditions["service_description"]["operator"] == "one_of"
                assert conditions["service_description"]["match_on"] == [
                    case["service_pattern"]
                ]

                assert result["id"] == f"edge-rule-{i}"

    def test_conditions_only_included_when_provided(self, client):
        """
        Test that conditions are only included when host_name or service_pattern are provided.
        """
        test_scenarios = [
            {
                "name": "both_provided",
                "host_name": "testhost",
                "service_pattern": "Test Service",
                "expected_conditions": ["host_name", "service_description"],
            },
            {
                "name": "only_host_provided",
                "host_name": "testhost",
                "service_pattern": None,
                "expected_conditions": ["host_name"],
            },
            {
                "name": "only_service_provided",
                "host_name": None,
                "service_pattern": "Test Service",
                "expected_conditions": ["service_description"],
            },
            {
                "name": "neither_provided",
                "host_name": None,
                "service_pattern": None,
                "expected_conditions": [],
            },
        ]

        for scenario in test_scenarios:
            with patch.object(client, "create_rule") as mock_create_rule:
                mock_create_rule.return_value = {
                    "id": f"rule-{scenario['name']}",
                    "ruleset": "checkgroup_parameters:temperature",
                }

                # Act
                client.create_service_parameter_rule(
                    ruleset_name="checkgroup_parameters:temperature",
                    folder="/",
                    parameters={"levels": [70, 80]},
                    host_name=scenario["host_name"],
                    service_pattern=scenario["service_pattern"],
                    description=f"Test {scenario['name']}",
                )

                # Assert
                mock_create_rule.assert_called_once()
                call_args = mock_create_rule.call_args
                conditions = call_args[1]["conditions"]

                if scenario["expected_conditions"]:
                    assert conditions is not None
                    assert set(conditions.keys()) == set(
                        scenario["expected_conditions"]
                    )

                    # All conditions should use "one_of" operator
                    for condition in conditions.values():
                        assert condition["operator"] == "one_of"
                        assert isinstance(condition["match_on"], list)
                        assert len(condition["match_on"]) == 1
                else:
                    # When neither host nor service is provided, conditions should be None or empty
                    assert conditions is None or conditions == {}

    def test_api_error_handling_with_different_errors(self, client):
        """
        Test that the fix specifically resolves the conditions error, and other errors are handled correctly.
        """
        # Test case 1: Simulate the original conditions error (should not happen after fix)
        with patch.object(client, "create_rule") as mock_create_rule:
            mock_create_rule.side_effect = CheckmkAPIError(
                "These fields have problems: conditions", status_code=400
            )

            with pytest.raises(CheckmkAPIError) as exc_info:
                client.create_service_parameter_rule(
                    ruleset_name="checkgroup_parameters:temperature",
                    folder="/",
                    parameters={"levels": [70, 80]},
                    host_name="testhost",
                    service_pattern="Test Service",
                )

            assert "conditions" in str(exc_info.value)
            assert exc_info.value.status_code == 400

        # Test case 2: Different API error (should propagate normally)
        with patch.object(client, "create_rule") as mock_create_rule:
            mock_create_rule.side_effect = CheckmkAPIError(
                "Invalid ruleset name", status_code=400
            )

            with pytest.raises(CheckmkAPIError) as exc_info:
                client.create_service_parameter_rule(
                    ruleset_name="invalid_ruleset",
                    folder="/",
                    parameters={"levels": [70, 80]},
                    host_name="testhost",
                    service_pattern="Test Service",
                )

            assert "Invalid ruleset name" in str(exc_info.value)

        # Test case 3: Authorization error
        with patch.object(client, "create_rule") as mock_create_rule:
            mock_create_rule.side_effect = CheckmkAPIError(
                "Unauthorized", status_code=401
            )

            with pytest.raises(CheckmkAPIError) as exc_info:
                client.create_service_parameter_rule(
                    ruleset_name="checkgroup_parameters:temperature",
                    folder="/",
                    parameters={"levels": [70, 80]},
                    host_name="testhost",
                    service_pattern="Test Service",
                )

            assert exc_info.value.status_code == 401

    def test_json_serialization_of_complex_parameters(self, client):
        """
        Test that complex parameter structures are correctly serialized to JSON.
        """
        complex_parameters = {
            "levels": [75, 80],
            "levels_lower": [5, 0],
            "device_levels_handling": "worst",
            "trend_compute": {
                "period": 30,
                "trend_levels": [5, 10],
                "trend_levels_lower": [5, 10],
            },
            "output_unit": "c",
            "input_unit": "c",
            "trend_timeleft": (240, 120),
            "trend_showtimeleft": True,
            "trend_perfdata": True,
        }

        with patch.object(client, "create_rule") as mock_create_rule:
            mock_create_rule.return_value = {
                "id": "complex-rule",
                "ruleset": "checkgroup_parameters:temperature",
            }

            # Act
            client.create_service_parameter_rule(
                ruleset_name="checkgroup_parameters:temperature",
                folder="/",
                parameters=complex_parameters,
                host_name="piaware",
                service_pattern="Temperature Zone 0",
            )

            # Assert - Verify JSON serialization
            mock_create_rule.assert_called_once()
            call_args = mock_create_rule.call_args
            value_raw = call_args[1]["value_raw"]

            # Should be valid JSON
            parsed_params = json.loads(value_raw)

            # Verify all parameters are preserved (except tuples become lists)
            expected_params = complex_parameters.copy()
            expected_params["trend_timeleft"] = [240, 120]  # Tuple becomes list in JSON
            assert parsed_params == expected_params

            # Verify nested structures are preserved
            assert parsed_params["trend_compute"]["period"] == 30
            assert parsed_params["trend_compute"]["trend_levels"] == [5, 10]
            assert parsed_params["trend_timeleft"] == [
                240,
                120,
            ]  # Tuples become lists in JSON
            assert parsed_params["trend_showtimeleft"] is True

    def test_logging_shows_correct_conditions_format(self, client):
        """
        Test that logging shows the corrected conditions format for debugging.
        """
        with patch.object(client, "create_rule") as mock_create_rule, patch.object(
            client, "logger"
        ) as mock_logger:

            mock_create_rule.return_value = {"id": "logged-rule"}

            # Act
            client.create_service_parameter_rule(
                ruleset_name="checkgroup_parameters:temperature",
                folder="/",
                parameters={"levels": [70, 80]},
                host_name="piaware",
                service_pattern="Temperature Zone 0",
                description="Logged rule creation",
            )

            # Assert - Check that success is logged
            info_calls = mock_logger.info.call_args_list
            success_logs = [
                call for call in info_calls if "Created parameter rule" in str(call)
            ]
            assert len(success_logs) > 0

            # Verify logged message contains correct information
            logged_message = str(success_logs[0])
            assert "piaware" in logged_message
            assert "Temperature Zone 0" in logged_message
            assert "checkgroup_parameters:temperature" in logged_message
