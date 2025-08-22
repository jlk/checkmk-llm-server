"""Base command interfaces and data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class CommandCategory(Enum):
    """Categories for organizing commands."""

    SERVICE = "service"
    PARAMETER = "parameter"
    HOST = "host"
    RULE = "rule"
    UTILITY = "utility"


@dataclass
class CommandContext:
    """Context information for command execution."""

    user_input: str
    parsed_parameters: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_llm_response: Optional[Dict[str, Any]] = None

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get parameter value with optional default."""
        return self.parsed_parameters.get(key, default)

    def has_parameter(self, key: str) -> bool:
        """Check if parameter exists."""
        return key in self.parsed_parameters

    def require_parameter(self, key: str) -> Any:
        """Get required parameter, raise ValueError if missing."""
        if key not in self.parsed_parameters:
            raise ValueError(f"Required parameter '{key}' not provided")
        return self.parsed_parameters[key]


@dataclass
class CommandResult:
    """Result of command execution."""

    success: bool
    data: Any = None
    message: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(cls, data: Any = None, message: str = "") -> "CommandResult":
        """Create a successful result."""
        return cls(success=True, data=data, message=message)

    @classmethod
    def error_result(cls, error: str, data: Any = None) -> "CommandResult":
        """Create an error result."""
        return cls(success=False, error=error, data=data)

    def with_metadata(self, **metadata) -> "CommandResult":
        """Add metadata to the result."""
        self.metadata.update(metadata)
        return self


class BaseCommand(ABC):
    """Abstract base class for all commands."""

    def __init__(self):
        self._aliases: List[str] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable command description."""
        pass

    @property
    @abstractmethod
    def category(self) -> CommandCategory:
        """Command category for organization."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Expected parameters and their specifications.

        Returns:
            Dictionary with parameter specifications:
            {
                'param_name': {
                    'type': str,  # Expected type
                    'required': bool,  # Whether required
                    'description': str,  # Parameter description
                    'default': Any,  # Default value if not required
                }
            }
        """
        pass

    @property
    def aliases(self) -> List[str]:
        """Alternative names for this command."""
        return self._aliases

    def add_alias(self, alias: str) -> "BaseCommand":
        """Add an alias for this command."""
        if alias not in self._aliases:
            self._aliases.append(alias)
        return self

    def validate(self, context: CommandContext) -> CommandResult:
        """Validate command parameters.

        Args:
            context: Command execution context

        Returns:
            CommandResult indicating validation success/failure
        """
        try:
            # Check required parameters
            for param_name, param_spec in self.parameters.items():
                if param_spec.get("required", False):
                    if not context.has_parameter(param_name):
                        return CommandResult.error_result(
                            f"Required parameter '{param_name}' not provided"
                        )

                # Type checking if parameter is provided
                if context.has_parameter(param_name):
                    expected_type = param_spec.get("type")
                    if expected_type:
                        value = context.get_parameter(param_name)
                        if not isinstance(value, expected_type) and value is not None:
                            return CommandResult.error_result(
                                f"Parameter '{param_name}' must be of type {expected_type.__name__}"
                            )

            # Allow subclasses to add custom validation
            custom_validation = self._custom_validate(context)
            if custom_validation and not custom_validation.success:
                return custom_validation

            return CommandResult.success_result()

        except Exception as e:
            return CommandResult.error_result(f"Validation error: {e}")

    def _custom_validate(self, context: CommandContext) -> Optional[CommandResult]:
        """Override for command-specific validation logic.

        Args:
            context: Command execution context

        Returns:
            CommandResult if validation fails, None if validation passes
        """
        return None

    @abstractmethod
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the command.

        Args:
            context: Command execution context

        Returns:
            CommandResult with execution results
        """
        pass

    def get_help_text(self) -> str:
        """Generate help text for this command."""
        help_text = f"**{self.name}** - {self.description}\n\n"

        if self.aliases:
            help_text += f"**Aliases:** {', '.join(self.aliases)}\n\n"

        if self.parameters:
            help_text += "**Parameters:**\n"
            for param_name, param_spec in self.parameters.items():
                required_text = (
                    "Required" if param_spec.get("required", False) else "Optional"
                )
                param_type = param_spec.get("type", object).__name__
                description = param_spec.get("description", "No description")
                default = param_spec.get("default")

                help_text += (
                    f"- `{param_name}` ({param_type}, {required_text}): {description}"
                )
                if default is not None:
                    help_text += f" (default: {default})"
                help_text += "\n"

        return help_text

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', category='{self.category.value}')"
