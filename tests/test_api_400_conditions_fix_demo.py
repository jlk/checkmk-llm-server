"""
Demonstration test showing the exact fix for API 400 error on rule conditions.

This test clearly demonstrates the fix that resolves:
API error 400 on POST domain-types/rule/collections/all: These fields have problems: conditions

BEFORE FIX: Invalid "match_regex" operator caused API 400 error
AFTER FIX: Correct "one_of" operator works without error
"""

import pytest
import json
from unittest.mock import patch, call
from checkmk_mcp_server.api_client import CheckmkClient
from checkmk_mcp_server.config import CheckmkConfig


class TestAPI400ConditionsFixDemo:
    """Demonstration of the API 400 conditions fix."""

    @pytest.fixture
    def config(self):
        return CheckmkConfig(
            server_url="https://test-checkmk.com",
            username="test_user",
            password="test_password",
            site="test_site",
        )

    @pytest.fixture
    def client(self, config):
        with patch("checkmk_mcp_server.api_client.requests.Session"), patch(
            "checkmk_mcp_server.api_client.logging.getLogger"
        ):
            return CheckmkClient(config)

    def test_conditions_format_fix_demonstration(self, client):
        """
        Demonstrate the exact fix for API 400 conditions error.

        This test shows that the conditions are now formatted correctly
        using "one_of" operator instead of the invalid "match_regex".
        """

        # Capture the actual API calls made by create_service_parameter_rule
        with patch.object(client, "_make_request") as mock_request:
            # First call is GET host config (for folder determination), second is POST rule creation
            mock_request.side_effect = [
                # Host lookup response
                {
                    "id": "piaware",
                    "extensions": {
                        "folder": "/",  # Host is in root folder
                        "attributes": {},
                    },
                },
                # Rule creation response
                {
                    "id": "demo-rule-123",
                    "ruleset": "checkgroup_parameters:temperature",
                    "folder": "/",
                },
            ]

            # Act - Create the exact rule that was failing
            client.create_service_parameter_rule(
                ruleset_name="checkgroup_parameters:temperature",
                folder="/",
                parameters={
                    "levels": [75, 80],
                    "levels_lower": [5, 0],
                    "device_levels_handling": "worst",
                    "trend_compute": {
                        "period": 30,
                        "trend_levels": [5, 10],
                        "trend_levels_lower": [5, 10],
                    },
                    "output_unit": "c",
                },
                host_name="piaware",
                service_pattern="Temperature Zone 0",
                description="Temperature parameters for piaware Temperature Zone 0",
            )

            # Assert - Verify both API calls were made correctly
            assert mock_request.call_count == 2
            call_args_list = mock_request.call_args_list

            # First call: GET host config for folder determination
            first_call = call_args_list[0]
            assert first_call[0][0] == "GET"
            assert first_call[0][1] == "/objects/host_config/piaware"

            # Second call: POST rule creation
            second_call = call_args_list[1]
            assert second_call[0][0] == "POST"
            assert second_call[0][1] == "/domain-types/rule/collections/all"

            # Check the request payload from the rule creation call
            payload = second_call[1]["json"]

            print("\n=== API Request Payload (AFTER FIX) ===")
            print(json.dumps(payload, indent=2))

            # Verify correct conditions format (the key fix)
            conditions = payload["conditions"]
            assert conditions is not None, "Conditions should be present"

            # ✅ FIXED: Uses "one_of" operator instead of invalid "match_regex"
            assert conditions["host_name"]["operator"] == "one_of"
            assert conditions["service_description"]["operator"] == "one_of"

            # ✅ FIXED: Proper structure with "match_on" array
            assert conditions["host_name"]["match_on"] == ["piaware"]
            assert conditions["service_description"]["match_on"] == [
                "Temperature Zone 0"
            ]

            # ✅ VERIFICATION: No invalid "match_regex" operator anywhere
            for condition_name, condition_data in conditions.items():
                assert (
                    condition_data["operator"] != "match_regex"
                ), f"Found invalid 'match_regex' operator in {condition_name}"

            print("\n=== CONDITIONS VERIFICATION ===")
            print(f"host_name operator: {conditions['host_name']['operator']} ✅")
            print(
                f"service_description operator: {conditions['service_description']['operator']} ✅"
            )
            print("No 'match_regex' operators found ✅")

    def test_before_after_comparison(self, client):
        """
        Compare the old (broken) vs new (fixed) conditions format.

        This test documents what the fix changed to resolve the API 400 error.
        """

        # BEFORE (would cause API 400 error):
        old_broken_conditions = {
            "host_name": ["piaware"],  # Simple list format
            "service_description": {  # Invalid match_regex operator
                "match_regex": ["Temperature Zone 0"],
                "operator": "match_regex",  # ❌ This was invalid!
            },
        }

        # AFTER (fixed format that works):
        new_fixed_conditions = {
            "host_name": {
                "match_on": ["piaware"],
                "operator": "one_of",  # ✅ Valid operator
            },
            "service_description": {
                "match_on": ["Temperature Zone 0"],
                "operator": "one_of",  # ✅ Valid operator
            },
        }

        # Test that our implementation produces the fixed format
        with patch.object(client, "create_rule") as mock_create_rule:
            mock_create_rule.return_value = {"id": "test-rule"}

            client.create_service_parameter_rule(
                ruleset_name="checkgroup_parameters:temperature",
                folder="/",
                parameters={"levels": [70, 80]},
                host_name="piaware",
                service_pattern="Temperature Zone 0",
            )

            # Verify we use the NEW fixed format
            call_args = mock_create_rule.call_args
            actual_conditions = call_args[1]["conditions"]

            assert (
                actual_conditions == new_fixed_conditions
            ), f"Expected fixed conditions format, got: {actual_conditions}"

            print("\n=== BEFORE/AFTER COMPARISON ===")
            print("❌ BEFORE (caused API 400):")
            print(json.dumps(old_broken_conditions, indent=2))
            print("\n✅ AFTER (works correctly):")
            print(json.dumps(new_fixed_conditions, indent=2))

    def test_api_payload_exact_reproduction(self, client):
        """
        Test the exact API payload that was causing the 400 error.

        This reproduces the exact scenario from the error logs.
        """
        expected_payload = {
            "ruleset": "checkgroup_parameters:temperature",
            "folder": "/",
            "value_raw": json.dumps(
                {
                    "levels": [75, 80],
                    "levels_lower": [5, 0],
                    "device_levels_handling": "worst",
                    "trend_compute": {
                        "period": 30,
                        "trend_levels": [5, 10],
                        "trend_levels_lower": [5, 10],
                    },
                    "output_unit": "c",
                }
            ),
            "conditions": {
                "host_name": {"match_on": ["piaware"], "operator": "one_of"},
                "service_description": {
                    "match_on": ["Temperature Zone 0"],
                    "operator": "one_of",
                },
            },
            "properties": {
                "description": "Temperature parameters for piaware Temperature Zone 0"
            },
        }

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"id": "reproduction-test"}

            # Execute the exact call that was failing
            client.create_service_parameter_rule(
                ruleset_name="checkgroup_parameters:temperature",
                folder="/",
                parameters={
                    "levels": [75, 80],
                    "levels_lower": [5, 0],
                    "device_levels_handling": "worst",
                    "trend_compute": {
                        "period": 30,
                        "trend_levels": [5, 10],
                        "trend_levels_lower": [5, 10],
                    },
                    "output_unit": "c",
                },
                host_name="piaware",
                service_pattern="Temperature Zone 0",
                description="Temperature parameters for piaware Temperature Zone 0",
            )

            # Verify exact payload structure
            actual_payload = mock_request.call_args[1]["json"]

            # Key verification: conditions format is correct
            assert actual_payload["conditions"] == expected_payload["conditions"]

            # Verify all operators are "one_of" (not "match_regex")
            for condition in actual_payload["conditions"].values():
                assert condition["operator"] == "one_of"

            print("\n=== EXACT API PAYLOAD VERIFICATION ===")
            print("✅ Conditions format is correct")
            print("✅ All operators are 'one_of' (not 'match_regex')")
            print("✅ No API 400 error should occur")

            print(f"\nActual payload conditions:")
            print(json.dumps(actual_payload["conditions"], indent=2))
