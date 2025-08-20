"""Prompt handlers for MCP server.

This module contains all prompt execution logic and service integration.
"""

from typing import Dict, Optional, Any, Union
from mcp.types import GetPromptResult, PromptMessage, TextContent
import logging

from ..utils.serialization import safe_json_dumps

logger = logging.getLogger(__name__)


class PromptHandlers:
    """Handles prompt execution logic and service integration."""
    
    def __init__(self):
        """Initialize prompt handlers."""
        self._services: Dict[str, Any] = {}
    
    def initialize_services(self, services: Dict[str, Any]) -> None:
        """Initialize with service instances.
        
        Args:
            services: Dictionary of service name to service instance
        """
        self._services = services
    
    async def handle_prompt(self, prompt_name: str, args: Dict[str, Any]) -> GetPromptResult:
        """Handle a prompt request by dispatching to the appropriate handler.
        
        Args:
            prompt_name: Name of the prompt to handle
            args: Validated prompt arguments
            
        Returns:
            GetPromptResult: Generated prompt result
        """
        try:
            if prompt_name == 'analyze_host_health':
                return await self._handle_analyze_host_health(args)
            elif prompt_name == 'troubleshoot_service':
                service_service = self._services.get('service_service')
                return await PromptHandlers.handle_troubleshoot_service(args, service_service)
            elif prompt_name == 'infrastructure_overview':
                status_service = self._services.get('status_service')
                return await PromptHandlers.handle_infrastructure_overview(args, status_service)
            elif prompt_name == 'optimize_parameters':
                parameter_service = self._services.get('parameter_service')
                return await PromptHandlers.handle_optimize_parameters(args, parameter_service)
            elif prompt_name == 'adjust_host_check_attempts':
                parameter_service = self._services.get('parameter_service')
                return await PromptHandlers.handle_adjust_host_check_attempts(args, parameter_service)
            elif prompt_name == 'adjust_host_retry_interval':
                parameter_service = self._services.get('parameter_service')
                return await PromptHandlers.handle_adjust_host_retry_interval(args, parameter_service)
            elif prompt_name == 'adjust_host_check_timeout':
                parameter_service = self._services.get('parameter_service')
                return await PromptHandlers.handle_adjust_host_check_timeout(args, parameter_service)
            else:
                return GetPromptResult(
                    description=f"Unknown prompt: {prompt_name}",
                    messages=[
                        PromptMessage(
                            role="user", 
                            content=TextContent(type="text", text=f"Error: Unknown prompt '{prompt_name}'")
                        )
                    ]
                )
        except Exception as e:
            logger.exception(f"Error handling prompt {prompt_name}")
            return GetPromptResult(
                description=f"Error processing prompt: {str(e)}",
                messages=[
                    PromptMessage(
                        role="user", 
                        content=TextContent(type="text", text=f"Error processing prompt '{prompt_name}': {str(e)}")
                    )
                ]
            )

    async def _handle_analyze_host_health(self, args: Dict[str, Any]) -> GetPromptResult:
        """Handle analyze_host_health prompt.
        
        Args:
            args: Validated prompt arguments
            
        Returns:
            GetPromptResult: Generated prompt result
        """
        host_name = args.get("host_name", "")
        include_grade = args.get("include_grade", True)

        host_service = self._services.get('host_service')
        status_service = self._services.get('status_service')

        # Get current host data
        host_result = await host_service.get_host(
            name=host_name, include_status=True
        )
        host_data = (
            host_result.data.model_dump() if host_result.success and host_result.data else {}
        )

        # Get host health analysis
        health_result = await status_service.analyze_host_health(
            host_name=host_name,
            include_grade=include_grade,
            include_recommendations=True,
        )
        health_data = health_result.data if health_result.success else {}

        prompt_text = f"""Analyze the health of host '{host_name}' based on the following monitoring data:

HOST INFORMATION:
{safe_json_dumps(host_data)}

HEALTH ANALYSIS:
{safe_json_dumps(health_data)}

Please provide:
1. Overall health assessment {'with letter grade (A+ through F)' if include_grade else ''}
2. Key issues requiring attention
3. Specific recommendations for improvement
4. Trend analysis if historical data is available

Focus on actionable insights for system administrators."""

        return GetPromptResult(
            description=f"Generated prompt for analyze_host_health",
            messages=[
                PromptMessage(
                    role="user", content=TextContent(type="text", text=prompt_text)
                )
            ]
        )

    @staticmethod
    async def handle_troubleshoot_service(
        args: Dict[str, Any],
        service_service: Any
    ) -> GetPromptResult:
        """Handle troubleshoot_service prompt.
        
        Args:
            args: Validated prompt arguments
            service_service: Service service instance
            
        Returns:
            GetPromptResult: Generated prompt result
        """
        host_name = args.get("host_name", "")
        service_name = args.get("service_name", "")

        # Get service status and details
        services_result = await service_service.list_host_services(
            host_name=host_name
        )
        service_data = None
        if services_result.success and services_result.data:
            for service in services_result.data.services:
                if hasattr(service, 'service_name') and service.service_name == service_name:
                    service_data = service.model_dump()
                    break

        prompt_text = f"""Troubleshoot the service '{service_name}' on host '{host_name}' based on this monitoring data:

SERVICE STATUS:
{safe_json_dumps(service_data or {'error': 'Service not found'})}

Please provide a comprehensive troubleshooting analysis including:
1. Current service state and what it indicates
2. Most likely root causes based on the service type and status
3. Step-by-step troubleshooting procedure
4. Commands to run for diagnosis
5. Common solutions for this type of problem
6. Prevention strategies

Be specific to the service type and provide practical commands where applicable."""

        return GetPromptResult(
            description=f"Generated prompt for troubleshoot_service",
            messages=[
                PromptMessage(
                    role="user", content=TextContent(type="text", text=prompt_text)
                )
            ]
        )

    @staticmethod
    async def handle_infrastructure_overview(
        args: Dict[str, Any],
        status_service: Any
    ) -> GetPromptResult:
        """Handle infrastructure_overview prompt.
        
        Args:
            args: Validated prompt arguments
            status_service: Status service instance
            
        Returns:
            GetPromptResult: Generated prompt result
        """
        time_range_hours = int(args.get("time_range_hours", "24"))

        # Get comprehensive infrastructure data
        dashboard_result = await status_service.get_health_dashboard()
        problems_result = await status_service.get_critical_problems()

        dashboard_data = (
            dashboard_result.data if dashboard_result.success else {}
        )
        problems_data = (
            problems_result.data if problems_result.success else {}
        )

        prompt_text = f"""Provide a comprehensive infrastructure overview based on the last {time_range_hours} hours of monitoring data:

HEALTH DASHBOARD:
{safe_json_dumps(dashboard_data)}

CRITICAL PROBLEMS:
{safe_json_dumps(problems_data)}

Please provide:
1. Executive summary of infrastructure health
2. Top 5 issues requiring immediate attention
3. Trending patterns and early warnings
4. Resource utilization highlights
5. Performance bottlenecks and capacity concerns
6. Security incidents or vulnerabilities
7. Maintenance windows or scheduled activities
8. Budget or cost optimization opportunities

Focus on strategic insights for IT leadership and operational priorities."""

        return GetPromptResult(
            description=f"Generated prompt for infrastructure_overview",
            messages=[
                PromptMessage(
                    role="user", content=TextContent(type="text", text=prompt_text)
                )
            ]
        )

    @staticmethod
    async def handle_optimize_parameters(
        args: Dict[str, Any],
        parameter_service: Any
    ) -> GetPromptResult:
        """Handle optimize_parameters prompt.
        
        Args:
            args: Validated prompt arguments
            parameter_service: Parameter service instance
            
        Returns:
            GetPromptResult: Generated prompt result
        """
        host_name = args.get("host_name", "")
        service_name = args.get("service_name", "")

        # Get current service parameters
        parameters_result = await parameter_service.get_service_effective_parameters(
            host_name=host_name,
            service_name=service_name,
            include_rule_info=True,
        )
        parameters_data = (
            parameters_result.data if parameters_result.success else {}
        )

        # Get service performance history (if available)
        try:
            metrics_data = {"note": "Historical metrics would be integrated here"}
        except Exception:
            metrics_data = {}

        prompt_text = f"""Optimize parameters for service '{service_name}' on host '{host_name}' based on current configuration and performance:

CURRENT PARAMETERS:
{safe_json_dumps(parameters_data)}

PERFORMANCE METRICS:
{safe_json_dumps(metrics_data)}

Please provide comprehensive parameter optimization recommendations:

1. Current parameter analysis and effectiveness
2. Recommended threshold adjustments with rationale
3. Optimal warning and critical levels
4. Frequency and timing adjustments
5. Alert suppression strategies to reduce noise
6. Performance impact considerations

Focus on reducing false positives while maintaining effective monitoring coverage."""

        return GetPromptResult(
            description=f"Generated prompt for optimize_parameters",
            messages=[
                PromptMessage(
                    role="user", content=TextContent(type="text", text=prompt_text)
                )
            ]
        )

    @staticmethod
    async def handle_adjust_host_check_attempts(
        args: Dict[str, Any],
        host_service: Any,
        checkmk_client: Any
    ) -> GetPromptResult:
        """Handle adjust_host_check_attempts prompt.
        
        Args:
            args: Validated prompt arguments
            host_service: Host service instance
            checkmk_client: Checkmk client instance
            
        Returns:
            GetPromptResult: Generated prompt result
        """
        host_name = args.get("host_name", "")
        max_attempts_str = args.get("max_attempts")
        reason = args.get("reason", "Not specified")

        # Validate parameters - will be moved to validators.py
        if not host_name:
            raise ValueError("host_name is required")
        
        if not max_attempts_str:
            raise ValueError("max_attempts is required")

        try:
            max_attempts = int(max_attempts_str)
            if max_attempts < 1 or max_attempts > 10:
                raise ValueError("max_attempts must be between 1 and 10")
        except (TypeError, ValueError):
            raise ValueError(
                "max_attempts must be a valid integer between 1 and 10"
            )

        # Get current host configuration
        current_config = {}
        if host_name != "all":
            try:
                # Get current host data
                host_result = await host_service.get_host(
                    name=host_name, include_status=True
                )
                if host_result.success:
                    host_data = host_result.data
                    current_config = {
                        "current_attempts": getattr(
                            host_data, "host_max_check_attempts", "Unknown"
                        ),
                        "retry_interval": getattr(
                            host_data, "host_retry_interval", "Unknown"
                        ),
                        "check_interval": getattr(
                            host_data, "host_check_interval", "Unknown"
                        ),
                    }
            except Exception as e:
                current_config = {
                    "error": f"Could not retrieve current configuration: {str(e)}"
                }

        # Create rule for max_check_attempts
        try:
            if host_name == "all":
                conditions = {}
            else:
                conditions = {"host_name": [host_name]}

            rule_result = await checkmk_client.create_rule(
                ruleset="extra_host_conf:max_check_attempts",
                folder="/",
                value_raw=str(max_attempts),
                conditions=conditions,
                properties={
                    "comment": f"Host check attempts adjustment - {reason}"
                },
            )
            rule_created = rule_result.get("id", "created successfully")
        except Exception as e:
            rule_created = f"Error creating rule: {str(e)}"

        # Calculate sensitivity level
        if max_attempts <= 2:
            sensitivity = "High (fast detection)"
        elif max_attempts <= 4:
            sensitivity = "Medium (balanced)"
        else:
            sensitivity = "Low (reduce false alerts)"

        check_interval = current_config.get("check_interval", "Unknown")
        if check_interval != "Unknown" and isinstance(
            check_interval, (int, float)
        ):
            detection_time = max_attempts * check_interval
            current_attempts = current_config.get(
                "current_attempts", "Unknown"
            )
            if current_attempts != "Unknown" and isinstance(
                current_attempts, (int, float)
            ):
                current_time = current_attempts * check_interval
            else:
                current_time = "Unknown"
        else:
            detection_time = "Unknown"
            current_time = "Unknown"

        prompt_text = f"""Host Check Attempts Configuration for '{host_name}'

CURRENT CONFIGURATION:
{safe_json_dumps(current_config)}

PROPOSED CHANGE:
- New max attempts: {max_attempts}
- Sensitivity level: {sensitivity}
- Reason for change: {reason}
- Expected detection time: {detection_time} minutes (if check interval is {check_interval})
- Current detection time: {current_time} minutes

ANALYSIS:
1. Impact on monitoring sensitivity:
   - Lower attempts (1-2): Fast detection, more false positives
   - Medium attempts (3-4): Balanced approach, good for most hosts
   - Higher attempts (5-10): Reduces false alerts, slower detection

2. Recommended scenarios:
   - Critical hosts with stable network: 2-3 attempts
   - Standard hosts: 3-4 attempts  
   - Unreliable network or non-critical hosts: 4-6 attempts
   - Test/development hosts: 5-10 attempts

3. Performance considerations:
   - More attempts = longer detection time
   - Consider network reliability and host criticality
   - Balance between alert noise and detection speed

RULE CONFIGURATION:
Rule created: {rule_created}
Ruleset: extra_host_conf:max_check_attempts
Target: {host_name if host_name != "all" else "All hosts"}
Value: {max_attempts} attempts

The host check attempts have been configured. Monitor the results and adjust based on false positive rates and detection requirements."""

        return GetPromptResult(
            description=f"Generated prompt for adjust_host_check_attempts",
            messages=[
                PromptMessage(
                    role="user", content=TextContent(type="text", text=prompt_text)
                )
            ]
        )

    @staticmethod 
    async def handle_adjust_host_retry_interval(
        args: Dict[str, Any],
        host_service: Any,
        checkmk_client: Any
    ) -> GetPromptResult:
        """Handle adjust_host_retry_interval prompt.
        
        Args:
            args: Validated prompt arguments
            host_service: Host service instance
            checkmk_client: Checkmk client instance
            
        Returns:
            GetPromptResult: Generated prompt result
        """
        host_name = args.get("host_name", "")
        retry_interval_str = args.get("retry_interval")
        reason = args.get("reason", "Not specified")

        # Validate parameters
        if not host_name:
            raise ValueError("host_name is required")
        
        if not retry_interval_str:
            raise ValueError("retry_interval is required")

        try:
            retry_interval = float(retry_interval_str)
            if retry_interval < 0.1 or retry_interval > 60:
                raise ValueError("retry_interval must be between 0.1 and 60 minutes")
        except (TypeError, ValueError):
            raise ValueError(
                "retry_interval must be a valid number between 0.1 and 60"
            )

        # Get current host configuration
        current_config = {}
        if host_name != "all":
            try:
                host_result = await host_service.get_host(
                    name=host_name, include_status=True
                )
                if host_result.success:
                    host_data = host_result.data
                    current_config = {
                        "current_retry": getattr(
                            host_data, "host_retry_interval", "Unknown"
                        ),
                        "max_attempts": getattr(
                            host_data, "host_max_check_attempts", "Unknown"
                        ),
                        "check_interval": getattr(
                            host_data, "host_check_interval", "Unknown"
                        ),
                    }
            except Exception as e:
                current_config = {
                    "error": f"Could not retrieve configuration: {str(e)}"
                }

        # Create rule for retry interval
        try:
            if host_name == "all":
                conditions = {}
            else:
                conditions = {"host_name": [host_name]}

            rule_result = await checkmk_client.create_rule(
                ruleset="extra_host_conf:retry_interval",
                folder="/",
                value_raw=str(retry_interval),
                conditions=conditions,
                properties={
                    "comment": f"Host retry interval adjustment - {reason}"
                },
            )
            rule_created = rule_result.get("id", "created successfully")
        except Exception as e:
            rule_created = f"Error creating rule: {str(e)}"

        # Calculate performance impact
        max_attempts = current_config.get("max_attempts", 3)
        if isinstance(max_attempts, (int, float)) and max_attempts > 1:
            total_retry_time = (max_attempts - 1) * retry_interval
        else:
            total_retry_time = "Unknown"

        # Determine load impact
        if retry_interval < 1:
            load_impact = "High (frequent retries)"
        elif retry_interval < 3:
            load_impact = "Medium (balanced)"
        else:
            load_impact = "Low (infrequent retries)"

        prompt_text = f"""Host Retry Interval Configuration for '{host_name}'

CURRENT CONFIGURATION:
{safe_json_dumps(current_config)}

PROPOSED CHANGE:
- New retry interval: {retry_interval} minutes
- Load impact: {load_impact}
- Reason for change: {reason}
- Total retry time: {total_retry_time} minutes (for {max_attempts} max attempts)

ANALYSIS:
1. Retry interval impact:
   - Shorter intervals (0.1-1 min): Faster recovery detection, higher load
   - Medium intervals (1-5 min): Balanced approach for most environments
   - Longer intervals (5-60 min): Lower load, slower recovery detection

2. Recommended scenarios:
   - Critical production hosts: 0.5-2 minutes
   - Standard hosts: 1-5 minutes
   - Non-critical/test hosts: 5-15 minutes
   - High-latency networks: 3-10 minutes

3. Performance considerations:
   - More frequent retries increase monitoring load
   - Consider network conditions and host importance
   - Balance between recovery speed and system resources

4. Network type recommendations:
   - LAN/Fast network: 0.1-2 minutes
   - Standard network: 1-5 minutes  
   - Slow/WAN network: 3-10 minutes
   - Unreliable network: 5-15 minutes

RULE CONFIGURATION:
Rule created: {rule_created}
Ruleset: extra_host_conf:retry_interval
Target: {host_name if host_name != "all" else "All hosts"}
Value: {retry_interval} minutes

The retry interval has been configured. Monitor system load and adjust based on network conditions and recovery requirements."""

        return GetPromptResult(
            description=f"Generated prompt for adjust_host_retry_interval",
            messages=[
                PromptMessage(
                    role="user", content=TextContent(type="text", text=prompt_text)
                )
            ]
        )

    @staticmethod
    async def handle_adjust_host_check_timeout(
        args: Dict[str, Any],
        host_service: Any,
        checkmk_client: Any
    ) -> GetPromptResult:
        """Handle adjust_host_check_timeout prompt.
        
        Args:
            args: Validated prompt arguments
            host_service: Host service instance
            checkmk_client: Checkmk client instance
            
        Returns:
            GetPromptResult: Generated prompt result
        """
        host_name = args.get("host_name", "")
        timeout_seconds_str = args.get("timeout_seconds")
        check_type = args.get("check_type", "icmp").lower()
        reason = args.get("reason", "Not specified")

        # Validate parameters
        if not host_name:
            raise ValueError("host_name is required")
        
        if not timeout_seconds_str:
            raise ValueError("timeout_seconds is required")

        if check_type not in ["icmp", "snmp", "all"]:
            raise ValueError("check_type must be 'icmp', 'snmp', or 'all'")

        try:
            timeout_seconds = int(timeout_seconds_str)
            if timeout_seconds < 1 or timeout_seconds > 60:
                raise ValueError("timeout_seconds must be between 1 and 60")
        except (TypeError, ValueError):
            raise ValueError(
                "timeout_seconds must be a valid integer between 1 and 60"
            )

        # Get current host configuration
        current_config = {}
        if host_name != "all":
            try:
                host_result = await host_service.get_host(
                    name=host_name, include_status=True
                )
                if host_result.success:
                    host_data = host_result.data
                    current_config = {
                        "check_command": getattr(
                            host_data, "host_check_command", "Unknown"
                        ),
                        "check_interval": getattr(
                            host_data, "host_check_interval", "Unknown"
                        ),
                    }
            except Exception as e:
                current_config = {
                    "error": f"Could not retrieve configuration: {str(e)}"
                }

        # Create rules based on check type
        rules_created = []
        try:
            if host_name == "all":
                conditions = {}
            else:
                conditions = {"host_name": [host_name]}

            # Create ICMP timeout rule
            if check_type in ["icmp", "all"]:
                icmp_rule = await checkmk_client.create_rule(
                    ruleset="active_checks:icmp",
                    folder="/",
                    value_raw={"timeout": timeout_seconds},
                    conditions=conditions,
                    properties={
                        "comment": f"ICMP timeout adjustment - {reason}"
                    },
                )
                rules_created.append(
                    f"ICMP rule: {icmp_rule.get('id', 'created')}"
                )

            # Create SNMP timeout rule  
            if check_type in ["snmp", "all"]:
                snmp_rule = await checkmk_client.create_rule(
                    ruleset="snmp_timing",
                    folder="/", 
                    value_raw={"timeout": timeout_seconds},
                    conditions=conditions,
                    properties={
                        "comment": f"SNMP timeout adjustment - {reason}"
                    },
                )
                rules_created.append(
                    f"SNMP rule: {snmp_rule.get('id', 'created')}"
                )

        except Exception as e:
            rules_created.append(f"Error creating rules: {str(e)}")

        # Network recommendations based on timeout
        if timeout_seconds <= 5:
            network_type = "LAN/Ethernet (1-5s)"
        elif timeout_seconds <= 8:
            network_type = "Good WiFi/5GHz (3-8s)"
        elif timeout_seconds <= 12:
            network_type = "Normal WiFi/2.4GHz (5-12s)"
        elif timeout_seconds <= 20:
            network_type = "Poor WiFi/WAN (10-20s)"
        elif timeout_seconds <= 35:
            network_type = "Mobile/Cellular (20-35s)"
        else:
            network_type = "Satellite/Very high latency (35-60s)"

        prompt_text = f"""Configure host check timeout for '{host_name}'

CURRENT CONFIGURATION:
- Host: {host_name}
- Check command: {current_config.get('check_command', 'Unknown')}
- Current timeout: Unknown (checking existing rules...)

PROPOSED CHANGE:
- New timeout: {timeout_seconds} seconds
- Check type affected: {check_type}
- Reason: {reason}
- Suitable for: {network_type}

ANALYSIS:
1. Timeout implications:
   - Too short: False DOWN states due to network delays
   - Too long: Delayed detection of actual problems
2. Recommendations by network type:
   - LAN/Ethernet: 1-5 seconds
   - Good WiFi (5GHz): 3-8 seconds
   - Normal WiFi (2.4GHz): 5-12 seconds
   - Poor WiFi/Congested: 10-20 seconds
   - WAN/Internet: 5-15 seconds
   - Slow Internet (DSL/Cable): 15-25 seconds
   - Mobile/Cellular: 20-35 seconds
   - Satellite/Distant: 25-45 seconds
   - Very high-latency: 45-60 seconds

3. Performance considerations:
   - Longer timeouts may delay check scheduling
   - Consider network RTT: timeout should be > 3×RTT
   - Balance between false positives and detection speed

4. Check type specifics:
   - ICMP: Direct network reachability test
   - SNMP: Query device for status information
   - Consider device response capabilities

CONFIGURATION:
Rules created: {'; '.join(rules_created)}
Rulesets: {"active_checks:icmp" if check_type in ["icmp", "all"] else ""}{"snmp_timing" if check_type in ["snmp", "all"] else ""}
Folder: / (root)

The timeout rules have been configured. Monitor for false positives or missed problems and adjust as needed."""

        return GetPromptResult(
            description=f"Generated prompt for adjust_host_check_timeout",
            messages=[
                PromptMessage(
                    role="user", content=TextContent(type="text", text=prompt_text)
                )
            ]
        )