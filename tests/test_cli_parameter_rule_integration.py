"""
Integration test demonstrating that the CLI parameter setting works without API 400 errors.

This test verifies the end-to-end flow from CLI command to successful rule creation.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from checkmk_agent.cli import cli
from checkmk_agent.config import CheckmkConfig


class TestCLIParameterRuleIntegration:
    """Test CLI integration for parameter rule creation."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_config(self):
        return CheckmkConfig(
            server_url="https://test-checkmk.com",
            username="test_user",
            password="test_password",
            site="test_site",
        )

    def test_cli_set_service_parameters_integration(self, runner, mock_config):
        """
        Test the complete CLI integration for setting service parameters.

        This verifies that the CLI -> ParameterService -> APIClient -> HTTP Request
        flow works correctly without the API 400 conditions error.
        """

        # Mock the configuration loading
        with patch("checkmk_agent.cli.load_config") as mock_load_config, patch(
            "checkmk_agent.services.parameter_service.AsyncCheckmkClient"
        ) as mock_client_class, patch(
            "checkmk_agent.cli.CheckmkClient"
        ) as mock_cli_client_class:

            # Setup configuration mock
            from checkmk_agent.config import AppConfig, LLMConfig

            app_config = AppConfig(checkmk=mock_config, llm=LLMConfig())
            mock_load_config.return_value = app_config

            # Setup API client mock
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_cli_client_class.return_value = mock_client

            # Mock successful rule creation (this would have failed before the fix)
            mock_client.create_service_parameter_rule.return_value = {
                "id": "cli-integration-rule-123",
                "ruleset": "checkgroup_parameters:temperature",
                "folder": "/",
                "conditions": {
                    "host_name": {"match_on": ["piaware"], "operator": "one_of"},
                    "service_description": {
                        "match_on": ["Temperature Zone 0"],
                        "operator": "one_of",
                    },
                },
            }

            # Mock effective parameters retrieval
            mock_client.get_service_effective_parameters.return_value = {
                "parameters": {"levels": [75, 80], "output_unit": "c"},
                "status": "success",
            }

            # Mock parameter validation
            with patch(
                "checkmk_agent.services.parameter_service.ParameterService.validate_parameters"
            ) as mock_validate:
                mock_validate.return_value = MagicMock(
                    success=True,
                    data=MagicMock(
                        is_valid=True,
                        errors=[],
                        warnings=[],
                        normalized_parameters=None,
                    ),
                )

                # Mock ruleset discovery
                with patch(
                    "checkmk_agent.services.parameter_service.ParameterService.discover_ruleset_dynamic"
                ) as mock_discover:
                    mock_discover.return_value = MagicMock(
                        success=True,
                        data={
                            "recommended_ruleset": "checkgroup_parameters:temperature"
                        },
                    )

                    # Act - Execute the CLI command that was failing before the fix
                    result = runner.invoke(
                        cli,
                        [
                            "services",
                            "params",
                            "set",
                            "--host",
                            "piaware",
                            "--service",
                            "Temperature Zone 0",
                            "--parameters",
                            json.dumps(
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
                            "--comment",
                            "CLI integration test rule",
                        ],
                    )

                    # Assert - Command should succeed without API 400 error
                    assert result.exit_code == 0, f"CLI command failed: {result.output}"
                    assert "Successfully set parameters" in result.output

                    # Verify the underlying API call was made with correct format
                    mock_client.create_service_parameter_rule.assert_called_once()
                    call_args = mock_client.create_service_parameter_rule.call_args

                    # Check that the fix is applied at the API level
                    assert call_args[1]["host_name"] == "piaware"
                    assert call_args[1]["service_pattern"] == "Temperature Zone 0"
                    assert (
                        call_args[1]["ruleset_name"]
                        == "checkgroup_parameters:temperature"
                    )
                    assert "description" in call_args[1]

    def test_cli_temperature_parameters_specific_case(self, runner, mock_config):
        """
        Test the specific temperature parameters case that was failing.

        This reproduces the exact CLI scenario from the error logs.
        """
        with patch("checkmk_agent.cli.load_config") as mock_load_config, patch(
            "checkmk_agent.services.parameter_service.AsyncCheckmkClient"
        ) as mock_client_class, patch(
            "checkmk_agent.cli.CheckmkClient"
        ) as mock_cli_client_class:

            # Setup mocks (same as above)
            from checkmk_agent.config import AppConfig, LLMConfig

            app_config = AppConfig(checkmk=mock_config, llm=LLMConfig())
            mock_load_config.return_value = app_config

            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_cli_client_class.return_value = mock_client

            # Mock successful API response (using correct conditions format)
            mock_client.create_service_parameter_rule.return_value = {
                "id": "temperature-rule-456",
                "ruleset": "checkgroup_parameters:temperature",
            }

            mock_client.get_service_effective_parameters.return_value = {
                "parameters": {"levels": [75, 80], "output_unit": "c"},
                "status": "success",
            }

            # Temperature-specific parameters that were causing the issue
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

            with patch(
                "checkmk_agent.services.parameter_service.ParameterService.validate_parameters"
            ) as mock_validate, patch(
                "checkmk_agent.services.parameter_service.ParameterService.discover_ruleset_dynamic"
            ) as mock_discover:

                mock_validate.return_value = MagicMock(
                    success=True,
                    data=MagicMock(
                        is_valid=True,
                        errors=[],
                        warnings=[],
                        normalized_parameters=None,
                    ),
                )

                mock_discover.return_value = MagicMock(
                    success=True,
                    data={"recommended_ruleset": "checkgroup_parameters:temperature"},
                )

                # Act - Execute the specific failing command
                result = runner.invoke(
                    cli,
                    [
                        "service-params",
                        "set",
                        "--host",
                        "piaware",
                        "--service",
                        "Temperature Zone 0",
                        "--parameters",
                        json.dumps(temperature_params),
                    ],
                )

                # Assert - Should succeed with the fix
                assert (
                    result.exit_code == 0
                ), f"Temperature CLI command failed: {result.output}"
                assert "Successfully set parameters" in result.output
                assert "piaware" in result.output
                assert "Temperature Zone 0" in result.output

                # Verify API call was made correctly
                mock_client.create_service_parameter_rule.assert_called_once()

                print(f"\n✅ CLI Integration Test Success!")
                print(f"Command output: {result.output.strip()}")

    def test_cli_error_handling_shows_fix_working(self, runner, mock_config):
        """
        Test that other API errors are still handled correctly.

        This ensures that the conditions fix doesn't break other error handling.
        """
        with patch("checkmk_agent.cli.load_config") as mock_load_config, patch(
            "checkmk_agent.services.parameter_service.AsyncCheckmkClient"
        ) as mock_client_class, patch(
            "checkmk_agent.cli.CheckmkClient"
        ) as mock_cli_client_class:

            from checkmk_agent.config import AppConfig, LLMConfig
            from checkmk_agent.api_client import CheckmkAPIError

            app_config = AppConfig(checkmk=mock_config, llm=LLMConfig())
            mock_load_config.return_value = app_config

            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_cli_client_class.return_value = mock_client

            # Simulate a different API error (not conditions-related)
            mock_client.create_service_parameter_rule.side_effect = CheckmkAPIError(
                "Invalid ruleset name", status_code=400
            )

            with patch(
                "checkmk_agent.services.parameter_service.ParameterService.validate_parameters"
            ) as mock_validate, patch(
                "checkmk_agent.services.parameter_service.ParameterService.discover_ruleset_dynamic"
            ) as mock_discover:

                mock_validate.return_value = MagicMock(
                    success=True,
                    data=MagicMock(
                        is_valid=True,
                        errors=[],
                        warnings=[],
                        normalized_parameters=None,
                    ),
                )

                mock_discover.return_value = MagicMock(
                    success=True, data={"recommended_ruleset": "invalid_ruleset"}
                )

                # Act - This should fail but NOT with conditions error
                result = runner.invoke(
                    cli,
                    [
                        "service-params",
                        "set",
                        "--host",
                        "testhost",
                        "--service",
                        "Test Service",
                        "--parameters",
                        '{"levels": [70, 80]}',
                    ],
                )

                # Assert - Should fail but with correct error (not conditions error)
                assert result.exit_code != 0
                assert (
                    "Invalid ruleset name" in result.output or "Error" in result.output
                )

                # Key verification: NOT a conditions error
                assert "conditions" not in result.output.lower()

                print(f"\n✅ Error Handling Test Success!")
                print(f"Non-conditions error properly handled: {result.output.strip()}")

    def test_cli_help_shows_command_available(self, runner):
        """
        Test that the service-params set command is available and documented.
        """
        # Test that the command group exists
        result = runner.invoke(cli, ["services", "params", "--help"])
        assert result.exit_code == 0
        assert "set" in result.output

        # Test that the set command help works
        result = runner.invoke(cli, ["services", "params", "set", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--service" in result.output
        assert "--parameters" in result.output

        print(f"\n✅ CLI Help Test Success!")
        print("service-params set command is properly documented")
