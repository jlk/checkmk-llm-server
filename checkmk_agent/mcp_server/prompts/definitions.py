"""Prompt definitions for MCP server.

This module contains all prompt schemas and metadata definitions.
All prompts available in the MCP server are defined here.
"""

from typing import Dict
from mcp.types import Prompt, PromptArgument


class PromptDefinitions:
    """Central repository for all prompt definitions."""

    @staticmethod
    def get_all_prompts() -> Dict[str, Prompt]:
        """Return all prompt definitions.
        
        Returns:
            Dict[str, Prompt]: Dictionary mapping prompt names to Prompt objects
        """
        return {
            "analyze_host_health": Prompt(
                name="analyze_host_health",
                description="Analyze the health of a specific host with detailed recommendations",
                arguments=[
                    PromptArgument(
                        name="host_name",
                        description="Name of the host to analyze",
                        required=True,
                    ),
                    PromptArgument(
                        name="include_grade",
                        description="Include health grade (A+ through F)",
                        required=False,
                    ),
                ],
            ),
            "troubleshoot_service": Prompt(
                name="troubleshoot_service",
                description="Comprehensive troubleshooting analysis for a service problem",
                arguments=[
                    PromptArgument(
                        name="host_name",
                        description="Host name where the service is running",
                        required=True,
                    ),
                    PromptArgument(
                        name="service_name",
                        description="Name of the service to troubleshoot",
                        required=True,
                    ),
                ],
            ),
            "infrastructure_overview": Prompt(
                name="infrastructure_overview",
                description="Get a comprehensive overview of infrastructure health and trends",
                arguments=[
                    PromptArgument(
                        name="time_range_hours",
                        description="Time range in hours for the analysis",
                        required=False,
                    )
                ],
            ),
            "optimize_parameters": Prompt(
                name="optimize_parameters",
                description="Get parameter optimization recommendations for a service",
                arguments=[
                    PromptArgument(
                        name="host_name",
                        description="Host name where the service is running",
                        required=True,
                    ),
                    PromptArgument(
                        name="service_name",
                        description="Name of the service to optimize",
                        required=True,
                    ),
                ],
            ),
            "adjust_host_check_attempts": Prompt(
                name="adjust_host_check_attempts",
                description="Configure host check sensitivity by adjusting maximum check attempts",
                arguments=[
                    PromptArgument(
                        name="host_name",
                        description="Name of the host to configure (or 'all' for global rule)",
                        required=True,
                    ),
                    PromptArgument(
                        name="max_attempts",
                        description="Maximum number of check attempts before host is considered down (1-10)",
                        required=True,
                    ),
                    PromptArgument(
                        name="reason",
                        description="Reason for adjustment (e.g., 'unreliable network', 'critical host')",
                        required=False,
                    ),
                ],
            ),
            "adjust_host_retry_interval": Prompt(
                name="adjust_host_retry_interval",
                description="Configure retry interval for host checks when in soft problem state",
                arguments=[
                    PromptArgument(
                        name="host_name",
                        description="Name of the host to configure (or 'all' for global rule)",
                        required=True,
                    ),
                    PromptArgument(
                        name="retry_interval",
                        description="Retry interval in minutes (0.1-60)",
                        required=True,
                    ),
                    PromptArgument(
                        name="reason",
                        description="Reason for adjustment (e.g., 'reduce load', 'faster recovery detection')",
                        required=False,
                    ),
                ],
            ),
            "adjust_host_check_timeout": Prompt(
                name="adjust_host_check_timeout",
                description="Configure timeout for host check commands",
                arguments=[
                    PromptArgument(
                        name="host_name",
                        description="Name of the host to configure (or 'all' for global rule)",
                        required=True,
                    ),
                    PromptArgument(
                        name="timeout_seconds",
                        description="Timeout in seconds (1-60)",
                        required=True,
                    ),
                    PromptArgument(
                        name="check_type",
                        description="Type of check: 'icmp', 'snmp', or 'all' (default: 'icmp')",
                        required=False,
                    ),
                    PromptArgument(
                        name="reason",
                        description="Reason for adjustment (e.g., 'slow network', 'distant location')",
                        required=False,
                    ),
                ],
            ),
        }

    @staticmethod
    def get_prompt_categories() -> Dict[str, list]:
        """Return prompts organized by categories.
        
        Returns:
            Dict[str, list]: Dictionary mapping categories to lists of prompt names
        """
        return {
            "health_analysis": [
                "analyze_host_health",
                "infrastructure_overview",
            ],
            "troubleshooting": [
                "troubleshoot_service", 
            ],
            "optimization": [
                "optimize_parameters",
            ],
            "host_configuration": [
                "adjust_host_check_attempts",
                "adjust_host_retry_interval", 
                "adjust_host_check_timeout",
            ],
        }

    @staticmethod
    def get_prompt_names() -> list:
        """Return list of all prompt names.
        
        Returns:
            list: List of all available prompt names
        """
        return list(PromptDefinitions.get_all_prompts().keys())

    @staticmethod
    def get_prompt_by_name(name: str) -> Prompt:
        """Get a specific prompt by name.
        
        Args:
            name: Name of the prompt
            
        Returns:
            Prompt: The prompt object
            
        Raises:
            KeyError: If prompt name not found
        """
        prompts = PromptDefinitions.get_all_prompts()
        if name not in prompts:
            raise KeyError(f"Prompt '{name}' not found. Available prompts: {list(prompts.keys())}")
        return prompts[name]