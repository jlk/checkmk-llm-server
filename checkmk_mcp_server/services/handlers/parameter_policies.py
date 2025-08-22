"""
Parameter filtering policies for controlling which parameters are included in rules.

This module implements a Strategy Pattern for parameter filtering, allowing different
business rules to be applied consistently across all parameter handlers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Set, Optional
import logging


logger = logging.getLogger(__name__)


class ParameterFilterStrategy(ABC):
    """Abstract strategy for filtering parameters based on business rules."""

    @abstractmethod
    def should_include_parameter(
        self, param_name: str, param_value: Any, context: Dict[str, Any]
    ) -> bool:
        """
        Determine if a parameter should be included based on business rules.

        Args:
            param_name: Name of the parameter
            param_value: Value of the parameter
            context: Context including user intent, existing parameters, etc.

        Returns:
            True if parameter should be included, False otherwise
        """
        pass

    @abstractmethod
    def get_filter_reason(
        self, param_name: str, param_value: Any, context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Get human-readable reason why parameter was filtered.

        Returns:
            Reason string if parameter would be filtered, None otherwise
        """
        pass


class TrendingParameterFilter(ParameterFilterStrategy):
    """Filter trending parameters based on user intent and existing rules."""

    TRENDING_PARAMS: Set[str] = {"trend_compute", "trend_levels", "trend_period"}

    def should_include_parameter(
        self, param_name: str, param_value: Any, context: Dict[str, Any]
    ) -> bool:
        if param_name not in self.TRENDING_PARAMS:
            return True

        # Check explicit user intent
        if context.get("include_trending", False):
            logger.debug(
                f"Including trending parameter '{param_name}' due to explicit user request"
            )
            return True

        # Check if trending already exists in current rule
        existing_params = context.get("existing_parameters", {})
        if any(p in existing_params for p in self.TRENDING_PARAMS):
            logger.debug(
                f"Including trending parameter '{param_name}' to preserve existing configuration"
            )
            return True

        # Default: exclude trending parameters
        logger.debug(
            f"Excluding trending parameter '{param_name}' (not explicitly requested)"
        )
        return False

    def get_filter_reason(
        self, param_name: str, param_value: Any, context: Dict[str, Any]
    ) -> Optional[str]:
        if param_name not in self.TRENDING_PARAMS:
            return None

        if not self.should_include_parameter(param_name, param_value, context):
            return f"Trending parameter '{param_name}' excluded (not explicitly requested and not present in existing rule)"

        return None


class ParameterPolicyManager:
    """Centralized manager for parameter inclusion policies."""

    def __init__(self):
        self.filters = {
            "trending": TrendingParameterFilter(),
            # Add other filters as needed
        }
        self.logger = logging.getLogger(__name__)

    def filter_parameters(
        self, parameters: Dict[str, Any], context: Dict[str, Any]
    ) -> tuple[Dict[str, Any], list[str]]:
        """
        Apply all registered filters to parameters.

        Args:
            parameters: Original parameters to filter
            context: Context including user intent, existing parameters, etc.

        Returns:
            Tuple of (filtered_parameters, filter_messages)
        """
        filtered = {}
        filter_messages = []

        for param_name, param_value in parameters.items():
            # Apply all filters
            should_include = True
            filter_reason = None

            for filter_name, filter_strategy in self.filters.items():
                if not filter_strategy.should_include_parameter(
                    param_name, param_value, context
                ):
                    should_include = False
                    filter_reason = filter_strategy.get_filter_reason(
                        param_name, param_value, context
                    )
                    break

            if should_include:
                filtered[param_name] = param_value
            elif filter_reason:
                filter_messages.append(filter_reason)
                self.logger.info(filter_reason)

        # Log summary if parameters were filtered
        if len(filtered) < len(parameters):
            filtered_count = len(parameters) - len(filtered)
            self.logger.info(
                f"Filtered out {filtered_count} parameter(s) based on policies"
            )

        return filtered, filter_messages

    def add_filter(self, name: str, filter_strategy: ParameterFilterStrategy):
        """Add a new parameter filter strategy."""
        self.filters[name] = filter_strategy

    def remove_filter(self, name: str):
        """Remove a parameter filter strategy."""
        if name in self.filters:
            del self.filters[name]

    def get_available_filters(self) -> list[str]:
        """Get list of available filter names."""
        return list(self.filters.keys())


# Global policy manager instance
default_policy_manager = ParameterPolicyManager()
