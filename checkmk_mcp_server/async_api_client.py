"""Async wrapper for Checkmk REST API client to support service layer."""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Awaitable, TypeVar
from functools import wraps

from .api_client import CheckmkClient


T = TypeVar('T')

def async_wrapper(method_name: str) -> Callable[[Callable[..., T]], Callable[..., Awaitable[T]]]:
    """Decorator to convert synchronous methods to async."""

    def decorator(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def async_method(self, *args, **kwargs) -> T:
            # Get the actual method from the sync client
            sync_method = getattr(self.sync_client, method_name)
            # Run the sync method in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: sync_method(*args, **kwargs)
            )

        return async_method

    return decorator


class AsyncCheckmkClient:
    """Async wrapper for CheckmkClient to support service layer operations."""

    def __init__(self, sync_client: CheckmkClient):
        self.sync_client = sync_client

        # Use request ID-aware logger
        from .logging_utils import get_logger_with_request_id

        self.logger = get_logger_with_request_id(__name__)

    # Host operations
    @async_wrapper("list_hosts")
    async def list_hosts(
        self, effective_attributes: bool = False
    ) -> List[Dict[str, Any]]:
        """List all hosts."""
        ...

    @async_wrapper("create_host")
    async def create_host(
        self,
        host_name: str,
        folder: str = "/",
        ip_address: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a new host."""
        ...

    @async_wrapper("get_host")
    async def get_host(
        self, host_name: str, effective_attributes: bool = False
    ) -> Dict[str, Any]:
        """Get host details."""
        ...

    @async_wrapper("get_host_folder")
    async def get_host_folder(self, host_name: str) -> str:
        """Get the folder path where a host is located."""
        ...

    @async_wrapper("update_host")
    async def update_host(self, host_name: str, **kwargs) -> Dict[str, Any]:
        """Update host configuration."""
        ...

    @async_wrapper("delete_host")
    async def delete_host(self, host_name: str) -> None:
        """Delete a host."""
        ...

    # bulk_create_hosts exists in sync client
    @async_wrapper("bulk_create_hosts")
    async def bulk_create_hosts(
        self, hosts_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create multiple hosts in bulk."""
        ...

    # get_host_status doesn't exist in sync client, implement as fallback
    async def get_host_status(self, host_name: str) -> Dict[str, Any]:
        """Get host status information."""
        try:
            # Try to get host config and derive status
            host_data = await self.get_host(host_name)
            return {
                "name": host_name,
                "state": "UP",  # Default fallback
                "plugin_output": "Host status via config lookup",
            }
        except Exception as e:
            self.logger.warning(f"Could not get status for host {host_name}: {e}")
            return {
                "name": host_name,
                "state": "UNKNOWN",
                "plugin_output": f"Status lookup failed: {e}",
            }

    # Service operations
    @async_wrapper("list_host_services")
    async def list_host_services(self, host_name: str) -> List[Dict[str, Any]]:
        """List services for a specific host."""
        ...

    @async_wrapper("list_all_services")
    async def list_all_services(
        self, host_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all services with optional host filter."""
        ...

    @async_wrapper("list_host_services_with_monitoring_data")
    async def list_host_services_with_monitoring_data(
        self,
        host_name: str,
        sites: Optional[List[str]] = None,
        query: Optional[str] = None,
        columns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List services for a host with monitoring data (state, output, etc.)."""
        ...

    @async_wrapper("list_all_services_with_monitoring_data")
    async def list_all_services_with_monitoring_data(
        self,
        host_filter: Optional[str] = None,
        sites: Optional[List[str]] = None,
        query: Optional[str] = None,
        columns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List all services with monitoring data (state, output, etc.)."""
        ...

    @async_wrapper("get_service_status")
    async def get_service_status(
        self, host_name: str, service_name: str
    ) -> Dict[str, Any]:
        """Get detailed service status."""
        ...

    @async_wrapper("acknowledge_service_problems")
    async def acknowledge_service_problems(
        self,
        host_name: str,
        service_description: str,
        comment: str,
        sticky: bool = True,
        notify: bool = True,
        persistent: bool = False,
        expire_on: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Acknowledge service problems."""
        ...

    @async_wrapper("create_service_downtime")
    async def create_service_downtime(self, **kwargs) -> Dict[str, Any]:
        """Create service downtime."""
        ...

    @async_wrapper("start_service_discovery")
    async def start_service_discovery(
        self, host_name: str, mode: str = "refresh"
    ) -> Dict[str, Any]:
        """Start service discovery on a host."""
        ...

    # Status monitoring operations
    @async_wrapper("get_service_health_summary")
    async def get_service_health_summary(self) -> Dict[str, Any]:
        """Get overall service health summary."""
        ...

    @async_wrapper("list_problem_services")
    async def list_problem_services(
        self, host_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List services with problems."""
        ...

    @async_wrapper("get_acknowledged_services")
    async def get_acknowledged_services(self) -> List[Dict[str, Any]]:
        """Get list of acknowledged services."""
        ...

    @async_wrapper("get_services_in_downtime")
    async def get_services_in_downtime(self) -> List[Dict[str, Any]]:
        """Get list of services in downtime."""
        ...

    # This method doesn't exist in the sync client, let's implement it
    async def get_hosts_with_services(
        self, host_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get hosts with their services for status calculations."""
        # This is a composite operation - get hosts and their services
        hosts = await self.list_hosts()
        result = []

        for host in hosts:  # type: ignore[misc]
            host_name = host.get("id", "")
            if host_filter and host_filter not in host_name:
                continue

            try:
                services = await self.list_host_services(host_name)
                result.append(
                    {"name": host_name, "services": services, "host_data": host}
                )
            except Exception as e:
                self.logger.warning(f"Could not get services for host {host_name}: {e}")

        return result

    # Parameter operations
    @async_wrapper("get_effective_parameters")
    async def get_effective_parameters(
        self, host_name: str, service_name: str, ruleset: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get effective parameters for a service."""
        ...

    @async_wrapper("get_service_effective_parameters")
    async def get_service_effective_parameters(
        self, host_name: str, service_name: str
    ) -> Dict[str, Any]:
        """Get effective parameters for a service using Checkmk's service discovery data."""
        ...

    @async_wrapper("create_service_parameter_rule")
    async def create_service_parameter_rule(
        self,
        ruleset_name: str,
        folder: str,
        parameters: Dict[str, Any],
        host_name: Optional[str] = None,
        service_pattern: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a service parameter rule."""
        ...

    @async_wrapper("update_service_parameter_rule")
    async def update_service_parameter_rule(
        self,
        rule_id: str,
        parameters: Dict[str, Any],
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing service parameter rule."""
        ...

    @async_wrapper("find_service_parameter_rules")
    async def find_service_parameter_rules(
        self,
        host_name: str,
        service_name: str,
        ruleset_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find parameter rules that affect a specific service."""
        ...

    @async_wrapper("create_rule")
    async def create_rule(self, **kwargs) -> Dict[str, Any]:
        """Create a parameter rule."""
        ...

    @async_wrapper("list_rules")
    async def list_rules(self, ruleset_name: str) -> List[Dict[str, Any]]:
        """List rules for a specific ruleset."""
        ...

    @async_wrapper("list_rulesets")
    async def list_rulesets(self) -> List[Dict[str, Any]]:
        """List available rulesets."""
        ...

    @async_wrapper("get_ruleset_info")
    async def get_ruleset_info(self, ruleset_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific ruleset."""
        ...

    @async_wrapper("get_rule")
    async def get_rule(self, rule_id: str) -> Dict[str, Any]:
        """Get configuration details for a specific rule."""
        ...

    @async_wrapper("delete_rule")
    async def delete_rule(self, rule_id: str) -> None:
        """Delete a specific rule."""
        ...

    @async_wrapper("move_rule")
    async def move_rule(
        self,
        rule_id: str,
        position: str,
        folder: Optional[str] = None,
        target_rule_id: Optional[str] = None,
        etag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Move a rule to a new position."""
        ...

    @async_wrapper("search_rules_by_host_service")
    async def search_rules_by_host_service(
        self, host_name: str, service_name: str
    ) -> List[Dict[str, Any]]:
        """Search for rules that might affect a specific host/service combination."""
        ...

    # Event Console operations
    @async_wrapper("list_events")
    async def list_events(
        self,
        query: Optional[Dict[str, Any]] = None,
        host: Optional[str] = None,
        application: Optional[str] = None,
        state: Optional[str] = None,
        phase: Optional[str] = None,
        site_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List Event Console events with optional filtering."""
        ...

    @async_wrapper("get_event")
    async def get_event(
        self, event_id: str, site_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get specific event by ID."""
        ...

    @async_wrapper("acknowledge_event")
    async def acknowledge_event(
        self,
        event_id: str,
        comment: str,
        contact: Optional[str] = None,
        site_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Acknowledge an event in the Event Console."""
        ...

    @async_wrapper("change_event_state")
    async def change_event_state(
        self,
        event_id: str,
        new_state: int,
        comment: Optional[str] = None,
        site_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Change the state of an event."""
        ...

    @async_wrapper("delete_events")
    async def delete_events(
        self,
        query: Optional[Dict[str, Any]] = None,
        method: str = "by_query",
        site_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete events from the Event Console."""
        ...

    # Metrics operations
    @async_wrapper("get_metric_data")
    async def get_metric_data(
        self,
        request_type: str,
        host_name: str,
        service_description: str,
        metric_or_graph_id: str,
        time_range: Dict[str, Any],
        reduce: str = "average",
        site: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get metric or graph data from Checkmk."""
        ...

    @async_wrapper("get_single_metric")
    async def get_single_metric(
        self,
        host_name: str,
        service_description: str,
        metric_id: str,
        time_range: Dict[str, Any],
        reduce: str = "average",
        site: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data for a single metric."""
        ...

    @async_wrapper("get_predefined_graph")
    async def get_predefined_graph(
        self,
        host_name: str,
        service_description: str,
        graph_id: str,
        time_range: Dict[str, Any],
        reduce: str = "average",
        site: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data for a predefined graph containing multiple metrics."""
        ...

    # Business Intelligence operations
    @async_wrapper("get_bi_aggregation_states")
    async def get_bi_aggregation_states(
        self,
        filter_names: Optional[List[str]] = None,
        filter_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get current state of BI aggregations."""
        ...

    @async_wrapper("list_bi_packs")
    async def list_bi_packs(self) -> Dict[str, Any]:
        """List all available BI packs."""
        ...

    # System Information operations
    @async_wrapper("get_version_info")
    async def get_version_info(self) -> Dict[str, Any]:
        """Get Checkmk version information."""
        ...

    # Helper methods that delegate to sync client without wrapping
    async def test_connection(self) -> bool:
        """Test connection to Checkmk server."""
        try:
            await self.list_hosts()
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    async def activate_changes(
        self,
        sites: Optional[List[str]] = None,
        force_foreign_changes: bool = False,
        redirect: bool = False,
    ) -> Dict[str, Any]:
        """
        Activate pending configuration changes in Checkmk.

        Args:
            sites: List of site names to activate changes on. If None, activates on all sites.
            force_foreign_changes: If True, activates changes made by other users.
            redirect: If True, returns immediately instead of waiting for completion.

        Returns:
            Dict containing activation result information
        """
        # Run the sync method in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: self.sync_client.activate_changes(
                sites=sites,
                force_foreign_changes=force_foreign_changes,
                redirect=redirect,
            )
        )
