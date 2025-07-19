"""Service operations facade integrating the new command system."""

import logging
from typing import Optional, Dict, Any

from .base import CommandContext, CommandResult
from .registry import CommandRegistry
from .analyzer import LLMCommandAnalyzer, AnalysisResult
from .factory import CommandFactory
from ..api_client import CheckmkClient
from ..llm_client import LLMClient
from ..config import AppConfig
from ..service_parameters import ServiceParameterManager


class ServiceOperationsFacade:
    """Simplified facade for service operations using the new command architecture."""
    
    def __init__(self, 
                 checkmk_client: CheckmkClient,
                 llm_client: LLMClient,
                 config: AppConfig):
        """Initialize the facade.
        
        Args:
            checkmk_client: Checkmk API client
            llm_client: LLM client for command analysis
            config: Application configuration
        """
        self.checkmk_client = checkmk_client
        self.llm_client = llm_client
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.parameter_manager = ServiceParameterManager(checkmk_client, config)
        self.factory = CommandFactory(checkmk_client, config, self.parameter_manager)
        self.registry = self.factory.create_command_registry()
        self.analyzer = LLMCommandAnalyzer(llm_client)
        
        # Action mapping for backward compatibility
        self._action_mapping = self._build_action_mapping()
        
        self.logger.info(f"Initialized facade with {len(self.registry)} commands")
    
    def _build_action_mapping(self) -> Dict[str, str]:
        """Build action mapping for backward compatibility with old system."""
        return {
            # Original mappings from service_operations.py
            'list_services': 'list_services',
            'show_services': 'list_services',
            'get_services': 'list_services',
            'get_service_status': 'get_service_status',
            'service_status': 'get_service_status',
            'check_service': 'get_service_status',
            'acknowledge_service': 'acknowledge_service',
            'ack_service': 'acknowledge_service',
            'acknowledge': 'acknowledge_service',
            'create_downtime': 'create_downtime',
            'schedule_downtime': 'create_downtime',
            'downtime': 'create_downtime',
            'discover_services': 'discover_services',
            'service_discovery': 'discover_services',
            'discover': 'discover_services',
            'get_instructions': 'get_instructions',
            'instructions': 'get_instructions',
            'help': 'help',
            'how_to': 'get_instructions',
            
            # Parameter operations
            'view_default_parameters': 'view_default_parameters',
            'show_default_parameters': 'view_default_parameters',
            'default_parameters': 'view_default_parameters',
            'view_service_parameters': 'view_service_parameters',
            'show_service_parameters': 'view_service_parameters',
            'service_parameters': 'view_service_parameters',
            'show_parameters': 'view_service_parameters',
            'set_service_parameters': 'set_service_parameters',
            'override_parameters': 'set_service_parameters',
            'set_parameters': 'set_service_parameters',
            'override_service': 'set_service_parameters',
            'create_parameter_rule': 'create_parameter_rule',
            'create_rule': 'create_parameter_rule',
            'list_parameter_rules': 'list_parameter_rules',
            'show_rules': 'list_parameter_rules',
            'list_rules': 'list_parameter_rules',
            'delete_parameter_rule': 'delete_parameter_rule',
            'delete_rule': 'delete_parameter_rule',
            'discover_ruleset': 'discover_ruleset',
            'find_ruleset': 'discover_ruleset',
            
            # Utility operations
            'test_connection': 'test_connection',
            'test': 'test_connection',
            'ping': 'test_connection',
            'get_service_statistics': 'get_service_statistics',
            'service_stats': 'get_service_statistics',
            'stats': 'get_service_statistics'
        }
    
    def process_command(self, user_input: str) -> str:
        """Process a natural language command using the new architecture.
        
        This method maintains compatibility with the original ServiceOperationsManager.process_command()
        while using the new command-based architecture underneath.
        
        Args:
            user_input: The user's command
            
        Returns:
            Human-readable response
        """
        try:
            # Analyze the command
            analysis = self.analyzer.analyze_command(user_input)
            
            # Log analysis results
            self.logger.debug(f"Command analysis: {analysis.action} from {analysis.source}")
            
            # Normalize action using backward compatibility mapping
            normalized_action = self._action_mapping.get(analysis.action, analysis.action)
            
            # Get the appropriate command
            command = self.registry.get_command(normalized_action)
            if not command:
                return self._handle_unknown_command(analysis.action, normalized_action)
            
            # Create command context
            context = CommandContext(
                user_input=user_input,
                parsed_parameters=analysis.parameters,
                raw_llm_response={'action': analysis.action, 'parameters': analysis.parameters}
            )
            
            # Validate command parameters
            validation_result = command.validate(context)
            if not validation_result.success:
                return f"❌ {validation_result.error}"
            
            # Execute the command
            result = command.execute(context)
            
            # Return formatted response
            if result.success:
                return result.message or "✅ Command executed successfully"
            else:
                return f"❌ {result.error}"
            
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return f"❌ Error processing command: {e}"
    
    def _handle_unknown_command(self, original_action: str, normalized_action: str) -> str:
        """Handle unknown command with suggestions.
        
        Args:
            original_action: Original action from analysis
            normalized_action: Normalized action after mapping
            
        Returns:
            Error message with suggestions
        """
        # Find similar commands
        suggestions = self.registry.find_similar_commands(original_action, max_suggestions=3)
        
        error_msg = f"❌ I don't understand how to handle the action: {original_action}"
        
        if normalized_action != original_action:
            error_msg += f" (normalized: {normalized_action})"
        
        if suggestions:
            error_msg += f"\n\nDid you mean one of these?\n"
            for suggestion in suggestions:
                error_msg += f"  • {suggestion}\n"
        
        # Show available actions
        service_commands = [cmd.name for cmd in self.registry.list_commands()]
        error_msg += f"\nAvailable commands: {', '.join(service_commands[:10])}"
        if len(service_commands) > 10:
            error_msg += f" (and {len(service_commands) - 10} more)"
        
        return error_msg
    
    def get_service_statistics(self) -> str:
        """Get service statistics (backward compatibility method)."""
        try:
            command = self.registry.get_command('get_service_statistics')
            if command:
                context = CommandContext("get service statistics", {})
                result = command.execute(context)
                return result.message if result.success else f"❌ {result.error}"
            else:
                return "❌ Service statistics command not available"
        except Exception as e:
            return f"❌ Error getting service statistics: {e}"
    
    def test_connection(self) -> str:
        """Test connection (backward compatibility method)."""
        try:
            command = self.registry.get_command('test_connection')
            if command:
                context = CommandContext("test connection", {})
                result = command.execute(context)
                return result.message if result.success else f"❌ {result.error}"
            else:
                return "❌ Test connection command not available"
        except Exception as e:
            return f"❌ Error testing connection: {e}"
    
    def get_available_commands(self) -> Dict[str, Any]:
        """Get information about available commands.
        
        Returns:
            Dictionary with command information
        """
        commands_by_category = {}
        for category in self.registry.get_categories():
            commands = self.registry.list_commands(category)
            commands_by_category[category.value] = [
                {
                    'name': cmd.name,
                    'description': cmd.description,
                    'aliases': cmd.aliases,
                    'parameters': list(cmd.parameters.keys())
                }
                for cmd in commands
            ]
        
        return {
            'total_commands': len(self.registry),
            'commands_by_category': commands_by_category,
            'registry_stats': self.registry.get_registry_stats(),
            'analyzer_stats': self.analyzer.get_cache_stats()
        }
    
    def validate_system(self) -> Dict[str, Any]:
        """Validate the command system.
        
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'registry_errors': self.registry.validate_registry(),
            'factory_errors': self.factory.validate_dependencies(),
            'command_count': len(self.registry),
            'cache_stats': self.analyzer.get_cache_stats()
        }
        
        validation_results['is_valid'] = (
            len(validation_results['registry_errors']) == 0 and
            len(validation_results['factory_errors']) == 0
        )
        
        return validation_results
    
    def clear_cache(self) -> None:
        """Clear analyzer cache."""
        self.analyzer.clear_cache()
        self.logger.info("Cleared command analyzer cache")
    
    def get_command_help(self, command_name: str) -> Optional[str]:
        """Get help text for a specific command.
        
        Args:
            command_name: Name of command to get help for
            
        Returns:
            Help text if command exists, None otherwise
        """
        command = self.registry.get_command(command_name)
        if command:
            return command.get_help_text()
        return None
    
    def __repr__(self) -> str:
        return (f"ServiceOperationsFacade(commands={len(self.registry)}, "
                f"cache_entries={len(self.analyzer._cache)})")


class BackwardCompatibilityWrapper:
    """Wrapper to maintain exact compatibility with the original ServiceOperationsManager."""
    
    def __init__(self, facade: ServiceOperationsFacade):
        """Initialize wrapper with facade.
        
        Args:
            facade: ServiceOperationsFacade instance
        """
        self.facade = facade
        self.checkmk_client = facade.checkmk_client
        self.llm_client = facade.llm_client
        self.config = facade.config
        self.logger = facade.logger
        self.parameter_manager = facade.parameter_manager
    
    def process_command(self, command: str) -> str:
        """Process command (exact API compatibility)."""
        return self.facade.process_command(command)
    
    def get_service_statistics(self) -> str:
        """Get service statistics (exact API compatibility)."""
        return self.facade.get_service_statistics()
    
    def test_connection(self) -> str:
        """Test connection (exact API compatibility)."""
        return self.facade.test_connection()
    
    def _get_state_emoji(self, state: str) -> str:
        """Get emoji for service state (backward compatibility)."""
        state_map = {
            'OK': '✅',
            'WARN': '⚠️',
            'WARNING': '⚠️',
            'CRIT': '❌',
            'CRITICAL': '❌',
            'UNKNOWN': '❓',
            'PENDING': '⏳',
            0: '✅',  # OK
            1: '⚠️',  # WARN
            2: '❌',  # CRIT
            3: '❓',  # UNKNOWN
        }
        return state_map.get(state, '❓')