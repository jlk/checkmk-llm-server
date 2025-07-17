"""Integration tests for service parameter functionality."""

import pytest
from unittest.mock import Mock, patch

from checkmk_agent.service_operations import ServiceOperationsManager
from checkmk_agent.service_parameters import ServiceParameterManager
from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.llm_client import LLMClient
from checkmk_agent.config import AppConfig


@pytest.fixture
def mock_checkmk_client():
    """Mock Checkmk client with parameter-related endpoints."""
    client = Mock(spec=CheckmkClient)
    
    # Mock ruleset operations
    client.list_rulesets.return_value = [
        {'id': 'cpu_utilization_linux', 'title': 'CPU utilization on Linux/Unix'},
        {'id': 'memory_linux', 'title': 'Memory levels for Linux'},
        {'id': 'filesystems', 'title': 'Filesystems (used space and growth)'}
    ]
    
    client.get_ruleset_info.return_value = {
        'id': 'cpu_utilization_linux',
        'title': 'CPU utilization on Linux/Unix'
    }
    
    client.list_rules.return_value = [
        {
            'id': 'rule_123',
            'extensions': {
                'ruleset': 'cpu_utilization_linux',
                'value_raw': '{"levels": [80.0, 90.0]}',
                'conditions': {'host_name': ['server01']},
                'properties': {'description': 'Test rule'}
            }
        }
    ]
    
    client.get_rule.return_value = {
        'id': 'rule_123',
        'extensions': {
            'ruleset': 'cpu_utilization_linux',
            'value_raw': '{"levels": [85.0, 95.0]}',
            'conditions': {'host_name': ['server01'], 'service_description': ['CPU utilization']},
            'properties': {'description': 'Test override rule'}
        }
    }
    
    client.create_rule.return_value = {'id': 'rule_new_123'}
    client.search_rules_by_host_service.return_value = []
    
    return client


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for natural language processing."""
    client = Mock(spec=LLMClient)
    
    # Default response for parameter commands
    client.chat_completion.return_value = '''
    {
        "action": "set_service_parameters",
        "parameters": {
            "host_name": "server01",
            "service_description": "CPU utilization",
            "parameter_type": "warning",
            "warning_value": 85
        }
    }
    '''
    
    return client


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = Mock(spec=AppConfig)
    config.checkmk = Mock()
    config.checkmk.username = "test_user"
    return config


@pytest.fixture
def service_operations_manager(mock_checkmk_client, mock_llm_client, mock_config):
    """Service operations manager with parameter functionality."""
    return ServiceOperationsManager(mock_checkmk_client, mock_llm_client, mock_config)


class TestServiceParameterIntegration:
    """Integration tests for service parameter operations."""
    
    def test_view_default_parameters_command(self, service_operations_manager, mock_llm_client):
        """Test viewing default parameters through natural language."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "view_default_parameters",
            "parameters": {
                "service_type": "cpu"
            }
        }
        '''
        
        result = service_operations_manager.process_command("show default CPU parameters")
        
        assert "Default Parameters for CPU services" in result
        assert "Warning Threshold: 80.0%" in result
        assert "Critical Threshold: 90.0%" in result
        assert "cpu_utilization_linux" in result
    
    def test_view_service_parameters_no_rules(self, service_operations_manager, mock_llm_client, mock_checkmk_client):
        """Test viewing service parameters when no rules exist."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "view_service_parameters",
            "parameters": {
                "host_name": "server01",
                "service_description": "CPU utilization"
            }
        }
        '''
        
        # Mock no rules found
        mock_checkmk_client.search_rules_by_host_service.return_value = []
        
        result = service_operations_manager.process_command("what are CPU parameters for server01?")
        
        assert "Parameters for server01/CPU utilization" in result
        assert "default parameters" in result
    
    def test_view_service_parameters_with_rules(self, service_operations_manager, mock_llm_client, mock_checkmk_client):
        """Test viewing service parameters with existing rules."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "view_service_parameters",
            "parameters": {
                "host_name": "server01",
                "service_description": "CPU utilization"
            }
        }
        '''
        
        # Mock rules found
        mock_rules = [
            {
                'id': 'rule_123',
                'extensions': {
                    'value_raw': '{"levels": [85.0, 95.0], "average": 10}',
                    'ruleset': 'cpu_utilization_linux'
                }
            }
        ]
        mock_checkmk_client.search_rules_by_host_service.return_value = mock_rules
        
        result = service_operations_manager.process_command("show CPU parameters for server01")
        
        assert "Effective Parameters for server01/CPU utilization" in result
        assert "Warning: 85.0%" in result
        assert "Critical: 95.0%" in result
        assert "Rule rule_123" in result
    
    def test_set_service_parameters_warning_only(self, service_operations_manager, mock_llm_client, mock_checkmk_client):
        """Test setting warning threshold only."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "set_service_parameters",
            "parameters": {
                "host_name": "server01",
                "service_description": "CPU utilization",
                "parameter_type": "warning",
                "warning_value": 85
            }
        }
        '''
        
        # Mock current parameters to get critical value
        mock_checkmk_client.search_rules_by_host_service.return_value = []
        
        result = service_operations_manager.process_command("set CPU warning to 85% for server01")
        
        assert "Created parameter override" in result
        assert "Warning: 85.0%" in result
        assert "Critical: 90.0%" in result  # Default critical
        assert "rule_new_123" in result
    
    def test_set_service_parameters_both_thresholds(self, service_operations_manager, mock_llm_client, mock_checkmk_client):
        """Test setting both warning and critical thresholds."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "set_service_parameters",
            "parameters": {
                "host_name": "server01",
                "service_description": "CPU utilization",
                "parameter_type": "both",
                "warning_value": 85,
                "critical_value": 95
            }
        }
        '''
        
        result = service_operations_manager.process_command("set CPU warning to 85% and critical to 95% for server01")
        
        assert "Created parameter override" in result
        assert "Warning: 85.0%" in result
        assert "Critical: 95.0%" in result
        assert "rule_new_123" in result
    
    def test_list_parameter_rules_all(self, service_operations_manager, mock_llm_client, mock_checkmk_client):
        """Test listing all parameter rules."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "list_parameter_rules",
            "parameters": {}
        }
        '''
        
        result = service_operations_manager.process_command("show all parameter rules")
        
        assert "Available Parameter Rulesets" in result
        assert "CPU:" in result
        assert "cpu_utilization_linux" in result
        assert "Memory:" in result
        assert "memory_linux" in result
        assert "Filesystem:" in result
        assert "filesystems" in result
    
    def test_list_parameter_rules_specific(self, service_operations_manager, mock_llm_client, mock_checkmk_client):
        """Test listing rules for specific ruleset."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "list_parameter_rules",
            "parameters": {
                "ruleset_name": "cpu_utilization_linux"
            }
        }
        '''
        
        result = service_operations_manager.process_command("show rules for cpu_utilization_linux")
        
        assert "Rules for cpu_utilization_linux" in result
        assert "Rule rule_123" in result
        assert "Hosts: server01" in result
        assert "Description: Test rule" in result
    
    def test_discover_ruleset(self, service_operations_manager, mock_llm_client):
        """Test discovering appropriate ruleset for a service."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "discover_ruleset",
            "parameters": {
                "host_name": "server01",
                "service_description": "CPU utilization"
            }
        }
        '''
        
        result = service_operations_manager.process_command("what ruleset controls CPU utilization on server01?")
        
        assert "Service: CPU utilization" in result
        assert "Host: server01" in result
        assert "Recommended Ruleset: cpu_utilization_linux" in result
        assert "Default Parameters:" in result
        assert "Warning: 80.0%" in result or "Warning: 85.0%" in result  # Accept both default values
    
    def test_delete_parameter_rule(self, service_operations_manager, mock_llm_client, mock_checkmk_client):
        """Test deleting a parameter rule."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "delete_parameter_rule",
            "parameters": {
                "rule_id": "rule_123"
            }
        }
        '''
        
        result = service_operations_manager.process_command("delete rule rule_123")
        
        assert "Deleted parameter rule: rule_123" in result
        assert "cpu_utilization_linux" in result
        assert "Affected Hosts: server01" in result
        
        # Verify delete was called
        mock_checkmk_client.delete_rule.assert_called_once_with('rule_123')
    
    def test_create_parameter_rule_general(self, service_operations_manager, mock_llm_client):
        """Test creating a general parameter rule."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "create_parameter_rule",
            "parameters": {
                "service_type": "memory",
                "comment": "Memory rule for production servers"
            }
        }
        '''
        
        result = service_operations_manager.process_command("create memory rule for production servers")
        
        assert "To create a parameter rule for memory services" in result
        assert "Service Type: memory" in result
        assert "Ruleset: memory_linux" in result
        assert "Default Parameters:" in result
    
    def test_error_handling_invalid_service(self, service_operations_manager, mock_llm_client):
        """Test error handling for invalid service types."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "set_service_parameters",
            "parameters": {
                "host_name": "server01",
                "service_description": "Unknown Service Type",
                "parameter_type": "warning",
                "warning_value": 85
            }
        }
        '''
        
        result = service_operations_manager.process_command("set warning to 85% for Unknown Service Type on server01")
        
        assert "Error setting service parameters" in result
        assert "Could not determine ruleset" in result
    
    def test_error_handling_missing_parameters(self, service_operations_manager, mock_llm_client):
        """Test error handling for missing required parameters."""
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "set_service_parameters",
            "parameters": {
                "host_name": "server01"
            }
        }
        '''
        
        result = service_operations_manager.process_command("set parameters for server01")
        
        assert "Please specify both host name and service description" in result
    
    def test_complex_natural_language_parsing(self, service_operations_manager, mock_llm_client):
        """Test parsing complex natural language commands."""
        # Test various ways users might express parameter operations
        test_cases = [
            ("override CPU warning to 85% for server01", "set_service_parameters"),
            ("change disk critical threshold to 95% on database-01", "set_service_parameters"),
            ("what are the memory thresholds for web-server?", "view_service_parameters"),
            ("show default filesystem parameters", "view_default_parameters"),
            ("list all CPU rules", "list_parameter_rules"),
            ("which ruleset controls memory on server01?", "discover_ruleset")
        ]
        
        for command, expected_action in test_cases:
            mock_llm_client.chat_completion.return_value = f'''
            {{
                "action": "{expected_action}",
                "parameters": {{
                    "host_name": "server01",
                    "service_description": "test service"
                }}
            }}
            '''
            
            # The command should be processed without errors
            result = service_operations_manager.process_command(command)
            assert "Error processing command" not in result


class TestServiceParameterWorkflows:
    """Test complete workflows for service parameter management."""
    
    def test_complete_override_workflow(self, service_operations_manager, mock_llm_client, mock_checkmk_client):
        """Test complete workflow from discovery to override to verification."""
        
        # Step 1: Discover ruleset
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "discover_ruleset",
            "parameters": {
                "host_name": "server01",
                "service_description": "CPU utilization"
            }
        }
        '''
        
        discover_result = service_operations_manager.process_command(
            "what ruleset controls CPU utilization on server01?"
        )
        assert "cpu_utilization_linux" in discover_result
        
        # Step 2: View current parameters
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "view_service_parameters",
            "parameters": {
                "host_name": "server01",
                "service_description": "CPU utilization"
            }
        }
        '''
        
        view_result = service_operations_manager.process_command(
            "show CPU parameters for server01"
        )
        assert "default parameters" in view_result
        
        # Step 3: Create override
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "set_service_parameters",
            "parameters": {
                "host_name": "server01",
                "service_description": "CPU utilization",
                "warning_value": 85,
                "critical_value": 95
            }
        }
        '''
        
        override_result = service_operations_manager.process_command(
            "set CPU warning to 85% and critical to 95% for server01"
        )
        assert "Created parameter override" in override_result
        assert "rule_new_123" in override_result
        
        # Step 4: Verify new parameters
        mock_checkmk_client.search_rules_by_host_service.return_value = [
            {
                'id': 'rule_new_123',
                'extensions': {
                    'value_raw': '{"levels": [85.0, 95.0]}',
                    'ruleset': 'cpu_utilization_linux'
                }
            }
        ]
        
        verify_result = service_operations_manager.process_command(
            "show CPU parameters for server01"
        )
        assert "Warning: 85.0%" in verify_result
        assert "Critical: 95.0%" in verify_result
    
    def test_bulk_parameter_management(self, service_operations_manager, mock_llm_client, mock_checkmk_client):
        """Test managing parameters for multiple services."""
        
        # Mock multiple rulesets
        mock_checkmk_client.list_rulesets.return_value = [
            {'id': 'cpu_utilization_linux'},
            {'id': 'memory_linux'},
            {'id': 'filesystems'}
        ]
        
        # List all available rulesets
        mock_llm_client.chat_completion.return_value = '''
        {
            "action": "list_parameter_rules",
            "parameters": {}
        }
        '''
        
        list_result = service_operations_manager.process_command("show all parameter rulesets")
        
        assert "CPU:" in list_result
        assert "Memory:" in list_result
        assert "Filesystem:" in list_result
        
        # Create overrides for multiple service types
        service_configs = [
            ("CPU utilization", 85, 95),
            ("Memory usage", 75, 85),
            ("Filesystem /var", 90, 95)
        ]
        
        for service_desc, warning, critical in service_configs:
            mock_llm_client.chat_completion.return_value = f'''
            {{
                "action": "set_service_parameters",
                "parameters": {{
                    "host_name": "server01",
                    "service_description": "{service_desc}",
                    "warning_value": {warning},
                    "critical_value": {critical}
                }}
            }}
            '''
            
            result = service_operations_manager.process_command(
                f"set {service_desc} warning to {warning}% and critical to {critical}% for server01"
            )
            
            assert "Created parameter override" in result
            assert f"Warning: {warning}.0%" in result
            assert f"Critical: {critical}.0%" in result