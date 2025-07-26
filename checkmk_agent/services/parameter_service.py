"""Parameter service - core business logic for service parameter management."""

import logging
from typing import Optional, Dict, Any, List

from .base import BaseService, ServiceResult
from .models.services import ServiceParameterResult
from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkAPIError
from ..config import AppConfig


class ParameterService(BaseService):
    """Core service parameter management service - presentation agnostic."""
    
    # Common service parameter rulesets
    PARAMETER_RULESETS = {
        'cpu': 'checkgroup_parameters:cpu_utilization',
        'memory': 'checkgroup_parameters:memory_linux',
        'disk': 'checkgroup_parameters:filesystem',
        'filesystem': 'checkgroup_parameters:filesystem',
        'network': 'checkgroup_parameters:if',
        'interface': 'checkgroup_parameters:if',
        'load': 'checkgroup_parameters:cpu_load',
        'swap': 'checkgroup_parameters:memory_linux'
    }
    
    # Default parameter values for common services
    DEFAULT_PARAMETERS = {
        'cpu_utilization': {
            'levels': (80.0, 90.0),  # (warning, critical)
            'average': 15  # minutes
        },
        'memory_linux': {
            'levels': (80.0, 90.0),  # % of RAM
            'levels_swap': (50.0, 75.0)  # % of swap
        },
        'filesystem': {
            'levels': (80.0, 90.0),  # % used
            'levels_low': (50.0, 10.0),  # MB free (warning, critical)
            'magic_normsize': 20,  # GB
            'levels_inode': (10.0, 5.0)  # % inodes free
        },
        'if': {
            'speed': 100000000,  # 100 Mbps default
            'traffic': [('both', ('upper', ('perc', (5.0, 20.0))))],
            'errors': (0.01, 0.1),  # % error rates
            'discards': (0.01, 0.1)  # % discard rates
        },
        'cpu_load': {
            'levels': (5.0, 10.0)  # Load average thresholds
        }
    }
    
    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        super().__init__(checkmk_client, config)
        self.logger = logging.getLogger(__name__)
    
    async def get_default_parameters(self, service_type: str) -> ServiceResult[Dict[str, Any]]:
        """
        Get default parameters for a service type.
        
        Args:
            service_type: Type of service (cpu, memory, disk, etc.)
            
        Returns:
            ServiceResult containing default parameters
        """
        async def _get_defaults_operation():
            service_type_lower = service_type.lower()
            
            # Try to find matching default parameters
            for param_key, params in self.DEFAULT_PARAMETERS.items():
                if service_type_lower in param_key or param_key in service_type_lower:
                    return {
                        'service_type': service_type,
                        'parameter_set': param_key,
                        'parameters': params,
                        'ruleset': self.PARAMETER_RULESETS.get(service_type_lower)
                    }
            
            # If no specific defaults found, return empty
            return {
                'service_type': service_type,
                'parameter_set': None,
                'parameters': {},
                'ruleset': self.PARAMETER_RULESETS.get(service_type_lower),
                'message': f'No default parameters available for service type: {service_type}'
            }
        
        return await self._execute_with_error_handling(_get_defaults_operation, f"get_default_parameters_{service_type}")
    
    async def get_effective_parameters(
        self,
        host_name: str,
        service_name: str
    ) -> ServiceResult[ServiceParameterResult]:
        """
        Get effective parameters for a specific service.
        
        Args:
            host_name: Host name
            service_name: Service name
            
        Returns:
            ServiceResult containing effective parameters
        """
        async def _get_effective_operation():
            # Validate parameters
            validation_errors = self._validate_required_params(
                {"host_name": host_name, "service_name": service_name},
                ["host_name", "service_name"]
            )
            if validation_errors:
                raise ValueError(f"Validation errors: {', '.join(validation_errors)}")
            
            # Try to determine the service type and ruleset
            service_type = self._determine_service_type(service_name)
            ruleset = self.PARAMETER_RULESETS.get(service_type)
            
            if not ruleset:
                # If we can't determine the ruleset, return default info
                return ServiceParameterResult(
                    host_name=host_name,
                    service_name=service_name,
                    success=True,
                    message=f"Cannot determine parameter ruleset for service: {service_name}",
                    effective_parameters={},
                    ruleset=None
                )
            
            try:
                # Get effective parameters from Checkmk API
                effective_params = await self.checkmk.get_effective_parameters(host_name, service_name)
                
                return ServiceParameterResult(
                    host_name=host_name,
                    service_name=service_name,
                    success=True,
                    message=f"Retrieved effective parameters for {host_name}/{service_name}",
                    parameters=effective_params.get('parameters', {}),
                    effective_parameters=effective_params,
                    ruleset=ruleset
                )
                
            except CheckmkAPIError as e:
                # If API call fails, return default parameters
                default_params = self.DEFAULT_PARAMETERS.get(service_type, {})
                
                return ServiceParameterResult(
                    host_name=host_name,
                    service_name=service_name,
                    success=True,
                    message=f"Using default parameters (API error: {e})",
                    parameters=default_params,
                    effective_parameters=default_params,
                    ruleset=ruleset,
                    warnings=[f"Could not retrieve effective parameters: {e}"]
                )
        
        return await self._execute_with_error_handling(_get_effective_operation, f"get_effective_parameters_{host_name}_{service_name}")
    
    async def set_service_parameters(
        self,
        host_name: str,
        service_name: str,
        parameters: Dict[str, Any],
        rule_comment: Optional[str] = None
    ) -> ServiceResult[ServiceParameterResult]:
        """
        Set custom parameters for a specific service by creating a rule.
        
        Args:
            host_name: Host name
            service_name: Service name
            parameters: Parameter values to set
            rule_comment: Optional comment for the rule
            
        Returns:
            ServiceResult containing parameter setting result
        """
        async def _set_parameters_operation():
            # Validate parameters
            validation_errors = self._validate_required_params(
                {"host_name": host_name, "service_name": service_name, "parameters": parameters},
                ["host_name", "service_name", "parameters"]
            )
            if validation_errors:
                raise ValueError(f"Validation errors: {', '.join(validation_errors)}")
            
            # Determine service type and ruleset
            service_type = self._determine_service_type(service_name)
            ruleset = self.PARAMETER_RULESETS.get(service_type)
            
            if not ruleset:
                raise ValueError(f"Cannot determine parameter ruleset for service: {service_name}")
            
            # Prepare rule data
            rule_data = {
                'ruleset': ruleset,
                'value_raw': parameters,
                'conditions': {
                    'host_name': [host_name],
                    'service_description': [service_name]
                },
                'properties': {
                    'comment': rule_comment or f"Parameter override for {host_name}/{service_name}",
                    'disabled': False
                }
            }
            
            # Create the rule
            rule_result = await self.checkmk.create_rule(**rule_data)
            rule_id = rule_result.get('id')
            
            # Get effective parameters after rule creation
            try:
                effective_params = await self.checkmk.get_effective_parameters(host_name, service_name)
            except Exception as e:
                self.logger.warning(f"Could not retrieve effective parameters after rule creation: {e}")
                effective_params = parameters
            
            changes_made = []
            for key, value in parameters.items():
                changes_made.append(f"{key} = {value}")
            
            return ServiceParameterResult(
                host_name=host_name,
                service_name=service_name,
                success=True,
                message=f"Successfully set parameters for {host_name}/{service_name}",
                parameters=parameters,
                rule_id=rule_id,
                ruleset=ruleset,
                effective_parameters=effective_params,
                changes_made=changes_made
            )
        
        return await self._execute_with_error_handling(_set_parameters_operation, f"set_parameters_{host_name}_{service_name}")
    
    async def discover_ruleset(self, service_name: str) -> ServiceResult[Dict[str, Any]]:
        """
        Discover the appropriate ruleset for a service.
        
        Args:
            service_name: Service name to analyze
            
        Returns:
            ServiceResult containing ruleset discovery information
        """
        async def _discover_ruleset_operation():
            service_type = self._determine_service_type(service_name)
            suggested_ruleset = self.PARAMETER_RULESETS.get(service_type)
            
            # Try to get available rulesets from API
            try:
                available_rulesets = await self.checkmk.list_rulesets()
                matching_rulesets = []
                
                # Look for rulesets that might match this service
                service_lower = service_name.lower()
                for ruleset_info in available_rulesets:
                    ruleset_name = ruleset_info.get('name', '').lower()
                    ruleset_title = ruleset_info.get('title', '').lower()
                    
                    if (service_type in ruleset_name or 
                        service_type in ruleset_title or
                        any(keyword in ruleset_name for keyword in service_lower.split())):
                        matching_rulesets.append(ruleset_info)
                
                return {
                    'service_name': service_name,
                    'detected_type': service_type,
                    'suggested_ruleset': suggested_ruleset,
                    'matching_rulesets': matching_rulesets,
                    'total_available_rulesets': len(available_rulesets)
                }
                
            except Exception as e:
                self.logger.warning(f"Could not retrieve available rulesets: {e}")
                return {
                    'service_name': service_name,
                    'detected_type': service_type,
                    'suggested_ruleset': suggested_ruleset,
                    'matching_rulesets': [],
                    'error': str(e)
                }
        
        return await self._execute_with_error_handling(_discover_ruleset_operation, f"discover_ruleset_{service_name}")
    
    async def list_parameter_rules(
        self,
        host_name: Optional[str] = None,
        service_name: Optional[str] = None,
        ruleset: Optional[str] = None
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        List parameter rules with optional filtering.
        
        Args:
            host_name: Optional host name filter
            service_name: Optional service name filter
            ruleset: Optional ruleset filter
            
        Returns:
            ServiceResult containing list of matching rules
        """
        async def _list_rules_operation():
            # Get all rules (or filtered by ruleset)
            if ruleset:
                rules = await self.checkmk.list_rules(ruleset_name=ruleset)
            else:
                rules = await self.checkmk.list_rules()
            
            # Apply additional filters
            filtered_rules = []
            for rule in rules:
                # Check if rule matches our filters
                if self._rule_matches_filters(rule, host_name, service_name):
                    filtered_rules.append(rule)
            
            return filtered_rules
        
        return await self._execute_with_error_handling(_list_rules_operation, "list_parameter_rules")
    
    def _determine_service_type(self, service_name: str) -> str:
        """Determine service type from service name."""
        service_lower = service_name.lower()
        
        # Check for exact matches first
        for service_type in self.PARAMETER_RULESETS.keys():
            if service_type in service_lower:
                return service_type
        
        # Check for partial matches and common variations
        if any(keyword in service_lower for keyword in ['cpu', 'processor', 'load']):
            return 'cpu'
        elif any(keyword in service_lower for keyword in ['mem', 'ram', 'swap']):
            return 'memory'
        elif any(keyword in service_lower for keyword in ['disk', 'filesystem', 'df', 'mount', 'fs']):
            return 'disk'
        elif any(keyword in service_lower for keyword in ['network', 'interface', 'eth', 'bond']):
            return 'network'
        elif any(keyword in service_lower for keyword in ['ping', 'ssh', 'tcp', 'http', 'connect']):
            return 'network'
        else:
            return 'unknown'
    
    def _rule_matches_filters(
        self, 
        rule: Dict[str, Any], 
        host_name: Optional[str], 
        service_name: Optional[str]
    ) -> bool:
        """Check if a rule matches the given filters."""
        conditions = rule.get('conditions', {})
        
        # Check host filter
        if host_name:
            rule_hosts = conditions.get('host_name', [])
            if rule_hosts and host_name not in rule_hosts:
                # Check for pattern matches
                if not any(self._pattern_matches(pattern, host_name) for pattern in rule_hosts):
                    return False
        
        # Check service filter
        if service_name:
            rule_services = conditions.get('service_description', [])
            if rule_services and service_name not in rule_services:
                # Check for pattern matches
                if not any(self._pattern_matches(pattern, service_name) for pattern in rule_services):
                    return False
        
        return True
    
    def _pattern_matches(self, pattern: str, text: str) -> bool:
        """Simple pattern matching (supports * wildcard)."""
        if '*' not in pattern:
            return pattern == text
        
        # Convert shell-style pattern to regex-like matching
        import fnmatch
        return fnmatch.fnmatch(text, pattern)