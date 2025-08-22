"""
Test for temperature parameter int-to-float conversion fix.

This test validates the fix for the API error:
"Upper Temperature Levels: The value 75 has type int, but must be of type float"
"""

import pytest
from unittest.mock import Mock

from checkmk_mcp_server.api_client import CheckmkClient


class TestTemperatureParameterFix:
    """Test temperature parameter conversion from integers to floats."""

    @pytest.fixture
    def client(self):
        """Create a mock client for testing conversion logic."""
        client = CheckmkClient.__new__(CheckmkClient)
        client.logger = Mock()
        return client

    def test_temperature_parameters_convert_integers_to_floats(self, client):
        """Test that temperature parameters selectively convert integers to floats to fix API error."""
        # Arrange - Original problematic parameters that caused API 400 error
        problematic_params = {
            "levels": [
                75,
                80,
            ],  # These integers caused the API error - should become floats
            "levels_lower": [
                5,
                0,
            ],  # These integers caused the API error - should become floats
            "trend_levels": [
                5,
                10,
            ],  # These should remain integers per Checkmk API requirements
            "trend_levels_lower": [
                15,
                10,
            ],  # These should remain integers per Checkmk API requirements
        }

        # Act - Convert parameters for temperature ruleset
        result = client._convert_lists_to_tuples_for_parameters(
            problematic_params, "checkgroup_parameters:temperature"
        )

        # Assert - Main temperature levels should be floats, trend levels should remain integers
        expected = {
            "levels": (75.0, 80.0),
            "levels_lower": (5.0, 0.0),
            "trend_levels": (5, 10),
            "trend_levels_lower": (15, 10),
        }

        assert result == expected

        # Verify main temperature levels are floats
        for key in ["levels", "levels_lower"]:
            value = result[key]
            assert isinstance(value, tuple), f"{key} should be tuple"
            for item in value:
                assert isinstance(item, float), f"All values in {key} should be floats"

        # Verify trend levels remain integers
        for key in ["trend_levels", "trend_levels_lower"]:
            value = result[key]
            assert isinstance(value, tuple), f"{key} should be tuple"
            for item in value:
                assert isinstance(
                    item, int
                ), f"All values in {key} should remain integers"

    def test_mixed_types_handled_correctly(self, client):
        """Test that mixed integer/float parameters are handled correctly."""
        # Arrange - Mix of integers and floats
        mixed_params = {
            "levels": [75, 80.5],  # Mix of int and float
            "levels_lower": [5.0, 0],  # Mix of float and int
        }

        # Act
        result = client._convert_lists_to_tuples_for_parameters(
            mixed_params, "checkgroup_parameters:temperature"
        )

        # Assert - Integers converted to floats, existing floats preserved
        expected = {"levels": (75.0, 80.5), "levels_lower": (5.0, 0.0)}

        assert result == expected

    def test_non_temperature_rulesets_preserve_integers(self, client):
        """Test that non-temperature rulesets preserve integers for backward compatibility."""
        # Arrange - Parameters for non-temperature ruleset
        cpu_params = {
            "levels": [75, 80],  # Should remain integers for non-temperature rules
        }

        # Act
        result = client._convert_lists_to_tuples_for_parameters(
            cpu_params, "checkgroup_parameters:cpu_utilization"
        )

        # Assert - Should convert to tuple but preserve integers
        expected = {"levels": (75, 80)}
        assert result == expected

        # Verify values remain integers
        for item in result["levels"]:
            assert isinstance(
                item, int
            ), "Non-temperature parameters should preserve integers"

    def test_non_numeric_values_preserved(self, client):
        """Test that non-numeric values (None, strings) are preserved."""
        # Arrange - Parameters with non-numeric values
        params_with_none = {
            "levels": [
                None,
                80,
            ],  # Mix of None and int - should become floats for main levels
            "trend_levels": [
                "auto",
                10,
            ],  # Mix of string and int - should remain integers for trend levels
        }

        # Act
        result = client._convert_lists_to_tuples_for_parameters(
            params_with_none, "checkgroup_parameters:temperature"
        )

        # Assert - Non-numeric values preserved, main levels converted to floats, trend levels remain integers
        expected = {"levels": (None, 80.0), "trend_levels": ("auto", 10)}

        assert result == expected

    def test_temperature_ruleset_detection(self, client):
        """Test that temperature rulesets are correctly identified."""
        test_params = {"levels": [75, 80]}

        # Test various temperature ruleset patterns
        temperature_rulesets = [
            "checkgroup_parameters:temperature",
            "checkgroup_parameters:hw_temperature",
            "checkgroup_parameters:ipmi_sensors",
            "checkgroup_parameters:ipmi_temperature",
            "some_ruleset_with_temperature_in_name",
            "custom_temp_ruleset",
        ]

        for ruleset in temperature_rulesets:
            result = client._convert_lists_to_tuples_for_parameters(
                test_params, ruleset
            )

            # Should convert integers to floats for temperature rulesets
            assert result["levels"] == (75.0, 80.0), f"Failed for ruleset: {ruleset}"
            for item in result["levels"]:
                assert isinstance(
                    item, float
                ), f"Should be float for ruleset: {ruleset}"

    def test_convert_integers_to_floats_helper(self, client):
        """Test the helper method for converting integers to floats."""
        # Test various input types
        test_cases = [
            ([75, 80], [75.0, 80.0]),
            ([5.5, 10], [5.5, 10.0]),
            ([None, 75], [None, 75.0]),
            (["auto", 80], ["auto", 80.0]),
            ([75, 80.5, None, "manual"], [75.0, 80.5, None, "manual"]),
        ]

        for input_list, expected in test_cases:
            result = client._convert_integers_to_floats(input_list)
            assert result == expected, f"Failed for input: {input_list}"
