"""Integration tests with mock Checkmk server."""

import pytest
import json
from unittest.mock import Mock, patch
import requests_mock

from checkmk_agent.api_client import CheckmkClient, CheckmkAPIError
from checkmk_agent.llm_client import OpenAIClient, ParsedCommand, HostOperation
from checkmk_agent.host_operations import HostOperationsManager
from checkmk_agent.config import CheckmkConfig, LLMConfig, AppConfig


@pytest.fixture
def checkmk_config():
    """Create test Checkmk configuration."""
    return CheckmkConfig(
        server_url="https://test-checkmk.example.com",
        username="automation",
        password="secret",
        site="mysite",
        max_retries=2,
        request_timeout=10,
    )


@pytest.fixture
def llm_config():
    """Create test LLM configuration."""
    return LLMConfig(openai_api_key="test-openai-key", default_model="gpt-3.5-turbo")


@pytest.fixture
def app_config(checkmk_config, llm_config):
    """Create test application configuration."""
    return AppConfig(
        checkmk=checkmk_config,
        llm=llm_config,
        default_folder="/automation",
        log_level="DEBUG",
    )


@pytest.fixture
def checkmk_client(checkmk_config):
    """Create CheckmkClient instance."""
    return CheckmkClient(checkmk_config)


class TestCheckmkAPIIntegration:
    """Integration tests for Checkmk API operations."""

    def test_list_hosts_integration(self, checkmk_client):
        """Test complete host listing workflow."""
        mock_hosts_response = {
            "domainType": "host_config",
            "value": [
                {
                    "domainType": "host_config",
                    "id": "web01",
                    "title": "Web Server 1",
                    "links": [],
                    "members": {},
                    "extensions": {
                        "folder": "/web",
                        "attributes": {
                            "ipaddress": "192.168.1.10",
                            "alias": "Primary Web Server",
                        },
                        "is_cluster": False,
                        "is_offline": False,
                    },
                },
                {
                    "domainType": "host_config",
                    "id": "db01",
                    "title": "Database Server 1",
                    "links": [],
                    "members": {},
                    "extensions": {
                        "folder": "/database",
                        "attributes": {
                            "ipaddress": "192.168.1.20",
                            "alias": "Primary Database",
                        },
                        "is_cluster": False,
                        "is_offline": False,
                    },
                },
            ],
        }

        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_hosts_response,
                status_code=200,
            )

            hosts = checkmk_client.list_hosts()

            assert len(hosts) == 2
            assert hosts[0]["id"] == "web01"
            assert hosts[0]["extensions"]["folder"] == "/web"
            assert hosts[0]["extensions"]["attributes"]["ipaddress"] == "192.168.1.10"
            assert hosts[1]["id"] == "db01"
            assert hosts[1]["extensions"]["folder"] == "/database"

    def test_create_host_integration(self, checkmk_client):
        """Test complete host creation workflow."""
        mock_create_response = {
            "domainType": "host_config",
            "id": "new-server",
            "title": "New Server",
            "links": [],
            "members": {},
            "extensions": {
                "folder": "/test",
                "attributes": {"ipaddress": "192.168.1.100", "alias": "Test Server"},
                "is_cluster": False,
                "is_offline": False,
            },
        }

        with requests_mock.Mocker() as m:
            m.post(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=mock_create_response,
                status_code=200,
            )

            result = checkmk_client.create_host(
                folder="/test",
                host_name="new-server",
                attributes={"ipaddress": "192.168.1.100", "alias": "Test Server"},
            )

            assert result["id"] == "new-server"
            assert result["extensions"]["attributes"]["ipaddress"] == "192.168.1.100"

            # Verify request was made correctly
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert request.method == "POST"

            request_data = json.loads(request.text)
            assert request_data["folder"] == "/test"
            assert request_data["host_name"] == "new-server"
            assert request_data["attributes"]["ipaddress"] == "192.168.1.100"

    def test_get_host_integration(self, checkmk_client):
        """Test complete get host workflow."""
        mock_host_response = {
            "domainType": "host_config",
            "id": "web01",
            "title": "Web Server 1",
            "links": [],
            "members": {},
            "extensions": {
                "folder": "/web",
                "attributes": {
                    "ipaddress": "192.168.1.10",
                    "alias": "Primary Web Server",
                    "tag_criticality": "prod",
                },
                "effective_attributes": {
                    "ipaddress": "192.168.1.10",
                    "alias": "Primary Web Server",
                    "tag_criticality": "prod",
                    "inherited_setting": "folder_value",
                },
                "is_cluster": False,
                "is_offline": False,
            },
        }

        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/objects/host_config/web01",
                json=mock_host_response,
                status_code=200,
            )

            host = checkmk_client.get_host("web01", effective_attributes=True)

            assert host["id"] == "web01"
            assert host["extensions"]["attributes"]["ipaddress"] == "192.168.1.10"
            assert (
                host["extensions"]["effective_attributes"]["inherited_setting"]
                == "folder_value"
            )

            # Verify request parameters
            request = m.request_history[0]
            assert "effective_attributes=true" in request.url

    def test_delete_host_integration(self, checkmk_client):
        """Test complete host deletion workflow."""
        with requests_mock.Mocker() as m:
            m.delete(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/objects/host_config/old-server",
                status_code=204,
            )

            # Should not raise an exception
            checkmk_client.delete_host("old-server")

            # Verify request was made
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert request.method == "DELETE"

    def test_api_error_handling_integration(self, checkmk_client):
        """Test API error handling in integration scenario."""
        error_response = {
            "title": "Conflict",
            "status": 409,
            "detail": "Host already exists",
        }

        with requests_mock.Mocker() as m:
            m.post(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json=error_response,
                status_code=409,
            )

            with pytest.raises(CheckmkAPIError) as exc_info:
                checkmk_client.create_host(
                    folder="/test", host_name="existing-host", attributes={}
                )

            assert exc_info.value.status_code == 409
            assert "Host already exists" in str(exc_info.value)

    def test_authentication_integration(self, checkmk_client):
        """Test authentication header in integration scenario."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json={"value": []},
                status_code=200,
            )

            checkmk_client.list_hosts()

            # Verify authentication header
            request = m.request_history[0]
            assert "Authorization" in request.headers
            assert request.headers["Authorization"] == "Bearer automation secret"

    def test_bulk_operations_integration(self, checkmk_client):
        """Test bulk operations integration."""
        mock_bulk_response = {
            "results": [
                {"id": "bulk-host-1", "status": "created"},
                {"id": "bulk-host-2", "status": "created"},
            ]
        }

        with requests_mock.Mocker() as m:
            # Bulk create
            m.post(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/actions/bulk-create/invoke",
                json=mock_bulk_response,
                status_code=200,
            )

            hosts_to_create = [
                {"folder": "/test", "host_name": "bulk-host-1"},
                {
                    "folder": "/test",
                    "host_name": "bulk-host-2",
                    "attributes": {"ipaddress": "192.168.1.50"},
                },
            ]

            result = checkmk_client.bulk_create_hosts(hosts_to_create)

            assert "results" in result
            assert len(result["results"]) == 2

            # Verify request structure
            request = m.request_history[0]
            request_data = json.loads(request.text)
            assert len(request_data["entries"]) == 2
            assert request_data["entries"][0]["host_name"] == "bulk-host-1"
            assert (
                request_data["entries"][1]["attributes"]["ipaddress"] == "192.168.1.50"
            )


class TestLLMIntegration:
    """Integration tests for LLM operations."""

    @patch("checkmk_agent.llm_client.openai.OpenAI")
    def test_command_parsing_integration(self, mock_openai, llm_config):
        """Test complete command parsing workflow."""
        # Setup mock OpenAI response
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps(
            {
                "operation": "create",
                "parameters": {
                    "host_name": "web-server-03",
                    "folder": "/web",
                    "attributes": {"ipaddress": "192.168.1.30"},
                },
                "confidence": 0.95,
            }
        )
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        with patch("checkmk_agent.llm_client.OPENAI_AVAILABLE", True):
            llm_client = OpenAIClient(llm_config)

            result = llm_client.parse_command(
                "create web server web-server-03 in /web folder with IP 192.168.1.30"
            )

            assert result.operation == HostOperation.CREATE
            assert result.parameters["host_name"] == "web-server-03"
            assert result.parameters["folder"] == "/web"
            assert result.parameters["attributes"]["ipaddress"] == "192.168.1.30"
            assert result.confidence == 0.95

            # Verify OpenAI API was called correctly
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["model"] == "gpt-3.5-turbo"
            assert call_args[1]["temperature"] == 0.1

    @patch("checkmk_agent.llm_client.openai.OpenAI")
    def test_response_formatting_integration(self, mock_openai, llm_config):
        """Test complete response formatting workflow."""
        mock_openai.return_value = Mock()

        with patch("checkmk_agent.llm_client.OPENAI_AVAILABLE", True):
            llm_client = OpenAIClient(llm_config)

            # Test formatting host list response
            hosts_data = [
                {
                    "id": "web01",
                    "extensions": {
                        "folder": "/web",
                        "attributes": {"ipaddress": "192.168.1.10"},
                    },
                },
                {
                    "id": "web02",
                    "extensions": {
                        "folder": "/web",
                        "attributes": {"ipaddress": "192.168.1.11"},
                    },
                },
            ]

            result = llm_client.format_response(
                HostOperation.LIST, hosts_data, success=True
            )

            assert "Found 2 hosts:" in result
            assert "web01 (folder: /web)" in result
            assert "web02 (folder: /web)" in result


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @patch("checkmk_agent.llm_client.openai.OpenAI")
    def test_complete_host_creation_workflow(self, mock_openai, app_config):
        """Test complete workflow from natural language to host creation."""
        # Setup LLM mock
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps(
            {
                "operation": "create",
                "parameters": {
                    "host_name": "integration-test-host",
                    "folder": "/test",
                    "ipaddress": "192.168.99.100",
                },
                "confidence": 0.9,
            }
        )
        mock_response.choices = [mock_choice]

        mock_openai_client = Mock()
        mock_openai_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_openai_client

        # Setup Checkmk API mock
        mock_create_response = {
            "id": "integration-test-host",
            "extensions": {
                "folder": "/test",
                "attributes": {"ipaddress": "192.168.99.100"},
            },
        }

        with patch("checkmk_agent.llm_client.OPENAI_AVAILABLE", True):
            with requests_mock.Mocker() as m:
                m.post(
                    "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                    json=mock_create_response,
                    status_code=200,
                )

                # Create components
                checkmk_client = CheckmkClient(app_config.checkmk)
                llm_client = OpenAIClient(app_config.llm)
                host_manager = HostOperationsManager(
                    checkmk_client, llm_client, app_config
                )

                # Execute end-to-end workflow
                result = host_manager.process_command(
                    "create a new host called integration-test-host in /test folder with IP 192.168.99.100"
                )

                # Verify the complete workflow worked
                assert "Successfully created host: integration-test-host" in result

                # Verify API call was made correctly
                assert len(m.request_history) == 1
                request = m.request_history[0]
                request_data = json.loads(request.text)
                assert request_data["host_name"] == "integration-test-host"
                assert request_data["folder"] == "/test"
                assert request_data["attributes"]["ipaddress"] == "192.168.99.100"

    @patch("checkmk_agent.llm_client.openai.OpenAI")
    def test_complete_host_listing_workflow(self, mock_openai, app_config):
        """Test complete workflow from natural language to host listing."""
        # Setup LLM mock for parsing
        mock_parse_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = json.dumps(
            {
                "operation": "list",
                "parameters": {"search_term": "web"},
                "confidence": 0.85,
            }
        )
        mock_parse_response.choices = [mock_choice]

        mock_openai_client = Mock()
        mock_openai_client.chat.completions.create.return_value = mock_parse_response
        mock_openai.return_value = mock_openai_client

        # Setup Checkmk API mock
        mock_hosts_response = {
            "value": [
                {
                    "id": "web01",
                    "extensions": {
                        "folder": "/web",
                        "attributes": {
                            "ipaddress": "192.168.1.10",
                            "alias": "Web Server 1",
                        },
                    },
                },
                {
                    "id": "web02",
                    "extensions": {
                        "folder": "/web",
                        "attributes": {
                            "ipaddress": "192.168.1.11",
                            "alias": "Web Server 2",
                        },
                    },
                },
                {
                    "id": "db01",
                    "extensions": {
                        "folder": "/database",
                        "attributes": {
                            "ipaddress": "192.168.1.20",
                            "alias": "Database Server",
                        },
                    },
                },
            ]
        }

        with patch("checkmk_agent.llm_client.OPENAI_AVAILABLE", True):
            with requests_mock.Mocker() as m:
                m.get(
                    "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                    json=mock_hosts_response,
                    status_code=200,
                )

                # Create components
                checkmk_client = CheckmkClient(app_config.checkmk)
                llm_client = OpenAIClient(app_config.llm)
                host_manager = HostOperationsManager(
                    checkmk_client, llm_client, app_config
                )

                # Execute end-to-end workflow
                result = host_manager.process_command("show me all web servers")

                # Verify filtering worked (should only show web01 and web02)
                assert "Found 2 hosts:" in result
                assert "web01 (folder: /web)" in result
                assert "web02 (folder: /web)" in result
                assert "db01" not in result  # Should be filtered out

    def test_error_handling_integration(self, app_config):
        """Test error handling in complete workflow."""
        with requests_mock.Mocker() as m:
            # Mock API error
            m.post(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json={"title": "Host already exists", "status": 409},
                status_code=409,
            )

            checkmk_client = CheckmkClient(app_config.checkmk)

            with pytest.raises(CheckmkAPIError) as exc_info:
                checkmk_client.create_host(
                    folder="/test", host_name="existing-host", attributes={}
                )

            assert exc_info.value.status_code == 409
            assert "Host already exists" in str(exc_info.value)

    def test_connection_test_integration(self, app_config):
        """Test connection testing workflow."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://test-checkmk.example.com/mysite/check_mk/api/1.0/domain-types/host_config/collections/all",
                json={"value": []},
                status_code=200,
            )

            checkmk_client = CheckmkClient(app_config.checkmk)

            # Test successful connection
            result = checkmk_client.test_connection()
            assert result is True

            # Verify API call was made
            assert len(m.request_history) == 1
            request = m.request_history[0]
            assert request.method == "GET"
            assert "Authorization" in request.headers
