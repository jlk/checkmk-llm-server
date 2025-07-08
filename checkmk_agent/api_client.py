"""Checkmk REST API client based on OpenAPI specification."""

import requests
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from pydantic import BaseModel, Field

from .config import CheckmkConfig
from .utils import retry_on_failure, extract_error_message


class CheckmkAPIError(Exception):
    """Exception raised for Checkmk API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class CreateHostRequest(BaseModel):
    """Request model for creating a host."""
    
    folder: str = Field(..., description="The path name of the folder where the host will be created")
    host_name: str = Field(..., description="The hostname or IP address of the host", regex=r'^[-0-9a-zA-Z_.]+$')
    attributes: Optional[Dict[str, Any]] = Field(None, description="Attributes to set on the newly created host")


class CheckmkClient:
    """Client for interacting with Checkmk REST API."""
    
    def __init__(self, config: CheckmkConfig):
        self.config = config
        self.base_url = f"{config.server_url}/{config.site}/check_mk/api/1.0"
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        
        # Set up authentication
        self._setup_authentication()
        
        # Set default headers
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def _setup_authentication(self):
        """Set up Bearer token authentication."""
        auth_token = f"{self.config.username} {self.config.password}"
        self.session.headers.update({
            'Authorization': f'Bearer {auth_token}'
        })
    
    @retry_on_failure(max_retries=3)
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling."""
        url = urljoin(self.base_url, endpoint)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.config.request_timeout,
                **kwargs
            )
            
            self.logger.debug(f"{method} {url} -> {response.status_code}")
            
            # Handle different response codes
            if response.status_code == 204:  # No Content
                return {}
            
            if response.status_code >= 400:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    error_data = {"message": response.text}
                
                error_msg = extract_error_message(error_data)
                raise CheckmkAPIError(
                    f"API request failed: {error_msg}",
                    status_code=response.status_code,
                    response_data=error_data
                )
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise CheckmkAPIError(f"Request failed: {e}")
    
    def list_hosts(self, effective_attributes: bool = False) -> List[Dict[str, Any]]:
        """
        List all host configurations.
        
        Args:
            effective_attributes: Show all effective attributes including parent folder attributes
            
        Returns:
            List of host configuration objects
        """
        params = {}
        if effective_attributes:
            params['effective_attributes'] = 'true'
        
        response = self._make_request(
            'GET', 
            '/domain-types/host_config/collections/all',
            params=params
        )
        
        # Extract host data from response
        hosts = response.get('value', [])
        self.logger.info(f"Retrieved {len(hosts)} hosts")
        return hosts
    
    def get_host(self, host_name: str, effective_attributes: bool = False) -> Dict[str, Any]:
        """
        Get configuration details for a specific host.
        
        Args:
            host_name: The hostname
            effective_attributes: Include inherited folder attributes
            
        Returns:
            Host configuration object
        """
        params = {}
        if effective_attributes:
            params['effective_attributes'] = 'true'
        
        response = self._make_request(
            'GET',
            f'/objects/host_config/{host_name}',
            params=params
        )
        
        self.logger.info(f"Retrieved host: {host_name}")
        return response
    
    def create_host(self, folder: str, host_name: str, attributes: Optional[Dict[str, Any]] = None, 
                   bake_agent: bool = False) -> Dict[str, Any]:
        """
        Create a new host.
        
        Args:
            folder: The folder path where the host will be created
            host_name: The hostname or IP address
            attributes: Optional host attributes
            bake_agent: Automatically bake agent for Enterprise editions
            
        Returns:
            Created host object
        """
        # Validate input
        request_data = CreateHostRequest(
            folder=folder,
            host_name=host_name,
            attributes=attributes or {}
        )
        
        params = {}
        if bake_agent:
            params['bake_agent'] = 'true'
        
        response = self._make_request(
            'POST',
            '/domain-types/host_config/collections/all',
            json=request_data.dict(),
            params=params
        )
        
        self.logger.info(f"Created host: {host_name} in folder: {folder}")
        return response
    
    def delete_host(self, host_name: str) -> None:
        """
        Delete a specific host.
        
        Args:
            host_name: The hostname to delete
        """
        self._make_request(
            'DELETE',
            f'/objects/host_config/{host_name}'
        )
        
        self.logger.info(f"Deleted host: {host_name}")
    
    def update_host(self, host_name: str, attributes: Dict[str, Any], 
                   etag: Optional[str] = None) -> Dict[str, Any]:
        """
        Update an existing host configuration.
        
        Args:
            host_name: The hostname
            attributes: Host attributes to update
            etag: ETag for concurrency control
            
        Returns:
            Updated host object
        """
        headers = {}
        if etag:
            headers['If-Match'] = etag
        
        response = self._make_request(
            'PUT',
            f'/objects/host_config/{host_name}',
            json={"attributes": attributes},
            headers=headers
        )
        
        self.logger.info(f"Updated host: {host_name}")
        return response
    
    def bulk_create_hosts(self, hosts: List[Dict[str, Any]], bake_agent: bool = False) -> Dict[str, Any]:
        """
        Create multiple hosts in a single request.
        
        Args:
            hosts: List of host creation requests
            bake_agent: Automatically bake agents for Enterprise editions
            
        Returns:
            Bulk creation response
        """
        # Validate all host entries
        entries = []
        for host_data in hosts:
            request_data = CreateHostRequest(**host_data)
            entries.append(request_data.dict())
        
        params = {}
        if bake_agent:
            params['bake_agent'] = 'true'
        
        response = self._make_request(
            'POST',
            '/domain-types/host_config/actions/bulk-create/invoke',
            json={"entries": entries},
            params=params
        )
        
        self.logger.info(f"Bulk created {len(entries)} hosts")
        return response
    
    def bulk_delete_hosts(self, host_names: List[str]) -> Dict[str, Any]:
        """
        Delete multiple hosts in a single request.
        
        Args:
            host_names: List of hostnames to delete
            
        Returns:
            Bulk deletion response
        """
        response = self._make_request(
            'POST',
            '/domain-types/host_config/actions/bulk-delete/invoke',
            json={"entries": host_names}
        )
        
        self.logger.info(f"Bulk deleted {len(host_names)} hosts")
        return response
    
    def test_connection(self) -> bool:
        """
        Test the connection to Checkmk API.
        
        Returns:
            True if connection is successful
        """
        try:
            # Try to list hosts as a connection test
            self.list_hosts()
            return True
        except CheckmkAPIError as e:
            self.logger.error(f"Connection test failed: {e}")
            return False