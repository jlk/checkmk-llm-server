"""Tests for service operations functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

from checkmk_agent.service_operations import ServiceOperationsManager
from checkmk_agent.api_client import CheckmkAPIError


class TestServiceOperationsManager:
    """Test suite for ServiceOperationsManager."""
    
    @pytest.fixture
    def mock_checkmk_client(self):
        """Create a mock CheckmkClient."""
        return Mock()
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLMClient."""
        return Mock()
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = Mock()
        config.checkmk.username = "test_user"
        return config
    
    @pytest.fixture
    def service_manager(self, mock_checkmk_client, mock_llm_client, mock_config):
        """Create a ServiceOperationsManager instance."""
        return ServiceOperationsManager(mock_checkmk_client, mock_llm_client, mock_config)
    
    def test_list_host_services(self, service_manager, mock_checkmk_client):
        """Test listing services for a specific host."""
        # Mock response
        mock_services = [
            {
                "id": "service1",
                "extensions": {
                    "description": "CPU utilization",
                    "state": "OK",
                    "host_name": "server01"
                }
            },
            {
                "id": "service2",
                "extensions": {
                    "description": "Memory utilization",
                    "state": "WARN",
                    "host_name": "server01"
                }
            }
        ]
        mock_checkmk_client.list_host_services.return_value = mock_services
        
        # Mock LLM response
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "list_services",
            "parameters": {"host_name": "server01"}
        })
        
        result = service_manager.process_command("list services for server01")
        
        assert "Found 2 services for host: server01" in result
        assert "CPU utilization" in result
        assert "Memory utilization" in result
        mock_checkmk_client.list_host_services.assert_called_once_with("server01", columns=['description', 'state', 'plugin_output'])
    
    def test_list_all_services(self, service_manager, mock_checkmk_client):
        """Test listing all services."""
        # Mock response
        mock_services = [
            {
                "id": "service1",
                "extensions": {
                    "description": "CPU utilization",
                    "state": "OK",
                    "host_name": "server01"
                }
            },
            {
                "id": "service2",
                "extensions": {
                    "description": "Disk space",
                    "state": "CRIT",
                    "host_name": "server02"
                }
            }
        ]
        mock_checkmk_client.list_all_services.return_value = mock_services
        
        # Mock LLM response
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "list_services",
            "parameters": {}
        })
        
        result = service_manager.process_command("show all services")
        
        assert "Found 2 services across 2 hosts" in result
        assert "server01" in result
        assert "server02" in result
        mock_checkmk_client.list_all_services.assert_called_once_with(columns=['description', 'state', 'plugin_output'])
    
    def test_acknowledge_service_problems(self, service_manager, mock_checkmk_client):
        """Test acknowledging service problems."""
        # Mock LLM response
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "acknowledge_service",
            "parameters": {
                "host_name": "server01",
                "service_description": "CPU load",
                "comment": "Working on it"
            }
        })
        
        result = service_manager.process_command("acknowledge CPU load on server01")
        
        assert "Acknowledged service problem: server01/CPU load" in result
        assert "Working on it" in result
        mock_checkmk_client.acknowledge_service_problems.assert_called_once_with(
            host_name="server01",
            service_description="CPU load",
            comment="Working on it",
            sticky=True
        )
    
    def test_create_service_downtime(self, service_manager, mock_checkmk_client):
        """Test creating service downtime."""
        # Mock LLM response
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "create_downtime",
            "parameters": {
                "host_name": "server01",
                "service_description": "disk space",
                "duration_hours": 2,
                "comment": "Maintenance"
            }
        })
        
        with patch('checkmk_agent.service_operations.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            result = service_manager.process_command("create 2 hour downtime for disk space on server01")
            
            assert "Created downtime for service: server01/disk space" in result
            assert "Duration: 2 hours" in result
            assert "Maintenance" in result
            mock_checkmk_client.create_service_downtime.assert_called_once()
    
    def test_discover_services(self, service_manager, mock_checkmk_client):
        """Test service discovery."""
        # Mock discovery result
        mock_discovery_result = {
            "extensions": {
                "new": [
                    {"service_description": "New Service 1"},
                    {"service_description": "New Service 2"}
                ],
                "vanished": [
                    {"service_description": "Old Service"}
                ],
                "ignored": []
            }
        }
        mock_checkmk_client.get_service_discovery_result.return_value = mock_discovery_result
        
        # Mock LLM response
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "discover_services",
            "parameters": {
                "host_name": "server01"
            }
        })
        
        result = service_manager.process_command("discover services on server01")
        
        assert "Service discovery completed for host: server01" in result
        assert "New services found (2)" in result
        assert "New Service 1" in result
        assert "New Service 2" in result
        assert "Vanished services (1)" in result
        assert "Old Service" in result
        
        mock_checkmk_client.start_service_discovery.assert_called_once_with("server01", "refresh")
        mock_checkmk_client.get_service_discovery_result.assert_called_once_with("server01")
    
    def test_get_service_statistics(self, service_manager, mock_checkmk_client):
        """Test getting service statistics."""
        # Mock response
        mock_services = [
            {
                "extensions": {
                    "state": "OK",
                    "host_name": "server01"
                }
            },
            {
                "extensions": {
                    "state": "WARN",
                    "host_name": "server01"
                }
            },
            {
                "extensions": {
                    "state": "CRIT",
                    "host_name": "server02"
                }
            }
        ]
        mock_checkmk_client.list_all_services.return_value = mock_services
        
        result = service_manager.get_service_statistics()
        
        assert "Service Statistics:" in result
        assert "Total Hosts: 2" in result
        assert "Total Services: 3" in result
        assert "OK: 1" in result
        assert "WARN: 1" in result
        assert "CRIT: 1" in result
    
    def test_get_state_emoji(self, service_manager):
        """Test state emoji mapping."""
        assert service_manager._get_state_emoji("OK") == "✅"
        assert service_manager._get_state_emoji("WARN") == "⚠️"
        assert service_manager._get_state_emoji("CRIT") == "❌"
        assert service_manager._get_state_emoji("UNKNOWN") == "❓"
        assert service_manager._get_state_emoji("PENDING") == "⏳"
        assert service_manager._get_state_emoji(0) == "✅"
        assert service_manager._get_state_emoji(1) == "⚠️"
        assert service_manager._get_state_emoji(2) == "❌"
        assert service_manager._get_state_emoji(3) == "❓"
        assert service_manager._get_state_emoji("UNKNOWN_STATE") == "❓"
    
    def test_handle_api_error(self, service_manager, mock_checkmk_client):
        """Test handling API errors."""
        # Mock API error
        mock_checkmk_client.list_host_services.side_effect = CheckmkAPIError("API Error")
        
        # Mock LLM response
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "list_services",
            "parameters": {"host_name": "server01"}
        })
        
        result = service_manager.process_command("list services for server01")
        
        # Should contain the basic error message
        assert "Error listing services" in result
        assert "API Error" in result
    
    def test_handle_invalid_llm_response(self, service_manager, mock_checkmk_client):
        """Test handling invalid LLM response."""
        # Mock invalid JSON response
        service_manager.llm_client.chat_completion.return_value = "invalid json"
        
        result = service_manager.process_command("list services")
        
        assert "I don't understand how to handle the action: unknown" in result
    
    def test_handle_missing_parameters(self, service_manager, mock_checkmk_client):
        """Test handling missing parameters."""
        # Mock LLM response with missing parameters
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "acknowledge_service",
            "parameters": {
                "host_name": "server01"
                # Missing service_description
            }
        })
        
        result = service_manager.process_command("acknowledge service on server01")
        
        assert "Please specify both host name and service description" in result
    
    def test_test_connection_success(self, service_manager, mock_checkmk_client):
        """Test successful connection test."""
        mock_checkmk_client.list_all_services.return_value = [{"id": "service1"}]
        
        result = service_manager.test_connection()
        
        assert "Connection successful. Found 1 services." in result
    
    def test_test_connection_failure(self, service_manager, mock_checkmk_client):
        """Test failed connection test."""
        mock_checkmk_client.list_all_services.side_effect = CheckmkAPIError("Connection failed")
        
        result = service_manager.test_connection()
        
        # Should contain connection error message  
        assert "Connection failed" in result
    
    def test_get_instructions_add_service(self, service_manager, mock_checkmk_client):
        """Test getting instructions for adding a service."""
        # Mock LLM response for instruction request
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "get_instructions",
            "parameters": {
                "host_name": "server01",
                "instruction_type": "add_service"
            }
        })
        
        result = service_manager.process_command("how can I add a service to server01?")
        
        assert "How to add a service to server01" in result
        assert "Method 1: Service Discovery" in result
        assert "checkmk-agent services discover server01" in result
        assert "discover services on server01" in result
    
    def test_get_instructions_acknowledge_service(self, service_manager, mock_checkmk_client):
        """Test getting instructions for acknowledging services."""
        # Mock LLM response for instruction request
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "get_instructions",
            "parameters": {
                "instruction_type": "acknowledge_service"
            }
        })
        
        result = service_manager.process_command("how do I acknowledge a service?")
        
        assert "How to acknowledge a service problem" in result
        assert "Purpose:" in result
        assert "checkmk-agent services acknowledge" in result
    
    def test_get_instructions_general(self, service_manager, mock_checkmk_client):
        """Test getting general service instructions."""
        # Mock LLM response for general instruction request
        service_manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "get_instructions",
            "parameters": {
                "instruction_type": "general"
            }
        })
        
        result = service_manager.process_command("what can I do with services?")
        
        assert "Available Service Operations Instructions" in result
        assert "Service Management:" in result
        assert "Quick Commands:" in result


class TestServiceOperationsIntegration:
    """Integration tests for service operations."""
    
    @pytest.fixture
    def mock_checkmk_client(self):
        """Create a mock CheckmkClient with realistic responses."""
        client = Mock()
        
        # Mock list_host_services
        client.list_host_services.return_value = [
            {
                "id": "service1",
                "extensions": {
                    "description": "CPU utilization",
                    "state": 0,  # OK
                    "host_name": "server01",
                    "last_check": "2023-01-01T12:00:00",
                    "plugin_output": "CPU usage: 25%"
                }
            },
            {
                "id": "service2",
                "extensions": {
                    "description": "Memory utilization",
                    "state": 1,  # WARN
                    "host_name": "server01",
                    "last_check": "2023-01-01T12:00:00",
                    "plugin_output": "Memory usage: 85%"
                }
            }
        ]
        
        # Mock list_all_services
        client.list_all_services.return_value = [
            {
                "id": "service1",
                "extensions": {
                    "description": "CPU utilization",
                    "state": 0,
                    "host_name": "server01"
                }
            },
            {
                "id": "service2",
                "extensions": {
                    "description": "Disk space",
                    "state": 2,  # CRIT
                    "host_name": "server02"
                }
            }
        ]
        
        # Mock service discovery
        client.get_service_discovery_result.return_value = {
            "extensions": {
                "new": [
                    {"service_description": "Network Interface eth0"},
                    {"service_description": "Process mysqld"}
                ],
                "vanished": [
                    {"service_description": "Old Process"}
                ],
                "ignored": [
                    {"service_description": "Temp sensor"}
                ]
            }
        }
        
        return client
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLMClient with realistic responses."""
        client = Mock()
        
        # Create a side effect function that returns appropriate responses
        def mock_chat_completion(prompt):
            # Look for the actual command in the prompt
            if '"list services for server01"' in prompt:
                return json.dumps({
                    "action": "list_services",
                    "parameters": {"host_name": "server01"}
                })
            elif '"acknowledge CPU utilization on server01"' in prompt:
                return json.dumps({
                    "action": "acknowledge_service",
                    "parameters": {
                        "host_name": "server01",
                        "service_description": "CPU utilization",
                        "comment": "Investigating high CPU usage"
                    }
                })
            elif '"create 4 hour downtime for Memory utilization on server01"' in prompt:
                return json.dumps({
                    "action": "create_downtime",
                    "parameters": {
                        "host_name": "server01",
                        "service_description": "Memory utilization",
                        "duration_hours": 4,
                        "comment": "Memory maintenance"
                    }
                })
            elif '"discover services on server01"' in prompt:
                return json.dumps({
                    "action": "discover_services",
                    "parameters": {
                        "host_name": "server01",
                        "mode": "refresh"
                    }
                })
            else:
                # Default to list_services if we can't match
                return json.dumps({
                    "action": "list_services",
                    "parameters": {}
                })
        
        client.chat_completion.side_effect = mock_chat_completion
        return client
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = Mock()
        config.checkmk.username = "admin"
        return config
    
    def test_service_manager_initialization(self, mock_checkmk_client, mock_llm_client, mock_config):
        """Test that ServiceOperationsManager initializes correctly."""
        manager = ServiceOperationsManager(mock_checkmk_client, mock_llm_client, mock_config)
        
        assert manager.checkmk_client == mock_checkmk_client
        assert manager.llm_client == mock_llm_client
        assert manager.config == mock_config
        assert manager.logger is not None
    
    def test_service_operations_api_calls(self, mock_checkmk_client, mock_llm_client, mock_config):
        """Test that service operations call the correct API methods."""
        manager = ServiceOperationsManager(mock_checkmk_client, mock_llm_client, mock_config)
        
        # Test list services API call
        mock_checkmk_client.list_host_services.return_value = [
            {
                "id": "service1",
                "extensions": {
                    "description": "CPU utilization",
                    "state": "OK",
                    "host_name": "server01"
                }
            }
        ]
        
        # Mock LLM response
        manager.llm_client.chat_completion.return_value = json.dumps({
            "action": "list_services",
            "parameters": {"host_name": "server01"}
        })
        
        result = manager.process_command("list services for server01")
        
        # Verify API was called
        mock_checkmk_client.list_host_services.assert_called_once_with("server01", columns=['description', 'state', 'plugin_output'])
        assert "Found 1 services for host: server01" in result
        assert "CPU utilization" in result