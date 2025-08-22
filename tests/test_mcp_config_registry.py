"""Tests for MCP server registry configuration."""

import pytest
from unittest.mock import Mock

from mcp.types import Prompt, PromptArgument

from checkmk_mcp_server.mcp_server.config.registry import RegistryConfig, ToolMetadata, ServiceDependency


class TestServiceDependency:
    """Test cases for ServiceDependency dataclass."""

    def test_service_dependency_initialization(self):
        """Test ServiceDependency initialization."""
        dep = ServiceDependency("test_service")
        
        assert dep.name == "test_service"
        assert dep.required is True
        assert dep.initialization_order == 1

    def test_service_dependency_custom_values(self):
        """Test ServiceDependency with custom values."""
        dep = ServiceDependency("test_service", required=False, initialization_order=5)
        
        assert dep.name == "test_service"
        assert dep.required is False
        assert dep.initialization_order == 5


class TestToolMetadata:
    """Test cases for ToolMetadata dataclass."""

    def test_tool_metadata_initialization(self):
        """Test ToolMetadata initialization."""
        metadata = ToolMetadata("test_category")
        
        assert metadata.category == "test_category"
        assert metadata.priority == 1
        assert metadata.requires_services == []
        assert metadata.description == ""
        assert metadata.examples == []

    def test_tool_metadata_custom_values(self):
        """Test ToolMetadata with custom values."""
        metadata = ToolMetadata(
            category="host",
            priority=5,
            requires_services=["host_service", "status_service"],
            description="Host management tool",
            examples=["list hosts", "create host"]
        )
        
        assert metadata.category == "host"
        assert metadata.priority == 5
        assert metadata.requires_services == ["host_service", "status_service"]
        assert metadata.description == "Host management tool"
        assert metadata.examples == ["list hosts", "create host"]


class TestRegistryConfig:
    """Test cases for RegistryConfig class."""

    @pytest.fixture
    def registry_config(self):
        """Create a RegistryConfig instance for testing."""
        return RegistryConfig()

    def test_registry_config_initialization(self, registry_config):
        """Test RegistryConfig initializes correctly."""
        assert len(registry_config._tool_categories) == 8
        assert len(registry_config._service_dependencies) == 11
        assert len(registry_config._tool_registration_patterns) == 4

    def test_get_tool_categories(self, registry_config):
        """Test getting tool categories."""
        categories = registry_config.get_tool_categories()
        
        expected_categories = {
            "host", "service", "parameter", "status", 
            "event", "metrics", "business", "advanced"
        }
        assert set(categories.keys()) == expected_categories
        
        # Test it returns a copy
        categories["new_category"] = "New category"
        assert "new_category" not in registry_config._tool_categories

    def test_get_service_dependencies(self, registry_config):
        """Test getting service dependencies."""
        dependencies = registry_config.get_service_dependencies()
        
        assert "host_service" in dependencies
        assert "service_service" in dependencies
        assert dependencies["host_service"].required is True
        assert dependencies["event_service"].required is False
        
        # Test it returns a copy
        dependencies["new_service"] = ServiceDependency("new_service")
        assert "new_service" not in registry_config._service_dependencies

    def test_get_required_services(self, registry_config):
        """Test getting required services."""
        required = registry_config.get_required_services()
        
        expected_required = [
            "host_service", "service_service", "status_service", "parameter_service"
        ]
        assert set(required) == set(expected_required)

    def test_get_service_initialization_order(self, registry_config):
        """Test getting services in initialization order."""
        ordered_services = registry_config.get_service_initialization_order()
        
        # Should be ordered by initialization_order
        assert ordered_services[0] == "host_service"  # order 1
        assert ordered_services[1] == "service_service"  # order 2
        assert ordered_services[2] == "status_service"  # order 3
        assert len(ordered_services) == 11  # All services

    def test_create_tool_metadata_valid(self, registry_config):
        """Test creating valid tool metadata."""
        metadata = registry_config.create_tool_metadata(
            category="host",
            priority=5,
            requires_services=["host_service"],
            description="Test tool",
            examples=["example1", "example2"]
        )
        
        assert isinstance(metadata, ToolMetadata)
        assert metadata.category == "host"
        assert metadata.priority == 5
        assert metadata.requires_services == ["host_service"]
        assert metadata.description == "Test tool"
        assert metadata.examples == ["example1", "example2"]

    def test_create_tool_metadata_invalid_category(self, registry_config):
        """Test creating tool metadata with invalid category."""
        with pytest.raises(ValueError, match="Invalid category 'invalid_category'"):
            registry_config.create_tool_metadata("invalid_category")

    def test_create_tool_metadata_invalid_priority(self, registry_config):
        """Test creating tool metadata with invalid priority."""
        with pytest.raises(ValueError, match="Priority must be between 1 and 10"):
            registry_config.create_tool_metadata("host", priority=0)
        
        with pytest.raises(ValueError, match="Priority must be between 1 and 10"):
            registry_config.create_tool_metadata("host", priority=11)

    def test_get_host_tools_config(self, registry_config):
        """Test getting host tools configuration."""
        config = registry_config.get_host_tools_config()
        
        assert config["category"] == "host"
        assert "list_hosts" in config["tools"]
        assert "create_host" in config["tools"]
        assert "host_service" in config["required_services"]
        assert "streaming_host_service" in config["optional_services"]

    def test_get_service_tools_config(self, registry_config):
        """Test getting service tools configuration."""
        config = registry_config.get_service_tools_config()
        
        assert config["category"] == "service"
        assert "list_all_services" in config["tools"]
        assert "service_service" in config["required_services"]

    def test_get_parameter_tools_config(self, registry_config):
        """Test getting parameter tools configuration."""
        config = registry_config.get_parameter_tools_config()
        
        assert config["category"] == "parameter"
        assert "get_effective_parameters" in config["tools"]
        assert "set_service_parameters" in config["tools"]
        assert "parameter_service" in config["required_services"]
        assert len(config["tools"]) > 15  # Parameter tools are numerous

    def test_get_status_tools_config(self, registry_config):
        """Test getting status tools configuration."""
        config = registry_config.get_status_tools_config()
        
        assert config["category"] == "status"
        assert "get_health_dashboard" in config["tools"]
        assert "status_service" in config["required_services"]

    def test_get_event_tools_config(self, registry_config):
        """Test getting event tools configuration."""
        config = registry_config.get_event_tools_config()
        
        assert config["category"] == "event"
        assert "list_service_events" in config["tools"]
        assert "event_service" in config["required_services"]

    def test_get_metrics_tools_config(self, registry_config):
        """Test getting metrics tools configuration."""
        config = registry_config.get_metrics_tools_config()
        
        assert config["category"] == "metrics"
        assert "get_service_metrics" in config["tools"]
        assert "metrics_service" in config["required_services"]

    def test_get_business_tools_config(self, registry_config):
        """Test getting business tools configuration."""
        config = registry_config.get_business_tools_config()
        
        assert config["category"] == "business"
        assert "get_business_status_summary" in config["tools"]
        assert "bi_service" in config["required_services"]

    def test_get_advanced_tools_config(self, registry_config):
        """Test getting advanced tools configuration."""
        config = registry_config.get_advanced_tools_config()
        
        assert config["category"] == "advanced"
        assert "batch_create_hosts" in config["tools"]
        assert len(config["required_services"]) == 0  # No required services
        assert "batch_processor" in config["optional_services"]

    def test_get_all_tool_configs(self, registry_config):
        """Test getting all tool configurations."""
        all_configs = registry_config.get_all_tool_configs()
        
        expected_categories = {
            "host", "service", "parameter", "status",
            "event", "metrics", "business", "advanced"
        }
        assert set(all_configs.keys()) == expected_categories
        
        # Each config should have required keys
        for category, config in all_configs.items():
            assert "category" in config
            assert "tools" in config
            assert "required_services" in config
            assert "optional_services" in config

    def test_get_prompt_definitions(self, registry_config):
        """Test getting prompt definitions."""
        prompts = registry_config.get_prompt_definitions()
        
        assert "analyze_host_health" in prompts
        assert "troubleshoot_service" in prompts
        
        # Verify prompt structure
        analyze_prompt = prompts["analyze_host_health"]
        assert isinstance(analyze_prompt, Prompt)
        assert analyze_prompt.name == "analyze_host_health"
        assert len(analyze_prompt.arguments) >= 1
        assert any(arg.name == "host_name" for arg in analyze_prompt.arguments)

    def test_validate_tool_registration_valid(self, registry_config):
        """Test valid tool registration validation."""
        result = registry_config.validate_tool_registration(
            "test_tool",
            "host",
            ["host_service"]
        )
        assert result is True

    def test_validate_tool_registration_invalid_category(self, registry_config):
        """Test tool registration validation with invalid category."""
        with pytest.raises(ValueError, match="Invalid category 'invalid_category'"):
            registry_config.validate_tool_registration(
                "test_tool",
                "invalid_category",
                []
            )

    def test_validate_tool_registration_unknown_service(self, registry_config):
        """Test tool registration validation with unknown service."""
        with pytest.raises(ValueError, match="Unknown service dependency: unknown_service"):
            registry_config.validate_tool_registration(
                "test_tool",
                "host",
                ["unknown_service"]
            )

    def test_validate_tool_registration_empty_name(self, registry_config):
        """Test tool registration validation with empty name."""
        with pytest.raises(ValueError, match="Tool name must be a non-empty string"):
            registry_config.validate_tool_registration(
                "",
                "host",
                []
            )

    def test_validate_tool_registration_none_name(self, registry_config):
        """Test tool registration validation with None name."""
        with pytest.raises(ValueError, match="Tool name must be a non-empty string"):
            registry_config.validate_tool_registration(
                None,
                "host",
                []
            )

    def test_tool_registration_patterns(self, registry_config):
        """Test tool registration patterns creation."""
        # Test standard pattern
        standard = registry_config._create_standard_tool_pattern()
        assert standard["type"] == "standard"
        assert standard["error_handling"] == "sanitize"
        assert standard["request_tracking"] is True
        assert standard["caching"] is False

        # Test parameter pattern
        parameter = registry_config._create_parameter_tool_pattern()
        assert parameter["type"] == "parameter"
        assert parameter["caching"] is True
        assert parameter["validation"] == "strict"

        # Test streaming pattern
        streaming = registry_config._create_streaming_tool_pattern()
        assert streaming["type"] == "streaming"
        assert streaming["streaming"] is True

        # Test batch pattern
        batch = registry_config._create_batch_tool_pattern()
        assert batch["type"] == "batch"
        assert batch["batch_processing"] is True