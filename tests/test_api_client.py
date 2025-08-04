"""Unit tests for CheckmkClient."""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import RequestException

from checkmk_agent.api_client import CheckmkClient, CheckmkAPIError, CreateHostRequest
from checkmk_agent.config import CheckmkConfig


@pytest.fixture
def config():
    """Create test configuration."""
    return CheckmkConfig(
        server_url="https://test-checkmk.com",
        username="test_user",
        password="test_pass",
        site="test_site",
        max_retries=3,
        request_timeout=30,
    )


@pytest.fixture
def client(config):
    """Create CheckmkClient instance."""
    return CheckmkClient(config)


@pytest.fixture
def mock_response():
    """Create mock response."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"test": "data"}
    return response


class TestCheckmkClient:
    """Test CheckmkClient functionality."""

    def test_initialization(self, config):
        """Test client initialization."""
        client = CheckmkClient(config)

        assert client.config == config
        assert client.base_url == "https://test-checkmk.com/test_site/check_mk/api/1.0"
        assert "Authorization" in client.session.headers
        assert client.session.headers["Authorization"] == "Bearer test_user test_pass"
        assert client.session.headers["Accept"] == "application/json"
        assert client.session.headers["Content-Type"] == "application/json"

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_make_request_success(self, mock_request, client, mock_response):
        """Test successful API request."""
        mock_request.return_value = mock_response

        result = client._make_request("GET", "/test-endpoint")

        assert result == {"test": "data"}
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert kwargs["method"] == "GET"
        assert "test-endpoint" in kwargs["url"]
        assert kwargs["timeout"] == 30

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_make_request_204_no_content(self, mock_request, client):
        """Test API request with 204 No Content response."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_request.return_value = mock_response

        result = client._make_request("DELETE", "/test-endpoint")

        assert result == {}

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_make_request_api_error(self, mock_request, client):
        """Test API request with error response."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Bad request"}
        mock_request.return_value = mock_response

        with pytest.raises(CheckmkAPIError) as exc_info:
            client._make_request("GET", "/test-endpoint")

        assert exc_info.value.status_code == 400
        assert "Bad request" in str(exc_info.value)

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_make_request_network_error(self, mock_request, client):
        """Test API request with network error."""
        mock_request.side_effect = RequestException("Network error")

        with pytest.raises(CheckmkAPIError) as exc_info:
            client._make_request("GET", "/test-endpoint")

        assert "Network error" in str(exc_info.value)

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_list_hosts(self, mock_request, client):
        """Test list_hosts method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {"id": "host1", "extensions": {"folder": "/"}},
                {"id": "host2", "extensions": {"folder": "/web"}},
            ]
        }
        mock_request.return_value = mock_response

        hosts = client.list_hosts()

        assert len(hosts) == 2
        assert hosts[0]["id"] == "host1"
        assert hosts[1]["id"] == "host2"

        # Check API call
        args, kwargs = mock_request.call_args
        assert "/domain-types/host_config/collections/all" in kwargs["url"]
        assert kwargs.get("params") == {}

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_list_hosts_with_effective_attributes(self, mock_request, client):
        """Test list_hosts with effective_attributes parameter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}
        mock_request.return_value = mock_response

        client.list_hosts(effective_attributes=True)

        args, kwargs = mock_request.call_args
        assert kwargs.get("params") == {"effective_attributes": "true"}

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_get_host(self, mock_request, client):
        """Test get_host method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-host",
            "extensions": {"folder": "/test"},
        }
        mock_request.return_value = mock_response

        host = client.get_host("test-host")

        assert host["id"] == "test-host"

        # Check API call
        args, kwargs = mock_request.call_args
        assert "/objects/host_config/test-host" in kwargs["url"]

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_create_host(self, mock_request, client):
        """Test create_host method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "new-host",
            "extensions": {"folder": "/test"},
        }
        mock_request.return_value = mock_response

        result = client.create_host(
            folder="/test",
            host_name="new-host",
            attributes={"ipaddress": "192.168.1.10"},
        )

        assert result["id"] == "new-host"

        # Check API call
        args, kwargs = mock_request.call_args
        assert "/domain-types/host_config/collections/all" in kwargs["url"]
        assert kwargs["json"]["folder"] == "/test"
        assert kwargs["json"]["host_name"] == "new-host"
        assert kwargs["json"]["attributes"]["ipaddress"] == "192.168.1.10"

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_create_host_with_bake_agent(self, mock_request, client):
        """Test create_host with bake_agent parameter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "new-host"}
        mock_request.return_value = mock_response

        client.create_host(folder="/", host_name="new-host", bake_agent=True)

        args, kwargs = mock_request.call_args
        assert kwargs.get("params") == {"bake_agent": "true"}

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_delete_host(self, mock_request, client):
        """Test delete_host method."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_request.return_value = mock_response

        client.delete_host("test-host")

        # Check API call
        args, kwargs = mock_request.call_args
        assert kwargs["method"] == "DELETE"
        assert "/objects/host_config/test-host" in kwargs["url"]

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_update_host(self, mock_request, client):
        """Test update_host method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "test-host"}
        mock_request.return_value = mock_response

        result = client.update_host(
            "test-host", {"ipaddress": "192.168.1.20"}, etag="test-etag"
        )

        assert result["id"] == "test-host"

        # Check API call
        args, kwargs = mock_request.call_args
        assert kwargs["method"] == "PUT"
        assert "/objects/host_config/test-host" in kwargs["url"]
        assert kwargs["json"]["attributes"]["ipaddress"] == "192.168.1.20"
        assert kwargs["headers"]["If-Match"] == "test-etag"

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_bulk_create_hosts(self, mock_request, client):
        """Test bulk_create_hosts method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_request.return_value = mock_response

        hosts_data = [
            {"folder": "/", "host_name": "host1"},
            {
                "folder": "/web",
                "host_name": "host2",
                "attributes": {"ipaddress": "192.168.1.10"},
            },
        ]

        client.bulk_create_hosts(hosts_data)

        # Check API call
        args, kwargs = mock_request.call_args
        assert "/domain-types/host_config/actions/bulk-create/invoke" in kwargs["url"]
        assert len(kwargs["json"]["entries"]) == 2
        assert kwargs["json"]["entries"][0]["host_name"] == "host1"
        assert kwargs["json"]["entries"][1]["attributes"]["ipaddress"] == "192.168.1.10"

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_bulk_delete_hosts(self, mock_request, client):
        """Test bulk_delete_hosts method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_request.return_value = mock_response

        host_names = ["host1", "host2", "host3"]

        client.bulk_delete_hosts(host_names)

        # Check API call
        args, kwargs = mock_request.call_args
        assert "/domain-types/host_config/actions/bulk-delete/invoke" in kwargs["url"]
        assert kwargs["json"]["entries"] == host_names

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_test_connection_success(self, mock_request, client):
        """Test test_connection method with successful connection."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}
        mock_request.return_value = mock_response

        result = client.test_connection()

        assert result is True

    @patch("checkmk_agent.api_client.requests.Session.request")
    def test_test_connection_failure(self, mock_request, client):
        """Test test_connection method with failed connection."""
        mock_request.side_effect = CheckmkAPIError("Connection failed")

        result = client.test_connection()

        assert result is False


class TestCreateHostRequest:
    """Test CreateHostRequest validation."""

    def test_valid_request(self):
        """Test valid host creation request."""
        request = CreateHostRequest(
            folder="/test",
            host_name="valid-host",
            attributes={"ipaddress": "192.168.1.10"},
        )

        assert request.folder == "/test"
        assert request.host_name == "valid-host"
        assert request.attributes["ipaddress"] == "192.168.1.10"

    def test_invalid_hostname(self):
        """Test invalid hostname validation."""
        with pytest.raises(ValueError):
            CreateHostRequest(
                folder="/test",
                host_name="invalid host name!",  # Contains invalid characters
                attributes={},
            )

    def test_minimal_request(self):
        """Test minimal valid request."""
        request = CreateHostRequest(folder="/", host_name="minimal-host")

        assert request.folder == "/"
        assert request.host_name == "minimal-host"
        assert request.attributes is None


class TestCheckmkAPIError:
    """Test CheckmkAPIError exception."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = CheckmkAPIError("Test error")

        assert str(error) == "Test error"
        assert error.status_code is None
        assert error.response_data is None

    def test_error_with_details(self):
        """Test error with status code and response data."""
        response_data = {"detail": "Host not found"}
        error = CheckmkAPIError(
            "API error", status_code=404, response_data=response_data
        )

        # Check that enhanced error message includes helpful context
        error_str = str(error)
        assert "API error" in error_str
        assert "Status: 404" in error_str
        assert "Resource not found - check hostname/service names" in error_str
        assert error.status_code == 404
        assert error.response_data == response_data
