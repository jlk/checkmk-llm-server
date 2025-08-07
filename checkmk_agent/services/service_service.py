"""Service service - core business logic for service operations (acknowledge, downtime, discovery, etc.)."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from .base import BaseService, ServiceResult
from .models.services import (
    ServiceInfo,
    ServiceListResult,
    ServiceStatusResult,
    ServiceAcknowledgeResult,
    ServiceDowntimeResult,
    ServiceDiscoveryResult,
    ServiceParameterResult,
    ServiceState,
)
from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkAPIError
from ..config import AppConfig


class ServiceService(BaseService):
    """Core service operations service - presentation agnostic."""

    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        super().__init__(checkmk_client, config)
        self.logger = logging.getLogger(__name__)

    async def list_host_services(
        self,
        host_name: str,
        state_filter: Optional[List[ServiceState]] = None,
        include_details: bool = False,
    ) -> ServiceResult[ServiceListResult]:
        """
        List all services for a specific host.

        Args:
            host_name: Host name to get services for
            state_filter: Optional filter by service states
            include_details: Whether to include detailed service information

        Returns:
            ServiceResult containing ServiceListResult
        """

        async def _list_services_operation():
            # Validate host name
            validation_errors = self._validate_required_params(
                {"host_name": host_name}, ["host_name"]
            )
            if validation_errors:
                raise ValueError(f"Validation errors: {', '.join(validation_errors)}")

            # Get services from API using monitoring endpoint
            services_data = await self.checkmk.list_host_services_with_monitoring_data(
                host_name=host_name, sites=None, query=None, columns=None
            )

            # Convert to ServiceInfo models
            services = []
            for service_data in services_data:
                service_info = self._convert_api_service_to_model(
                    service_data, include_details
                )
                services.append(service_info)

            # Apply state filter
            if state_filter:
                services = [s for s in services if s.state in state_filter]

            # Calculate statistics
            stats = self._calculate_service_stats(services)

            return ServiceListResult(
                services=services,
                total_count=len(services),
                host_filter=host_name,
                state_filter=(
                    state_filter[0] if state_filter and len(state_filter) == 1 else None
                ),
                stats=stats,
                metadata={
                    "include_details": include_details,
                    "original_count": len(services_data),
                },
            )

        return await self._execute_with_error_handling(
            _list_services_operation, f"list_host_services_{host_name}"
        )

    async def get_service_status(
        self, host_name: str, service_name: str, include_related: bool = True
    ) -> ServiceResult[ServiceStatusResult]:
        """
        Get detailed status for a specific service.

        Args:
            host_name: Host name
            service_name: Service name
            include_related: Whether to include related services on same host

        Returns:
            ServiceResult containing ServiceStatusResult
        """

        async def _get_status_operation():
            # Validate parameters
            validation_errors = self._validate_required_params(
                {"host_name": host_name, "service_name": service_name},
                ["host_name", "service_name"],
            )
            if validation_errors:
                raise ValueError(f"Validation errors: {', '.join(validation_errors)}")

            # Get service status
            service_data = await self.checkmk.get_service_status(
                host_name, service_name
            )
            service_info = self._convert_api_service_to_model(
                service_data, include_details=True
            )

            # Get related services if requested
            related_services = []
            host_status = None

            if include_related:
                try:
                    # Get other services on the same host
                    all_host_services = await self.checkmk.list_host_services(host_name)
                    related_services = [
                        self._convert_api_service_to_model(s)
                        for s in all_host_services
                        if s.get("service_description") != service_name
                    ]

                    # Get host status summary
                    host_data = await self.checkmk.get_host_status(host_name)
                    host_status = f"{host_data.get('state', 'Unknown')} - {host_data.get('plugin_output', '')}"

                except Exception as e:
                    self.logger.warning(
                        f"Could not get related services for {host_name}: {e}"
                    )

            return ServiceStatusResult(
                service=service_info,
                success=True,
                message=f"Retrieved status for {host_name}/{service_name}",
                related_services=related_services,
                host_status=host_status,
            )

        return await self._execute_with_error_handling(
            _get_status_operation, f"get_service_status_{host_name}_{service_name}"
        )

    async def acknowledge_problem(
        self,
        host_name: str,
        service_name: str,
        comment: str = "Acknowledged via service layer",
        sticky: bool = True,
        notify: bool = True,
        persistent: bool = False,
        author: Optional[str] = None,
    ) -> ServiceResult[ServiceAcknowledgeResult]:
        """
        Acknowledge a service problem.

        Args:
            host_name: Host name
            service_name: Service name
            comment: Acknowledgement comment
            sticky: Whether acknowledgement should remain until service recovers
            notify: Whether to send notifications
            persistent: Whether acknowledgement persists across Checkmk restarts
            author: Who is making the acknowledgement

        Returns:
            ServiceResult containing ServiceAcknowledgeResult
        """

        async def _acknowledge_operation():
            nonlocal author

            # Validate parameters
            validation_errors = self._validate_required_params(
                {
                    "host_name": host_name,
                    "service_name": service_name,
                    "comment": comment,
                },
                ["host_name", "service_name", "comment"],
            )
            if validation_errors:
                raise ValueError(f"Validation errors: {', '.join(validation_errors)}")

            # Set default author if not provided
            if not author:
                author = self.config.checkmk.username or "checkmk_agent"

            # Acknowledge via API
            ack_data = {
                "host_name": host_name,
                "service_description": service_name,
                "comment": comment,
                "sticky": sticky,
                "notify": notify,
                "persistent": persistent,
            }

            await self.checkmk.acknowledge_service_problems([ack_data])

            return ServiceAcknowledgeResult(
                host_name=host_name,
                service_name=service_name,
                success=True,
                message=f"Successfully acknowledged {host_name}/{service_name}",
                comment=comment,
                author=author,
                sticky=sticky,
                notify=notify,
                persistent=persistent,
                acknowledgement_time=datetime.now(),
            )

        return await self._execute_with_error_handling(
            _acknowledge_operation, f"acknowledge_{host_name}_{service_name}"
        )

    async def create_downtime(
        self,
        host_name: str,
        service_name: str,
        duration_hours: float,
        comment: str = "Scheduled downtime via service layer",
        start_time: Optional[datetime] = None,
        fixed: bool = True,
        author: Optional[str] = None,
    ) -> ServiceResult[ServiceDowntimeResult]:
        """
        Create scheduled downtime for a service.

        Args:
            host_name: Host name
            service_name: Service name
            duration_hours: Downtime duration in hours
            comment: Downtime comment
            start_time: When downtime should start (default: now)
            fixed: Whether downtime has fixed duration
            author: Who is creating the downtime

        Returns:
            ServiceResult containing ServiceDowntimeResult
        """

        async def _create_downtime_operation():
            nonlocal start_time, author

            # Validate parameters
            validation_errors = self._validate_required_params(
                {
                    "host_name": host_name,
                    "service_name": service_name,
                    "duration_hours": duration_hours,
                },
                ["host_name", "service_name", "duration_hours"],
            )
            if validation_errors:
                raise ValueError(f"Validation errors: {', '.join(validation_errors)}")

            if duration_hours <= 0:
                raise ValueError("Duration must be positive")

            # Set defaults
            if not start_time:
                start_time = datetime.now()

            if not author:
                author = self.config.checkmk.username or "checkmk_agent"

            end_time = start_time + timedelta(hours=duration_hours)

            # Create downtime via API
            downtime_data = {
                "host_name": host_name,
                "service_description": service_name,
                "start_time": int(start_time.timestamp()),
                "end_time": int(end_time.timestamp()),
                "comment": comment,
                "fixed": fixed,
            }

            result = await self.checkmk.create_service_downtime(**downtime_data)
            downtime_id = result.get("downtime_id")

            return ServiceDowntimeResult(
                host_name=host_name,
                service_name=service_name,
                success=True,
                message=f"Successfully created {duration_hours}h downtime for {host_name}/{service_name}",
                downtime_id=downtime_id,
                start_time=start_time,
                end_time=end_time,
                duration_hours=duration_hours,
                comment=comment,
                author=author,
                fixed=fixed,
            )

        return await self._execute_with_error_handling(
            _create_downtime_operation, f"create_downtime_{host_name}_{service_name}"
        )

    async def discover_services(
        self, host_name: str, mode: str = "refresh"
    ) -> ServiceResult[ServiceDiscoveryResult]:
        """
        Perform service discovery on a host.

        Args:
            host_name: Host name to discover services on
            mode: Discovery mode (refresh, new, remove, fixall)

        Returns:
            ServiceResult containing ServiceDiscoveryResult
        """

        async def _discovery_operation():
            # Validate parameters
            validation_errors = self._validate_required_params(
                {"host_name": host_name}, ["host_name"]
            )
            if validation_errors:
                raise ValueError(f"Validation errors: {', '.join(validation_errors)}")

            valid_modes = ["refresh", "new", "remove", "fixall"]
            if mode not in valid_modes:
                raise ValueError(
                    f"Invalid discovery mode: {mode}. Valid modes: {valid_modes}"
                )

            # Perform discovery via API
            discovery_result = await self.checkmk.start_service_discovery(
                host_name, mode
            )

            # Parse discovery results
            discovery_data = discovery_result.get("discovery_result", {})

            new_services = discovery_data.get("new_services", [])
            removed_services = discovery_data.get("removed_services", [])
            changed_services = discovery_data.get("changed_services", [])
            unchanged_services = discovery_data.get("unchanged_services", [])

            return ServiceDiscoveryResult(
                host_name=host_name,
                success=True,
                message=f"Discovery completed on {host_name} using mode '{mode}'",
                new_services=new_services,
                removed_services=removed_services,
                changed_services=changed_services,
                unchanged_services=unchanged_services,
                new_count=len(new_services),
                removed_count=len(removed_services),
                changed_count=len(changed_services),
                unchanged_count=len(unchanged_services),
                discovery_mode=mode,
                discovery_time=datetime.now(),
            )

        return await self._execute_with_error_handling(
            _discovery_operation, f"discover_services_{host_name}"
        )

    async def list_all_services(
        self,
        host_filter: Optional[str] = None,
        state_filter: Optional[List[ServiceState]] = None,
        limit: Optional[int] = None,
    ) -> ServiceResult[ServiceListResult]:
        """
        List services across all hosts with filtering.

        Args:
            host_filter: Optional host name pattern filter
            state_filter: Optional filter by service states
            limit: Maximum number of services to return

        Returns:
            ServiceResult containing ServiceListResult
        """

        async def _list_all_services_operation():
            # Get services from API using monitoring endpoint
            services_data = await self.checkmk.list_all_services_with_monitoring_data(
                host_filter=host_filter, sites=None, query=None, columns=None
            )

            # Convert to ServiceInfo models
            services = []
            for service_data in services_data:
                service_info = self._convert_api_service_to_model(service_data)
                services.append(service_info)

            # Apply state filter
            if state_filter:
                services = [s for s in services if s.state in state_filter]

            # Apply limit
            total_count = len(services)
            if limit:
                services = services[:limit]

            # Calculate statistics
            stats = self._calculate_service_stats(services)

            return ServiceListResult(
                services=services,
                total_count=total_count,
                host_filter=host_filter,
                state_filter=(
                    state_filter[0] if state_filter and len(state_filter) == 1 else None
                ),
                stats=stats,
                metadata={
                    "limited_results": limit is not None and total_count > limit,
                    "limit_applied": limit,
                },
            )

        return await self._execute_with_error_handling(
            _list_all_services_operation, "list_all_services"
        )

    def _convert_api_service_to_model(
        self, service_data: Dict[str, Any], include_details: bool = False
    ) -> ServiceInfo:
        """Convert API service data to ServiceInfo model."""
        # Handle both monitoring endpoint (with extensions) and configuration endpoint data
        extensions = service_data.get("extensions", {})

        # Extract basic information - try extensions first, then direct access
        # Import the safe utility function to handle falsy values properly
        from ..utils import safe_get_with_fallback

        host_name = safe_get_with_fallback(extensions, service_data, "host_name", "")
        service_name = safe_get_with_fallback(
            extensions,
            service_data,
            "description",
            service_data.get("service_description", ""),
        )
        state_value = safe_get_with_fallback(extensions, service_data, "state", "OK")

        # Handle both string and numeric state values from Checkmk API
        if isinstance(state_value, str):
            # API returns string values like "OK", "WARNING", "CRITICAL", "UNKNOWN"
            state_mapping = {
                "OK": ServiceState.OK,
                "WARNING": ServiceState.WARNING,
                "CRITICAL": ServiceState.CRITICAL,
                "UNKNOWN": ServiceState.UNKNOWN,
                "WARN": ServiceState.WARNING,  # Some APIs use WARN instead of WARNING
                "CRIT": ServiceState.CRITICAL,  # Some APIs use CRIT instead of CRITICAL
            }
            state = state_mapping.get(state_value.upper(), ServiceState.UNKNOWN)
        else:
            # Fallback for numeric codes (0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN)
            numeric_mapping = {
                0: ServiceState.OK,
                1: ServiceState.WARNING,
                2: ServiceState.CRITICAL,
                3: ServiceState.UNKNOWN,
            }
            state = numeric_mapping.get(state_value, ServiceState.UNKNOWN)

        # Basic service info - try extensions first, then direct access
        # Use explicit None checks to avoid issues with falsy values like 0
        service_info = ServiceInfo(
            host_name=host_name,
            service_name=service_name,
            state=state,
            state_type=self._convert_state_type_to_string(
                extensions.get("state_type")
                if extensions.get("state_type") is not None
                else service_data.get("state_type", 1)
            ),
            plugin_output=(
                extensions.get("plugin_output")
                if extensions.get("plugin_output") is not None
                else service_data.get("plugin_output", "")
            ),
            long_plugin_output=(
                extensions.get("long_plugin_output")
                if extensions.get("long_plugin_output") is not None
                else service_data.get("long_plugin_output")
            ),
            performance_data=(
                extensions.get("performance_data")
                if extensions.get("performance_data") is not None
                else service_data.get("performance_data")
            ),
            last_check=datetime.fromtimestamp(
                extensions.get("last_check")
                if extensions.get("last_check") is not None
                else service_data.get("last_check", 0)
            ),
            last_state_change=datetime.fromtimestamp(
                extensions.get("last_state_change")
                if extensions.get("last_state_change") is not None
                else service_data.get("last_state_change", 0)
            ),
            acknowledged=(
                extensions.get("acknowledged")
                if extensions.get("acknowledged") is not None
                else service_data.get("acknowledged", False)
            ),
            in_downtime=(
                extensions.get("in_downtime")
                if extensions.get("in_downtime") is not None
                else service_data.get("in_downtime", False)
            ),
        )

        # Add detailed information if requested
        if include_details:
            service_info.last_ok = self._safe_timestamp_conversion(
                service_data.get("last_time_ok")
            )
            service_info.next_check = self._safe_timestamp_conversion(
                service_data.get("next_check")
            )
            service_info.acknowledgement_author = service_data.get(
                "acknowledgement_author"
            )
            service_info.acknowledgement_comment = service_data.get(
                "acknowledgement_comment"
            )
            service_info.acknowledgement_time = self._safe_timestamp_conversion(
                service_data.get("acknowledgement_time")
            )
            service_info.downtime_start = self._safe_timestamp_conversion(
                service_data.get("downtime_start")
            )
            service_info.downtime_end = self._safe_timestamp_conversion(
                service_data.get("downtime_end")
            )
            service_info.downtime_comment = service_data.get("downtime_comment")
            service_info.check_command = service_data.get("check_command")
            service_info.check_interval = service_data.get("check_interval")
            service_info.retry_interval = service_data.get("retry_interval")
            service_info.max_check_attempts = service_data.get("max_check_attempts")
            service_info.current_attempt = service_data.get("current_attempt")
            service_info.notifications_enabled = service_data.get(
                "notifications_enabled", True
            )
            service_info.active_checks_enabled = service_data.get(
                "active_checks_enabled", True
            )
            service_info.passive_checks_enabled = service_data.get(
                "passive_checks_enabled", True
            )

        return service_info

    def _safe_timestamp_conversion(self, timestamp: Any) -> Optional[datetime]:
        """Safely convert timestamp to datetime."""
        if timestamp and isinstance(timestamp, (int, float)) and timestamp > 0:
            try:
                return datetime.fromtimestamp(timestamp)
            except (ValueError, OSError):
                return None
        return None

    def _convert_state_type_to_string(self, state_type_value: Any) -> str:
        """Convert numeric state_type to string format."""
        if isinstance(state_type_value, int):
            # Checkmk API returns: 0=soft, 1=hard
            state_type_mapping = {0: "soft", 1: "hard"}
            return state_type_mapping.get(state_type_value, "hard")
        elif isinstance(state_type_value, str):
            # Already a string, return as-is if valid
            if state_type_value.lower() in ["soft", "hard"]:
                return state_type_value.lower()
        # Default fallback
        return "hard"

    def _calculate_service_stats(self, services: List[ServiceInfo]) -> Dict[str, int]:
        """Calculate service statistics."""
        stats = {
            "total": len(services),
            "ok": 0,
            "warning": 0,
            "critical": 0,
            "unknown": 0,
            "acknowledged": 0,
            "in_downtime": 0,
            "unhandled_problems": 0,
        }

        for service in services:
            # Count by state
            if service.state == ServiceState.OK:
                stats["ok"] += 1
            elif service.state == ServiceState.WARNING:
                stats["warning"] += 1
            elif service.state == ServiceState.CRITICAL:
                stats["critical"] += 1
            elif service.state == ServiceState.UNKNOWN:
                stats["unknown"] += 1

            # Count special states
            if service.acknowledged:
                stats["acknowledged"] += 1

            if service.in_downtime:
                stats["in_downtime"] += 1

            # Count unhandled problems (not OK and not acknowledged/downtime)
            if (
                service.state != ServiceState.OK
                and not service.acknowledged
                and not service.in_downtime
            ):
                stats["unhandled_problems"] += 1

        return stats
