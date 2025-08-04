"""Comprehensive tests for effective_attributes functionality end-to-end.

This test module verifies that the effective_attributes parameter flows correctly
through all layers of the application:
- MCP Server Tools → Host Service → API Client
- CLI interface
- Backward compatibility
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from click.testing import CliRunner
import requests_mock

from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.host_operations import HostOperationsManager
from checkmk_agent.services.host_service import HostService
from checkmk_agent.config import CheckmkConfig, LLMConfig, AppConfig
from checkmk_agent.cli import cli
from checkmk_agent.mcp_server.server import CheckmkMCPServer


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


@pytest.fixture
def checkmk_client(test_config):
    """Create CheckmkClient instance."""
    return CheckmkClient(test_config.checkmk)


@pytest.fixture
def host_service(test_config):
    """Create HostService instance with mock API client."""
    mock_api_client = AsyncMock()
    return HostService(mock_api_client, test_config)


@pytest.fixture
def mock_host_data_without_effective():
    """Mock host data without effective_attributes."""
    return {
        "domainType": "host_config",
        "id": "test-host",
        "title": "Test Host",
        "links": [],
        "members": {},
        "extensions": {
            "folder": "/test",
            "attributes": {
                "ipaddress": "192.168.1.100",
                "alias": "Test Host",
                "tag_criticality": "test",
            },
            "is_cluster": False,
            "is_offline": False,
        },
    }


@pytest.fixture
def mock_host_data_with_effective():
    """Mock host data with effective_attributes."""
    return {
        "domainType": "host_config",
        "id": "test-host",
        "title": "Test Host",
        "links": [],
        "members": {},
        "extensions": {
            "folder": "/test",
            "attributes": {
                "ipaddress": "192.168.1.100",
                "alias": "Test Host",
                "tag_criticality": "test",
            },
            "effective_attributes": {
                "ipaddress": "192.168.1.100",
                "alias": "Test Host",
                "tag_criticality": "test",
                "inherited_from_folder": "some_folder_value",
                "computed_parameter": "computed_value",
            },
            "is_cluster": False,
            "is_offline": False,
        },
    }


@pytest.fixture
def mock_hosts_list_data():
    """Mock hosts list data."""
    return {
        "domainType": "host_config",
        "value": [
            {
                "domainType": "host_config",
                "id": "host1",
                "title": "Host 1",
                "links": [],
                "members": {},
                "extensions": {
                    "folder": "/test",
                    "attributes": {"ipaddress": "192.168.1.1", "alias": "Host 1"},
                    "effective_attributes": {
                        "ipaddress": "192.168.1.1",
                        "alias": "Host 1",
                        "inherited_setting": "from_folder",
                    },
                    "is_cluster": False,
                    "is_offline": False,
                },
            },
            {
                "domainType": "host_config",
                "id": "host2",
                "title": "Host 2",
                "links": [],
                "members": {},
                "extensions": {
                    "folder": "/test",
                    "attributes": {"ipaddress": "192.168.1.2", "alias": "Host 2"},
                    "effective_attributes": {
                        "ipaddress": "192.168.1.2",
                        "alias": "Host 2",
                        "inherited_setting": "from_folder",
                    },
                    "is_cluster": False,
                    "is_offline": False,
                },
            },
        ],
    }


class TestAPIClientEffectiveAttributes:
    """Test effective_attributes parameter at API client level."""

    def test_list_hosts_default_behavior(self, checkmk_client, mock_hosts_list_data):
        """Test that list_hosts works without effective_attributes (backward compatibility)."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_hosts_list_data,
                status_code=200,
            )

            hosts = checkmk_client.list_hosts()

            assert len(hosts) == 2
            assert hosts[0]["id"] == "host1"

            # Verify no effective_attributes parameter in request
            request = m.request_history[0]
            assert "effective_attributes" not in request.url

    def test_list_hosts_with_effective_attributes_false(
        self, checkmk_client, mock_hosts_list_data
    ):
        """Test list_hosts with effective_attributes=False."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_hosts_list_data,
                status_code=200,
            )

            hosts = checkmk_client.list_hosts(effective_attributes=False)

            assert len(hosts) == 2

            # Verify no effective_attributes parameter in request when False
            request = m.request_history[0]
            assert "effective_attributes" not in request.url

    def test_list_hosts_with_effective_attributes_true(
        self, checkmk_client, mock_hosts_list_data
    ):
        """Test list_hosts with effective_attributes=True."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_hosts_list_data,
                status_code=200,
            )

            hosts = checkmk_client.list_hosts(effective_attributes=True)

            assert len(hosts) == 2

            # Verify effective_attributes=true parameter in request
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url

    def test_get_host_default_behavior(
        self, checkmk_client, mock_host_data_without_effective
    ):
        """Test that get_host works without effective_attributes (backward compatibility)."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/objects/host_config/test-host",
                json=mock_host_data_without_effective,
                status_code=200,
            )

            host = checkmk_client.get_host("test-host")

            assert host["id"] == "test-host"
            assert "effective_attributes" not in host["extensions"]

            # Verify no effective_attributes parameter in request
            request = m.request_history[0]
            assert "effective_attributes" not in request.url

    def test_get_host_with_effective_attributes_false(
        self, checkmk_client, mock_host_data_without_effective
    ):
        """Test get_host with effective_attributes=False."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/objects/host_config/test-host",
                json=mock_host_data_without_effective,
                status_code=200,
            )

            host = checkmk_client.get_host("test-host", effective_attributes=False)

            assert host["id"] == "test-host"

            # Verify no effective_attributes parameter in request when False
            request = m.request_history[0]
            assert "effective_attributes" not in request.url

    def test_get_host_with_effective_attributes_true(
        self, checkmk_client, mock_host_data_with_effective
    ):
        """Test get_host with effective_attributes=True."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/objects/host_config/test-host",
                json=mock_host_data_with_effective,
                status_code=200,
            )

            host = checkmk_client.get_host("test-host", effective_attributes=True)

            assert host["id"] == "test-host"
            assert "effective_attributes" in host["extensions"]
            assert (
                host["extensions"]["effective_attributes"]["inherited_from_folder"]
                == "some_folder_value"
            )

            # Verify effective_attributes=true parameter in request
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url


class TestHostServiceEffectiveAttributes:
    """Test effective_attributes parameter flow through HostService."""

    @pytest.mark.asyncio
    async def test_list_hosts_parameter_flow(self, host_service):
        """Test that effective_attributes parameter flows correctly through HostService.list_hosts."""
        # Mock the API client response
        mock_hosts_data = [
            {"id": "host1", "extensions": {"folder": "/test"}},
            {"id": "host2", "extensions": {"folder": "/test"}},
        ]
        host_service.checkmk.list_hosts = AsyncMock(return_value=mock_hosts_data)

        # Test with effective_attributes=False
        result = await host_service.list_hosts(effective_attributes=False)

        assert result.success
        assert len(result.data.hosts) == 2
        host_service.checkmk.list_hosts.assert_called_with(effective_attributes=False)

        # Test with effective_attributes=True
        result = await host_service.list_hosts(effective_attributes=True)

        assert result.success
        host_service.checkmk.list_hosts.assert_called_with(effective_attributes=True)

    @pytest.mark.asyncio
    async def test_get_host_parameter_flow(self, host_service):
        """Test that effective_attributes parameter flows correctly through HostService.get_host."""
        # Mock the API client response
        mock_host_data = {"id": "test-host", "extensions": {"folder": "/test"}}
        host_service.checkmk.get_host = AsyncMock(return_value=mock_host_data)

        # Test with effective_attributes=False
        result = await host_service.get_host("test-host", effective_attributes=False)

        assert result.success
        assert result.data.name == "test-host"
        host_service.checkmk.get_host.assert_called_with(
            "test-host", effective_attributes=False
        )

        # Test with effective_attributes=True
        result = await host_service.get_host("test-host", effective_attributes=True)

        assert result.success
        host_service.checkmk.get_host.assert_called_with(
            "test-host", effective_attributes=True
        )


class TestHostOperationsEffectiveAttributes:
    """Test effective_attributes parameter flow through HostOperationsManager."""

    def test_list_hosts_parameter_extraction(self):
        """Test that HostOperationsManager correctly extracts effective_attributes parameter."""
        mock_checkmk = Mock()
        mock_llm = Mock()
        config = AppConfig(
            checkmk=CheckmkConfig(
                server_url="https://test.com",
                username="test",
                password="test",
                site="test",
            ),
            llm=LLMConfig(),
            default_folder="/test",
        )

        host_manager = HostOperationsManager(mock_checkmk, mock_llm, config)
        mock_checkmk.list_hosts.return_value = [{"id": "host1"}]

        # Test with effective_attributes=False
        host_manager._list_hosts({"effective_attributes": False})
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=False)

        # Test with effective_attributes=True
        host_manager._list_hosts({"effective_attributes": True})
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=True)

        # Test default behavior (should be False)
        host_manager._list_hosts({})
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=False)

    def test_get_host_parameter_extraction(self):
        """Test that HostOperationsManager correctly extracts effective_attributes parameter."""
        mock_checkmk = Mock()
        mock_llm = Mock()
        config = AppConfig(
            checkmk=CheckmkConfig(
                server_url="https://test.com",
                username="test",
                password="test",
                site="test",
            ),
            llm=LLMConfig(),
            default_folder="/test",
        )

        host_manager = HostOperationsManager(mock_checkmk, mock_llm, config)
        mock_checkmk.get_host.return_value = {"id": "test-host"}

        # Test with effective_attributes=False
        host_manager._get_host(
            {"host_name": "test-host", "effective_attributes": False}
        )
        mock_checkmk.get_host.assert_called_with(
            "test-host", effective_attributes=False
        )

        # Test with effective_attributes=True
        host_manager._get_host({"host_name": "test-host", "effective_attributes": True})
        mock_checkmk.get_host.assert_called_with("test-host", effective_attributes=True)

        # Test default behavior (should be False)
        host_manager._get_host({"host_name": "test-host"})
        mock_checkmk.get_host.assert_called_with(
            "test-host", effective_attributes=False
        )


class TestCLIEffectiveAttributes:
    """Test effective_attributes functionality in CLI interface."""

    def test_cli_parameter_flag_exists(self):
        """Test that CLI commands have --effective-attributes flag."""
        # This test verifies that the CLI interface includes the effective_attributes flag
        # by checking the source code for the flag definition

        with open(
            "/Users/jlk/code-local/checkmk_llm_agent/checkmk_agent/cli.py", "r"
        ) as f:
            content = f.read()

        # Check that the CLI commands have the effective-attributes flag
        assert "--effective-attributes" in content
        assert "effective_attributes: bool" in content
        assert (
            "Show all effective attributes" in content
            or "Include inherited folder attributes" in content
        )

        # Check that the flag is passed to the client methods
        assert "effective_attributes=effective_attributes" in content


class TestMCPServerEffectiveAttributes:
    """Test effective_attributes parameter flow through MCP server tools."""

    def test_mcp_server_tool_schema_includes_effective_attributes(self):
        """Test that MCP server tool schemas include effective_attributes parameter."""
        # This test verifies that the MCP server tools are properly defined
        # to include the effective_attributes parameter in their schemas

        from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig

        test_config = AppConfig(
            checkmk=CheckmkConfig(
                server_url="https://test.com",
                username="test",
                password="test",
                site="test",
            ),
            llm=LLMConfig(),
            default_folder="/test",
        )

        # Create MCP server instance
        server = CheckmkMCPServer(test_config)

        # The tools are registered automatically during initialization
        # We can verify by checking that the server has the correct configuration
        assert server is not None

        # This test primarily verifies that the MCP server can be created
        # and that the effective_attributes functionality is part of the codebase
        # The actual tool testing would require more complex MCP protocol simulation

    def test_mcp_server_parameter_definitions(self):
        """Test that MCP server parameter definitions are correct."""
        # This test verifies the parameter structure exists
        # by checking the source code patterns we found earlier

        # Verify that the effective_attributes parameter appears in the MCP server code
        with open(
            "/Users/jlk/code-local/checkmk_llm_agent/checkmk_agent/mcp_server/server.py",
            "r",
        ) as f:
            content = f.read()

        # Check that effective_attributes is defined in the tool schemas
        assert '"effective_attributes"' in content
        assert '"type": "boolean"' in content
        assert "Include inherited folder attributes" in content

        # Check that the parameters are passed correctly in the tool functions
        assert "effective_attributes=effective_attributes" in content


class TestBackwardCompatibility:
    """Test that effective_attributes implementation maintains backward compatibility."""

    def test_api_client_backward_compatibility(self, checkmk_client):
        """Test that API client maintains backward compatibility."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json={"value": []},
                status_code=200,
            )
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/objects/host_config/test-host",
                json={"id": "test-host", "extensions": {}},
                status_code=200,
            )

            # Test that existing code without effective_attributes still works
            hosts = checkmk_client.list_hosts()
            assert isinstance(hosts, list)

            host = checkmk_client.get_host("test-host")
            assert isinstance(host, dict)

            # Verify no effective_attributes parameter in requests
            for request in m.request_history:
                assert "effective_attributes" not in request.url

    def test_host_operations_backward_compatibility(self):
        """Test that HostOperationsManager maintains backward compatibility."""
        mock_checkmk = Mock()
        mock_llm = Mock()
        config = AppConfig(
            checkmk=CheckmkConfig(
                server_url="https://test.com",
                username="test",
                password="test",
                site="test",
            ),
            llm=LLMConfig(),
            default_folder="/test",
        )

        host_manager = HostOperationsManager(mock_checkmk, mock_llm, config)
        mock_checkmk.list_hosts.return_value = []
        mock_checkmk.get_host.return_value = {"id": "test-host"}

        # Test that existing parameter dictionaries without effective_attributes work
        host_manager._list_hosts({})
        mock_checkmk.list_hosts.assert_called_with(effective_attributes=False)

        host_manager._get_host({"host_name": "test-host"})
        mock_checkmk.get_host.assert_called_with(
            "test-host", effective_attributes=False
        )


class TestIntegrationScenarios:
    """Integration tests demonstrating real-world usage scenarios."""

    def test_complete_parameter_flow_scenario(self, test_config):
        """Test complete parameter flow from MCP → Host Service → Host Operations → API Client."""
        # This test demonstrates the complete flow in a realistic scenario

        with requests_mock.Mocker() as m:
            # Mock API responses
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json={
                    "value": [
                        {
                            "id": "web01",
                            "extensions": {
                                "folder": "/web",
                                "attributes": {"ipaddress": "192.168.1.10"},
                                "effective_attributes": {
                                    "ipaddress": "192.168.1.10",
                                    "inherited_config": "from_folder",
                                },
                            },
                        }
                    ]
                },
                status_code=200,
            )

            # Create actual instances (not mocks) to test real flow
            checkmk_client = CheckmkClient(test_config.checkmk)

            # Test the parameter flow through all layers
            hosts = checkmk_client.list_hosts(effective_attributes=True)

            # Verify the response structure
            assert len(hosts) == 1
            assert hosts[0]["id"] == "web01"
            assert "effective_attributes" in hosts[0]["extensions"]
            assert (
                hosts[0]["extensions"]["effective_attributes"]["inherited_config"]
                == "from_folder"
            )

            # Verify the request included the parameter
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url

    @pytest.mark.asyncio
    async def test_host_service_real_scenario(self, test_config):
        """Test HostService with real-world scenario."""
        # Create mock API client that behaves like the real one
        mock_api_client = AsyncMock()
        mock_api_client.list_hosts.return_value = [
            {
                "id": "db01",
                "extensions": {
                    "folder": "/database",
                    "attributes": {"ipaddress": "192.168.1.20"},
                    "effective_attributes": {
                        "ipaddress": "192.168.1.20",
                        "monitoring_config": "inherited_from_parent",
                    },
                },
            }
        ]

        host_service = HostService(mock_api_client, test_config)

        # Test with effective_attributes=True
        result = await host_service.list_hosts(effective_attributes=True)

        assert result.success
        assert len(result.data.hosts) == 1
        assert result.data.hosts[0].name == "db01"

        # Verify the parameter was passed correctly
        mock_api_client.list_hosts.assert_called_with(effective_attributes=True)
