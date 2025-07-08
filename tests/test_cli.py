"""Unit tests for CLI interface."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from checkmk_agent.cli import cli, show_help
from checkmk_agent.config import AppConfig, CheckmkConfig, LLMConfig
from checkmk_agent.api_client import CheckmkClient, CheckmkAPIError
from checkmk_agent.host_operations import HostOperationsManager


@pytest.fixture
def runner():
    """Create Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return AppConfig(
        checkmk=CheckmkConfig(
            server_url="https://test.com",
            username="test",
            password="test",
            site="test"
        ),
        llm=LLMConfig(openai_api_key="test-key"),
        default_folder="/test"
    )


class TestCLIInitialization:
    """Test CLI initialization and setup."""
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    @patch('checkmk_agent.cli.create_llm_client')
    @patch('checkmk_agent.cli.HostOperationsManager')
    def test_cli_initialization_success(self, mock_host_manager, mock_llm_client, 
                                       mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test successful CLI initialization."""
        mock_load_config.return_value = mock_config
        mock_checkmk_instance = Mock()
        mock_checkmk_instance.test_connection.return_value = True
        mock_checkmk_client.return_value = mock_checkmk_instance
        mock_llm_instance = Mock()
        mock_llm_client.return_value = mock_llm_instance
        mock_host_instance = Mock()
        mock_host_manager.return_value = mock_host_instance
        
        result = runner.invoke(cli, ['test'])
        
        assert result.exit_code == 0
        mock_load_config.assert_called_once()
        mock_checkmk_client.assert_called_once_with(mock_config.checkmk)
        mock_llm_client.assert_called_once_with(mock_config.llm)
    
    @patch('checkmk_agent.cli.load_config')
    def test_cli_initialization_config_error(self, mock_load_config, runner):
        """Test CLI initialization with configuration error."""
        mock_load_config.side_effect = Exception("Config error")
        
        result = runner.invoke(cli, ['test'])
        
        assert result.exit_code == 1
        assert "Config error" in result.output
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    @patch('checkmk_agent.cli.create_llm_client')
    def test_cli_initialization_llm_error(self, mock_llm_client, mock_checkmk_client, 
                                         mock_load_config, runner, mock_config):
        """Test CLI initialization with LLM client error."""
        mock_load_config.return_value = mock_config
        mock_checkmk_client.return_value = Mock()
        mock_llm_client.side_effect = Exception("LLM error")
        
        # Should not fail, just log warning
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0


class TestTestCommand:
    """Test the 'test' command."""
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_test_command_success(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test successful connection test."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.test_connection.return_value = True
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['test'])
        
        assert result.exit_code == 0
        assert "✅ Successfully connected" in result.output
        mock_client_instance.test_connection.assert_called_once()
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_test_command_failure(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test failed connection test."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.test_connection.return_value = False
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['test'])
        
        assert result.exit_code == 1
        assert "❌ Failed to connect" in result.output
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_test_command_exception(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test connection test with exception."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.test_connection.side_effect = Exception("Network error")
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['test'])
        
        assert result.exit_code == 1
        assert "❌ Connection test failed: Network error" in result.output


class TestHostsListCommand:
    """Test the 'hosts list' command."""
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_list_success(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test successful host listing."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.list_hosts.return_value = [
            {
                "id": "web01",
                "extensions": {
                    "folder": "/web",
                    "attributes": {"ipaddress": "192.168.1.10"}
                }
            },
            {
                "id": "db01",
                "extensions": {
                    "folder": "/database",
                    "attributes": {"ipaddress": "192.168.1.20"}
                }
            }
        ]
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'list'])
        
        assert result.exit_code == 0
        assert "Found 2 hosts:" in result.output
        assert "📦 web01" in result.output
        assert "📦 db01" in result.output
        assert "Folder: /web" in result.output
        assert "IP: 192.168.1.10" in result.output
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_list_empty(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test host listing with no hosts."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.list_hosts.return_value = []
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'list'])
        
        assert result.exit_code == 0
        assert "No hosts found." in result.output
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_list_with_filters(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test host listing with filters."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.list_hosts.return_value = [
            {
                "id": "web01",
                "extensions": {
                    "folder": "/web",
                    "attributes": {"ipaddress": "192.168.1.10", "alias": "Web Server"}
                }
            }
        ]
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'list', '--folder', '/web', '--search', 'web'])
        
        assert result.exit_code == 0
        assert "📦 web01" in result.output
        mock_client_instance.list_hosts.assert_called_once_with(effective_attributes=False)
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_list_error(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test host listing with error."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.list_hosts.side_effect = Exception("API error")
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'list'])
        
        assert result.exit_code == 1
        assert "❌ Error listing hosts: API error" in result.output


class TestHostsCreateCommand:
    """Test the 'hosts create' command."""
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_create_success(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test successful host creation."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.create_host.return_value = {"id": "new-host"}
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, [
            'hosts', 'create', 'new-host',
            '--folder', '/test',
            '--ip', '192.168.1.100',
            '--alias', 'New Host'
        ])
        
        assert result.exit_code == 0
        assert "✅ Successfully created host: new-host" in result.output
        assert "Folder: /test" in result.output
        
        mock_client_instance.create_host.assert_called_once_with(
            folder='/test',
            host_name='new-host',
            attributes={'ipaddress': '192.168.1.100', 'alias': 'New Host'},
            bake_agent=False
        )
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_create_minimal(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test host creation with minimal parameters."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.create_host.return_value = {"id": "minimal-host"}
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'create', 'minimal-host'])
        
        assert result.exit_code == 0
        assert "✅ Successfully created host: minimal-host" in result.output
        
        mock_client_instance.create_host.assert_called_once_with(
            folder='/',
            host_name='minimal-host',
            attributes={},
            bake_agent=False
        )
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_create_error(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test host creation with error."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.create_host.side_effect = Exception("Creation failed")
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'create', 'error-host'])
        
        assert result.exit_code == 1
        assert "❌ Error creating host: Creation failed" in result.output


class TestHostsDeleteCommand:
    """Test the 'hosts delete' command."""
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_delete_success_with_force(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test successful host deletion with force flag."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.get_host.return_value = {
            "id": "test-host",
            "extensions": {"folder": "/test"}
        }
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'delete', 'test-host', '--force'])
        
        assert result.exit_code == 0
        assert "✅ Successfully deleted host: test-host" in result.output
        
        mock_client_instance.get_host.assert_called_once_with('test-host')
        mock_client_instance.delete_host.assert_called_once_with('test-host')
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_delete_with_confirmation(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test host deletion with user confirmation."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.get_host.return_value = {
            "id": "test-host",
            "extensions": {"folder": "/test"}
        }
        mock_checkmk_client.return_value = mock_client_instance
        
        # Simulate user confirming deletion
        result = runner.invoke(cli, ['hosts', 'delete', 'test-host'], input='y\n')
        
        assert result.exit_code == 0
        assert "✅ Successfully deleted host: test-host" in result.output
        mock_client_instance.delete_host.assert_called_once_with('test-host')
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_delete_cancelled(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test host deletion cancelled by user."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.get_host.return_value = {
            "id": "test-host",
            "extensions": {"folder": "/test"}
        }
        mock_checkmk_client.return_value = mock_client_instance
        
        # Simulate user cancelling deletion
        result = runner.invoke(cli, ['hosts', 'delete', 'test-host'], input='n\n')
        
        assert result.exit_code == 0
        assert "❌ Deletion cancelled." in result.output
        mock_client_instance.delete_host.assert_not_called()
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_delete_not_found(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test deletion of non-existent host."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.get_host.side_effect = Exception("Host not found")
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'delete', 'nonexistent', '--force'])
        
        assert result.exit_code == 1
        assert "❌ Host 'nonexistent' not found: Host not found" in result.output


class TestHostsGetCommand:
    """Test the 'hosts get' command."""
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_get_success(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test successful host retrieval."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.get_host.return_value = {
            "id": "test-host",
            "extensions": {
                "folder": "/test",
                "is_cluster": False,
                "is_offline": True,
                "attributes": {
                    "ipaddress": "192.168.1.10",
                    "alias": "Test Host"
                }
            }
        }
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'get', 'test-host'])
        
        assert result.exit_code == 0
        assert "📦 Host Details: test-host" in result.output
        assert "Folder: /test" in result.output
        assert "Cluster: No" in result.output
        assert "Offline: Yes" in result.output
        assert "ipaddress: 192.168.1.10" in result.output
        assert "alias: Test Host" in result.output
        
        mock_client_instance.get_host.assert_called_once_with('test-host', effective_attributes=False)
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    def test_hosts_get_with_effective_attributes(self, mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test host retrieval with effective attributes."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.get_host.return_value = {
            "id": "test-host",
            "extensions": {
                "folder": "/test",
                "is_cluster": False,
                "is_offline": False,
                "attributes": {},
                "effective_attributes": {"inherited_attr": "value"}
            }
        }
        mock_checkmk_client.return_value = mock_client_instance
        
        result = runner.invoke(cli, ['hosts', 'get', 'test-host', '--effective-attributes'])
        
        assert result.exit_code == 0
        assert "Effective Attributes:" in result.output
        assert "inherited_attr: value" in result.output
        
        mock_client_instance.get_host.assert_called_once_with('test-host', effective_attributes=True)


class TestInteractiveMode:
    """Test interactive mode functionality."""
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    @patch('checkmk_agent.cli.create_llm_client')
    @patch('checkmk_agent.cli.HostOperationsManager')
    def test_interactive_mode_no_llm(self, mock_host_manager, mock_llm_client, 
                                    mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test interactive mode when LLM client is not available."""
        mock_load_config.return_value = mock_config
        mock_checkmk_client.return_value = Mock()
        mock_llm_client.side_effect = Exception("LLM error")
        
        result = runner.invoke(cli, ['interactive'])
        
        assert result.exit_code == 1
        assert "❌ LLM client not available" in result.output
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    @patch('checkmk_agent.cli.create_llm_client')
    @patch('checkmk_agent.cli.HostOperationsManager')
    @patch('builtins.input')
    def test_interactive_mode_exit(self, mock_input, mock_host_manager, mock_llm_client,
                                  mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test interactive mode with exit command."""
        mock_load_config.return_value = mock_config
        mock_checkmk_client.return_value = Mock()
        mock_llm_client.return_value = Mock()
        mock_host_instance = Mock()
        mock_host_manager.return_value = mock_host_instance
        
        mock_input.return_value = 'exit'
        
        result = runner.invoke(cli, ['interactive'])
        
        assert result.exit_code == 0
        assert "👋 Goodbye!" in result.output
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    @patch('checkmk_agent.cli.create_llm_client')
    @patch('checkmk_agent.cli.HostOperationsManager')
    @patch('builtins.input')
    def test_interactive_mode_command_processing(self, mock_input, mock_host_manager, mock_llm_client,
                                                mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test interactive mode with command processing."""
        mock_load_config.return_value = mock_config
        mock_checkmk_client.return_value = Mock()
        mock_llm_client.return_value = Mock()
        mock_host_instance = Mock()
        mock_host_instance.process_command.return_value = "Command processed successfully"
        mock_host_manager.return_value = mock_host_instance
        
        mock_input.side_effect = ['list hosts', 'exit']
        
        result = runner.invoke(cli, ['interactive'])
        
        assert result.exit_code == 0
        assert "Command processed successfully" in result.output
        mock_host_instance.process_command.assert_called_with('list hosts')


class TestStatsCommand:
    """Test the 'stats' command."""
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    @patch('checkmk_agent.cli.create_llm_client')
    @patch('checkmk_agent.cli.HostOperationsManager')
    def test_stats_with_host_manager(self, mock_host_manager, mock_llm_client,
                                    mock_checkmk_client, mock_load_config, runner, mock_config):
        """Test stats command with host manager available."""
        mock_load_config.return_value = mock_config
        mock_checkmk_client.return_value = Mock()
        mock_llm_client.return_value = Mock()
        mock_host_instance = Mock()
        mock_host_instance.get_host_statistics.return_value = "📊 Total hosts: 5"
        mock_host_manager.return_value = mock_host_instance
        
        result = runner.invoke(cli, ['stats'])
        
        assert result.exit_code == 0
        assert "📊 Total hosts: 5" in result.output
        mock_host_instance.get_host_statistics.assert_called_once()
    
    @patch('checkmk_agent.cli.load_config')
    @patch('checkmk_agent.cli.CheckmkClient')
    @patch('checkmk_agent.cli.create_llm_client')
    def test_stats_fallback(self, mock_llm_client, mock_checkmk_client, 
                           mock_load_config, runner, mock_config):
        """Test stats command fallback when host manager not available."""
        mock_load_config.return_value = mock_config
        mock_client_instance = Mock()
        mock_client_instance.list_hosts.return_value = [{"id": "host1"}, {"id": "host2"}]
        mock_checkmk_client.return_value = mock_client_instance
        mock_llm_client.side_effect = Exception("LLM error")
        
        result = runner.invoke(cli, ['stats'])
        
        assert result.exit_code == 0
        assert "📊 Total hosts: 2" in result.output


class TestShowHelp:
    """Test help functionality."""
    
    def test_show_help_function(self, capsys):
        """Test show_help function output."""
        show_help()
        captured = capsys.readouterr()
        
        assert "🔧 Available Commands:" in captured.out
        assert "Natural Language Commands:" in captured.out
        assert "Special Commands:" in captured.out
        assert "Examples:" in captured.out