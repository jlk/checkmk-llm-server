"""CLI tests for effective_attributes functionality.

This test module verifies that the CLI interface correctly handles
the --effective-attributes flag and passes it through to the API client.
"""

import pytest
import tempfile
import json
import os
from unittest.mock import patch, Mock
from click.testing import CliRunner
import requests_mock

from checkmk_agent.cli import cli


@pytest.fixture
def cli_runner():
    """Create Click CLI runner."""
    return CliRunner()


@pytest.fixture
def test_config_file():
    """Create temporary config file for CLI tests."""
    config_data = {
        "checkmk": {
            "server_url": "https://test-cli.example.com",
            "username": "automation",
            "password": "test-password",
            "site": "testsite",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_config_path = f.name

    yield temp_config_path

    # Cleanup
    os.unlink(temp_config_path)


class TestCLIEffectiveAttributesFlag:
    """Test CLI --effective-attributes flag functionality."""

    def test_hosts_list_without_effective_attributes_flag(
        self, cli_runner, test_config_file
    ):
        """Test 'hosts list' command without --effective-attributes flag."""
        with requests_mock.Mocker() as m:
            # Mock the API response
            mock_response = {
                "value": [
                    {
                        "domainType": "host_config",
                        "id": "test-host",
                        "title": "Test Host",
                        "extensions": {
                            "folder": "/test",
                            "attributes": {
                                "ipaddress": "192.168.1.100",
                                "alias": "Test Host",
                            },
                            "is_cluster": False,
                            "is_offline": False,
                        },
                    }
                ]
            }

            m.get(
                "https://test-cli.example.com/testsite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            # Run CLI command without --effective-attributes flag
            result = cli_runner.invoke(
                cli, ["--config", test_config_file, "hosts", "list"]
            )

            # Should succeed
            if result.exit_code != 0:
                print(f"CLI Error: {result.output}")
                print(f"Exception: {result.exception}")
            assert result.exit_code == 0
            assert "test-host" in result.output

            # Verify no effective_attributes parameter was sent
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert "effective_attributes" not in request.url

    def test_hosts_list_with_effective_attributes_flag(
        self, cli_runner, test_config_file
    ):
        """Test 'hosts list' command with --effective-attributes flag."""
        with requests_mock.Mocker() as m:
            # Mock the API response with effective_attributes
            mock_response = {
                "value": [
                    {
                        "domainType": "host_config",
                        "id": "test-host",
                        "title": "Test Host",
                        "extensions": {
                            "folder": "/test",
                            "attributes": {
                                "ipaddress": "192.168.1.100",
                                "alias": "Test Host",
                            },
                            "effective_attributes": {
                                "ipaddress": "192.168.1.100",
                                "alias": "Test Host",
                                "inherited_monitoring": "24x7",
                                "computed_checks": "standard_set",
                            },
                            "is_cluster": False,
                            "is_offline": False,
                        },
                    }
                ]
            }

            m.get(
                "https://test-cli.example.com/testsite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            # Run CLI command with --effective-attributes flag
            result = cli_runner.invoke(
                cli,
                [
                    "--config",
                    test_config_file,
                    "hosts",
                    "list",
                    "--effective-attributes",
                ],
            )

            # Should succeed
            assert result.exit_code == 0
            assert "test-host" in result.output

            # Verify effective_attributes=true parameter was sent
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url

    def test_hosts_get_without_effective_attributes_flag(
        self, cli_runner, test_config_file
    ):
        """Test 'hosts get' command without --effective-attributes flag."""
        with requests_mock.Mocker() as m:
            # Mock the API response
            mock_response = {
                "domainType": "host_config",
                "id": "test-host",
                "title": "Test Host",
                "extensions": {
                    "folder": "/test",
                    "attributes": {"ipaddress": "192.168.1.100", "alias": "Test Host"},
                    "is_cluster": False,
                    "is_offline": False,
                },
            }

            m.get(
                "https://test-cli.example.com/testsite/check_mk/api/1.0/objects/host_config/test-host",
                json=mock_response,
                status_code=200,
            )

            # Run CLI command without --effective-attributes flag
            result = cli_runner.invoke(
                cli, ["--config", test_config_file, "hosts", "get", "test-host"]
            )

            # Should succeed
            assert result.exit_code == 0
            assert "📦 Host Details: test-host" in result.output
            assert "Folder: /test" in result.output
            assert "Effective Attributes:" not in result.output

            # Verify no effective_attributes parameter was sent
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert "effective_attributes" not in request.url

    def test_hosts_get_with_effective_attributes_flag(
        self, cli_runner, test_config_file
    ):
        """Test 'hosts get' command with --effective-attributes flag."""
        with requests_mock.Mocker() as m:
            # Mock the API response with effective_attributes
            mock_response = {
                "domainType": "host_config",
                "id": "test-host",
                "title": "Test Host",
                "extensions": {
                    "folder": "/test",
                    "attributes": {"ipaddress": "192.168.1.100", "alias": "Test Host"},
                    "effective_attributes": {
                        "ipaddress": "192.168.1.100",
                        "alias": "Test Host",
                        "inherited_monitoring": "24x7",
                        "contact_groups": ["admins"],
                        "computed_checks": "standard_set",
                    },
                    "is_cluster": False,
                    "is_offline": False,
                },
            }

            m.get(
                "https://test-cli.example.com/testsite/check_mk/api/1.0/objects/host_config/test-host",
                json=mock_response,
                status_code=200,
            )

            # Run CLI command with --effective-attributes flag
            result = cli_runner.invoke(
                cli,
                [
                    "--config",
                    test_config_file,
                    "hosts",
                    "get",
                    "test-host",
                    "--effective-attributes",
                ],
            )

            # Should succeed
            assert result.exit_code == 0
            assert "📦 Host Details: test-host" in result.output
            assert "Folder: /test" in result.output
            assert "Effective Attributes:" in result.output
            assert "inherited_monitoring: 24x7" in result.output
            assert "contact_groups: ['admins']" in result.output

            # Verify effective_attributes=true parameter was sent
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url


class TestCLIEffectiveAttributesRealScenarios:
    """Test real-world CLI scenarios with effective_attributes."""

    def test_production_monitoring_review_scenario(self, cli_runner, test_config_file):
        """
        Test scenario: Production administrator reviewing complete monitoring configuration.
        """
        with requests_mock.Mocker() as m:
            # Mock response showing rich production configuration
            mock_response = {
                "value": [
                    {
                        "domainType": "host_config",
                        "id": "prod-db-01",
                        "title": "Production Database 01",
                        "extensions": {
                            "folder": "/production/critical/database",
                            "attributes": {
                                "ipaddress": "10.1.1.100",
                                "alias": "Primary Production Database",
                                "tag_criticality": "critical",
                            },
                            "effective_attributes": {
                                "ipaddress": "10.1.1.100",
                                "alias": "Primary Production Database",
                                "tag_criticality": "critical",
                                # Inherited from production folder hierarchy
                                "notification_period": "24x7",
                                "contact_groups": [
                                    "dba-team",
                                    "critical-ops",
                                    "management",
                                ],
                                "max_check_attempts": "5",
                                "notification_escalation": "immediate",
                                "check_interval": "30s",
                                "retry_interval": "10s",
                                # Computed by Checkmk for critical systems
                                "active_service_checks": "247",
                                "passive_service_checks": "12",
                                "monitoring_state": "active",
                                "last_discovery": "2024-08-01",
                                "performance_impact": "optimized",
                            },
                            "is_cluster": False,
                            "is_offline": False,
                        },
                    }
                ]
            }

            m.get(
                "https://test-cli.example.com/testsite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            # Administrator uses CLI to review complete configuration
            result = cli_runner.invoke(
                cli,
                [
                    "--config",
                    test_config_file,
                    "hosts",
                    "list",
                    "--effective-attributes",
                ],
            )

            # Verify comprehensive information is displayed
            assert result.exit_code == 0
            assert "prod-db-01" in result.output
            assert "Primary Production Database" in result.output

            # The CLI displays host info but doesn't show effective_attributes in list view
            # This is expected behavior - list view is meant to be concise

            # Verify the API request included effective_attributes
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url

    def test_troubleshooting_host_configuration_scenario(
        self, cli_runner, test_config_file
    ):
        """
        Test scenario: Troubleshooting specific host configuration issues.
        """
        with requests_mock.Mocker() as m:
            # Mock response for host with problematic configuration
            mock_response = {
                "domainType": "host_config",
                "id": "problematic-host",
                "title": "Host with Configuration Issues",
                "extensions": {
                    "folder": "/development/unstable",
                    "attributes": {
                        "ipaddress": "192.168.100.50",
                        "alias": "Development Host with Issues",
                        "tag_environment": "development",
                    },
                    "effective_attributes": {
                        "ipaddress": "192.168.100.50",
                        "alias": "Development Host with Issues",
                        "tag_environment": "development",
                        # Configuration that might cause issues
                        "max_check_attempts": "1",  # Too aggressive
                        "check_interval": "5s",  # Too frequent for dev
                        "notification_interval": "1",  # Too frequent
                        "contact_groups": ["dev-team"],
                        # Computed values showing the impact
                        "notifications_per_hour": "720",  # Way too many
                        "cpu_usage_from_monitoring": "15%",  # High impact
                        "active_service_checks": "200",  # Too many for dev
                    },
                    "is_cluster": False,
                    "is_offline": False,
                },
            }

            m.get(
                "https://test-cli.example.com/testsite/check_mk/api/1.0/objects/host_config/problematic-host",
                json=mock_response,
                status_code=200,
            )

            # Troubleshooting: Get detailed host configuration
            result = cli_runner.invoke(
                cli,
                [
                    "--config",
                    test_config_file,
                    "hosts",
                    "get",
                    "problematic-host",
                    "--effective-attributes",
                ],
            )

            # Verify troubleshooting information is available
            assert result.exit_code == 0
            assert "📦 Host Details: problematic-host" in result.output
            assert "Folder: /development/unstable" in result.output
            assert "Effective Attributes:" in result.output

            # The CLI should show the problematic configuration values
            assert "max_check_attempts: 1" in result.output
            assert "check_interval: 5s" in result.output
            assert "notifications_per_hour: 720" in result.output

            # Verify the API request included effective_attributes
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url


class TestCLIBackwardCompatibility:
    """Test that CLI maintains backward compatibility with effective_attributes."""

    def test_existing_scripts_without_flag_still_work(
        self, cli_runner, test_config_file
    ):
        """Test that existing scripts that don't use --effective-attributes continue to work."""
        with requests_mock.Mocker() as m:
            # Mock basic response
            mock_response = {
                "value": [
                    {
                        "domainType": "host_config",
                        "id": "legacy-host",
                        "extensions": {
                            "folder": "/legacy",
                            "attributes": {"ipaddress": "192.168.1.200"},
                        },
                    }
                ]
            }

            m.get(
                "https://test-cli.example.com/testsite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            # Run legacy command (no new flags)
            result = cli_runner.invoke(
                cli, ["--config", test_config_file, "hosts", "list"]
            )

            # Should work exactly as before
            assert result.exit_code == 0
            assert "legacy-host" in result.output

            # Verify backward compatibility - no new parameters sent
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert "effective_attributes" not in request.url

    def test_help_includes_effective_attributes_flag(self, cli_runner):
        """Test that CLI help includes information about --effective-attributes flag."""
        # Test hosts list help
        result = cli_runner.invoke(cli, ["hosts", "list", "--help"])
        assert result.exit_code == 0
        assert "--effective-attributes" in result.output
        assert "effective attributes" in result.output.lower()

        # Test hosts get help
        result = cli_runner.invoke(cli, ["hosts", "get", "--help"])
        assert result.exit_code == 0
        assert "--effective-attributes" in result.output
        assert "effective attributes" in result.output.lower()


class TestCLIErrorHandling:
    """Test CLI error handling with effective_attributes flag."""

    def test_permission_denied_with_effective_attributes(
        self, cli_runner, test_config_file
    ):
        """Test CLI handling of permission denied when using --effective-attributes."""
        with requests_mock.Mocker() as m:
            # Mock permission denied response
            m.get(
                "https://test-cli.example.com/testsite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json={
                    "title": "Forbidden",
                    "detail": "Permission denied for effective_attributes parameter",
                },
                status_code=403,
            )

            # Run CLI with effective-attributes flag
            result = cli_runner.invoke(
                cli,
                [
                    "--config",
                    test_config_file,
                    "hosts",
                    "list",
                    "--effective-attributes",
                ],
            )

            # Should fail with appropriate error message
            assert result.exit_code != 0
            assert "Error listing hosts" in result.output

            # Verify the request included the parameter that caused the error
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url
