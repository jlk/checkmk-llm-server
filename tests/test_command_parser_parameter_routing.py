"""Test command parser routing for parameter-related commands."""

import pytest
from checkmk_agent.interactive.command_parser import CommandParser


class TestCommandParserParameterRouting:
    """Test cases for parameter command routing fixes."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CommandParser()
    
    def test_parameter_commands_route_to_service(self):
        """Test that parameter-related commands are routed to service operations."""
        parameter_commands = [
            'show parameters for "Temperature Zone 0" on piaware',
            'show parameters for CPU on server01',
            'set parameters for memory on server01',
            'view thresholds for disk on server01',
            'set threshold for CPU on server01',
            'override parameter values for memory',
            'what are the threshold values for server01',
            'show parameter configuration for CPU'
        ]
        
        for command in parameter_commands:
            intent = self.parser.parse_command(command)
            command_type = self.parser.get_command_type(intent.command, intent.parameters, command)
            
            assert command_type == 'service', (
                f"Command '{command}' should route to service operations, "
                f"but was routed to '{command_type}'"
            )
    
    def test_host_commands_still_route_to_host(self):
        """Test that host commands are still correctly routed to host operations."""
        host_commands = [
            'list hosts',
            'show all hosts',
            'create host server01',
            'delete host server01',
            'get host details for server01'
        ]
        
        for command in host_commands:
            intent = self.parser.parse_command(command)
            command_type = self.parser.get_command_type(intent.command, intent.parameters, command)
            
            assert command_type == 'host', (
                f"Command '{command}' should route to host operations, "
                f"but was routed to '{command_type}'"
            )
    
    def test_service_commands_without_parameters_route_to_service(self):
        """Test that other service commands are still correctly routed."""
        service_commands = [
            'list services for server01',
            'acknowledge CPU load on server01',
            'create downtime for disk space on server01',
            'discover services on server01'
        ]
        
        for command in service_commands:
            intent = self.parser.parse_command(command)
            command_type = self.parser.get_command_type(intent.command, intent.parameters, command)
            
            assert command_type == 'service', (
                f"Command '{command}' should route to service operations, "
                f"but was routed to '{command_type}'"
            )
    
    def test_original_problematic_command(self):
        """Test the specific command that was reported as problematic."""
        command = 'show parameters for "Temperature Zone 0" on piaware'
        
        intent = self.parser.parse_command(command)
        command_type = self.parser.get_command_type(intent.command, intent.parameters, command)
        
        assert command_type == 'service', (
            f"The original problematic command '{command}' should now route to "
            f"service operations, but was routed to '{command_type}'"
        )
        
        # Verify it's parsed as a 'list' command (which is correct for 'show')
        assert intent.command == 'list', (
            f"Command should be parsed as 'list', but was parsed as '{intent.command}'"
        )
        
        # Verify parameter extraction works correctly
        assert intent.parameters.get('service_description') == 'temperature zone 0', (
            f"Expected service_description 'temperature zone 0', got '{intent.parameters.get('service_description')}'"
        )
        assert intent.parameters.get('host_name') == 'piaware', (
            f"Expected host_name 'piaware', got '{intent.parameters.get('host_name')}'"
        )
    
    def test_parameter_extraction_patterns(self):
        """Test various parameter extraction patterns."""
        test_cases = [
            ('show parameters for CPU on server01', 'CPU utilization', 'server01'),
            ('view thresholds for "Filesystem /" on server01', 'filesystem /', 'server01'),
            ('show parameter values for memory on server01', 'Memory', 'server01'),
            ('show parameters for disk space for server01', 'Filesystem /', 'server01'),
        ]
        
        for command, expected_service, expected_host in test_cases:
            intent = self.parser.parse_command(command)
            
            actual_service = intent.parameters.get('service_description', '').lower()
            actual_host = intent.parameters.get('host_name', '')
            
            assert actual_service == expected_service.lower(), (
                f"Command '{command}': expected service '{expected_service}', got '{actual_service}'"
            )
            assert actual_host == expected_host, (
                f"Command '{command}': expected host '{expected_host}', got '{actual_host}'"
            )