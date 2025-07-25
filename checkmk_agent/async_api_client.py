"""Async wrapper for Checkmk REST API client to support service layer."""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from functools import wraps

from .api_client import CheckmkClient, CheckmkAPIError


def async_wrapper(method_name):
    """Decorator to convert synchronous methods to async."""
    def decorator(func):
        @wraps(func)
        async def async_method(self, *args, **kwargs):
            # Get the actual method from the sync client
            sync_method = getattr(self.sync_client, method_name)
            # Run the sync method in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: sync_method(*args, **kwargs))
        return async_method
    return decorator


class AsyncCheckmkClient:
    """Async wrapper for CheckmkClient to support service layer operations."""
    
    def __init__(self, sync_client: CheckmkClient):
        self.sync_client = sync_client
        self.logger = logging.getLogger(__name__)
    
    # Host operations
    @async_wrapper("list_hosts")
    def list_hosts(self, effective_attributes: bool = False) -> List[Dict[str, Any]]:
        """List all hosts."""
        pass
    
    @async_wrapper("create_host")
    def create_host(self, host_name: str, folder: str = "/", ip_address: Optional[str] = None, 
                   attributes: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Create a new host."""
        pass
    
    @async_wrapper("get_host")
    def get_host(self, host_name: str) -> Dict[str, Any]:
        """Get host details."""
        pass
    
    @async_wrapper("update_host")
    def update_host(self, host_name: str, **kwargs) -> Dict[str, Any]:
        """Update host configuration."""
        pass
    
    @async_wrapper("delete_host")
    def delete_host(self, host_name: str) -> None:
        """Delete a host."""
        pass
    
    # bulk_create_hosts exists in sync client
    @async_wrapper("bulk_create_hosts")
    def bulk_create_hosts(self, hosts_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple hosts in bulk."""
        pass
    
    # get_host_status doesn't exist in sync client, implement as fallback
    async def get_host_status(self, host_name: str) -> Dict[str, Any]:
        """Get host status information."""
        try:
            # Try to get host config and derive status
            host_data = await self.get_host(host_name)
            return {
                'name': host_name,
                'state': 'UP',  # Default fallback
                'plugin_output': 'Host status via config lookup'
            }
        except Exception as e:
            self.logger.warning(f"Could not get status for host {host_name}: {e}")
            return {
                'name': host_name,
                'state': 'UNKNOWN',
                'plugin_output': f'Status lookup failed: {e}'
            }
    
    # Service operations
    @async_wrapper("list_host_services")
    def list_host_services(self, host_name: str) -> List[Dict[str, Any]]:
        """List services for a specific host."""
        pass
    
    @async_wrapper("list_all_services")
    def list_all_services(self, host_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all services with optional host filter."""
        pass
    
    @async_wrapper("get_service_status")
    def get_service_status(self, host_name: str, service_name: str) -> Dict[str, Any]:
        """Get detailed service status."""
        pass
    
    @async_wrapper("acknowledge_service_problems")
    def acknowledge_service_problems(self, acknowledgments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Acknowledge service problems."""
        pass
    
    @async_wrapper("create_service_downtime")
    def create_service_downtime(self, **kwargs) -> Dict[str, Any]:
        """Create service downtime."""
        pass
    
    @async_wrapper("start_service_discovery")
    def start_service_discovery(self, host_name: str, mode: str = "refresh") -> Dict[str, Any]:
        """Start service discovery on a host."""
        pass
    
    # Status monitoring operations
    @async_wrapper("get_service_health_summary")
    def get_service_health_summary(self) -> Dict[str, Any]:
        """Get overall service health summary."""
        pass
    
    @async_wrapper("list_problem_services")
    def list_problem_services(self, host_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List services with problems."""
        pass
    
    @async_wrapper("get_acknowledged_services")
    def get_acknowledged_services(self) -> List[Dict[str, Any]]:
        """Get list of acknowledged services."""
        pass
    
    @async_wrapper("get_services_in_downtime")
    def get_services_in_downtime(self) -> List[Dict[str, Any]]:
        """Get list of services in downtime."""
        pass
    
    # This method doesn't exist in the sync client, let's implement it
    async def get_hosts_with_services(self, host_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get hosts with their services for status calculations."""
        # This is a composite operation - get hosts and their services
        hosts = await self.list_hosts()
        result = []
        
        for host in hosts:
            host_name = host.get('id', '')
            if host_filter and host_filter not in host_name:
                continue
                
            try:
                services = await self.list_host_services(host_name)
                result.append({
                    'name': host_name,
                    'services': services,
                    'host_data': host
                })
            except Exception as e:
                self.logger.warning(f"Could not get services for host {host_name}: {e}")
                
        return result
    
    # Parameter operations
    @async_wrapper("get_effective_parameters")
    def get_effective_parameters(self, host_name: str, service_name: str, ruleset: str) -> Dict[str, Any]:
        """Get effective parameters for a service."""
        pass
    
    @async_wrapper("create_rule")
    def create_rule(self, **kwargs) -> Dict[str, Any]:
        """Create a parameter rule."""
        pass
    
    @async_wrapper("list_rules")
    def list_rules(self, ruleset_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List rules with optional ruleset filter."""
        pass
    
    @async_wrapper("list_rulesets")
    def list_rulesets(self) -> List[Dict[str, Any]]:
        """List available rulesets."""
        pass
    
    # Helper methods that delegate to sync client without wrapping
    async def test_connection(self) -> bool:
        """Test connection to Checkmk server."""
        try:
            await self.list_hosts()
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False