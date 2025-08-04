"""
Test suite for specialized parameter handlers.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from checkmk_agent.services.handlers import (
    get_handler_registry,
    HandlerRegistry,
    BaseParameterHandler,
    HandlerResult,
    ValidationSeverity,
    TemperatureParameterHandler,
    CustomCheckParameterHandler,
    DatabaseParameterHandler,
    NetworkServiceParameterHandler,
)


class TestHandlerRegistry:
    """Test cases for the handler registry system."""

    @pytest.fixture
    def registry(self):
        """Create a fresh handler registry for testing."""
        return HandlerRegistry()

    def test_registry_initialization(self, registry):
        """Test that the registry initializes correctly."""
        assert isinstance(registry, HandlerRegistry)
        assert len(registry._handlers) == 0
        assert len(registry._initialized_handlers) == 0

    def test_handler_registration(self, registry):
        """Test handler registration."""
        registry.register_handler(
            TemperatureParameterHandler,
            priority=10,
            description="Test temperature handler",
        )

        assert "temperature" in registry._handlers
        registration = registry._handlers["temperature"]
        assert registration.handler_class == TemperatureParameterHandler
        assert registration.priority == 10
        assert registration.description == "Test temperature handler"
        assert registration.enabled is True

    def test_handler_retrieval(self, registry):
        """Test getting handler instances."""
        registry.register_handler(TemperatureParameterHandler)

        handler = registry.get_handler("temperature")
        assert isinstance(handler, TemperatureParameterHandler)
        assert handler.name == "temperature"

        # Test caching
        handler2 = registry.get_handler("temperature")
        assert handler is handler2

    def test_handlers_for_service(self, registry):
        """Test getting handlers for a specific service."""
        registry.register_handler(TemperatureParameterHandler)
        registry.register_handler(DatabaseParameterHandler)

        # Temperature service should match temperature handler
        handlers = registry.get_handlers_for_service("CPU Temperature")
        assert len(handlers) == 1
        assert handlers[0].name == "temperature"

        # Database service should match database handler
        handlers = registry.get_handlers_for_service("Oracle Tablespace")
        assert len(handlers) == 1
        assert handlers[0].name == "database"

    def test_handlers_for_ruleset(self, registry):
        """Test getting handlers for a specific ruleset."""
        registry.register_handler(TemperatureParameterHandler)
        registry.register_handler(NetworkServiceParameterHandler)

        # Temperature ruleset should match temperature handler
        handlers = registry.get_handlers_for_ruleset(
            "checkgroup_parameters:temperature"
        )
        assert len(handlers) == 1
        assert handlers[0].name == "temperature"

        # HTTP ruleset should match network handler
        handlers = registry.get_handlers_for_ruleset("checkgroup_parameters:http")
        assert len(handlers) == 1
        assert handlers[0].name == "network_services"

    def test_best_handler_selection(self, registry):
        """Test selecting the best handler for service/ruleset combination."""
        registry.register_handler(TemperatureParameterHandler, priority=10)
        registry.register_handler(CustomCheckParameterHandler, priority=20)

        # Service and ruleset both match temperature handler
        handler = registry.get_best_handler(
            service_name="CPU Temperature", ruleset="checkgroup_parameters:temperature"
        )
        assert handler.name == "temperature"

        # Only service matches
        handler = registry.get_best_handler(service_name="CPU Temperature")
        assert handler.name == "temperature"

    def test_handler_enable_disable(self, registry):
        """Test enabling and disabling handlers."""
        registry.register_handler(TemperatureParameterHandler)

        # Should be enabled by default
        handler = registry.get_handler("temperature")
        assert handler is not None

        # Disable handler
        registry.disable_handler("temperature")
        handler = registry.get_handler("temperature")
        assert handler is None

        # Re-enable handler
        registry.enable_handler("temperature")
        handler = registry.get_handler("temperature")
        assert handler is not None


class TestTemperatureParameterHandler:
    """Test cases for the temperature parameter handler."""

    @pytest.fixture
    def handler(self):
        """Create a temperature handler for testing."""
        return TemperatureParameterHandler()

    def test_handler_properties(self, handler):
        """Test basic handler properties."""
        assert handler.name == "temperature"
        assert len(handler.service_patterns) > 0
        assert len(handler.supported_rulesets) > 0
        assert "checkgroup_parameters:temperature" in handler.supported_rulesets

    def test_service_matching(self, handler):
        """Test service name pattern matching."""
        assert handler.matches_service("CPU Temperature")
        assert handler.matches_service("System temp")
        assert handler.matches_service("thermal sensor")
        assert not handler.matches_service("Memory Usage")
        assert not handler.matches_service("Disk Space")

    def test_ruleset_matching(self, handler):
        """Test ruleset matching."""
        assert handler.matches_ruleset("checkgroup_parameters:temperature")
        assert handler.matches_ruleset("checkgroup_parameters:hw_temperature")
        assert not handler.matches_ruleset("checkgroup_parameters:memory_linux")

    def test_default_parameters_cpu(self, handler):
        """Test getting default parameters for CPU temperature."""
        result = handler.get_default_parameters("CPU Temperature")

        assert result.success is True
        assert result.parameters is not None
        assert "levels" in result.parameters
        assert "levels_lower" in result.parameters
        assert "output_unit" in result.parameters

        # CPU should have specific temperature profile
        levels = result.parameters["levels"]
        assert levels == (75.0, 85.0)  # CPU profile defaults

    def test_default_parameters_ambient(self, handler):
        """Test getting default parameters for ambient temperature."""
        result = handler.get_default_parameters("Ambient Temperature")

        assert result.success is True
        levels = result.parameters["levels"]
        assert levels == (35.0, 40.0)  # Ambient profile defaults

    def test_parameter_validation_valid(self, handler):
        """Test validation of valid temperature parameters."""
        parameters = {
            "levels": (70.0, 80.0),
            "levels_lower": (5.0, 0.0),
            "output_unit": "c",
        }

        result = handler.validate_parameters(parameters, "CPU Temperature")

        assert result.success is True
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.normalized_parameters is not None

    def test_parameter_validation_invalid(self, handler):
        """Test validation of invalid temperature parameters."""
        parameters = {
            "levels": (90.0, 80.0),  # Warning > Critical (invalid)
            "output_unit": "x",  # Invalid unit
        }

        result = handler.validate_parameters(parameters, "CPU Temperature")

        assert result.success is True  # Validation completed
        assert result.is_valid is False  # But parameters are invalid
        assert len(result.errors) > 0

    def test_temperature_unit_conversion(self, handler):
        """Test temperature unit conversion logic."""
        # Test internal conversion method
        celsius_temps = handler._convert_to_celsius(70.0, 80.0, "c")
        assert celsius_temps == (70.0, 80.0)

        fahrenheit_temps = handler._convert_to_celsius(158.0, 176.0, "f")
        assert abs(fahrenheit_temps[0] - 70.0) < 0.1
        assert abs(fahrenheit_temps[1] - 80.0) < 0.1

    def test_parameter_suggestions(self, handler):
        """Test parameter optimization suggestions."""
        current_params = {"levels": (60.0, 70.0), "output_unit": "c"}

        suggestions = handler.suggest_parameters("CPU Temperature", current_params)

        assert isinstance(suggestions, list)
        # Should suggest CPU-optimized thresholds
        cpu_suggestion = next(
            (s for s in suggestions if s["parameter"] == "levels"), None
        )
        if cpu_suggestion:
            assert cpu_suggestion["suggested_value"] == (75.0, 85.0)


class TestCustomCheckParameterHandler:
    """Test cases for the custom check parameter handler."""

    @pytest.fixture
    def handler(self):
        """Create a custom check handler for testing."""
        return CustomCheckParameterHandler()

    def test_handler_properties(self, handler):
        """Test basic handler properties."""
        assert handler.name == "custom_checks"
        assert len(handler.service_patterns) > 0
        assert len(handler.supported_rulesets) > 0

    def test_service_matching(self, handler):
        """Test service name pattern matching."""
        assert handler.matches_service("Local check_disk")
        assert handler.matches_service("MRPE check_load")
        assert handler.matches_service("Custom script")
        assert handler.matches_service("check_mysql")
        assert not handler.matches_service("CPU utilization")

    def test_check_type_detection(self, handler):
        """Test detection of check types."""
        assert handler._detect_check_type("Local check_disk") == "local"
        assert handler._detect_check_type("MRPE check_load") == "mrpe"
        assert handler._detect_check_type("check_mysql") == "nagios_plugin"
        assert handler._detect_check_type("Custom script") == "script"

    def test_default_parameters_nagios(self, handler):
        """Test default parameters for Nagios-style plugins."""
        result = handler.get_default_parameters("check_mysql")

        assert result.success is True
        assert result.parameters is not None
        assert result.parameters.get("timeout") == 30  # Nagios plugin timeout
        assert result.parameters.get("check_type") == "nagios_plugin"

    def test_nagios_threshold_validation(self, handler):
        """Test Nagios threshold format validation."""
        assert handler._is_valid_nagios_threshold("80") is True
        assert handler._is_valid_nagios_threshold("80:") is True
        assert handler._is_valid_nagios_threshold("~:80") is True
        assert handler._is_valid_nagios_threshold("10:80") is True
        assert handler._is_valid_nagios_threshold("@10:80") is True
        assert handler._is_valid_nagios_threshold("invalid") is False

    def test_command_validation(self, handler):
        """Test command parameter validation."""
        valid_params = {"command_line": "check_disk -w 80% -c 90% /var", "timeout": 30}

        result = handler.validate_parameters(valid_params, "MRPE check_disk")
        assert result.success is True
        assert result.is_valid is True

        # Test dangerous command
        dangerous_params = {"command_line": "check_disk; rm -rf /", "timeout": 30}

        result = handler.validate_parameters(dangerous_params, "MRPE check_disk")
        assert result.success is True
        assert len(result.warnings) > 0  # Should warn about dangerous characters


class TestDatabaseParameterHandler:
    """Test cases for the database parameter handler."""

    @pytest.fixture
    def handler(self):
        """Create a database handler for testing."""
        return DatabaseParameterHandler()

    def test_handler_properties(self, handler):
        """Test basic handler properties."""
        assert handler.name == "database"
        assert len(handler.service_patterns) > 0
        assert len(handler.supported_rulesets) > 0

    def test_database_detection(self, handler):
        """Test database type detection."""
        db_type, metric = handler._detect_database_and_metric("Oracle Tablespace Usage")
        assert db_type == "oracle"
        assert metric == "tablespaces"

        db_type, metric = handler._detect_database_and_metric("MySQL Connections")
        assert db_type == "mysql"
        assert metric == "connections"

        db_type, metric = handler._detect_database_and_metric("PostgreSQL Locks")
        assert db_type == "postgresql"
        assert metric == "locks"

    def test_oracle_defaults(self, handler):
        """Test Oracle-specific default parameters."""
        result = handler.get_default_parameters("Oracle Tablespace Usage")

        assert result.success is True
        assert result.parameters is not None
        assert "levels" in result.parameters

        # Should use Oracle tablespace defaults
        levels = result.parameters["levels"]
        assert levels == (80.0, 90.0)

    def test_mysql_validation(self, handler):
        """Test MySQL-specific parameter validation."""
        mysql_params = {
            "levels": (80.0, 90.0),
            "buffer_pool_hit_rate": (90.0, 95.0),
            "connection_timeout": 30,
        }

        result = handler.validate_parameters(mysql_params, "MySQL InnoDB")
        assert result.success is True
        assert result.is_valid is True

    def test_connection_params_validation(self, handler):
        """Test database connection parameter validation."""
        conn_params = {"hostname": "db.example.com", "port": 3306, "database": "testdb"}

        messages = handler._validate_connection_params(
            conn_params, ["hostname", "port", "database"]
        )
        errors = [msg for msg in messages if msg.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0


class TestNetworkServiceParameterHandler:
    """Test cases for the network service parameter handler."""

    @pytest.fixture
    def handler(self):
        """Create a network service handler for testing."""
        return NetworkServiceParameterHandler()

    def test_handler_properties(self, handler):
        """Test basic handler properties."""
        assert handler.name == "network_services"
        assert len(handler.service_patterns) > 0
        assert len(handler.supported_rulesets) > 0

    def test_service_type_detection(self, handler):
        """Test network service type detection."""
        assert handler._detect_service_type("HTTP www.example.com") == "http"
        assert handler._detect_service_type("HTTPS secure.example.com") == "https"
        assert handler._detect_service_type("TCP Port 22") == "tcp"
        assert handler._detect_service_type("DNS Lookup") == "dns"
        assert handler._detect_service_type("SSH Connection") == "ssh"

    def test_https_defaults(self, handler):
        """Test HTTPS-specific default parameters."""
        result = handler.get_default_parameters("HTTPS secure.example.com")

        assert result.success is True
        assert result.parameters is not None
        assert "ssl_cert_age" in result.parameters
        assert "ssl_verify" in result.parameters
        assert result.parameters["ssl_cert_age"] == (30, 7)
        assert result.parameters["ssl_verify"] is True

    def test_url_validation(self, handler):
        """Test URL parameter validation."""
        valid_params = {
            "url": "https://www.example.com/health",
            "response_time": (2.0, 5.0),
            "timeout": 10,
        }

        result = handler.validate_parameters(valid_params, "HTTPS Health Check")
        assert result.success is True
        assert result.is_valid is True

        # Test invalid URL
        invalid_params = {"url": "not-a-url", "response_time": (2.0, 5.0)}

        result = handler.validate_parameters(invalid_params, "HTTPS Health Check")
        assert result.success is False
        assert len(result.errors) > 0

    def test_hostname_validation(self, handler):
        """Test hostname validation."""
        # Valid hostnames
        assert len(handler._validate_hostname("example.com")) == 0
        assert len(handler._validate_hostname("192.168.1.1")) == 0
        assert len(handler._validate_hostname("sub.example.com")) == 0

        # Invalid hostnames
        assert len(handler._validate_hostname("")) > 0
        assert len(handler._validate_hostname("invalid..hostname")) > 0

    def test_port_validation(self, handler):
        """Test port number validation."""
        assert len(handler._validate_port(80)) == 0
        assert len(handler._validate_port(443)) == 0
        assert len(handler._validate_port(65535)) == 0

        assert len(handler._validate_port(0)) > 0
        assert len(handler._validate_port(65536)) > 0
        assert len(handler._validate_port("not-a-port")) > 0


class TestHandlerIntegration:
    """Integration tests for the handler system."""

    def test_global_registry(self):
        """Test that the global registry works correctly."""
        registry = get_handler_registry()

        assert isinstance(registry, HandlerRegistry)

        # Should have default handlers registered
        handlers_info = registry.list_handlers()
        assert len(handlers_info) > 0

        # Check for expected handlers
        handler_names = set(handlers_info.keys())
        expected_handlers = {
            "temperature",
            "custom_checks",
            "database",
            "network_services",
        }
        assert expected_handlers.issubset(handler_names)

    def test_handler_chaining(self):
        """Test that handlers can be chained for fallback."""
        registry = get_handler_registry()

        # Service that might match multiple handlers
        handlers = registry.get_handlers_for_service(
            "Custom Temperature Check", limit=3
        )

        # Should get multiple handlers in priority order
        assert len(handlers) >= 1

        # Handlers should be ordered by priority
        if len(handlers) > 1:
            handler_names = [h.name for h in handlers]
            # Temperature handler should have higher priority than custom checks
            temp_idx = next(
                (i for i, name in enumerate(handler_names) if name == "temperature"), -1
            )
            custom_idx = next(
                (i for i, name in enumerate(handler_names) if name == "custom_checks"),
                -1,
            )

            if temp_idx >= 0 and custom_idx >= 0:
                assert temp_idx < custom_idx  # Temperature should come first

    def test_context_usage(self):
        """Test that handlers properly use context information."""
        registry = get_handler_registry()
        handler = registry.get_handler("temperature")

        if handler:
            # Test with production context
            prod_context = {"environment": "production"}
            result = handler.get_default_parameters("CPU Temperature", prod_context)

            assert result.success is True

            # Test with datacenter context
            dc_context = {"environment": "datacenter"}
            result2 = handler.get_default_parameters("CPU Temperature", dc_context)

            assert result2.success is True

            # Parameters might be different based on context
            # (This depends on handler implementation)


@pytest.mark.asyncio
class TestParameterServiceIntegration:
    """Test integration with the parameter service."""

    @pytest.fixture
    def mock_checkmk_client(self):
        """Create a mock Checkmk client."""
        client = Mock()
        client.get_effective_parameters = AsyncMock()
        client.create_rule = AsyncMock()
        client.list_rulesets = AsyncMock()
        client.get_ruleset_info = AsyncMock()
        return client

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        return Mock()

    async def test_handler_integration_basic(self, mock_checkmk_client, mock_config):
        """Test basic handler integration with parameter service."""
        from checkmk_agent.services.parameter_service import ParameterService

        service = ParameterService(mock_checkmk_client, mock_config)

        # Test that handler registry is initialized
        assert service.handler_registry is not None

        # Test getting specialized defaults
        result = await service.get_specialized_defaults("CPU Temperature")
        assert result.success is True

        if result.data.get("handler_used"):
            assert result.data["handler_used"] == "temperature"
            assert "parameters" in result.data
            assert result.data["parameters"] != {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
