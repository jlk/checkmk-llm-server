"""
Test for the rule finding empty conditions fix.

This test ensures that rules with empty host or service conditions
(which apply to ALL hosts/services) are correctly found by the
rule finding logic.

Addresses the bug where "no existing rule" was reported when rules
with empty conditions actually existed.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, List

from checkmk_mcp_server.services.parameter_service import ParameterService, RuleSearchFilter
from checkmk_mcp_server.config import AppConfig, CheckmkConfig, LLMConfig


class TestRuleFindingEmptyConditionsFix:
    """Test the rule finding fix for empty conditions."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return AppConfig(
            checkmk=CheckmkConfig(
                server_url="https://test-server.local",
                username="test_user",
                password="test_password",
                site="test_site",
            ),
            llm=LLMConfig(openai_api_key="test_key", default_model="gpt-3.5-turbo"),
        )

    @pytest.fixture
    def mock_client(self):
        """Create mock client."""
        client = Mock()
        client.list_rules = AsyncMock()
        return client

    @pytest.fixture
    def parameter_service(self, mock_client, mock_config):
        """Create parameter service with mocked dependencies."""
        return ParameterService(mock_client, mock_config)

    def create_test_rules(self) -> List[Dict[str, Any]]:
        """Create test rules including those with empty conditions."""
        return [
            # Rule with exact match
            {
                "id": "exact_match_rule",
                "ruleset": "checkgroup_parameters:temperature",
                "properties": {"disabled": False},
                "conditions": {
                    "host_name": ["piaware"],
                    "service_description": ["Temperature Zone 0"],
                },
                "value_raw": {"levels": (60, 70)},
            },
            # Rule with empty host conditions (applies to ALL hosts)
            {
                "id": "all_hosts_rule",
                "ruleset": "checkgroup_parameters:temperature",
                "properties": {"disabled": False},
                "conditions": {"service_description": ["Temperature Zone 0"]},
                "value_raw": {"levels": (55, 65)},
            },
            # Rule with empty service conditions (applies to ALL services)
            {
                "id": "all_services_rule",
                "ruleset": "checkgroup_parameters:temperature",
                "properties": {"disabled": False},
                "conditions": {"host_name": ["piaware"]},
                "value_raw": {"levels": (70, 80)},
            },
            # Rule with completely empty conditions (global rule)
            {
                "id": "global_rule",
                "ruleset": "checkgroup_parameters:temperature",
                "properties": {"disabled": False},
                "conditions": {},
                "value_raw": {"levels": (50, 60)},
            },
            # Rule from different ruleset (should not match)
            {
                "id": "different_ruleset",
                "ruleset": "checkgroup_parameters:cpu_utilization",
                "properties": {"disabled": False},
                "conditions": {
                    "host_name": ["piaware"],
                    "service_description": ["Temperature Zone 0"],
                },
                "value_raw": {"levels": (80, 90)},
            },
        ]

    @pytest.mark.asyncio
    async def test_search_filter_handles_empty_host_conditions(self, parameter_service):
        """Test that search filter correctly handles rules with empty host conditions."""

        # Rule with empty host conditions should match any host
        rule_with_empty_hosts = {
            "id": "empty_hosts_rule",
            "ruleset": "checkgroup_parameters:temperature",
            "properties": {"disabled": False},
            "conditions": {"service_description": ["Temperature Zone 0"]},
            "value_raw": {"levels": (55, 65)},
        }

        search_filter = RuleSearchFilter(
            host_patterns=["piaware"],
            service_patterns=["Temperature Zone 0"],
            rulesets=["checkgroup_parameters:temperature"],
            enabled_only=True,
        )

        # This should match because empty host conditions mean "applies to all hosts"
        matches = parameter_service._rule_matches_search_filter(
            rule_with_empty_hosts, search_filter
        )
        assert matches, "Rule with empty host conditions should match any host"

    @pytest.mark.asyncio
    async def test_search_filter_handles_empty_service_conditions(
        self, parameter_service
    ):
        """Test that search filter correctly handles rules with empty service conditions."""

        # Rule with empty service conditions should match any service
        rule_with_empty_services = {
            "id": "empty_services_rule",
            "ruleset": "checkgroup_parameters:temperature",
            "properties": {"disabled": False},
            "conditions": {"host_name": ["piaware"]},
            "value_raw": {"levels": (70, 80)},
        }

        search_filter = RuleSearchFilter(
            host_patterns=["piaware"],
            service_patterns=["Temperature Zone 0"],
            rulesets=["checkgroup_parameters:temperature"],
            enabled_only=True,
        )

        # This should match because empty service conditions mean "applies to all services"
        matches = parameter_service._rule_matches_search_filter(
            rule_with_empty_services, search_filter
        )
        assert matches, "Rule with empty service conditions should match any service"

    @pytest.mark.asyncio
    async def test_search_filter_handles_completely_empty_conditions(
        self, parameter_service
    ):
        """Test that search filter correctly handles rules with no conditions at all."""

        # Global rule with no conditions should match everything
        global_rule = {
            "id": "global_rule",
            "ruleset": "checkgroup_parameters:temperature",
            "properties": {"disabled": False},
            "conditions": {},
            "value_raw": {"levels": (50, 60)},
        }

        search_filter = RuleSearchFilter(
            host_patterns=["piaware"],
            service_patterns=["Temperature Zone 0"],
            rulesets=["checkgroup_parameters:temperature"],
            enabled_only=True,
        )

        # This should match because empty conditions mean "applies to everything"
        matches = parameter_service._rule_matches_search_filter(
            global_rule, search_filter
        )
        assert matches, "Rule with no conditions should match any host/service"

    @pytest.mark.asyncio
    async def test_find_existing_rule_finds_empty_condition_rules(
        self, parameter_service, mock_client
    ):
        """Test that _find_existing_rule_for_service finds rules with empty conditions."""

        test_rules = self.create_test_rules()
        mock_client.list_rules.return_value = test_rules

        # Test finding a rule for piaware/Temperature Zone 0
        # Should find multiple rules including those with empty conditions
        existing_rule = await parameter_service._find_existing_rule_for_service(
            "piaware", "Temperature Zone 0", "checkgroup_parameters:temperature"
        )

        # Should find one of the matching rules
        assert existing_rule is not None, "Should find an existing rule"
        assert existing_rule["id"] in [
            "exact_match_rule",
            "all_hosts_rule",
            "all_services_rule",
            "global_rule",
        ], f"Found unexpected rule: {existing_rule['id']}"

    @pytest.mark.asyncio
    async def test_find_existing_rule_finds_global_rules_for_any_host_service(
        self, parameter_service, mock_client
    ):
        """Test that global rules (empty conditions) are found for any host/service."""

        # Only include the global rule
        global_rule_only = [
            {
                "id": "global_rule",
                "ruleset": "checkgroup_parameters:temperature",
                "properties": {"disabled": False},
                "conditions": {},
                "value_raw": {"levels": (50, 60)},
            }
        ]

        mock_client.list_rules.return_value = global_rule_only

        # Test with any host/service combination - should find the global rule
        test_cases = [
            ("piaware", "Temperature Zone 0"),
            ("other-host", "CPU Load"),
            ("random-server", "Disk Space"),
        ]

        for host, service in test_cases:
            existing_rule = await parameter_service._find_existing_rule_for_service(
                host, service, "checkgroup_parameters:temperature"
            )

            assert (
                existing_rule is not None
            ), f"Global rule should be found for {host}/{service}"
            assert (
                existing_rule["id"] == "global_rule"
            ), f"Should find global rule for {host}/{service}"

    @pytest.mark.asyncio
    async def test_find_existing_rule_respects_ruleset_filtering(
        self, parameter_service, mock_client
    ):
        """Test that rules from different rulesets are not returned."""

        test_rules = self.create_test_rules()
        mock_client.list_rules.return_value = test_rules

        # Look for temperature rules but in CPU ruleset - should not find anything
        existing_rule = await parameter_service._find_existing_rule_for_service(
            "piaware", "Temperature Zone 0", "checkgroup_parameters:cpu_utilization"
        )

        # Should not find temperature rules when looking in CPU ruleset
        if existing_rule:
            assert (
                existing_rule["id"] == "different_ruleset"
            ), "Should only find CPU ruleset rule"
        # Note: might be None if the mock doesn't return the CPU rule

    @pytest.mark.asyncio
    async def test_piaware_temperature_zone_0_specific_case(
        self, parameter_service, mock_client
    ):
        """Test the specific case reported: piaware/Temperature Zone 0."""

        # Simulate a realistic scenario where there's a global temperature rule
        realistic_rules = [
            {
                "id": "global_temp_rule",
                "ruleset": "checkgroup_parameters:temperature",
                "properties": {"disabled": False},
                "conditions": {},  # Empty conditions = applies to all hosts/services
                "value_raw": {
                    "levels": (60, 70),
                    "device_levels_handling": "devdefault",
                    "input_unit": "c",
                    "output_unit": "c",
                },
            }
        ]

        mock_client.list_rules.return_value = realistic_rules

        # This exact case was failing before the fix
        existing_rule = await parameter_service._find_existing_rule_for_service(
            "piaware", "Temperature Zone 0", "checkgroup_parameters:temperature"
        )

        # Should now find the global rule
        assert existing_rule is not None, "Should find the global temperature rule"
        assert (
            existing_rule["id"] == "global_temp_rule"
        ), "Should find the specific global rule"
        assert existing_rule["value_raw"]["levels"] == (
            60,
            70,
        ), "Should return correct rule parameters"
