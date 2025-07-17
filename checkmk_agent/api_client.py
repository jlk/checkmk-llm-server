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


class ServiceRequest(BaseModel):
    """Request model for service operations."""
    
    host_name: Optional[str] = Field(None, description="Filter by hostname")
    sites: Optional[List[str]] = Field(None, description="Restrict to specific sites")
    query: Optional[str] = Field(None, description="Livestatus query expressions")
    columns: Optional[List[str]] = Field(None, description="Desired columns (default: host_name, description)")


class AcknowledgeServiceRequest(BaseModel):
    """Request model for acknowledging service problems."""
    
    acknowledge_type: str = Field(..., description="Type of acknowledgment", pattern=r'^(service)$')
    host_name: str = Field(..., description="The hostname")
    service_description: str = Field(..., description="The service description")
    comment: str = Field(..., description="A comment for the acknowledgment")
    sticky: bool = Field(True, description="Whether acknowledgment persists until service is OK")
    notify: bool = Field(True, description="Whether to send notifications")
    persistent: bool = Field(False, description="Whether acknowledgment survives restarts")


class ServiceDowntimeRequest(BaseModel):
    """Request model for creating service downtime."""
    
    downtime_type: str = Field(..., description="Type of downtime", pattern=r'^(service)$')
    host_name: str = Field(..., description="The hostname")
    service_descriptions: List[str] = Field(..., description="List of service descriptions")
    start_time: str = Field(..., description="Start time as ISO timestamp")
    end_time: str = Field(..., description="End time as ISO timestamp")
    comment: str = Field(..., description="A comment for the downtime")


class ServiceDiscoveryRequest(BaseModel):
    """Request model for service discovery operations."""
    
    host_name: str = Field(..., description="The hostname")
    mode: str = Field(default="refresh", description="Discovery mode", pattern=r'^(refresh|new|remove|fixall|refresh_autochecks)$')


class ServiceParameterRequest(BaseModel):
    """Request model for service parameter operations."""
    
    host_name: str = Field(..., description="Target hostname")
    service_pattern: str = Field(..., description="Service name pattern")
    ruleset: str = Field(..., description="Check parameter ruleset name")
    parameters: Dict[str, Any] = Field(..., description="Parameter values")
    conditions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Rule conditions")
    rule_properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Rule properties")


class ParameterRule(BaseModel):
    """Model for service parameter rules."""
    
    rule_id: str = Field(..., description="Rule identifier")
    ruleset: str = Field(..., description="Ruleset name")
    folder: str = Field(..., description="Folder path")
    value_raw: str = Field(..., description="Raw parameter value as JSON string")
    conditions: Dict[str, Any] = Field(default_factory=dict, description="Rule conditions")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Rule properties")
    effective_parameters: Optional[Dict[str, Any]] = Field(None, description="Parsed effective parameters")


class ServiceParameterTemplate(BaseModel):
    """Template for common service parameter configurations."""
    
    service_type: str = Field(..., description="Service type (cpu, memory, filesystem, etc.)")
    ruleset: str = Field(..., description="Associated ruleset name")
    default_parameters: Dict[str, Any] = Field(..., description="Default parameter values")
    parameter_schema: Dict[str, Any] = Field(..., description="Parameter validation schema")
    description: str = Field(..., description="Template description")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Example configurations")


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
    
    # Service operations
    
    def list_host_services(self, host_name: str, sites: Optional[List[str]] = None, 
                          query: Optional[str] = None, columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        List all services for a specific host.
        
        Args:
            host_name: The hostname
            sites: Restrict to specific sites
            query: Livestatus query expressions
            columns: Desired columns (default: host_name, description)
            
        Returns:
            List of service objects
        """
        params = {}
        if sites:
            params['sites'] = sites
        if query:
            params['query'] = query
        if columns:
            params['columns'] = columns
        
        response = self._make_request(
            'GET',
            f'/objects/host/{host_name}/collections/services',
            params=params
        )
        
        # Extract service data from response
        services = response.get('value', [])
        self.logger.info(f"Retrieved {len(services)} services for host: {host_name}")
        return services
    
    def list_all_services(self, host_name: Optional[str] = None, sites: Optional[List[str]] = None,
                         query: Optional[str] = None, columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        List all services across all hosts with optional filtering.
        
        Args:
            host_name: Filter by hostname
            sites: Restrict to specific sites
            query: Livestatus query expressions
            columns: Desired columns (default: host_name, description)
            
        Returns:
            List of service objects
        """
        params = {}
        if host_name:
            params['host_name'] = host_name
        if sites:
            params['sites'] = sites
        if query:
            params['query'] = query
        if columns:
            params['columns'] = columns
        
        response = self._make_request(
            'GET',
            '/domain-types/service/collections/all',
            params=params
        )
        
        # Extract service data from response
        services = response.get('value', [])
        self.logger.info(f"Retrieved {len(services)} services")
        return services
    
    def acknowledge_service_problems(self, host_name: str, service_description: str, 
                                   comment: str, sticky: bool = True,
                                   notify: bool = True, persistent: bool = False) -> Dict[str, Any]:
        """
        Acknowledge service problems.
        
        Args:
            host_name: The hostname
            service_description: The service description
            comment: A comment for the acknowledgment
            sticky: Whether acknowledgment persists until service is OK
            notify: Whether to send notifications
            persistent: Whether acknowledgment survives restarts
            
        Returns:
            Acknowledgment response
        """
        # Validate input
        request_data = AcknowledgeServiceRequest(
            acknowledge_type="service",
            host_name=host_name,
            service_description=service_description,
            comment=comment,
            sticky=sticky,
            notify=notify,
            persistent=persistent
        )
        
        response = self._make_request(
            'POST',
            '/domain-types/acknowledge/collections/service',
            json=request_data.model_dump()
        )
        
        self.logger.info(f"Acknowledged service problem: {host_name}/{service_description}")
        return response
    
    def create_service_downtime(self, host_name: str, service_description: str,
                               start_time: str, end_time: str, comment: str) -> Dict[str, Any]:
        """
        Create downtime for a service.
        
        Args:
            host_name: The hostname
            service_description: The service description
            start_time: Start time as ISO timestamp
            end_time: End time as ISO timestamp
            comment: A comment for the downtime
            
        Returns:
            Downtime creation response
        """
        # Validate input - note that service_descriptions is a list
        request_data = ServiceDowntimeRequest(
            downtime_type="service",
            host_name=host_name,
            service_descriptions=[service_description],  # Convert to list
            start_time=start_time,
            end_time=end_time,
            comment=comment
        )
        
        response = self._make_request(
            'POST',
            '/domain-types/downtime/collections/service',
            json=request_data.model_dump()
        )
        
        self.logger.info(f"Created downtime for service: {host_name}/{service_description}")
        return response
    
    # Service discovery operations
    
    def get_service_discovery_result(self, host_name: str) -> Dict[str, Any]:
        """
        Get the current service discovery result for a host.
        
        Args:
            host_name: The hostname
            
        Returns:
            Service discovery result object
        """
        response = self._make_request(
            'GET',
            f'/objects/service_discovery/{host_name}'
        )
        
        self.logger.info(f"Retrieved service discovery result for host: {host_name}")
        return response
    
    def get_service_discovery_status(self, host_name: str) -> Dict[str, Any]:
        """
        Get the status of the last service discovery background job for a host.
        
        Args:
            host_name: The hostname
            
        Returns:
            Service discovery job status object
        """
        response = self._make_request(
            'GET',
            f'/objects/service_discovery_run/{host_name}'
        )
        
        self.logger.info(f"Retrieved service discovery status for host: {host_name}")
        return response
    
    def start_service_discovery(self, host_name: str, mode: str = "refresh") -> Dict[str, Any]:
        """
        Start a service discovery background job for a host.
        
        Args:
            host_name: The hostname
            mode: Discovery mode (refresh, new, remove, fixall, refresh_autochecks)
            
        Returns:
            Service discovery job start response
        """
        # Validate input
        request_data = ServiceDiscoveryRequest(
            host_name=host_name,
            mode=mode
        )
        
        response = self._make_request(
            'POST',
            '/domain-types/service_discovery_run/actions/start/invoke',
            json=request_data.model_dump()
        )
        
        self.logger.info(f"Started service discovery for host: {host_name} with mode: {mode}")
        return response
    
    # Ruleset operations for service parameters
    
    def list_rulesets(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available rulesets.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of ruleset objects
        """
        params = {}
        if category:
            params['group'] = category
        
        response = self._make_request(
            'GET',
            '/domain-types/ruleset/collections/all',
            params=params
        )
        
        # Extract ruleset data from response
        rulesets = response.get('value', [])
        self.logger.info(f"Retrieved {len(rulesets)} rulesets")
        return rulesets
    
    def get_ruleset_info(self, ruleset_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific ruleset.
        
        Args:
            ruleset_name: The name of the ruleset
            
        Returns:
            Ruleset information object
        """
        response = self._make_request(
            'GET',
            f'/objects/ruleset/{ruleset_name}'
        )
        
        self.logger.info(f"Retrieved ruleset info: {ruleset_name}")
        return response
    
    def search_rules_by_host_service(self, host_name: str, 
                                   service_name: str) -> List[Dict[str, Any]]:
        """
        Search for rules that might affect a specific host/service combination.
        
        Args:
            host_name: The hostname
            service_name: The service description
            
        Returns:
            List of potentially matching rules
        """
        # Get all rules and filter client-side since API doesn't support complex filtering
        all_rules = []
        
        # We need to check multiple rulesets that could affect services
        potential_rulesets = [
            'cpu_utilization_linux',
            'cpu_utilization_simple', 
            'memory_linux',
            'memory_level_windows',
            'filesystems',
            'interfaces',
            'disk_io'
        ]
        
        for ruleset in potential_rulesets:
            try:
                rules = self.list_rules(ruleset)
                # Filter rules that could match this host/service
                for rule in rules:
                    conditions = rule.get('extensions', {}).get('conditions', {})
                    if self._rule_matches_host_service(conditions, host_name, service_name):
                        all_rules.append(rule)
            except CheckmkAPIError:
                # Ruleset might not exist, continue with others
                continue
        
        self.logger.info(f"Found {len(all_rules)} rules affecting {host_name}/{service_name}")
        return all_rules
    
    def get_effective_parameters(self, host_name: str, 
                               service_name: str) -> Dict[str, Any]:
        """
        Get effective parameters for a service (placeholder - would need service discovery).
        
        Args:
            host_name: The hostname
            service_name: The service description
            
        Returns:
            Effective parameter information
        """
        # This is a placeholder - in practice, you'd need to query the service
        # discovery or monitoring data to get actual effective parameters
        rules = self.search_rules_by_host_service(host_name, service_name)
        
        return {
            'host_name': host_name,
            'service_name': service_name,
            'affecting_rules': rules,
            'note': 'This is a placeholder implementation'
        }
    
    def _rule_matches_host_service(self, conditions: Dict[str, Any], 
                                 host_name: str, service_name: str) -> bool:
        """
        Check if rule conditions could match a host/service combination.
        
        Args:
            conditions: Rule conditions
            host_name: Target hostname
            service_name: Target service name
            
        Returns:
            True if rule could match
        """
        # Check host name conditions
        host_names = conditions.get('host_name', [])
        if host_names:
            host_match = False
            for pattern in host_names:
                if pattern.startswith('~'):
                    # Regex pattern - simplified check
                    if pattern[1:] in host_name:
                        host_match = True
                        break
                elif pattern == host_name:
                    host_match = True
                    break
            if not host_match:
                return False
        
        # Check service description conditions
        service_descriptions = conditions.get('service_description', [])
        if service_descriptions:
            service_match = False
            for pattern in service_descriptions:
                if pattern.startswith('~'):
                    # Regex pattern - simplified check
                    if pattern[1:] in service_name:
                        service_match = True
                        break
                elif pattern == service_name:
                    service_match = True
                    break
            if not service_match:
                return False
        
        # If we get here, the rule could match
        return True

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