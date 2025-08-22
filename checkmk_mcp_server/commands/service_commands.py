"""Service-related command implementations."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .base import BaseCommand, CommandContext, CommandResult, CommandCategory
from ..api_client import CheckmkClient, CheckmkAPIError


class ServiceCommand(BaseCommand):
    """Base class for service-related commands."""

    def __init__(self, checkmk_client: CheckmkClient):
        super().__init__()
        self.checkmk_client = checkmk_client
        self.logger = logging.getLogger(__name__)

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.SERVICE

    def _get_state_emoji(self, state: Any) -> str:
        """Get emoji for service state."""
        state_map = {
            "OK": "✅",
            "WARN": "⚠️",
            "WARNING": "⚠️",
            "CRIT": "❌",
            "CRITICAL": "❌",
            "UNKNOWN": "❓",
            "PENDING": "⏳",
            0: "✅",  # OK
            1: "⚠️",  # WARN
            2: "❌",  # CRIT
            3: "❓",  # UNKNOWN
        }
        return state_map.get(state, "❓")


class ListServicesCommand(ServiceCommand):
    """Command to list services for a host or all services."""

    @property
    def name(self) -> str:
        return "list_services"

    @property
    def description(self) -> str:
        return "List services for a specific host or all services"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "host_name": {
                "type": str,
                "required": False,
                "description": "Hostname to list services for (if not provided, lists all services)",
            }
        }

    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the list services command."""
        try:
            host_name = context.get_parameter("host_name")

            if host_name:
                # List services for specific host
                services = self.checkmk_client.list_host_services(host_name)
                if not services:
                    return CommandResult.success_result(
                        data=[], message=f"📦 No services found for host: {host_name}"
                    )

                # Format results
                result_message = (
                    f"📦 Found {len(services)} services for host: {host_name}\n\n"
                )
                for service in services:
                    service_desc = service.get("extensions", {}).get(
                        "description", "Unknown"
                    )
                    service_state = service.get("extensions", {}).get(
                        "state", "Unknown"
                    )
                    state_emoji = self._get_state_emoji(service_state)
                    result_message += f"  {state_emoji} {service_desc}\n"

                return CommandResult.success_result(
                    data=services, message=result_message
                )
            else:
                # List all services
                services = self.checkmk_client.list_all_services()
                if not services:
                    return CommandResult.success_result(
                        data=[], message="📦 No services found"
                    )

                # Group by host
                services_by_host = {}
                for service in services:
                    host = service.get("extensions", {}).get("host_name", "Unknown")
                    if host not in services_by_host:
                        services_by_host[host] = []
                    services_by_host[host].append(service)

                result_message = f"📦 Found {len(services)} services across {len(services_by_host)} hosts:\n\n"
                for host, host_services in services_by_host.items():
                    result_message += f"  🖥️  {host} ({len(host_services)} services)\n"
                    for service in host_services[:3]:  # Show first 3 services
                        service_desc = service.get("extensions", {}).get(
                            "description", "Unknown"
                        )
                        service_state = service.get("extensions", {}).get(
                            "state", "Unknown"
                        )
                        state_emoji = self._get_state_emoji(service_state)
                        result_message += f"    {state_emoji} {service_desc}\n"
                    if len(host_services) > 3:
                        result_message += f"    ... and {len(host_services) - 3} more\n"
                    result_message += "\n"

                return CommandResult.success_result(
                    data=services_by_host, message=result_message
                )

        except CheckmkAPIError as e:
            return CommandResult.error_result(f"Error listing services: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in list_services: {e}")
            return CommandResult.error_result(f"Unexpected error: {e}")


class GetServiceStatusCommand(ServiceCommand):
    """Command to get status of a specific service."""

    @property
    def name(self) -> str:
        return "get_service_status"

    @property
    def description(self) -> str:
        return "Get detailed status of a specific service"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "host_name": {
                "type": str,
                "required": True,
                "description": "Hostname where the service is running",
            },
            "service_description": {
                "type": str,
                "required": True,
                "description": "Description/name of the service",
            },
        }

    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the get service status command."""
        try:
            host_name = context.require_parameter("host_name")
            service_desc = context.require_parameter("service_description")

            # Get specific service status
            services = self.checkmk_client.list_host_services(
                host_name, query=f"service_description = '{service_desc}'"
            )
            if not services:
                return CommandResult.error_result(
                    f"Service '{service_desc}' not found on host '{host_name}'"
                )

            service = services[0]
            extensions = service.get("extensions", {})
            service_state = extensions.get("state", "Unknown")
            state_emoji = self._get_state_emoji(service_state)
            last_check = extensions.get("last_check", "Unknown")
            plugin_output = extensions.get("plugin_output", "No output")

            result_message = f"""📊 Service Status: {host_name}/{service_desc}
{state_emoji} State: {service_state}
⏰ Last Check: {last_check}
💬 Output: {plugin_output}"""

            return CommandResult.success_result(data=service, message=result_message)

        except CheckmkAPIError as e:
            return CommandResult.error_result(f"Error getting service status: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in get_service_status: {e}")
            return CommandResult.error_result(f"Unexpected error: {e}")


class AcknowledgeServiceCommand(ServiceCommand):
    """Command to acknowledge service problems."""

    @property
    def name(self) -> str:
        return "acknowledge_service"

    @property
    def description(self) -> str:
        return "Acknowledge service problems to suppress notifications"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "host_name": {
                "type": str,
                "required": True,
                "description": "Hostname where the service is running",
            },
            "service_description": {
                "type": str,
                "required": True,
                "description": "Description/name of the service",
            },
            "comment": {
                "type": str,
                "required": False,
                "default": "Acknowledged via LLM Agent",
                "description": "Comment explaining the acknowledgment",
            },
            "sticky": {
                "type": bool,
                "required": False,
                "default": True,
                "description": "Whether acknowledgment persists until service is OK",
            },
        }

    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the acknowledge service command."""
        try:
            host_name = context.require_parameter("host_name")
            service_desc = context.require_parameter("service_description")
            comment = context.get_parameter("comment", "Acknowledged via LLM Agent")
            sticky = context.get_parameter("sticky", True)

            # Ensure comment is a string
            if not isinstance(comment, str):
                comment = "Acknowledged via LLM Agent"

            self.checkmk_client.acknowledge_service_problems(
                host_name=host_name,
                service_description=service_desc,
                comment=comment,
                sticky=sticky,
            )

            result_message = f"✅ Acknowledged service problem: {host_name}/{service_desc}\n💬 Comment: {comment}"

            return CommandResult.success_result(
                data={
                    "host_name": host_name,
                    "service_description": service_desc,
                    "comment": comment,
                },
                message=result_message,
            )

        except CheckmkAPIError as e:
            return CommandResult.error_result(f"Error acknowledging service: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in acknowledge_service: {e}")
            return CommandResult.error_result(f"Unexpected error: {e}")


class CreateDowntimeCommand(ServiceCommand):
    """Command to create service downtime."""

    @property
    def name(self) -> str:
        return "create_downtime"

    @property
    def description(self) -> str:
        return "Create scheduled downtime for a service"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "host_name": {
                "type": str,
                "required": True,
                "description": "Hostname where the service is running",
            },
            "service_description": {
                "type": str,
                "required": True,
                "description": "Description/name of the service",
            },
            "duration_hours": {
                "type": (int, float),
                "required": False,
                "default": 2,
                "description": "Duration of downtime in hours",
            },
            "comment": {
                "type": str,
                "required": False,
                "default": "Downtime created via LLM Agent",
                "description": "Comment explaining the downtime",
            },
        }

    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the create downtime command."""
        try:
            host_name = context.require_parameter("host_name")
            service_desc = context.require_parameter("service_description")
            duration_hours = context.get_parameter("duration_hours", 2)
            comment = context.get_parameter("comment", "Downtime created via LLM Agent")

            # Handle duration_hours validation
            if not isinstance(duration_hours, (int, float)) or duration_hours <= 0:
                duration_hours = 2  # Default to 2 hours

            # Ensure comment is a string
            if not isinstance(comment, str):
                comment = "Downtime created via LLM Agent"

            # Calculate start and end times
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=duration_hours)

            self.checkmk_client.create_service_downtime(
                host_name=host_name,
                service_description=service_desc,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                comment=comment,
            )

            result_message = f"""✅ Created downtime for service: {host_name}/{service_desc}
⏰ Duration: {duration_hours} hours
🕐 Start: {start_time.strftime('%Y-%m-%d %H:%M')}
🕑 End: {end_time.strftime('%Y-%m-%d %H:%M')}
💬 Comment: {comment}"""

            return CommandResult.success_result(
                data={
                    "host_name": host_name,
                    "service_description": service_desc,
                    "duration_hours": duration_hours,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "comment": comment,
                },
                message=result_message,
            )

        except CheckmkAPIError as e:
            return CommandResult.error_result(f"Error creating downtime: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in create_downtime: {e}")
            return CommandResult.error_result(f"Unexpected error: {e}")


class DiscoverServicesCommand(ServiceCommand):
    """Command to discover services on a host."""

    @property
    def name(self) -> str:
        return "discover_services"

    @property
    def description(self) -> str:
        return "Discover services on a host using service discovery"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "host_name": {
                "type": str,
                "required": True,
                "description": "Hostname to discover services on",
            },
            "mode": {
                "type": str,
                "required": False,
                "default": "refresh",
                "description": "Discovery mode (refresh, new, remove, fixall, refresh_autochecks)",
            },
        }

    def _custom_validate(self, context: CommandContext) -> Optional[CommandResult]:
        """Validate discovery mode parameter."""
        mode = context.get_parameter("mode", "refresh")
        valid_modes = ["refresh", "new", "remove", "fixall", "refresh_autochecks"]

        if mode not in valid_modes:
            return CommandResult.error_result(
                f"Invalid discovery mode '{mode}'. Valid modes: {', '.join(valid_modes)}"
            )

        return None

    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the discover services command."""
        try:
            host_name = context.require_parameter("host_name")
            mode = context.get_parameter("mode", "refresh")

            # Map common mode variations to valid values
            mode_mapping = {
                "discovery": "refresh",
                "scan": "refresh",
                "find": "refresh",
                "detect": "refresh",
                "new": "new",
                "add": "new",
                "refresh": "refresh",
                "remove": "remove",
                "delete": "remove",
                "fixall": "fixall",
                "fix": "fixall",
                "refresh_autochecks": "refresh_autochecks",
            }

            # Normalize the mode
            mode = mode_mapping.get(mode.lower(), "refresh")

            # Start service discovery
            result = self.checkmk_client.start_service_discovery(host_name, mode)

            # Get discovery results
            discovery_result = self.checkmk_client.get_service_discovery_result(
                host_name
            )

            # Format response
            extensions = discovery_result.get("extensions", {})
            vanished = extensions.get("vanished", [])
            new = extensions.get("new", [])
            ignored = extensions.get("ignored", [])

            response = f"🔍 Service discovery completed for host: {host_name}\n\n"

            if new:
                response += f"✨ New services found ({len(new)}):\n"
                for service in new:
                    service_desc = service.get("service_description", "Unknown")
                    response += f"  + {service_desc}\n"
                response += "\n"

            if vanished:
                response += f"👻 Vanished services ({len(vanished)}):\n"
                for service in vanished:
                    service_desc = service.get("service_description", "Unknown")
                    response += f"  - {service_desc}\n"
                response += "\n"

            if ignored:
                response += f"🚫 Ignored services ({len(ignored)}):\n"
                for service in ignored:
                    service_desc = service.get("service_description", "Unknown")
                    response += f"  ! {service_desc}\n"
                response += "\n"

            if not new and not vanished and not ignored:
                response += "✅ No service changes detected"

            return CommandResult.success_result(
                data={
                    "host_name": host_name,
                    "mode": mode,
                    "new": new,
                    "vanished": vanished,
                    "ignored": ignored,
                },
                message=response,
            )

        except CheckmkAPIError as e:
            return CommandResult.error_result(f"Error discovering services: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in discover_services: {e}")
            return CommandResult.error_result(f"Unexpected error: {e}")


class GetServiceStatisticsCommand(ServiceCommand):
    """Command to get service statistics."""

    @property
    def name(self) -> str:
        return "get_service_statistics"

    @property
    def description(self) -> str:
        return "Get statistics about services across all hosts"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {}

    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the get service statistics command."""
        try:
            services = self.checkmk_client.list_all_services()

            if not services:
                return CommandResult.success_result(
                    data={"total_services": 0, "total_hosts": 0, "state_counts": {}},
                    message="📊 No services found",
                )

            # Count by state
            state_counts = {}
            hosts = set()

            for service in services:
                extensions = service.get("extensions", {})
                state = extensions.get("state", "Unknown")
                host = extensions.get("host_name", "Unknown")

                hosts.add(host)
                state_counts[state] = state_counts.get(state, 0) + 1

            result_data = {
                "total_services": len(services),
                "total_hosts": len(hosts),
                "state_counts": state_counts,
            }

            result_message = f"📊 Service Statistics:\n\n"
            result_message += f"🖥️  Total Hosts: {len(hosts)}\n"
            result_message += f"🔧 Total Services: {len(services)}\n\n"

            result_message += "Service States:\n"
            for state, count in state_counts.items():
                emoji = self._get_state_emoji(state)
                result_message += f"  {emoji} {state}: {count}\n"

            return CommandResult.success_result(
                data=result_data, message=result_message
            )

        except CheckmkAPIError as e:
            return CommandResult.error_result(f"Error getting service statistics: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in get_service_statistics: {e}")
            return CommandResult.error_result(f"Unexpected error: {e}")
