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
    host_name: str = Field(..., description="The hostname or IP address of the host", pattern=r'^[-0-9a-zA-Z_.]+$')
    attributes: Optional[Dict[str, Any]] = Field(None, description="Attributes to set on the newly created host")


class CreateRuleRequest(BaseModel):
    """Request model for creating a rule."""
    
    ruleset: str = Field(..., description="The name of the ruleset")
    folder: str = Field(..., description="The folder path where the rule will be created")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Rule properties (disabled, description, etc.)")
    value_raw: str = Field(..., description="The rule value as JSON string")
    conditions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Rule conditions for matching")


class MoveRuleRequest(BaseModel):
    """Request model for moving a rule."""
    
    position: str = Field(..., description="Position to move rule to", pattern=r'^(top_of_folder|bottom_of_folder|before|after)$')
    folder: Optional[str] = Field(None, description="Target folder for the rule")
    target_rule_id: Optional[str] = Field(None, description="Target rule ID for before/after positioning")


class CheckmkClient:
    """Client for interacting with Checkmk REST API."""
    
    def __init__(self, config: CheckmkConfig):
        self.config = config
        self.base_url = f"{config.server_url}/{config.site}/check_mk/api/1.0"
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        
        # Set up authentication
        self.logger.debug(f"Setting up authentication for user: {self.config.username}")
        self._setup_authentication()
        
        # Set default headers
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        self.logger.debug(f"Session headers: {self.session.headers}")
    
    def _setup_authentication(self):
        """Set up Bearer token authentication."""
        auth_token = f"{self.config.username} {self.config.password}"
        self.session.headers.update({
            'Authorization': f'Bearer {auth_token}'
        })
        self.logger.debug("Authentication header set.")
    
    @retry_on_failure(max_retries=3)
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling."""
        # Ensure endpoint doesn't start with / to avoid urljoin path replacement
        if endpoint.startswith('/'):
            endpoint = endpoint[1:]
        url = urljoin(self.base_url + '/', endpoint)
        self.logger.debug(f"Preparing {method} request to {url} with kwargs: {kwargs}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.config.request_timeout,
                **kwargs
            )
            self.logger.debug(f"Response status: {response.status_code}")
            self.logger.debug(f"Response headers: {response.headers}")
            self.logger.debug(f"Response text: {response.text}")
            
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
            json=request_data.model_dump(),
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
            entries.append(request_data.model_dump())
        
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
    
    # Rule operations
    
    def list_rules(self, ruleset_name: str) -> List[Dict[str, Any]]:
        """
        List all rules in a specific ruleset.
        
        Args:
            ruleset_name: The name of the ruleset to list rules for
            
        Returns:
            List of rule objects
        """
        response = self._make_request(
            'GET',
            '/domain-types/rule/collections/all',
            params={'ruleset_name': ruleset_name}
        )
        
        # Extract rule data from response
        rules = response.get('value', [])
        self.logger.info(f"Retrieved {len(rules)} rules for ruleset: {ruleset_name}")
        return rules
    
    def get_rule(self, rule_id: str) -> Dict[str, Any]:
        """
        Get configuration details for a specific rule.
        
        Args:
            rule_id: The rule ID
            
        Returns:
            Rule configuration object
        """
        response = self._make_request(
            'GET',
            f'/objects/rule/{rule_id}'
        )
        
        self.logger.info(f"Retrieved rule: {rule_id}")
        return response
    
    def create_rule(self, ruleset: str, folder: str, value_raw: str, 
                   conditions: Optional[Dict[str, Any]] = None,
                   properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new rule.
        
        Args:
            ruleset: The name of the ruleset
            folder: The folder path where the rule will be created
            value_raw: The rule value as JSON string
            conditions: Optional rule conditions for matching
            properties: Optional rule properties (disabled, description, etc.)
            
        Returns:
            Created rule object
        """
        # Validate input
        request_data = CreateRuleRequest(
            ruleset=ruleset,
            folder=folder,
            value_raw=value_raw,
            conditions=conditions or {},
            properties=properties or {}
        )
        
        response = self._make_request(
            'POST',
            '/domain-types/rule/collections/all',
            json=request_data.model_dump()
        )
        
        self.logger.info(f"Created rule in ruleset: {ruleset}, folder: {folder}")
        return response
    
    def delete_rule(self, rule_id: str) -> None:
        """
        Delete a specific rule.
        
        Args:
            rule_id: The rule ID to delete
        """
        self._make_request(
            'DELETE',
            f'/objects/rule/{rule_id}'
        )
        
        self.logger.info(f"Deleted rule: {rule_id}")
    
    def move_rule(self, rule_id: str, position: str, folder: Optional[str] = None,
                 target_rule_id: Optional[str] = None, etag: Optional[str] = None) -> Dict[str, Any]:
        """
        Move a rule to a new position.
        
        Args:
            rule_id: The rule ID to move
            position: Position to move rule to (top_of_folder, bottom_of_folder, before, after)
            folder: Target folder for the rule
            target_rule_id: Target rule ID for before/after positioning
            etag: ETag for concurrency control
            
        Returns:
            Updated rule object
        """
        # Validate input
        move_data = MoveRuleRequest(
            position=position,
            folder=folder,
            target_rule_id=target_rule_id
        )
        
        headers = {}
        if etag:
            headers['If-Match'] = etag
        
        response = self._make_request(
            'POST',
            f'/objects/rule/{rule_id}/actions/move/invoke',
            json=move_data.model_dump(exclude_none=True),
            headers=headers
        )
        
        self.logger.info(f"Moved rule: {rule_id} to position: {position}")
        return response
    
    def test_connection(self) -> bool:
        """
        Test the connection to Checkmk API.
        
        Returns:
            True if connection is successful
        """
        self.logger.debug("Testing connection to Checkmk API by listing hosts.")
        try:
            self.list_hosts()
            self.logger.debug("Connection test succeeded.")
            return True
        except CheckmkAPIError as e:
            self.logger.error(f"Connection test failed: {e}")
            return False