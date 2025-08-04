"""Tests for the new command system."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from checkmk_agent.commands.base import (
    BaseCommand,
    CommandContext,
    CommandResult,
    CommandCategory,
)
from checkmk_agent.commands.registry import CommandRegistry
from checkmk_agent.commands.factory import CommandFactory
from checkmk_agent.commands.service_commands import (
    ListServicesCommand,
    GetServiceStatusCommand,
    AcknowledgeServiceCommand,
)
from checkmk_agent.commands.parameter_commands import ViewDefaultParametersCommand
from checkmk_agent.commands.utility_commands import ConnectionTestCommand, HelpCommand
from checkmk_agent.api_client import CheckmkAPIError


class TestBaseCommand:
    """Test the BaseCommand abstract class and related data structures."""

    def test_command_context_creation(self):
        """Test CommandContext creation and parameter access."""
        context = CommandContext(
            user_input="test command",
            parsed_parameters={"host_name": "server01", "count": 5},
        )

        assert context.user_input == "test command"
        assert context.get_parameter("host_name") == "server01"
        assert context.get_parameter("count") == 5
        assert context.get_parameter("missing", "default") == "default"
        assert context.has_parameter("host_name") is True
        assert context.has_parameter("missing") is False

        # Test require_parameter
        assert context.require_parameter("host_name") == "server01"
        with pytest.raises(
            ValueError, match="Required parameter 'missing' not provided"
        ):
            context.require_parameter("missing")

    def test_command_result_creation(self):
        """Test CommandResult creation and methods."""
        # Success result
        success_result = CommandResult.success_result(
            data={"key": "value"}, message="Success!"
        )
        assert success_result.success is True
        assert success_result.data == {"key": "value"}
        assert success_result.message == "Success!"
        assert success_result.error is None

        # Error result
        error_result = CommandResult.error_result(
            "Something went wrong", data={"error_code": 500}
        )
        assert error_result.success is False
        assert error_result.error == "Something went wrong"
        assert error_result.data == {"error_code": 500}

        # Metadata
        result = CommandResult.success_result().with_metadata(
            timestamp=datetime.now(), source="test"
        )
        assert "timestamp" in result.metadata
        assert result.metadata["source"] == "test"


class TestCommandRegistry:
    """Test the CommandRegistry functionality."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return CommandRegistry()

    @pytest.fixture
    def mock_command(self):
        """Create a mock command for testing."""
        command = Mock(spec=BaseCommand)
        command.name = "test_command"
        command.category = CommandCategory.UTILITY
        command.aliases = ["test_alias"]
        return command

    def test_register_command(self, registry, mock_command):
        """Test command registration."""
        registry.register(mock_command, aliases=["extra_alias"])

        assert registry.has_command("test_command")
        assert registry.has_command("test_alias")
        assert registry.has_command("extra_alias")
        assert registry.get_command("test_command") == mock_command
        assert registry.get_command("test_alias") == mock_command
        assert len(registry) == 1

    def test_register_command_conflicts(self, registry, mock_command):
        """Test command registration conflicts."""
        registry.register(mock_command)

        # Duplicate command name
        with pytest.raises(
            ValueError, match="Command 'test_command' is already registered"
        ):
            registry.register(mock_command)

        # Alias conflicts with command name
        other_command = Mock(spec=BaseCommand)
        other_command.name = "other_command"
        other_command.category = CommandCategory.UTILITY
        other_command.aliases = []

        with pytest.raises(
            ValueError,
            match="Alias 'test_command' conflicts with existing command name",
        ):
            registry.register(other_command, aliases=["test_command"])

    def test_unregister_command(self, registry, mock_command):
        """Test command unregistration."""
        registry.register(mock_command, aliases=["extra_alias"])

        assert registry.unregister("test_command") is True
        assert not registry.has_command("test_command")
        assert not registry.has_command("test_alias")
        assert not registry.has_command("extra_alias")
        assert len(registry) == 0

        # Unregister non-existent command
        assert registry.unregister("missing_command") is False

    def test_list_commands_by_category(self, registry):
        """Test listing commands by category."""
        service_cmd = Mock(spec=BaseCommand)
        service_cmd.name = "service_cmd"
        service_cmd.category = CommandCategory.SERVICE
        service_cmd.aliases = []

        util_cmd = Mock(spec=BaseCommand)
        util_cmd.name = "util_cmd"
        util_cmd.category = CommandCategory.UTILITY
        util_cmd.aliases = []

        registry.register(service_cmd)
        registry.register(util_cmd)

        service_commands = registry.list_commands(CommandCategory.SERVICE)
        util_commands = registry.list_commands(CommandCategory.UTILITY)
        all_commands = registry.list_commands()

        assert len(service_commands) == 1
        assert len(util_commands) == 1
        assert len(all_commands) == 2
        assert service_commands[0] == service_cmd
        assert util_commands[0] == util_cmd

    def test_find_similar_commands(self, registry, mock_command):
        """Test finding similar command names."""
        registry.register(mock_command)

        # Exact match should not be suggested since it exists
        suggestions = registry.find_similar_commands("test_command")
        assert "test_command" in suggestions

        # Partial matches
        suggestions = registry.find_similar_commands("test")
        assert len(suggestions) > 0
        assert any("test" in cmd.lower() for cmd in suggestions)

    def test_registry_validation(self, registry, mock_command):
        """Test registry validation."""
        registry.register(mock_command)

        # Valid registry should have no errors
        errors = registry.validate_registry()
        assert errors == []

        # Manually break the registry to test validation
        registry._aliases["broken_alias"] = "nonexistent_command"
        errors = registry.validate_registry()
        assert len(errors) > 0
        assert any("non-existent command" in error.lower() for error in errors)


class TestServiceCommands:
    """Test service command implementations."""

    @pytest.fixture
    def mock_checkmk_client(self):
        """Create a mock CheckmkClient."""
        return Mock()

    def test_list_services_command(self, mock_checkmk_client):
        """Test the ListServicesCommand."""
        command = ListServicesCommand(mock_checkmk_client)

        # Test command properties
        assert command.name == "list_services"
        assert command.category == CommandCategory.SERVICE
        assert command.description
        assert "host_name" in command.parameters

        # Test validation
        context = CommandContext("list services", {})
        validation_result = command.validate(context)
        assert validation_result.success is True

        # Test execution with host_name
        mock_checkmk_client.list_host_services.return_value = [
            {"extensions": {"description": "CPU utilization", "state": "OK"}}
        ]

        context = CommandContext("list services", {"host_name": "server01"})
        result = command.execute(context)

        assert result.success is True
        assert "server01" in result.message
        assert "CPU utilization" in result.message
        mock_checkmk_client.list_host_services.assert_called_once_with("server01")

    def test_get_service_status_command(self, mock_checkmk_client):
        """Test the GetServiceStatusCommand."""
        command = GetServiceStatusCommand(mock_checkmk_client)

        assert command.name == "get_service_status"
        assert command.parameters["host_name"]["required"] is True
        assert command.parameters["service_description"]["required"] is True

        # Test validation failure
        context = CommandContext(
            "get status", {"host_name": "server01"}
        )  # Missing service_description
        validation_result = command.validate(context)
        assert validation_result.success is False
        assert "service_description" in validation_result.error

        # Test successful execution
        mock_checkmk_client.list_host_services.return_value = [
            {
                "extensions": {
                    "state": "WARNING",
                    "last_check": "2024-01-01 12:00:00",
                    "plugin_output": "CPU usage at 85%",
                }
            }
        ]

        context = CommandContext(
            "get status",
            {"host_name": "server01", "service_description": "CPU utilization"},
        )
        result = command.execute(context)

        assert result.success is True
        assert "WARNING" in result.message
        assert "CPU usage at 85%" in result.message

    def test_acknowledge_service_command(self, mock_checkmk_client):
        """Test the AcknowledgeServiceCommand."""
        command = AcknowledgeServiceCommand(mock_checkmk_client)

        assert command.name == "acknowledge_service"

        # Test execution
        context = CommandContext(
            "acknowledge service",
            {
                "host_name": "server01",
                "service_description": "CPU utilization",
                "comment": "Working on it",
            },
        )

        result = command.execute(context)

        assert result.success is True
        assert "server01/CPU utilization" in result.message
        assert "Working on it" in result.message

        mock_checkmk_client.acknowledge_service_problems.assert_called_once_with(
            host_name="server01",
            service_description="CPU utilization",
            comment="Working on it",
            sticky=True,
        )

    def test_service_command_error_handling(self, mock_checkmk_client):
        """Test error handling in service commands."""
        command = ListServicesCommand(mock_checkmk_client)

        # Test API error
        mock_checkmk_client.list_host_services.side_effect = CheckmkAPIError(
            "API Error"
        )

        context = CommandContext("list services", {"host_name": "server01"})
        result = command.execute(context)

        assert result.success is False
        assert "Error listing services" in result.error


class TestParameterCommands:
    """Test parameter command implementations."""

    @pytest.fixture
    def mock_parameter_manager(self):
        """Create a mock ServiceParameterManager."""
        return Mock()

    def test_view_default_parameters_command(self, mock_parameter_manager):
        """Test the ViewDefaultParametersCommand."""
        command = ViewDefaultParametersCommand(mock_parameter_manager)

        assert command.name == "view_default_parameters"
        assert command.category == CommandCategory.PARAMETER

        # Test execution
        mock_parameter_manager.get_default_parameters.return_value = {
            "levels": (80.0, 90.0),
            "average": 15,
        }
        mock_parameter_manager.PARAMETER_RULESETS = {
            "cpu": {"default": "cpu_utilization_linux"}
        }

        context = CommandContext("view defaults", {"service_type": "cpu"})
        result = command.execute(context)

        assert result.success is True
        assert "80.0%" in result.message
        assert "90.0%" in result.message
        assert "cpu_utilization_linux" in result.message

    def test_parameter_command_validation(self, mock_parameter_manager):
        """Test parameter command validation."""
        command = ViewDefaultParametersCommand(mock_parameter_manager)

        # Test invalid service type
        context = CommandContext("view defaults", {"service_type": "invalid"})
        validation_result = command.validate(context)

        assert validation_result.success is False
        assert "Invalid service type" in validation_result.error


class TestUtilityCommands:
    """Test utility command implementations."""

    def test_help_command(self):
        """Test the HelpCommand."""
        command = HelpCommand()

        assert command.name == "help"
        assert command.category == CommandCategory.UTILITY

        # Test general help
        context = CommandContext("help", {})
        result = command.execute(context)

        assert result.success is True
        assert "Available Command Categories" in result.message
        assert "Service Commands" in result.message

    def test_test_connection_command(self):
        """Test the ConnectionTestCommand."""
        mock_checkmk_client = Mock()
        command = ConnectionTestCommand(mock_checkmk_client)

        assert command.name == "test_connection"

        # Test successful connection
        mock_checkmk_client.test_connection.return_value = True
        mock_checkmk_client.list_all_services.return_value = ["service1", "service2"]

        context = CommandContext("test connection", {})
        result = command.execute(context)

        assert result.success is True
        assert "Connection successful" in result.message
        assert "2 services" in result.message

        # Test failed connection
        mock_checkmk_client.test_connection.return_value = False

        result = command.execute(context)
        assert result.success is False
        assert "Connection failed" in result.error


class TestCommandFactory:
    """Test the CommandFactory."""

    @pytest.fixture
    def mock_checkmk_client(self):
        return Mock()

    @pytest.fixture
    def mock_config(self):
        return Mock()

    @pytest.fixture
    def factory(self, mock_checkmk_client, mock_config):
        return CommandFactory(mock_checkmk_client, mock_config)

    def test_factory_initialization(self, factory, mock_checkmk_client, mock_config):
        """Test factory initialization."""
        assert factory.checkmk_client == mock_checkmk_client
        assert factory.config == mock_config
        assert factory.parameter_manager is not None

    def test_create_command_registry(self, factory):
        """Test creating a command registry."""
        registry = factory.create_command_registry()

        assert len(registry) > 0
        assert registry.has_command("list_services")
        assert registry.has_command("test_connection")
        assert registry.has_command("help")

    def test_create_service_commands(self, factory):
        """Test creating service commands."""
        commands = factory.create_service_commands()

        assert len(commands) > 0
        command_names = [cmd.name for cmd in commands]
        assert "list_services" in command_names
        assert "get_service_status" in command_names
        assert "acknowledge_service" in command_names

    def test_validate_dependencies(self, factory, mock_checkmk_client):
        """Test dependency validation."""
        # Valid dependencies
        mock_checkmk_client.test_connection.return_value = True
        errors = factory.validate_dependencies()
        assert errors == []

        # Invalid dependencies
        mock_checkmk_client.test_connection.return_value = False
        errors = factory.validate_dependencies()
        assert len(errors) > 0
        assert any("connection test failed" in error.lower() for error in errors)

    def test_get_factory_info(self, factory):
        """Test getting factory information."""
        info = factory.get_factory_info()

        assert "checkmk_client" in info
        assert "parameter_manager" in info
        assert "config_available" in info
        assert info["config_available"] is True
