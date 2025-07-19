"""Enhanced service operations manager using the new command architecture.

This module provides a drop-in replacement for the original service_operations.py
that uses the new command-based architecture while maintaining full backward compatibility.
"""

import logging
from typing import Dict, Any

from .api_client import CheckmkClient
from .llm_client import LLMClient
from .config import AppConfig
from .service_parameters import ServiceParameterManager
from .commands import ServiceOperationsFacade, BackwardCompatibilityWrapper


class ServiceOperationsManager:
    """Enhanced service operations manager using command-based architecture.
    
    This class provides the same interface as the original ServiceOperationsManager
    but uses the new command system underneath for better maintainability,
    testability, and extensibility.
    """
    
    def __init__(self, checkmk_client: CheckmkClient, llm_client: LLMClient, config: AppConfig):
        """Initialize the service operations manager.
        
        Args:
            checkmk_client: Checkmk API client
            llm_client: LLM client for natural language processing
            config: Application configuration
        """
        self.checkmk_client = checkmk_client
        self.llm_client = llm_client
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize the new command-based facade
        self.facade = ServiceOperationsFacade(checkmk_client, llm_client, config)
        
        # Create backward compatibility wrapper
        self.wrapper = BackwardCompatibilityWrapper(self.facade)
        
        # Expose wrapped methods for compatibility
        self.parameter_manager = self.wrapper.parameter_manager
        
        self.logger.info("Initialized enhanced ServiceOperationsManager with command architecture")
    
    def process_command(self, command: str) -> str:
        """Process a natural language command related to services.
        
        This method maintains the exact same interface as the original implementation
        but uses the new command-based architecture underneath.
        
        Args:
            command: The user's command
            
        Returns:
            Human-readable response
        """
        return self.wrapper.process_command(command)
    
    def get_service_statistics(self) -> str:
        """Get service statistics across all hosts.
        
        Returns:
            Formatted service statistics
        """
        return self.wrapper.get_service_statistics()
    
    def test_connection(self) -> str:
        """Test connection by listing services.
        
        Returns:
            Connection test result
        """
        return self.wrapper.test_connection()
    
    def _get_state_emoji(self, state: str) -> str:
        """Get emoji for service state (backward compatibility).
        
        Args:
            state: Service state
            
        Returns:
            Emoji representing the state
        """
        return self.wrapper._get_state_emoji(state)
    
    # Enhanced methods using new architecture
    
    def get_available_commands(self) -> Dict[str, Any]:
        """Get information about available commands.
        
        Returns:
            Dictionary with command information organized by category
        """
        return self.facade.get_available_commands()
    
    def validate_system(self) -> Dict[str, Any]:
        """Validate the command system integrity.
        
        Returns:
            Dictionary with validation results
        """
        return self.facade.validate_system()
    
    def clear_cache(self) -> None:
        """Clear the command analysis cache."""
        self.facade.clear_cache()
    
    def get_command_help(self, command_name: str) -> str:
        """Get help text for a specific command.
        
        Args:
            command_name: Name of command to get help for
            
        Returns:
            Help text or error message
        """
        help_text = self.facade.get_command_help(command_name)
        if help_text:
            return help_text
        else:
            suggestions = self.facade.registry.find_similar_commands(command_name)
            error_msg = f"❌ Unknown command: {command_name}"
            if suggestions:
                error_msg += f"\n\nDid you mean: {', '.join(suggestions)}"
            return error_msg
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information.
        
        Returns:
            Dictionary with system information
        """
        validation_results = self.validate_system()
        command_info = self.get_available_commands()
        
        return {
            'version': '2.0',
            'architecture': 'command-based',
            'total_commands': command_info['total_commands'],
            'commands_by_category': command_info['commands_by_category'],
            'registry_stats': command_info['registry_stats'],
            'analyzer_stats': command_info['analyzer_stats'],
            'validation': validation_results,
            'is_healthy': validation_results['is_valid']
        }
    
    def list_commands_by_category(self, category: str = None) -> Dict[str, Any]:
        """List commands by category.
        
        Args:
            category: Optional category filter
            
        Returns:
            Dictionary with command listings
        """
        available_commands = self.get_available_commands()
        
        if category:
            if category in available_commands['commands_by_category']:
                return {
                    'category': category,
                    'commands': available_commands['commands_by_category'][category]
                }
            else:
                available_categories = list(available_commands['commands_by_category'].keys())
                return {
                    'error': f"Unknown category: {category}",
                    'available_categories': available_categories
                }
        else:
            return available_commands['commands_by_category']
    
    def execute_command_directly(self, command_name: str, parameters: Dict[str, Any]) -> str:
        """Execute a command directly by name with specified parameters.
        
        This method bypasses natural language processing and executes a command
        directly with the provided parameters. Useful for programmatic access.
        
        Args:
            command_name: Name of command to execute
            parameters: Command parameters
            
        Returns:
            Command execution result
        """
        from .commands.base import CommandContext
        
        command = self.facade.registry.get_command(command_name)
        if not command:
            return f"❌ Unknown command: {command_name}"
        
        try:
            context = CommandContext(
                user_input=f"Direct execution of {command_name}",
                parsed_parameters=parameters
            )
            
            # Validate parameters
            validation_result = command.validate(context)
            if not validation_result.success:
                return f"❌ Validation failed: {validation_result.error}"
            
            # Execute command
            result = command.execute(context)
            
            if result.success:
                return result.message or "✅ Command executed successfully"
            else:
                return f"❌ Execution failed: {result.error}"
                
        except Exception as e:
            self.logger.error(f"Error executing command {command_name}: {e}")
            return f"❌ Error executing command: {e}"
    
    # Maintain original private methods for any legacy code that might access them
    
    def _analyze_command(self, command: str) -> Dict[str, Any]:
        """Analyze command using new architecture (legacy compatibility).
        
        Args:
            command: User command
            
        Returns:
            Analysis result in original format
        """
        analysis = self.facade.analyzer.analyze_command(command)
        return {
            'action': analysis.action,
            'parameters': analysis.parameters
        }
    
    def _handle_list_services(self, analysis: Dict[str, Any]) -> str:
        """Handle list services (legacy method)."""
        return self.execute_command_directly('list_services', analysis.get('parameters', {}))
    
    def _handle_get_service_status(self, analysis: Dict[str, Any]) -> str:
        """Handle get service status (legacy method)."""
        return self.execute_command_directly('get_service_status', analysis.get('parameters', {}))
    
    def _handle_acknowledge_service(self, analysis: Dict[str, Any]) -> str:
        """Handle acknowledge service (legacy method)."""
        return self.execute_command_directly('acknowledge_service', analysis.get('parameters', {}))
    
    def _handle_create_downtime(self, analysis: Dict[str, Any]) -> str:
        """Handle create downtime (legacy method)."""
        return self.execute_command_directly('create_downtime', analysis.get('parameters', {}))
    
    def _handle_discover_services(self, analysis: Dict[str, Any]) -> str:
        """Handle discover services (legacy method)."""
        return self.execute_command_directly('discover_services', analysis.get('parameters', {}))
    
    def _handle_get_instructions(self, analysis: Dict[str, Any]) -> str:
        """Handle get instructions (legacy method)."""
        return self.execute_command_directly('get_instructions', analysis.get('parameters', {}))
    
    def __repr__(self) -> str:
        return f"ServiceOperationsManager(v2.0, commands={len(self.facade.registry)})"