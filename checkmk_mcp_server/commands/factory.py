"""Command factory for creating command instances with dependency injection."""

import logging
from typing import List, Dict, Any, Optional, Type

from .base import BaseCommand, CommandCategory
from .registry import CommandRegistry
from ..api_client import CheckmkClient
from ..service_parameters import ServiceParameterManager
from ..config import AppConfig


class CommandFactory:
    """Factory for creating command instances with dependencies."""

    def __init__(
        self,
        checkmk_client: CheckmkClient,
        config: AppConfig,
        parameter_manager: Optional[ServiceParameterManager] = None,
    ):
        """Initialize the command factory.

        Args:
            checkmk_client: Checkmk API client
            config: Application configuration
            parameter_manager: Optional service parameter manager
        """
        self.checkmk_client = checkmk_client
        self.config = config
        self.parameter_manager = parameter_manager or ServiceParameterManager(
            checkmk_client, config
        )
        self.logger = logging.getLogger(__name__)

        # Registry of command classes
        self._command_classes: Dict[str, Type[BaseCommand]] = {}
        self._initialized = False

    def register_command_class(
        self, name: str, command_class: Type[BaseCommand]
    ) -> "CommandFactory":
        """Register a command class for later instantiation.

        Args:
            name: Command identifier
            command_class: Command class to register

        Returns:
            Self for method chaining
        """
        self._command_classes[name] = command_class
        self.logger.debug(
            f"Registered command class '{name}': {command_class.__name__}"
        )
        return self

    def create_command_registry(self) -> CommandRegistry:
        """Create a command registry with all available commands.

        Returns:
            Configured CommandRegistry instance
        """
        registry = CommandRegistry()

        # Create and register all commands
        service_commands = self.create_service_commands()
        parameter_commands = self.create_parameter_commands()
        utility_commands = self.create_utility_commands()

        all_commands = service_commands + parameter_commands + utility_commands

        for command in all_commands:
            try:
                registry.register(command)
                self.logger.debug(f"Registered command: {command.name}")
            except ValueError as e:
                self.logger.error(f"Failed to register command {command.name}: {e}")

        self.logger.info(f"Created command registry with {len(registry)} commands")
        return registry

    def create_service_commands(self) -> List[BaseCommand]:
        """Create all service-related commands.

        Returns:
            List of service command instances
        """
        # Import here to avoid circular imports
        from .service_commands import (
            ListServicesCommand,
            GetServiceStatusCommand,
            AcknowledgeServiceCommand,
            CreateDowntimeCommand,
            DiscoverServicesCommand,
            GetServiceStatisticsCommand,
        )

        commands = [
            ListServicesCommand(self.checkmk_client),
            GetServiceStatusCommand(self.checkmk_client),
            AcknowledgeServiceCommand(self.checkmk_client),
            CreateDowntimeCommand(self.checkmk_client),
            DiscoverServicesCommand(self.checkmk_client),
            GetServiceStatisticsCommand(self.checkmk_client),
        ]

        # Add aliases for common variations
        commands[0].add_alias("show_services").add_alias("get_services")
        commands[1].add_alias("service_status").add_alias("check_service")
        commands[2].add_alias("ack_service").add_alias("acknowledge")
        commands[3].add_alias("schedule_downtime").add_alias("downtime")
        commands[4].add_alias("service_discovery").add_alias("discover")
        commands[5].add_alias("service_stats").add_alias("stats")

        return commands

    def create_parameter_commands(self) -> List[BaseCommand]:
        """Create all parameter-related commands.

        Returns:
            List of parameter command instances
        """
        # Import here to avoid circular imports
        from .parameter_commands import (
            ViewDefaultParametersCommand,
            ViewServiceParametersCommand,
            SetServiceParametersCommand,
            CreateParameterRuleCommand,
            ListParameterRulesCommand,
            DeleteParameterRuleCommand,
            DiscoverRulesetCommand,
        )

        commands = [
            ViewDefaultParametersCommand(self.parameter_manager),
            ViewServiceParametersCommand(self.parameter_manager),
            SetServiceParametersCommand(self.parameter_manager),
            CreateParameterRuleCommand(self.parameter_manager),
            ListParameterRulesCommand(self.parameter_manager),
            DeleteParameterRuleCommand(self.parameter_manager),
            DiscoverRulesetCommand(self.parameter_manager),
        ]

        # Add aliases
        commands[0].add_alias("show_default_parameters").add_alias("default_parameters")
        commands[1].add_alias("show_service_parameters").add_alias("service_parameters")
        commands[2].add_alias("override_parameters").add_alias("set_parameters")
        commands[3].add_alias("create_rule")
        commands[4].add_alias("show_rules").add_alias("list_rules")
        commands[5].add_alias("delete_rule")
        commands[6].add_alias("find_ruleset")

        return commands

    def create_utility_commands(self) -> List[BaseCommand]:
        """Create all utility commands.

        Returns:
            List of utility command instances
        """
        # Import here to avoid circular imports
        from .utility_commands import (
            GetInstructionsCommand,
            ConnectionTestCommand,
            HelpCommand,
        )

        commands = [
            GetInstructionsCommand(),
            ConnectionTestCommand(self.checkmk_client),
            HelpCommand(),
        ]

        # Add aliases
        commands[0].add_alias("instructions").add_alias("how_to")
        commands[1].add_alias("test").add_alias("ping")
        commands[2].add_alias("?").add_alias("help")

        return commands

    def create_command(self, command_name: str, **kwargs) -> Optional[BaseCommand]:
        """Create a specific command by name.

        Args:
            command_name: Name of command to create
            **kwargs: Additional arguments for command creation

        Returns:
            Command instance if successful, None if command not found
        """
        if command_name not in self._command_classes:
            self.logger.warning(f"Unknown command class: {command_name}")
            return None

        command_class = self._command_classes[command_name]

        try:
            # Determine dependencies based on command category/type
            if hasattr(command_class, "_requires_checkmk_client"):
                kwargs["checkmk_client"] = self.checkmk_client

            if hasattr(command_class, "_requires_parameter_manager"):
                kwargs["parameter_manager"] = self.parameter_manager

            if hasattr(command_class, "_requires_config"):
                kwargs["config"] = self.config

            return command_class(**kwargs)

        except Exception as e:
            self.logger.error(f"Failed to create command '{command_name}': {e}")
            return None

    def get_available_commands(self) -> Dict[str, str]:
        """Get list of available command classes.

        Returns:
            Dictionary mapping command names to class names
        """
        return {name: cls.__name__ for name, cls in self._command_classes.items()}

    def validate_dependencies(self) -> List[str]:
        """Validate that all required dependencies are available.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.checkmk_client is None:
            errors.append("CheckmkClient is required but not provided")

        if self.config is None:
            errors.append("AppConfig is required but not provided")

        # Test API client connection
        try:
            if self.checkmk_client and not self.checkmk_client.test_connection():
                errors.append("CheckmkClient connection test failed")
        except Exception as e:
            errors.append(f"CheckmkClient validation error: {e}")

        return errors

    def get_factory_info(self) -> Dict[str, Any]:
        """Get information about the factory configuration.

        Returns:
            Dictionary with factory information
        """
        return {
            "checkmk_client": (
                self.checkmk_client.__class__.__name__ if self.checkmk_client else None
            ),
            "parameter_manager": (
                self.parameter_manager.__class__.__name__
                if self.parameter_manager
                else None
            ),
            "config_available": self.config is not None,
            "registered_command_classes": len(self._command_classes),
            "available_commands": list(self._command_classes.keys()),
        }
