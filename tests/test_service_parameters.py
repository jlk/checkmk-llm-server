"""Tests for service parameter functionality."""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from checkmk_agent.service_parameters import ServiceParameterManager
from checkmk_agent.api_client import CheckmkClient, CheckmkAPIError
from checkmk_agent.config import AppConfig


@pytest.fixture
def mock_checkmk_client():
    """Mock Checkmk client."""
    return Mock(spec=CheckmkClient)


@pytest.fixture
def mock_config():
    """Mock application config."""
    config = Mock(spec=AppConfig)
    config.checkmk = Mock()
    config.checkmk.username = "test_user"
    return config


@pytest.fixture
def service_parameter_manager(mock_checkmk_client, mock_config):
    """Service parameter manager instance."""
    return ServiceParameterManager(mock_checkmk_client, mock_config)


class TestServiceParameterManager:
    """Test ServiceParameterManager class."""

    def test_init(self, service_parameter_manager, mock_checkmk_client, mock_config):
        """Test initialization."""
        assert service_parameter_manager.checkmk_client == mock_checkmk_client
        assert service_parameter_manager.config == mock_config
        assert service_parameter_manager._cache_ttl == 900
        assert service_parameter_manager._ruleset_cache == {}

    def test_get_default_parameters_cpu(self, service_parameter_manager):
        """Test getting default CPU parameters."""
        result = service_parameter_manager.get_default_parameters("cpu")

        expected = {"levels": (80.0, 90.0), "average": 15, "horizon": 90}
        assert result == expected

    def test_get_default_parameters_memory(self, service_parameter_manager):
        """Test getting default memory parameters."""
        result = service_parameter_manager.get_default_parameters("memory")

        expected = {"levels": (80.0, 90.0), "average": 3, "handle_zero": True}
        assert result == expected

    def test_get_default_parameters_filesystem(self, service_parameter_manager):
        """Test getting default filesystem parameters."""
        result = service_parameter_manager.get_default_parameters("filesystem")

        expected = {
            "levels": (80.0, 90.0),
            "magic_normsize": 20,
            "magic": 0.8,
            "trend_range": 24,
        }
        assert result == expected

    def test_get_default_parameters_unknown(self, service_parameter_manager):
        """Test getting default parameters for unknown service type."""
        result = service_parameter_manager.get_default_parameters("unknown")
        assert result == {}

    def test_discover_service_ruleset_cpu(self, service_parameter_manager):
        """Test discovering ruleset for CPU service."""
        result = service_parameter_manager.discover_service_ruleset(
            "server01", "CPU utilization"
        )
        assert result == "cpu_utilization_linux"

    def test_discover_service_ruleset_memory(self, service_parameter_manager):
        """Test discovering ruleset for memory service."""
        result = service_parameter_manager.discover_service_ruleset(
            "server01", "Memory usage"
        )
        assert result == "memory_linux"

    def test_discover_service_ruleset_filesystem(self, service_parameter_manager):
        """Test discovering ruleset for filesystem service."""
        result = service_parameter_manager.discover_service_ruleset(
            "server01", "Filesystem /var"
        )
        assert result == "filesystems"

    def test_discover_service_ruleset_unknown(self, service_parameter_manager):
        """Test discovering ruleset for unknown service."""
        result = service_parameter_manager.discover_service_ruleset(
            "server01", "Unknown Service"
        )
        assert result is None

    def test_validate_parameters_valid_levels(self, service_parameter_manager):
        """Test parameter validation with valid levels."""
        parameters = {"levels": (80.0, 90.0), "average": 15}
        result = service_parameter_manager.validate_parameters(
            "cpu_utilization_linux", parameters
        )
        assert result is True

    def test_validate_parameters_invalid_levels_order(self, service_parameter_manager):
        """Test parameter validation with invalid level order."""
        parameters = {"levels": (90.0, 80.0), "average": 15}  # Warning > Critical
        result = service_parameter_manager.validate_parameters(
            "cpu_utilization_linux", parameters
        )
        assert result is False

    def test_validate_parameters_invalid_levels_range(self, service_parameter_manager):
        """Test parameter validation with invalid level range."""
        parameters = {"levels": (110.0, 120.0), "average": 15}  # > 100%
        result = service_parameter_manager.validate_parameters(
            "cpu_utilization_linux", parameters
        )
        assert result is False

    def test_validate_parameters_filesystem_valid(self, service_parameter_manager):
        """Test filesystem parameter validation."""
        parameters = {"levels": (80.0, 90.0), "magic_normsize": 20, "magic": 0.8}
        result = service_parameter_manager.validate_parameters(
            "filesystems", parameters
        )
        assert result is True

    def test_validate_parameters_filesystem_invalid_magic(
        self, service_parameter_manager
    ):
        """Test filesystem parameter validation with invalid magic factor."""
        parameters = {
            "levels": (80.0, 90.0),
            "magic_normsize": 20,
            "magic": 1.5,  # > 1.0
        }
        result = service_parameter_manager.validate_parameters(
            "filesystems", parameters
        )
        assert result is False

    def test_create_parameter_rule(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test creating a parameter rule."""
        # Mock API response
        mock_response = {"id": "rule_123"}
        mock_checkmk_client.create_rule.return_value = mock_response

        parameters = {"levels": (85.0, 95.0)}

        result = service_parameter_manager.create_parameter_rule(
            ruleset="cpu_utilization_linux",
            host_name="server01",
            service_pattern="CPU utilization",
            parameters=parameters,
            comment="Test rule",
        )

        assert result == "rule_123"

        # Verify API call
        mock_checkmk_client.create_rule.assert_called_once()
        call_args = mock_checkmk_client.create_rule.call_args

        assert call_args[1]["ruleset"] == "cpu_utilization_linux"
        assert call_args[1]["folder"] == "~"
        assert call_args[1]["value_raw"] == '{"levels":[85.0,95.0]}'
        assert call_args[1]["conditions"] == {
            "host_name": ["server01"],
            "service_description": ["CPU utilization"],
        }
        assert call_args[1]["properties"]["description"] == "Test rule"

    def test_create_parameter_rule_invalid_parameters(self, service_parameter_manager):
        """Test creating rule with invalid parameters."""
        parameters = {"levels": (95.0, 85.0)}  # Invalid order

        with pytest.raises(ValueError, match="Invalid parameters"):
            service_parameter_manager.create_parameter_rule(
                ruleset="cpu_utilization_linux",
                host_name="server01",
                service_pattern="CPU utilization",
                parameters=parameters,
            )

    def test_create_simple_override(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test creating a simple parameter override."""
        # Mock API response
        mock_response = {"id": "rule_456"}
        mock_checkmk_client.create_rule.return_value = mock_response

        result = service_parameter_manager.create_simple_override(
            host_name="server01",
            service_name="CPU utilization",
            warning=85.0,
            critical=95.0,
            comment="Test override",
        )

        assert result == "rule_456"

        # Verify API call
        mock_checkmk_client.create_rule.assert_called_once()
        call_args = mock_checkmk_client.create_rule.call_args

        assert call_args[1]["ruleset"] == "cpu_utilization_linux"
        assert json.loads(call_args[1]["value_raw"])["levels"] == [85.0, 95.0]

    def test_create_simple_override_unknown_service(self, service_parameter_manager):
        """Test creating override for unknown service type."""
        with pytest.raises(ValueError, match="Could not determine ruleset"):
            service_parameter_manager.create_simple_override(
                host_name="server01",
                service_name="Unknown Service",
                warning=85.0,
                critical=95.0,
            )

    def test_get_service_parameters_no_rules(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test getting service parameters when no rules exist."""
        mock_checkmk_client.search_rules_by_host_service.return_value = []

        result = service_parameter_manager.get_service_parameters(
            "server01", "CPU utilization"
        )

        assert result["source"] == "default"
        assert result["parameters"] == {}
        assert result["rules"] == []

    def test_get_service_parameters_with_rules(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test getting service parameters with existing rules."""
        mock_rules = [
            {
                "id": "rule_123",
                "extensions": {
                    "value_raw": '{"levels": [85.0, 95.0], "average": 10}',
                    "ruleset": "cpu_utilization_linux",
                },
            }
        ]
        mock_checkmk_client.search_rules_by_host_service.return_value = mock_rules

        result = service_parameter_manager.get_service_parameters(
            "server01", "CPU utilization"
        )

        assert result["source"] == "rule"
        assert result["parameters"] == {"levels": [85.0, 95.0], "average": 10}
        assert result["primary_rule"]["id"] == "rule_123"
        assert len(result["all_rules"]) == 1

    def test_delete_parameter_rule(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test deleting a parameter rule."""
        service_parameter_manager.delete_parameter_rule("rule_123")

        mock_checkmk_client.delete_rule.assert_called_once_with("rule_123")

    def test_list_parameter_rulesets(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test listing parameter rulesets."""
        mock_rulesets = [
            {"id": "cpu_utilization_linux", "title": "CPU utilization on Linux/Unix"},
            {"id": "memory_linux", "title": "Memory levels for Linux"},
            {"id": "filesystems", "title": "Filesystems (used space and growth)"},
        ]
        mock_checkmk_client.list_rulesets.return_value = mock_rulesets

        result = service_parameter_manager.list_parameter_rulesets()

        # Should return known service parameter rulesets
        assert len(result) == 3
        ruleset_ids = [rs["id"] for rs in result]
        assert "cpu_utilization_linux" in ruleset_ids
        assert "memory_linux" in ruleset_ids
        assert "filesystems" in ruleset_ids

    def test_list_parameter_rulesets_filtered(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test listing parameter rulesets with category filter."""
        mock_rulesets = [
            {"id": "cpu_utilization_linux", "title": "CPU utilization on Linux/Unix"},
            {"id": "memory_linux", "title": "Memory levels for Linux"},
        ]
        mock_checkmk_client.list_rulesets.return_value = mock_rulesets

        result = service_parameter_manager.list_parameter_rulesets("cpu")

        # Should return only CPU-related rulesets
        assert len(result) == 1
        assert result[0]["id"] == "cpu_utilization_linux"

    def test_cache_functionality(self, service_parameter_manager, mock_checkmk_client):
        """Test ruleset caching functionality."""
        mock_rulesets = [{"id": "test_ruleset"}]
        mock_checkmk_client.list_rulesets.return_value = mock_rulesets

        # First call should hit API
        result1 = service_parameter_manager.list_parameter_rulesets()
        mock_checkmk_client.list_rulesets.assert_called_once()

        # Second call should use cache
        result2 = service_parameter_manager.list_parameter_rulesets()
        # Still only one API call
        assert mock_checkmk_client.list_rulesets.call_count == 1

        assert result1 == result2

    def test_sort_rules_by_precedence(self, service_parameter_manager):
        """Test rule precedence sorting."""
        rules = [
            {
                "id": "rule_general",
                "extensions": {"conditions": {}},  # No specific conditions
            },
            {
                "id": "rule_host_specific",
                "extensions": {"conditions": {"host_name": ["server01"]}},
            },
            {
                "id": "rule_host_and_service",
                "extensions": {
                    "conditions": {
                        "host_name": ["server01"],
                        "service_description": ["CPU utilization"],
                    }
                },
            },
        ]

        sorted_rules = service_parameter_manager._sort_rules_by_precedence(
            rules, "server01", "CPU utilization"
        )

        # Most specific rule should be first
        assert sorted_rules[0]["id"] == "rule_host_and_service"
        assert sorted_rules[1]["id"] == "rule_host_specific"
        assert sorted_rules[2]["id"] == "rule_general"


class TestServiceParameterManagerError:
    """Test error handling in ServiceParameterManager."""

    def test_create_rule_api_error(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test handling API errors when creating rules."""
        mock_checkmk_client.create_rule.side_effect = CheckmkAPIError("API Error")

        parameters = {"levels": (85.0, 95.0)}

        with pytest.raises(CheckmkAPIError):
            service_parameter_manager.create_parameter_rule(
                ruleset="cpu_utilization_linux",
                host_name="server01",
                service_pattern="CPU utilization",
                parameters=parameters,
            )

    def test_get_service_parameters_api_error(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test handling API errors when getting service parameters."""
        mock_checkmk_client.search_rules_by_host_service.side_effect = CheckmkAPIError(
            "API Error"
        )

        with pytest.raises(CheckmkAPIError):
            service_parameter_manager.get_service_parameters(
                "server01", "CPU utilization"
            )

    def test_list_rulesets_api_error(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test handling API errors when listing rulesets."""
        mock_checkmk_client.list_rulesets.side_effect = CheckmkAPIError("API Error")

        with pytest.raises(CheckmkAPIError):
            service_parameter_manager.list_parameter_rulesets()


class TestServiceParameterManagerIntegration:
    """Integration-style tests for ServiceParameterManager."""

    def test_full_override_workflow(
        self, service_parameter_manager, mock_checkmk_client
    ):
        """Test complete workflow of creating and retrieving parameter overrides."""
        # Mock rule creation
        mock_checkmk_client.create_rule.return_value = {"id": "rule_789"}

        # Mock getting service parameters after creation
        mock_rules = [
            {
                "id": "rule_789",
                "extensions": {
                    "value_raw": '{"levels": [85.0, 95.0], "average": 15, "horizon": 90}',
                    "ruleset": "cpu_utilization_linux",
                    "conditions": {
                        "host_name": ["server01"],
                        "service_description": ["CPU utilization"],
                    },
                },
            }
        ]
        mock_checkmk_client.search_rules_by_host_service.return_value = mock_rules

        # Create override
        rule_id = service_parameter_manager.create_simple_override(
            host_name="server01",
            service_name="CPU utilization",
            warning=85.0,
            critical=95.0,
            comment="Integration test override",
        )

        assert rule_id == "rule_789"

        # Retrieve parameters
        result = service_parameter_manager.get_service_parameters(
            "server01", "CPU utilization"
        )

        assert result["source"] == "rule"
        assert result["parameters"]["levels"] == [85.0, 95.0]
        assert result["primary_rule"]["id"] == "rule_789"

    def test_cache_expiration(self, service_parameter_manager, mock_checkmk_client):
        """Test that cache expires after TTL."""
        from unittest.mock import patch
        import time

        mock_rulesets = [{"id": "test_ruleset"}]
        mock_checkmk_client.list_rulesets.return_value = mock_rulesets

        # First call - should cache
        service_parameter_manager.list_parameter_rulesets()
        assert mock_checkmk_client.list_rulesets.call_count == 1

        # Manually expire the cache by setting an old timestamp
        service_parameter_manager._cache_timestamp = datetime(2023, 1, 1, 12, 0, 0)

        # Second call after expiration - should hit API again
        service_parameter_manager.list_parameter_rulesets()
        assert mock_checkmk_client.list_rulesets.call_count == 2
