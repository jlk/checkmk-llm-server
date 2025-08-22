"""Command registry for managing available commands."""

import logging
from typing import Dict, List, Optional, Set
from collections import defaultdict

from .base import BaseCommand, CommandCategory


class CommandRegistry:
    """Registry for managing available commands."""

    def __init__(self):
        self._commands: Dict[str, BaseCommand] = {}
        self._aliases: Dict[str, str] = {}
        self._categories: Dict[CommandCategory, List[str]] = defaultdict(list)
        self.logger = logging.getLogger(__name__)

    def register(
        self, command: BaseCommand, aliases: Optional[List[str]] = None
    ) -> "CommandRegistry":
        """Register a command with optional aliases.

        Args:
            command: Command instance to register
            aliases: Optional list of command aliases

        Returns:
            Self for method chaining

        Raises:
            ValueError: If command name or alias conflicts with existing registration
        """
        # Check for name conflicts
        if command.name in self._commands:
            raise ValueError(f"Command '{command.name}' is already registered")

        if command.name in self._aliases:
            raise ValueError(
                f"Command name '{command.name}' conflicts with existing alias"
            )

        # Check for alias conflicts
        all_aliases = (aliases or []) + command.aliases
        for alias in all_aliases:
            if alias in self._commands:
                raise ValueError(
                    f"Alias '{alias}' conflicts with existing command name"
                )
            if alias in self._aliases:
                raise ValueError(f"Alias '{alias}' is already registered")

        # Register the command
        self._commands[command.name] = command
        self._categories[command.category].append(command.name)

        # Register aliases
        for alias in all_aliases:
            self._aliases[alias] = command.name

        self.logger.debug(
            f"Registered command '{command.name}' with {len(all_aliases)} aliases"
        )
        return self

    def unregister(self, command_name: str) -> bool:
        """Unregister a command and its aliases.

        Args:
            command_name: Name of command to unregister

        Returns:
            True if command was unregistered, False if not found
        """
        if command_name not in self._commands:
            return False

        command = self._commands[command_name]

        # Remove from commands
        del self._commands[command_name]

        # Remove from category
        if command_name in self._categories[command.category]:
            self._categories[command.category].remove(command_name)

        # Remove aliases
        aliases_to_remove = [
            alias
            for alias, cmd_name in self._aliases.items()
            if cmd_name == command_name
        ]
        for alias in aliases_to_remove:
            del self._aliases[alias]

        self.logger.debug(
            f"Unregistered command '{command_name}' and {len(aliases_to_remove)} aliases"
        )
        return True

    def get_command(self, name: str) -> Optional[BaseCommand]:
        """Get command by name or alias.

        Args:
            name: Command name or alias

        Returns:
            Command instance if found, None otherwise
        """
        # Check direct name first
        if name in self._commands:
            return self._commands[name]

        # Check aliases
        if name in self._aliases:
            return self._commands[self._aliases[name]]

        return None

    def has_command(self, name: str) -> bool:
        """Check if command exists by name or alias.

        Args:
            name: Command name or alias

        Returns:
            True if command exists, False otherwise
        """
        return name in self._commands or name in self._aliases

    def list_commands(
        self, category: Optional[CommandCategory] = None
    ) -> List[BaseCommand]:
        """List all registered commands, optionally by category.

        Args:
            category: Optional category filter

        Returns:
            List of command instances
        """
        if category is None:
            return list(self._commands.values())

        command_names = self._categories.get(category, [])
        return [self._commands[name] for name in command_names]

    def list_command_names(
        self, category: Optional[CommandCategory] = None
    ) -> List[str]:
        """List command names, optionally by category.

        Args:
            category: Optional category filter

        Returns:
            List of command names
        """
        if category is None:
            return list(self._commands.keys())

        return self._categories.get(category, []).copy()

    def get_command_names_and_aliases(self) -> Set[str]:
        """Get all command names and aliases.

        Returns:
            Set of all valid command names and aliases
        """
        return set(self._commands.keys()) | set(self._aliases.keys())

    def find_similar_commands(self, name: str, max_suggestions: int = 3) -> List[str]:
        """Find commands with similar names for suggestions.

        Args:
            name: Command name to find similar matches for
            max_suggestions: Maximum number of suggestions to return

        Returns:
            List of similar command names
        """
        name_lower = name.lower()
        all_names = self.get_command_names_and_aliases()

        # Find commands that contain the search term
        containing = [cmd for cmd in all_names if name_lower in cmd.lower()]

        # Find commands that start with the search term
        starting = [cmd for cmd in all_names if cmd.lower().startswith(name_lower)]

        # Combine and deduplicate, prioritizing exact starts
        suggestions = list(dict.fromkeys(starting + containing))

        return suggestions[:max_suggestions]

    def get_categories(self) -> List[CommandCategory]:
        """Get all categories that have registered commands.

        Returns:
            List of categories with commands
        """
        return [category for category, commands in self._categories.items() if commands]

    def get_registry_stats(self) -> Dict[str, int]:
        """Get statistics about the registry.

        Returns:
            Dictionary with registry statistics
        """
        return {
            "total_commands": len(self._commands),
            "total_aliases": len(self._aliases),
            "categories": len(self.get_categories()),
            "service_commands": len(self._categories[CommandCategory.SERVICE]),
            "parameter_commands": len(self._categories[CommandCategory.PARAMETER]),
            "host_commands": len(self._categories[CommandCategory.HOST]),
            "rule_commands": len(self._categories[CommandCategory.RULE]),
            "utility_commands": len(self._categories[CommandCategory.UTILITY]),
        }

    def validate_registry(self) -> List[str]:
        """Validate the registry for consistency issues.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for orphaned aliases
        for alias, command_name in self._aliases.items():
            if command_name not in self._commands:
                errors.append(
                    f"Alias '{alias}' points to non-existent command '{command_name}'"
                )

        # Check for category consistency
        for category, command_names in self._categories.items():
            for command_name in command_names:
                if command_name not in self._commands:
                    errors.append(
                        f"Category '{category.value}' contains non-existent command '{command_name}'"
                    )
                elif self._commands[command_name].category != category:
                    errors.append(f"Command '{command_name}' category mismatch")

        return errors

    def clear(self) -> None:
        """Clear all registered commands."""
        self._commands.clear()
        self._aliases.clear()
        self._categories.clear()
        self.logger.debug("Cleared all registered commands")

    def __len__(self) -> int:
        """Return number of registered commands."""
        return len(self._commands)

    def __contains__(self, name: str) -> bool:
        """Check if command exists (supports 'in' operator)."""
        return self.has_command(name)

    def __repr__(self) -> str:
        stats = self.get_registry_stats()
        return f"CommandRegistry(commands={stats['total_commands']}, aliases={stats['total_aliases']})"
