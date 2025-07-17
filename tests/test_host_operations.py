"""Unit tests for HostOperationsManager."""

import pytest
from unittest.mock import Mock, patch
from io import StringIO

from checkmk_agent.host_operations import HostOperationsManager
from checkmk_agent.api_client import CheckmkClient, CheckmkAPIError
from checkmk_agent.llm_client import LLMClient, ParsedCommand, HostOperation
from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig


@pytest.fixture
def app_config():
    """Create test application configuration."""
    return AppConfig(
        checkmk=CheckmkConfig(
            server_url="https://test.com",
            username="test",
            password="test",
            site="test"
        ),
        llm=LLMConfig(),
        default_folder="/test",
        log_level="INFO"
    )


@pytest.fixture
def mock_checkmk_client():
    """Create mock Checkmk client."""
    return Mock(spec=CheckmkClient)


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    return Mock(spec=LLMClient)


@pytest.fixture
def host_manager(mock_checkmk_client, mock_llm_client, app_config):
    """Create HostOperationsManager instance."""
    return HostOperationsManager(mock_checkmk_client, mock_llm_client, app_config)


class TestHostOperationsManager:
    """Test HostOperationsManager functionality."""
    
    def test_initialization(self, mock_checkmk_client, mock_llm_client, app_config):
        """Test manager initialization."""
        manager = HostOperationsManager(mock_checkmk_client, mock_llm_client, app_config)
        
        assert manager.checkmk == mock_checkmk_client
        assert manager.llm == mock_llm_client
        assert manager.config == app_config
    
    def test_process_command_success(self, host_manager, mock_llm_client, mock_checkmk_client):
        """Test successful command processing."""
        # Setup mocks
        parsed_command = ParsedCommand(
            operation=HostOperation.LIST,
            parameters={},
            confidence=0.9
        )
        mock_llm_client.parse_command.return_value = parsed_command
        mock_checkmk_client.list_hosts.return_value = [
            {"id": "host1", "extensions": {"folder": "/"}}
        ]
        mock_llm_client.format_response.return_value = "Found 1 host: host1"
        
        result = host_manager.process_command("list hosts")
        
        assert result == "Found 1 host: host1"
        mock_llm_client.parse_command.assert_called_once_with("list hosts")
        mock_checkmk_client.list_hosts.assert_called_once()
        mock_llm_client.format_response.assert_called_once_with(
            HostOperation.LIST, [{"id": "host1", "extensions": {"folder": "/"}}], success=True
        )
    
    def test_process_command_error(self, host_manager, mock_llm_client, mock_checkmk_client):
        """Test command processing with error."""
        # Setup mocks
        parsed_command = ParsedCommand(
            operation=HostOperation.GET,
            parameters={"host_name": "nonexistent"},
            confidence=0.9
        )
        mock_llm_client.parse_command.return_value = parsed_command
        mock_checkmk_client.get_host.side_effect = CheckmkAPIError("Host not found", status_code=404)
        
        result = host_manager.process_command("get nonexistent host")
        
        # Updated to match new error handling format
        assert result == "❌ Error: Host not found"
        # LLM format_response should not be called for errors anymore
        mock_llm_client.format_response.assert_not_called()
    
    def test_process_command_syntax_error(self, host_manager, mock_llm_client, mock_checkmk_client):
        """Test command processing with syntax error."""
        # Setup mocks
        parsed_command = ParsedCommand(
            operation=HostOperation.SYNTAX_ERROR,
            parameters={},
            confidence=0.1,
            raw_text="blah blah invalid command"
        )
        mock_llm_client.parse_command.return_value = parsed_command
        
        result = host_manager.process_command("blah blah invalid command")
        
        # Should return syntax error message without executing any operations
        assert "❌ Error: Unrecognized command: 'blah blah invalid command'" in result
        assert "Try 'help' for available commands" in result
        # No API calls should be made
        mock_checkmk_client.list_hosts.assert_not_called()
        mock_checkmk_client.get_host.assert_not_called()
        # LLM format_response should not be called for syntax errors
        mock_llm_client.format_response.assert_not_called()
    
    def test_list_hosts_basic(self, host_manager, mock_checkmk_client):
        """Test basic host listing."""
        mock_checkmk_client.list_hosts.return_value = [
            {"id": "host1", "extensions": {"folder": "/"}},
            {"id": "host2", "extensions": {"folder": "/web"}}
        ]
        
        result = host_manager._list_hosts({})
        
        assert len(result) == 2
        assert result[0]["id"] == "host1"
        assert result[1]["id"] == "host2"
        mock_checkmk_client.list_hosts.assert_called_once_with(effective_attributes=False)
    
    def test_list_hosts_with_search(self, host_manager, mock_checkmk_client):
        """Test host listing with search filter."""
        mock_checkmk_client.list_hosts.return_value = [
            {"id": "web01", "extensions": {"folder": "/web", "attributes": {"alias": "Web Server"}}},
            {"id": "db01", "extensions": {"folder": "/database", "attributes": {"alias": "Database"}}},
            {"id": "web02", "extensions": {"folder": "/web", "attributes": {"alias": "Web Server 2"}}}
        ]
        
        result = host_manager._list_hosts({"search_term": "web"})
        
        assert len(result) == 2  # web01 and web02 should match
        host_ids = [host["id"] for host in result]
        assert "web01" in host_ids
        assert "web02" in host_ids
        assert "db01" not in host_ids
    
    def test_create_host_basic(self, host_manager, mock_checkmk_client):
        """Test basic host creation."""
        mock_checkmk_client.create_host.return_value = {"id": "new-host"}
        
        result = host_manager._create_host({
            "host_name": "new-host",
            "folder": "/test"
        })
        
        assert result["id"] == "new-host"
        mock_checkmk_client.create_host.assert_called_once_with(
            folder="/test",
            host_name="new-host",
            attributes={},
            bake_agent=False
        )
    
    def test_create_host_with_attributes(self, host_manager, mock_checkmk_client):
        """Test host creation with attributes."""
        mock_checkmk_client.create_host.return_value = {"id": "new-host"}
        
        result = host_manager._create_host({
            "host_name": "new-host",
            "folder": "/test",
            "ipaddress": "192.168.1.10",
            "alias": "Test Host",
            "attributes": {"tag_criticality": "prod"}
        })
        
        expected_attributes = {
            "ipaddress": "192.168.1.10",
            "alias": "Test Host",
            "tag_criticality": "prod"
        }
        
        mock_checkmk_client.create_host.assert_called_once_with(
            folder="/test",
            host_name="new-host",
            attributes=expected_attributes,
            bake_agent=False
        )
    
    def test_create_host_missing_name(self, host_manager):
        """Test host creation without host name."""
        with pytest.raises(ValueError, match="Host name is required"):
            host_manager._create_host({})
    
    def test_create_host_invalid_name(self, host_manager):
        """Test host creation with invalid host name."""
        with pytest.raises(ValueError, match="Invalid hostname format"):
            host_manager._create_host({"host_name": "invalid host name!"})
    
    def test_create_host_default_folder(self, host_manager, mock_checkmk_client):
        """Test host creation uses default folder when not specified."""
        mock_checkmk_client.create_host.return_value = {"id": "new-host"}
        
        host_manager._create_host({"host_name": "new-host"})
        
        mock_checkmk_client.create_host.assert_called_once_with(
            folder="/test",  # Should use config default
            host_name="new-host",
            attributes={},
            bake_agent=False
        )
    
    def test_delete_host_success(self, host_manager, mock_checkmk_client):
        """Test successful host deletion."""
        # Host exists
        mock_checkmk_client.get_host.return_value = {"id": "test-host"}
        
        host_manager._delete_host({"host_name": "test-host"})
        
        mock_checkmk_client.get_host.assert_called_once_with("test-host")
        mock_checkmk_client.delete_host.assert_called_once_with("test-host")
    
    def test_delete_host_not_found(self, host_manager, mock_checkmk_client):
        """Test host deletion when host doesn't exist."""
        mock_checkmk_client.get_host.side_effect = CheckmkAPIError("Not found", status_code=404)
        
        with pytest.raises(ValueError, match="Host 'test-host' not found"):
            host_manager._delete_host({"host_name": "test-host"})
    
    def test_delete_host_missing_name(self, host_manager):
        """Test host deletion without host name."""
        with pytest.raises(ValueError, match="Host name is required"):
            host_manager._delete_host({})
    
    def test_get_host_success(self, host_manager, mock_checkmk_client):
        """Test successful host retrieval."""
        mock_checkmk_client.get_host.return_value = {"id": "test-host"}
        
        result = host_manager._get_host({"host_name": "test-host"})
        
        assert result["id"] == "test-host"
        mock_checkmk_client.get_host.assert_called_once_with("test-host", effective_attributes=False)
    
    def test_get_host_with_effective_attributes(self, host_manager, mock_checkmk_client):
        """Test host retrieval with effective attributes."""
        mock_checkmk_client.get_host.return_value = {"id": "test-host"}
        
        host_manager._get_host({
            "host_name": "test-host",
            "effective_attributes": True
        })
        
        mock_checkmk_client.get_host.assert_called_once_with("test-host", effective_attributes=True)
    
    def test_get_host_missing_name(self, host_manager):
        """Test host retrieval without host name."""
        with pytest.raises(ValueError, match="Host name is required"):
            host_manager._get_host({})
    
    def test_update_host_success(self, host_manager, mock_checkmk_client):
        """Test successful host update."""
        mock_checkmk_client.update_host.return_value = {"id": "test-host"}
        
        result = host_manager._update_host({
            "host_name": "test-host",
            "attributes": {"ipaddress": "192.168.1.20"}
        })
        
        assert result["id"] == "test-host"
        mock_checkmk_client.update_host.assert_called_once_with(
            "test-host",
            {"ipaddress": "192.168.1.20"},
            etag=None
        )
    
    def test_update_host_missing_name(self, host_manager):
        """Test host update without host name."""
        with pytest.raises(ValueError, match="Host name is required"):
            host_manager._update_host({"attributes": {"ipaddress": "192.168.1.20"}})
    
    def test_update_host_missing_attributes(self, host_manager):
        """Test host update without attributes."""
        with pytest.raises(ValueError, match="Attributes are required"):
            host_manager._update_host({"host_name": "test-host"})
    
    def test_execute_operation_unsupported(self, host_manager):
        """Test execution of unsupported operation."""
        command = ParsedCommand(
            operation="unsupported_operation",  # Invalid operation
            parameters={}
        )
        
        with pytest.raises(ValueError, match="Unsupported operation"):
            host_manager._execute_operation(command)
    
    def test_test_connection_success(self, host_manager, mock_checkmk_client):
        """Test successful connection test."""
        mock_checkmk_client.test_connection.return_value = True
        
        result = host_manager.test_connection()
        
        assert "✅ Successfully connected" in result
    
    def test_test_connection_failure(self, host_manager, mock_checkmk_client):
        """Test failed connection test."""
        mock_checkmk_client.test_connection.return_value = False
        
        result = host_manager.test_connection()
        
        assert "❌ Failed to connect" in result
    
    def test_test_connection_exception(self, host_manager, mock_checkmk_client):
        """Test connection test with exception."""
        mock_checkmk_client.test_connection.side_effect = Exception("Network error")
        
        result = host_manager.test_connection()
        
        assert "❌ Connection test failed: Network error" in result
    
    def test_get_host_statistics(self, host_manager, mock_checkmk_client):
        """Test host statistics generation."""
        mock_checkmk_client.list_hosts.return_value = [
            {
                "id": "web01",
                "extensions": {
                    "folder": "/web",
                    "is_cluster": False,
                    "is_offline": False
                }
            },
            {
                "id": "web02",
                "extensions": {
                    "folder": "/web",
                    "is_cluster": False,
                    "is_offline": True
                }
            },
            {
                "id": "cluster01",
                "extensions": {
                    "folder": "/clusters",
                    "is_cluster": True,
                    "is_offline": False
                }
            }
        ]
        
        result = host_manager.get_host_statistics()
        
        assert "📊 Host Statistics:" in result
        assert "Total hosts: 3" in result
        assert "Cluster hosts: 1" in result
        assert "Offline hosts: 1" in result
        assert "/web: 2" in result
        assert "/clusters: 1" in result
    
    def test_get_host_statistics_error(self, host_manager, mock_checkmk_client):
        """Test host statistics with error."""
        mock_checkmk_client.list_hosts.side_effect = Exception("API error")
        
        result = host_manager.get_host_statistics()
        
        assert "❌ Failed to get host statistics: API error" in result
    
    @patch('builtins.input')
    def test_interactive_create_host_success(self, mock_input, host_manager, mock_checkmk_client):
        """Test successful interactive host creation."""
        # Mock user inputs
        mock_input.side_effect = [
            "test-host",     # host name
            "/web",          # folder
            "192.168.1.10",  # IP address
            "Test Host",     # alias
            "y"              # confirmation
        ]
        
        mock_checkmk_client.create_host.return_value = {"id": "test-host"}
        
        with patch('builtins.print'):  # Suppress print output
            result = host_manager.interactive_create_host()
        
        assert "✅ Successfully created host: test-host" in result
        mock_checkmk_client.create_host.assert_called_once_with(
            folder="/web",
            host_name="test-host",
            attributes={"ipaddress": "192.168.1.10", "alias": "Test Host"}
        )
    
    @patch('builtins.input')
    def test_interactive_create_host_cancelled(self, mock_input, host_manager):
        """Test interactive host creation cancelled by user."""
        mock_input.side_effect = [
            "test-host",  # host name
            "",           # folder (use default)
            "",           # IP address (skip)
            "",           # alias (skip)
            "n"           # reject confirmation
        ]
        
        with patch('builtins.print'):  # Suppress print output
            result = host_manager.interactive_create_host()
        
        assert "❌ Host creation cancelled." in result
    
    @patch('builtins.input')
    def test_interactive_create_host_invalid_name(self, mock_input, host_manager):
        """Test interactive host creation with invalid hostname."""
        mock_input.side_effect = [
            "invalid host!",  # invalid name
            "valid-host",     # valid name
            "",               # folder (default)
            "",               # IP (skip)
            "",               # alias (skip)
            "y"               # confirm
        ]
        
        mock_checkmk_client = Mock()
        mock_checkmk_client.create_host.return_value = {"id": "valid-host"}
        host_manager.checkmk = mock_checkmk_client
        
        with patch('builtins.print'):  # Suppress print output
            result = host_manager.interactive_create_host()
        
        assert "✅ Successfully created host: valid-host" in result
    
    @patch('builtins.input')
    def test_interactive_create_host_keyboard_interrupt(self, mock_input, host_manager):
        """Test interactive host creation with keyboard interrupt."""
        mock_input.side_effect = KeyboardInterrupt()
        
        with patch('builtins.print'):  # Suppress print output
            result = host_manager.interactive_create_host()
        
        assert "❌ Host creation cancelled." in result