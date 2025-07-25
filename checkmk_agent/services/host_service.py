"""Host service - core business logic for host operations."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from .base import BaseService, ServiceResult
from .models.hosts import (
    HostInfo, HostListResult, HostCreateResult, HostUpdateResult, 
    HostDeleteResult, HostBulkCreateResult, HostBulkDeleteResult, HostState
)
from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkAPIError
from ..config import AppConfig
from ..utils import validate_hostname, sanitize_folder_path


class HostService(BaseService):
    """Core host operations service - presentation agnostic."""
    
    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        super().__init__(checkmk_client, config)
        self.logger = logging.getLogger(__name__)
    
    async def list_hosts(
        self, 
        search: Optional[str] = None,
        folder: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        include_status: bool = False
    ) -> ServiceResult[HostListResult]:
        """
        List hosts with optional filtering.
        
        Args:
            search: Search pattern for host names
            folder: Filter by Checkmk folder
            limit: Maximum number of hosts to return
            offset: Starting index for pagination
            include_status: Whether to include status information
            
        Returns:
            ServiceResult containing HostListResult
        """
        async def _list_operation():
            # Get hosts from Checkmk API
            hosts_data = await self.checkmk.list_hosts(effective_attributes=True)
            
            # Convert to HostInfo models
            hosts = []
            for host_data in hosts_data:
                host_info = self._convert_api_host_to_model(host_data, include_status)
                hosts.append(host_info)
            
            # Apply filters
            filtered_hosts = self._apply_host_filters(hosts, search, folder)
            
            # Calculate statistics
            stats = self._calculate_host_stats(filtered_hosts)
            
            # Apply pagination
            paginated_hosts = self._apply_pagination(filtered_hosts, offset, limit)
            
            return HostListResult(
                hosts=paginated_hosts,
                total_count=len(filtered_hosts),
                search_applied=search,
                folder_filter=folder,
                stats=stats,
                metadata={
                    "offset": offset,
                    "limit": limit,
                    "original_count": len(hosts_data),
                    "filtered_count": len(filtered_hosts),
                    "include_status": include_status
                }
            )
        
        return await self._execute_with_error_handling(_list_operation, "list_hosts")
    
    async def create_host(
        self,
        name: str,
        folder: str = "/",
        ip_address: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> ServiceResult[HostCreateResult]:
        """
        Create a new host with validation.
        
        Args:
            name: Host name
            folder: Checkmk folder path
            ip_address: IP address (optional)
            attributes: Host attributes
            labels: Host labels
            
        Returns:
            ServiceResult containing HostCreateResult
        """
        async def _create_operation():
            # Validate input parameters
            validation_errors = self._validate_create_host_params(name, folder, ip_address)
            if validation_errors:
                raise ValueError(f"Validation errors: {', '.join(validation_errors)}")
            
            # Prepare host data
            host_data = {
                "host_name": name,
                "folder": sanitize_folder_path(folder),
                "attributes": attributes or {},
                "labels": labels or {}
            }
            
            if ip_address:
                host_data["attributes"]["ipaddress"] = ip_address
            
            # Create host via API
            result = await self.checkmk.create_host(**host_data)
            
            # Convert result to model
            host_info = self._convert_api_host_to_model(result)
            
            return HostCreateResult(
                host=host_info,
                success=True,
                message=f"Successfully created host {name}",
                etag=result.get("etag")
            )
        
        return await self._execute_with_error_handling(_create_operation, f"create_host_{name}")
    
    async def update_host(
        self,
        name: str,
        folder: Optional[str] = None,
        ip_address: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        labels: Optional[Dict[str, str]] = None,
        etag: Optional[str] = None
    ) -> ServiceResult[HostUpdateResult]:
        """
        Update an existing host.
        
        Args:
            name: Host name
            folder: New folder path
            ip_address: New IP address
            attributes: Updated attributes
            labels: Updated labels  
            etag: ETag for optimistic locking
            
        Returns:
            ServiceResult containing HostUpdateResult
        """
        async def _update_operation():
            # Validate host exists
            if not validate_hostname(name):
                raise ValueError(f"Invalid hostname: {name}")
            
            # Prepare update data
            update_data = {}
            changes_made = []
            
            if folder is not None:
                update_data["folder"] = sanitize_folder_path(folder)
                changes_made.append(f"folder changed to {folder}")
            
            if attributes is not None:
                update_data["attributes"] = attributes
                changes_made.append("attributes updated")
                
                if ip_address is not None:
                    update_data["attributes"]["ipaddress"] = ip_address
                    changes_made.append(f"IP address changed to {ip_address}")
            elif ip_address is not None:
                # If only IP address is being updated
                update_data["attributes"] = {"ipaddress": ip_address}
                changes_made.append(f"IP address changed to {ip_address}")
            
            if labels is not None:
                update_data["labels"] = labels
                changes_made.append("labels updated")
            
            if etag:
                update_data["etag"] = etag
            
            # Update via API
            result = await self.checkmk.update_host(name, **update_data)
            
            # Convert result to model
            host_info = self._convert_api_host_to_model(result)
            
            return HostUpdateResult(
                host=host_info,
                success=True,
                message=f"Successfully updated host {name}",
                changes_made=changes_made,
                etag=result.get("etag")
            )
        
        return await self._execute_with_error_handling(_update_operation, f"update_host_{name}")
    
    async def delete_host(self, name: str) -> ServiceResult[HostDeleteResult]:
        """
        Delete a host.
        
        Args:
            name: Host name to delete
            
        Returns:
            ServiceResult containing HostDeleteResult
        """
        async def _delete_operation():
            # Validate host name
            if not validate_hostname(name):
                raise ValueError(f"Invalid hostname: {name}")
            
            # Delete via API
            await self.checkmk.delete_host(name)
            
            return HostDeleteResult(
                host_name=name,
                success=True,
                message=f"Successfully deleted host {name}"
            )
        
        return await self._execute_with_error_handling(_delete_operation, f"delete_host_{name}")
    
    async def get_host(self, name: str, include_status: bool = True) -> ServiceResult[HostInfo]:
        """
        Get detailed information about a specific host.
        
        Args:
            name: Host name
            include_status: Whether to include status information
            
        Returns:
            ServiceResult containing HostInfo
        """
        async def _get_operation():
            # Validate host name
            if not validate_hostname(name):
                raise ValueError(f"Invalid hostname: {name}")
            
            # Get host data via API
            host_data = await self.checkmk.get_host(name)
            
            # Convert to model
            host_info = self._convert_api_host_to_model(host_data, include_status)
            
            return host_info
        
        return await self._execute_with_error_handling(_get_operation, f"get_host_{name}")
    
    async def bulk_create_hosts(self, hosts_data: List[Dict[str, Any]]) -> ServiceResult[HostBulkCreateResult]:
        """
        Create multiple hosts in bulk.
        
        Args:
            hosts_data: List of host creation data
            
        Returns:
            ServiceResult containing HostBulkCreateResult
        """
        async def _bulk_create_operation():
            # Validate all host data first
            validation_errors = []
            for i, host_data in enumerate(hosts_data):
                name = host_data.get("name")
                folder = host_data.get("folder", "/")
                ip_address = host_data.get("ip_address")
                
                errors = self._validate_create_host_params(name, folder, ip_address)
                if errors:
                    validation_errors.extend([f"Host {i+1}: {error}" for error in errors])
            
            if validation_errors:
                raise ValueError(f"Validation errors: {'; '.join(validation_errors)}")
            
            # Create hosts via API
            results = await self.checkmk.bulk_create_hosts(hosts_data)
            
            created_hosts = []
            failed_hosts = []
            
            for result in results:
                if result.get("success", False):
                    host_info = self._convert_api_host_to_model(result["data"])
                    created_hosts.append(host_info)
                else:
                    failed_hosts.append({
                        "name": result.get("name", "unknown"),
                        "error": result.get("error", "Unknown error")
                    })
            
            return HostBulkCreateResult(
                created_hosts=created_hosts,
                failed_hosts=failed_hosts,
                success_count=len(created_hosts),
                failure_count=len(failed_hosts),
                total_requested=len(hosts_data)
            )
        
        return await self._execute_with_error_handling(_bulk_create_operation, "bulk_create_hosts")
    
    def _convert_api_host_to_model(self, host_data: Dict[str, Any], include_status: bool = False) -> HostInfo:
        """Convert API host data to HostInfo model."""
        extensions = host_data.get("extensions", {})
        attributes = extensions.get("attributes", {})
        
        host_info = HostInfo(
            name=host_data.get("id", ""),
            folder=extensions.get("folder", "/"),
            ip_address=attributes.get("ipaddress"),
            attributes=attributes,
            labels=extensions.get("labels", {})
        )
        
        # Add status information if requested and available
        if include_status and "status" in extensions:
            status = extensions["status"]
            host_info.state = HostState(status.get("state", "PENDING"))
            host_info.state_type = status.get("state_type")
            host_info.plugin_output = status.get("plugin_output")
            host_info.performance_data = status.get("performance_data")
            host_info.acknowledged = status.get("acknowledged", False)
            host_info.in_downtime = status.get("in_downtime", False)
            
            # Convert timestamps
            if status.get("last_check"):
                host_info.last_check = datetime.fromtimestamp(status["last_check"])
            if status.get("last_state_change"):
                host_info.last_state_change = datetime.fromtimestamp(status["last_state_change"])
        
        return host_info
    
    def _apply_host_filters(self, hosts: List[HostInfo], search: Optional[str], folder: Optional[str]) -> List[HostInfo]:
        """Apply search and folder filters to hosts."""
        filtered_hosts = hosts
        
        # Apply search filter
        if search:
            filtered_hosts = self._apply_text_filter(
                filtered_hosts, 
                search, 
                ["name", "ip_address", "attributes.alias"]
            )
        
        # Apply folder filter
        if folder:
            folder_lower = folder.lower()
            filtered_hosts = [
                host for host in filtered_hosts 
                if host.folder.lower().startswith(folder_lower)
            ]
        
        return filtered_hosts
    
    def _calculate_host_stats(self, hosts: List[HostInfo]) -> Dict[str, int]:
        """Calculate host statistics."""
        stats = {
            "total": len(hosts),
            "up": 0,
            "down": 0,
            "unreachable": 0,
            "pending": 0,
            "with_ip": 0,
            "without_ip": 0
        }
        
        for host in hosts:
            if host.state:
                stats[host.state.lower()] += 1
            else:
                stats["pending"] += 1
            
            if host.ip_address:
                stats["with_ip"] += 1
            else:
                stats["without_ip"] += 1
        
        return stats
    
    def _validate_create_host_params(self, name: str, folder: str, ip_address: Optional[str]) -> List[str]:
        """Validate parameters for host creation."""
        errors = []
        
        if not name or not name.strip():
            errors.append("Host name is required")
        elif not validate_hostname(name):
            errors.append(f"Invalid hostname: {name}")
        
        if not folder or not folder.strip():
            errors.append("Folder is required")
        elif not folder.startswith("/"):
            errors.append("Folder must start with '/'")
        
        if ip_address and not self._is_valid_ip_address(ip_address):
            errors.append(f"Invalid IP address: {ip_address}")
        
        return errors
    
    def _is_valid_ip_address(self, ip: str) -> bool:
        """Validate IP address format."""
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False