"""Focused end-to-end tests for effective_attributes functionality.

This test module provides targeted testing to verify that the
effective_attributes parameter flows correctly through the system.
"""

import pytest
import requests_mock
from unittest.mock import Mock, AsyncMock

from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.async_api_client import AsyncCheckmkClient
from checkmk_agent.services.host_service import HostService
from checkmk_agent.config import CheckmkConfig, LLMConfig, AppConfig


@pytest.fixture
def test_config():
    """Create test configuration."""
    return AppConfig(
        checkmk=CheckmkConfig(
            server_url="https://test-checkmk.example.com",
            username="automation",
            password="secret",
            site="mysite",
        ),
        llm=LLMConfig(),
        default_folder="/test",
        log_level="DEBUG",
    )


class TestEffectiveAttributesParameterFlow:
    """Test that effective_attributes parameter flows correctly through all layers."""

    def test_api_client_parameter_flow(self, test_config):
        """Test that CheckmkClient correctly handles effective_attributes parameter."""
        client = CheckmkClient(test_config.checkmk)

        with requests_mock.Mocker() as m:
            # Mock response with effective_attributes
            mock_response = {
                "value": [
                    {
                        "id": "test-host",
                        "extensions": {
                            "folder": "/test",
                            "attributes": {"ipaddress": "192.168.1.100"},
                            "effective_attributes": {
                                "ipaddress": "192.168.1.100",
                                "inherited_setting": "from_parent",
                            },
                        },
                    }
                ]
            }

            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            # Test with effective_attributes=False (should not include parameter)
            hosts_false = client.list_hosts(effective_attributes=False)
            assert len(hosts_false) == 1

            # Verify no effective_attributes parameter was sent
            request_false = m.request_history[0]
            assert "effective_attributes" not in request_false.url

            # Reset and test with effective_attributes=True
            m.reset_mock()
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            hosts_true = client.list_hosts(effective_attributes=True)
            assert len(hosts_true) == 1

            # Verify effective_attributes=true parameter was sent
            request_true = m.request_history[0]
            assert "effective_attributes=true" in request_true.url

    def test_api_client_get_host_parameter_flow(self, test_config):
        """Test that CheckmkClient get_host correctly handles effective_attributes parameter."""
        client = CheckmkClient(test_config.checkmk)

        with requests_mock.Mocker() as m:
            # Mock response with effective_attributes
            mock_response = {
                "id": "test-host",
                "extensions": {
                    "folder": "/test",
                    "attributes": {"ipaddress": "192.168.1.100"},
                    "effective_attributes": {
                        "ipaddress": "192.168.1.100",
                        "inherited_setting": "from_parent",
                    },
                },
            }

            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/objects/host_config/test-host",
                json=mock_response,
                status_code=200,
            )

            # Test with effective_attributes=False
            host_false = client.get_host("test-host", effective_attributes=False)
            assert host_false["id"] == "test-host"

            # Verify no effective_attributes parameter was sent
            request_false = m.request_history[0]
            assert "effective_attributes" not in request_false.url

            # Reset and test with effective_attributes=True
            m.reset_mock()
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/objects/host_config/test-host",
                json=mock_response,
                status_code=200,
            )

            host_true = client.get_host("test-host", effective_attributes=True)
            assert host_true["id"] == "test-host"

            # Verify effective_attributes=true parameter was sent
            request_true = m.request_history[0]
            assert "effective_attributes=true" in request_true.url

    @pytest.mark.asyncio
    async def test_async_api_client_parameter_flow(self, test_config):
        """Test that AsyncCheckmkClient correctly handles effective_attributes parameter."""
        # Mock the synchronous client that the async client wraps
        mock_sync_client = Mock()
        mock_sync_client.list_hosts.return_value = [
            {"id": "test-host", "extensions": {"folder": "/test"}}
        ]

        async_client = AsyncCheckmkClient(test_config.checkmk)
        async_client.sync_client = mock_sync_client

        # Test with effective_attributes=False
        hosts_false = await async_client.list_hosts(effective_attributes=False)
        assert len(hosts_false) == 1
        mock_sync_client.list_hosts.assert_called_with(effective_attributes=False)

        # Test with effective_attributes=True
        hosts_true = await async_client.list_hosts(effective_attributes=True)
        assert len(hosts_true) == 1
        mock_sync_client.list_hosts.assert_called_with(effective_attributes=True)

    @pytest.mark.asyncio
    async def test_host_service_parameter_flow(self, test_config):
        """Test that HostService correctly passes effective_attributes to the API client."""
        # Mock the async API client
        mock_async_client = AsyncMock()
        mock_async_client.list_hosts.return_value = [
            {"id": "test-host", "extensions": {"folder": "/test"}}
        ]

        host_service = HostService(mock_async_client, test_config)

        # Test with effective_attributes=False
        result_false = await host_service.list_hosts(effective_attributes=False)
        assert result_false.success
        mock_async_client.list_hosts.assert_called_with(effective_attributes=False)

        # Test with effective_attributes=True
        result_true = await host_service.list_hosts(effective_attributes=True)
        assert result_true.success
        mock_async_client.list_hosts.assert_called_with(effective_attributes=True)

    @pytest.mark.asyncio
    async def test_host_service_get_host_parameter_flow(self, test_config):
        """Test that HostService get_host correctly passes effective_attributes to the API client."""
        # Mock the async API client
        mock_async_client = AsyncMock()
        mock_async_client.get_host.return_value = {
            "id": "test-host",
            "extensions": {"folder": "/test"},
        }

        host_service = HostService(mock_async_client, test_config)

        # Test with effective_attributes=False
        result_false = await host_service.get_host(
            "test-host", effective_attributes=False
        )
        assert result_false.success
        mock_async_client.get_host.assert_called_with(
            "test-host", effective_attributes=False
        )

        # Test with effective_attributes=True
        result_true = await host_service.get_host(
            "test-host", effective_attributes=True
        )
        assert result_true.success
        mock_async_client.get_host.assert_called_with(
            "test-host", effective_attributes=True
        )


class TestEffectiveAttributesRealWorldScenarios:
    """Test real-world scenarios demonstrating effective_attributes functionality."""

    def test_monitoring_inheritance_scenario(self, test_config):
        """
        Test scenario: Administrator wants to see complete monitoring configuration
        including inherited folder settings and computed parameters.
        """
        client = CheckmkClient(test_config.checkmk)

        with requests_mock.Mocker() as m:
            # Mock response showing rich effective_attributes
            mock_response = {
                "value": [
                    {
                        "id": "prod-web-01",
                        "extensions": {
                            "folder": "/production/web",
                            "attributes": {
                                "ipaddress": "10.1.1.10",
                                "alias": "Production Web Server 01",
                            },
                            "effective_attributes": {
                                "ipaddress": "10.1.1.10",
                                "alias": "Production Web Server 01",
                                # Inherited from parent folders
                                "notification_period": "24x7",
                                "contact_groups": ["web-admins", "production-team"],
                                "max_check_attempts": "3",
                                "notification_interval": "60",
                                # Computed by Checkmk
                                "effective_check_interval": "1min",
                                "service_discovery_mode": "automatic",
                                "active_checks_enabled": "yes",
                            },
                        },
                    }
                ]
            }

            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            # Administrator requests full configuration view
            hosts = client.list_hosts(effective_attributes=True)

            # Verify complete configuration is available
            assert len(hosts) == 1
            host = hosts[0]

            # Basic host info
            assert host["id"] == "prod-web-01"
            assert host["extensions"]["attributes"]["ipaddress"] == "10.1.1.10"

            # Effective attributes provide the complete picture
            effective = host["extensions"]["effective_attributes"]

            # Inherited settings
            assert effective["notification_period"] == "24x7"
            assert effective["contact_groups"] == ["web-admins", "production-team"]
            assert effective["max_check_attempts"] == "3"

            # Computed settings
            assert effective["effective_check_interval"] == "1min"
            assert effective["service_discovery_mode"] == "automatic"

            # Verify the API was called with effective_attributes
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url

    def test_troubleshooting_scenario(self, test_config):
        """
        Test scenario: Troubleshooting unexpected monitoring behavior
        by examining complete effective configuration.
        """
        client = CheckmkClient(test_config.checkmk)

        with requests_mock.Mocker() as m:
            # Mock response for specific host troubleshooting
            mock_response = {
                "id": "problematic-host",
                "extensions": {
                    "folder": "/critical/database",
                    "attributes": {
                        "ipaddress": "10.2.1.100",
                        "alias": "Database Server with Issues",
                        "tag_criticality": "critical",
                    },
                    "effective_attributes": {
                        "ipaddress": "10.2.1.100",
                        "alias": "Database Server with Issues",
                        "tag_criticality": "critical",
                        # Configuration causing the issue
                        "max_check_attempts": "1",  # Too aggressive
                        "check_interval": "10s",  # Too frequent
                        "notification_escalation": "immediate",
                        "contact_groups": ["db-team", "critical-ops", "management"],
                        # Effective computed values show the impact
                        "notifications_per_hour": "360",  # Way too many!
                        "cpu_load_from_checks": "high",
                        "active_service_checks": "156",
                    },
                },
            }

            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/objects/host_config/problematic-host",
                json=mock_response,
                status_code=200,
            )

            # Troubleshooting: Get complete effective configuration
            host = client.get_host("problematic-host", effective_attributes=True)

            # Identify the configuration issues
            assert host["id"] == "problematic-host"
            effective = host["extensions"]["effective_attributes"]

            # Root cause analysis - aggressive monitoring settings
            assert effective["max_check_attempts"] == "1"  # Should be higher
            assert effective["check_interval"] == "10s"  # Too frequent
            assert effective["notification_escalation"] == "immediate"

            # Impact analysis - computed values show the problem
            assert effective["notifications_per_hour"] == "360"  # Notification storm
            assert effective["cpu_load_from_checks"] == "high"  # Performance impact

            # Verify the API was called with effective_attributes
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url


class TestBackwardCompatibility:
    """Test that effective_attributes maintains backward compatibility."""

    def test_default_behavior_unchanged(self, test_config):
        """Test that default API behavior is unchanged."""
        client = CheckmkClient(test_config.checkmk)

        with requests_mock.Mocker() as m:
            mock_response = {
                "value": [
                    {
                        "id": "legacy-host",
                        "extensions": {
                            "folder": "/legacy",
                            "attributes": {"ipaddress": "192.168.1.100"},
                        },
                    }
                ]
            }

            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            # Test that default behavior hasn't changed
            hosts = client.list_hosts()  # No effective_attributes parameter

            assert len(hosts) == 1
            assert hosts[0]["id"] == "legacy-host"

            # Verify no effective_attributes parameter was sent (backward compatibility)
            request = m.request_history[0]
            assert "effective_attributes" not in request.url

    def test_explicit_false_parameter(self, test_config):
        """Test that explicitly setting effective_attributes=False works correctly."""
        client = CheckmkClient(test_config.checkmk)

        with requests_mock.Mocker() as m:
            mock_response = {
                "value": [
                    {
                        "id": "test-host",
                        "extensions": {
                            "folder": "/test",
                            "attributes": {"ipaddress": "192.168.1.100"},
                        },
                    }
                ]
            }

            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            # Test explicit False parameter
            hosts = client.list_hosts(effective_attributes=False)

            assert len(hosts) == 1
            assert hosts[0]["id"] == "test-host"

            # Verify no effective_attributes parameter was sent when False
            request = m.request_history[0]
            assert "effective_attributes" not in request.url


class TestErrorHandling:
    """Test error handling with effective_attributes parameter."""

    def test_permission_denied_error(self, test_config):
        """Test handling of permission denied errors when requesting effective_attributes."""
        client = CheckmkClient(test_config.checkmk)

        with requests_mock.Mocker() as m:
            # Mock permission denied response
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json={
                    "title": "Forbidden",
                    "detail": "Permission denied for effective_attributes parameter",
                },
                status_code=403,
            )

            # Test that permission errors are properly handled
            with pytest.raises(Exception) as exc_info:
                client.list_hosts(effective_attributes=True)

            # Verify error information is preserved
            assert "403" in str(exc_info.value) or "Forbidden" in str(exc_info.value)

            # Verify the request included the parameter that caused the error
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url

    def test_malformed_effective_attributes_response(self, test_config):
        """Test handling of malformed effective_attributes in response."""
        client = CheckmkClient(test_config.checkmk)

        with requests_mock.Mocker() as m:
            # Mock response with malformed effective_attributes
            mock_response = {
                "value": [
                    {
                        "id": "test-host",
                        "extensions": {
                            "folder": "/test",
                            "attributes": {"ipaddress": "192.168.1.100"},
                            "effective_attributes": "invalid_structure",  # Should be dict, not string
                        },
                    }
                ]
            }

            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_response,
                status_code=200,
            )

            # Should still work - the client should handle unexpected data gracefully
            hosts = client.list_hosts(effective_attributes=True)

            assert len(hosts) == 1
            assert hosts[0]["id"] == "test-host"
            # The malformed effective_attributes should be preserved as-is
            assert hosts[0]["extensions"]["effective_attributes"] == "invalid_structure"
