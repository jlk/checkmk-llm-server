"""Parameter service - core business logic for service parameter management."""

import json
import logging
import re
import fnmatch
from typing import Optional, Dict, Any, List, Union, Tuple
from dataclasses import dataclass

from .base import BaseService, ServiceResult
from .models.services import ServiceParameterResult
from .handlers import get_handler_registry, HandlerResult, ValidationSeverity
from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkAPIError
from ..config import AppConfig


@dataclass
class ValidationResult:
    """Result of parameter validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    normalized_parameters: Optional[Dict[str, Any]] = None


@dataclass
class BulkOperationResult:
    """Result of bulk parameter operations."""
    total_operations: int
    successful_operations: int
    failed_operations: int
    results: List[Dict[str, Any]]
    errors: List[str]


@dataclass 
class RuleSearchFilter:
    """Filter criteria for rule search operations."""
    host_patterns: Optional[List[str]] = None
    service_patterns: Optional[List[str]] = None
    parameter_filters: Optional[Dict[str, Any]] = None
    rule_properties: Optional[Dict[str, Any]] = None
    rulesets: Optional[List[str]] = None
    enabled_only: bool = True


class ParameterService(BaseService):
    """Core service parameter management service - presentation agnostic."""
    
    # Comprehensive service parameter rulesets mapping
    PARAMETER_RULESETS = {
        # Core system monitoring
        'cpu': 'checkgroup_parameters:cpu_utilization',
        'cpu_load': 'checkgroup_parameters:cpu_load',
        'memory': 'checkgroup_parameters:memory_linux',
        'disk': 'checkgroup_parameters:filesystem',
        'filesystem': 'checkgroup_parameters:filesystem',
        'network': 'checkgroup_parameters:if',
        'interface': 'checkgroup_parameters:if',
        'load': 'checkgroup_parameters:cpu_load',
        'swap': 'checkgroup_parameters:memory_linux',
        
        # Environmental monitoring
        'temperature': 'checkgroup_parameters:temperature',
        'temp': 'checkgroup_parameters:temperature',
        'humidity': 'checkgroup_parameters:humidity',
        'power': 'checkgroup_parameters:ups_power',
        'voltage': 'checkgroup_parameters:voltage',
        'current': 'checkgroup_parameters:current',
        'airflow': 'checkgroup_parameters:airflow',
        'fan': 'checkgroup_parameters:fan',
        'fanspeed': 'checkgroup_parameters:fan',
        
        # Hardware monitoring
        'smart': 'checkgroup_parameters:disk_smart',
        'raid': 'checkgroup_parameters:raid',
        'ipmi': 'checkgroup_parameters:ipmi',
        'ipmi_sensors': 'checkgroup_parameters:ipmi_sensors',
        'hw_temperature': 'checkgroup_parameters:hw_temperature',
        'hw_fans': 'checkgroup_parameters:hw_fans',
        'hw_psu': 'checkgroup_parameters:hw_psu',
        
        # Database monitoring
        'oracle_tablespace': 'checkgroup_parameters:oracle_tablespaces',
        'oracle': 'checkgroup_parameters:oracle_instance',
        'mssql': 'checkgroup_parameters:mssql_counters',
        'mysql': 'checkgroup_parameters:mysql_connections',
        'postgres': 'checkgroup_parameters:postgres_sessions',
        'mongodb': 'checkgroup_parameters:mongodb_collections',
        
        # Application monitoring
        'jvm': 'checkgroup_parameters:jvm_memory',
        'apache': 'checkgroup_parameters:apache_status',
        'nginx': 'checkgroup_parameters:nginx_status',
        'docker': 'checkgroup_parameters:docker_container_status',
        'k8s': 'checkgroup_parameters:k8s_resources',
        'elasticsearch': 'checkgroup_parameters:elasticsearch_cluster',
        
        # Network services
        'tcp': 'checkgroup_parameters:tcp_connections',
        'http': 'checkgroup_parameters:http',
        'https': 'checkgroup_parameters:https',
        'dns': 'checkgroup_parameters:dns',
        'smtp': 'checkgroup_parameters:smtp',
        'ssh': 'checkgroup_parameters:ssh',
        'ssl': 'checkgroup_parameters:ssl_certificates',
        'certificate': 'checkgroup_parameters:ssl_certificates',
        
        # Storage monitoring
        'nfs': 'checkgroup_parameters:nfs_mounts',
        'ceph': 'checkgroup_parameters:ceph_status',
        'netapp': 'checkgroup_parameters:netapp_volumes',
        'emc': 'checkgroup_parameters:emc_storage',
        
        # Virtualization
        'vmware': 'checkgroup_parameters:vmware_snapshots',
        'vm': 'checkgroup_parameters:vm_resources',
        'hyperv': 'checkgroup_parameters:hyperv_vms',
        
        # Custom/local checks
        'custom': 'checkgroup_parameters:custom_checks',
        'local': 'checkgroup_parameters:local',
        'mrpe': 'checkgroup_parameters:mrpe',
        
        # Windows specific
        'windows_service': 'checkgroup_parameters:windows_services',
        'windows_updates': 'checkgroup_parameters:windows_updates',
        'eventlog': 'checkgroup_parameters:windows_eventlog',
        
        # Process monitoring
        'process': 'checkgroup_parameters:processes',
        'service': 'checkgroup_parameters:services',
        'systemd': 'checkgroup_parameters:systemd_services',
        
        # Log monitoring
        'logwatch': 'checkgroup_parameters:logwatch',
        'logfile': 'checkgroup_parameters:logfile',
        
        # Backup monitoring
        'backup': 'checkgroup_parameters:backup_jobs',
        'bacula': 'checkgroup_parameters:bacula_jobs',
        'veeam': 'checkgroup_parameters:veeam_jobs'
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
        },
        # Temperature monitoring defaults
        'temperature': {
            'levels': (70.0, 80.0),  # Default temperature thresholds in Celsius
            'levels_lower': (5.0, 0.0),  # Lower temperature thresholds
            'device_levels_handling': 'worst',  # How to handle multiple sensors
            'trend_compute': {
                'period': 30,  # Minutes
                'trend_levels': (5.0, 10.0),  # Temperature rise per period
                'trend_levels_lower': (5.0, 10.0)  # Temperature drop per period
            },
            'output_unit': 'c'  # Celsius by default
        },
        # Hardware-specific temperature defaults
        'hw_temperature': {
            'cpu': {
                'levels': (75.0, 85.0),  # CPU temperature thresholds
                'levels_lower': (5.0, 0.0)
            },
            'ambient': {
                'levels': (40.0, 45.0),  # Ambient temperature thresholds
                'levels_lower': (10.0, 5.0)
            },
            'disk': {
                'levels': (50.0, 60.0),  # Disk temperature thresholds
                'levels_lower': (5.0, 0.0)
            }
        },
        # Environmental monitoring
        'humidity': {
            'levels': (60.0, 70.0),  # Upper humidity thresholds
            'levels_lower': (30.0, 20.0)  # Lower humidity thresholds
        },
        'voltage': {
            'levels_upper': (13.0, 14.0),  # Upper voltage thresholds
            'levels_lower': (11.0, 10.0)  # Lower voltage thresholds
        },
        'fan': {
            'levels_lower': (2000, 1000),  # Lower RPM thresholds
            'levels': (8000, 10000)  # Upper RPM thresholds
        },
        # Database monitoring
        'oracle_tablespaces': {
            'levels': (80.0, 90.0),  # % used
            'magic_normsize': 100,  # GB
            'magic': 0.9
        },
        'mysql_connections': {
            'levels': (80.0, 90.0)  # % of max connections
        },
        # Custom checks
        'custom_checks': {
            'levels': (0, 0),  # Default: no thresholds
            'perfdata': True,
            'inventory': 'always'
        },
        # Process monitoring
        'processes': {
            'levels': (100, 200, 300, 400),  # Warning/critical min/max
            'cpu_rescale_max': 100.0,
            'match': 'exact'
        },
        # Network services
        'tcp_connections': {
            'levels': (80, 100)  # Number of connections
        },
        'http': {
            'response_time': (1.0, 2.0),  # Response time in seconds
            'timeout': 10.0
        },
        'ssl_certificates': {
            'age': (30, 7)  # Days before expiry
        }
    }
    
    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        super().__init__(checkmk_client, config)
        self.logger = logging.getLogger(__name__)
        self.handler_registry = get_handler_registry()
    
    async def get_default_parameters(self, service_type: str, context: Optional[Dict[str, Any]] = None) -> ServiceResult[Dict[str, Any]]:
        """
        Get default parameters for a service type.
        
        Args:
            service_type: Type of service (cpu, memory, disk, etc.)
            context: Optional context for specialized handlers
            
        Returns:
            ServiceResult containing default parameters
        """
        async def _get_defaults_operation():
            service_type_lower = service_type.lower()
            
            # Try specialized handlers first
            handlers = self.handler_registry.get_handlers_for_service(service_type, limit=1)
            if handlers:
                handler = handlers[0]
                try:
                    handler_result = handler.get_default_parameters(service_type, context)
                    if handler_result.success:
                        return {
                            'service_type': service_type,
                            'parameter_set': f'{handler.name}_specialized',
                            'parameters': handler_result.parameters,
                            'ruleset': self.PARAMETER_RULESETS.get(service_type_lower),
                            'handler_used': handler.name,
                            'handler_messages': [msg.message for msg in handler_result.validation_messages],
                            'message': f'Using specialized {handler.name} handler for {service_type}'
                        }
                except Exception as e:
                    self.logger.warning(f"Handler {handler.name} failed for service {service_type}: {e}")
            
            # Fall back to built-in defaults
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
            
            # If no direct mapping, try dynamic discovery
            if not ruleset:
                discovery_result = await self.discover_ruleset_dynamic(service_name)
                if discovery_result.success and discovery_result.data:
                    ruleset = discovery_result.data.get('recommended_ruleset')
                    if not ruleset:
                        # If we can't determine the ruleset, return default info
                        return ServiceParameterResult(
                            host_name=host_name,
                            service_name=service_name,
                            success=True,
                            message=f"Cannot determine parameter ruleset for service: {service_name}",
                            effective_parameters={},
                            ruleset=None,
                            warnings=[f"No matching ruleset found. Discovered options: {discovery_result.data.get('discovered_rulesets', [])}"]
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
        rule_comment: Optional[str] = None,
        rule_properties: Optional[Dict[str, Any]] = None
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
            
            # If no direct mapping, try dynamic discovery
            if not ruleset:
                discovery_result = await self.discover_ruleset_dynamic(service_name)
                if discovery_result.success and discovery_result.data:
                    ruleset = discovery_result.data.get('recommended_ruleset')
                    if not ruleset:
                        discovered = discovery_result.data.get('discovered_rulesets', [])
                        raise ValueError(
                            f"Cannot determine parameter ruleset for service: {service_name}. "
                            f"Discovered options: {[d['ruleset'] for d in discovered[:3]]}"
                        )
            
            # Validate parameters before creating rule
            validation_result = await self.validate_parameters(ruleset, parameters)
            if validation_result.success:
                validation = validation_result.data
                if not validation.is_valid:
                    raise ValueError(
                        f"Parameter validation failed: {'; '.join(validation.errors)}"
                    )
                
                # Use normalized parameters if available
                validated_params = validation.normalized_parameters or parameters
                
                # Log warnings if any
                if validation.warnings:
                    for warning in validation.warnings:
                        self.logger.warning(f"Parameter warning: {warning}")
            else:
                # If validation service fails, continue with original parameters
                self.logger.warning(f"Could not validate parameters: {validation_result.error}")
                validated_params = parameters
            
            # Prepare rule data
            properties = rule_properties or {}
            if 'comment' not in properties:
                properties['comment'] = rule_comment or f"Parameter override for {host_name}/{service_name}"
            if 'disabled' not in properties:
                properties['disabled'] = False
            
            # Extract folder from properties (required as positional argument)
            folder = properties.pop('folder', '/')  # Default to root folder if not specified
            
            # Convert parameters to JSON string as required by the API
            value_raw = json.dumps(validated_params)
                
            rule_data = {
                'ruleset': ruleset,
                'folder': folder,
                'value_raw': value_raw,
                'conditions': {
                    'host_name': [host_name],
                    'service_description': [service_name]
                },
                'properties': properties
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
    
    async def discover_ruleset_dynamic(self, service_name: str) -> ServiceResult[Dict[str, Any]]:
        """
        Dynamically discover the appropriate ruleset for any service type.
        
        This method:
        1. Tries exact mapping from PARAMETER_RULESETS
        2. Performs fuzzy matching on service name
        3. Queries API for all rulesets and finds best match
        4. Uses service check plugin name if available
        
        Args:
            service_name: Service name to analyze
            
        Returns:
            ServiceResult containing discovered ruleset information
        """
        async def _dynamic_discovery_operation():
            service_name_lower = service_name.lower()
            results = {
                'service_name': service_name,
                'discovered_rulesets': [],
                'recommended_ruleset': None,
                'confidence': 'low'
            }
            
            # Step 1: Try exact mapping first
            service_type = self._determine_service_type(service_name)
            if service_type != 'unknown':
                direct_ruleset = self.PARAMETER_RULESETS.get(service_type)
                if direct_ruleset:
                    results['discovered_rulesets'].append({
                        'ruleset': direct_ruleset,
                        'match_type': 'direct_mapping',
                        'confidence': 'high'
                    })
                    results['recommended_ruleset'] = direct_ruleset
                    results['confidence'] = 'high'
            
            # Step 2: Get all available rulesets from API
            try:
                all_rulesets = await self.checkmk.list_rulesets()
                
                # Step 3: Fuzzy match against service name
                service_words = set(service_name_lower.split())
                service_words.update(service_name_lower.split('_'))
                service_words.update(service_name_lower.split('-'))
                
                for ruleset_info in all_rulesets:
                    ruleset_id = ruleset_info.get('id', '')
                    ruleset_title = ruleset_info.get('title', '').lower()
                    
                    # Skip non-checkgroup_parameters rulesets
                    if not ruleset_id.startswith('checkgroup_parameters:'):
                        continue
                    
                    # Calculate match score
                    match_score = 0
                    match_reasons = []
                    
                    # Check for exact substring matches
                    ruleset_name = ruleset_id.split(':', 1)[-1]
                    if service_type in ruleset_name:
                        match_score += 10
                        match_reasons.append(f"service type '{service_type}' in ruleset name")
                    
                    # Check for word matches
                    ruleset_words = set(ruleset_name.split('_'))
                    ruleset_words.update(ruleset_title.split())
                    common_words = service_words.intersection(ruleset_words)
                    if common_words:
                        match_score += len(common_words) * 3
                        match_reasons.append(f"common words: {', '.join(common_words)}")
                    
                    # Special cases
                    if 'temperature' in service_name_lower and 'temp' in ruleset_name:
                        match_score += 8
                        match_reasons.append("temperature match")
                    elif 'cpu' in service_name_lower and 'cpu' in ruleset_name:
                        match_score += 8
                        match_reasons.append("cpu match")
                    elif 'memory' in service_name_lower and 'mem' in ruleset_name:
                        match_score += 8
                        match_reasons.append("memory match")
                    
                    if match_score > 0:
                        results['discovered_rulesets'].append({
                            'ruleset': ruleset_id,
                            'title': ruleset_info.get('title', ''),
                            'match_type': 'fuzzy_match',
                            'match_score': match_score,
                            'match_reasons': match_reasons,
                            'confidence': 'high' if match_score >= 10 else 'medium' if match_score >= 5 else 'low'
                        })
                
                # Sort by match score and pick the best
                if results['discovered_rulesets']:
                    results['discovered_rulesets'].sort(
                        key=lambda x: x.get('match_score', 0), 
                        reverse=True
                    )
                    
                    best_match = results['discovered_rulesets'][0]
                    if not results['recommended_ruleset'] or best_match.get('match_score', 0) > 5:
                        results['recommended_ruleset'] = best_match['ruleset']
                        results['confidence'] = best_match['confidence']
                
                # Step 4: Try to extract check plugin name from service
                # Many services follow pattern: "Check_MK <plugin>" or "<plugin> <details>"
                if not results['recommended_ruleset']:
                    check_patterns = [
                        r'^Check_MK\s+(\w+)',
                        r'^(\w+)\s+',
                        r'^(\w+)$'
                    ]
                    import re
                    for pattern in check_patterns:
                        match = re.match(pattern, service_name)
                        if match:
                            potential_plugin = match.group(1).lower()
                            # Look for ruleset matching this plugin name
                            for ruleset_info in all_rulesets:
                                ruleset_id = ruleset_info.get('id', '')
                                if f"checkgroup_parameters:{potential_plugin}" == ruleset_id:
                                    results['discovered_rulesets'].append({
                                        'ruleset': ruleset_id,
                                        'match_type': 'plugin_name_match',
                                        'confidence': 'medium'
                                    })
                                    results['recommended_ruleset'] = ruleset_id
                                    results['confidence'] = 'medium'
                                    break
                
                results['total_rulesets_checked'] = len(all_rulesets)
                
            except Exception as e:
                self.logger.warning(f"Could not query rulesets from API: {e}")
                results['error'] = str(e)
            
            return results
        
        return await self._execute_with_error_handling(_dynamic_discovery_operation, f"discover_ruleset_dynamic_{service_name}")
    
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
                # Get all parameter rules since list_rules requires a ruleset_name
                try:
                    all_rulesets_response = await self.checkmk.list_rulesets()
                    all_rulesets = all_rulesets_response.get('value', []) if isinstance(all_rulesets_response, dict) else all_rulesets_response
                    
                    # Get all parameter-related rulesets
                    parameter_rulesets = [
                        ruleset.get('id', '') for ruleset in all_rulesets
                        if ruleset.get('id', '').startswith('checkgroup_parameters:')
                    ]
                    
                    # Collect rules from all parameter rulesets
                    rules = []
                    for ruleset_name in parameter_rulesets:
                        try:
                            ruleset_rules = await self.checkmk.list_rules(ruleset_name)
                            rules.extend(ruleset_rules)
                        except CheckmkAPIError as e:
                            self.logger.warning(f"Could not retrieve rules for ruleset {ruleset_name}: {e}")
                
                except CheckmkAPIError as e:
                    self.logger.warning(f"Could not retrieve rulesets list: {e}")
                    # Return empty list if we can't get rulesets
                    rules = []
            
            # Apply additional filters
            filtered_rules = []
            for rule in rules:
                # Check if rule matches our filters
                if self._rule_matches_filters(rule, host_name, service_name):
                    filtered_rules.append(rule)
            
            return filtered_rules
        
        return await self._execute_with_error_handling(_list_rules_operation, "list_parameter_rules")
    
    async def get_parameter_schema(self, ruleset_name: str) -> ServiceResult[Dict[str, Any]]:
        """
        Get parameter schema and metadata for a specific ruleset.
        
        Args:
            ruleset_name: Name of the ruleset (e.g., 'checkgroup_parameters:temperature')
            
        Returns:
            ServiceResult containing schema information and parameter definitions
        """
        async def _get_schema_operation():
            try:
                # Get ruleset info from API
                ruleset_info = await self.checkmk.get_ruleset_info(ruleset_name)
                
                # Extract schema information
                schema_data = {
                    'ruleset': ruleset_name,
                    'title': ruleset_info.get('title', ''),
                    'help': ruleset_info.get('help', ''),
                    'item_type': ruleset_info.get('item_type'),
                    'item_spec': ruleset_info.get('item_spec'),
                    'parameter_definitions': {},
                    'default_value': None,
                    'value_mode': ruleset_info.get('value_mode', 'tuple')
                }
                
                # Parse parameter valuespec if available
                valuespec = ruleset_info.get('valuespec', {})
                if valuespec:
                    schema_data['parameter_definitions'] = self._parse_valuespec(valuespec)
                    schema_data['default_value'] = valuespec.get('default_value')
                
                # Add examples if we have them
                if ruleset_name in self.DEFAULT_PARAMETERS:
                    schema_data['examples'] = self.DEFAULT_PARAMETERS[ruleset_name]
                
                return schema_data
                
            except CheckmkAPIError as e:
                self.logger.warning(f"Could not retrieve schema for ruleset {ruleset_name}: {e}")
                # Return basic schema based on our defaults if API fails
                if ruleset_name.endswith(':temperature'):
                    return {
                        'ruleset': ruleset_name,
                        'title': 'Temperature monitoring',
                        'parameter_definitions': {
                            'levels': {
                                'type': 'tuple',
                                'elements': ['float', 'float'],
                                'help': 'Upper warning and critical temperature thresholds'
                            },
                            'levels_lower': {
                                'type': 'tuple',
                                'elements': ['float', 'float'],
                                'help': 'Lower warning and critical temperature thresholds'
                            },
                            'device_levels_handling': {
                                'type': 'choice',
                                'choices': ['worst', 'best', 'average'],
                                'help': 'How to handle multiple temperature sensors'
                            },
                            'output_unit': {
                                'type': 'choice',
                                'choices': ['c', 'f', 'k'],
                                'help': 'Temperature output unit'
                            }
                        },
                        'examples': self.DEFAULT_PARAMETERS.get('temperature', {})
                    }
                else:
                    raise
        
        return await self._execute_with_error_handling(_get_schema_operation, f"get_parameter_schema_{ruleset_name}")
    
    def _parse_valuespec(self, valuespec: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Checkmk valuespec into parameter definitions."""
        definitions = {}
        
        # Handle different valuespec types
        vs_type = valuespec.get('type', '')
        
        if vs_type == 'dictionary':
            # Dictionary valuespec with elements
            elements = valuespec.get('elements', [])
            for element in elements:
                param_name = element.get('name')
                if param_name:
                    definitions[param_name] = {
                        'type': element.get('valuespec', {}).get('type', 'unknown'),
                        'title': element.get('title', ''),
                        'help': element.get('help', ''),
                        'required': element.get('required', False),
                        'default': element.get('valuespec', {}).get('default_value')
                    }
                    
        elif vs_type == 'tuple':
            # Tuple valuespec (common for thresholds)
            elements = valuespec.get('elements', [])
            definitions['_value'] = {
                'type': 'tuple',
                'elements': [e.get('type', 'unknown') for e in elements],
                'help': valuespec.get('help', ''),
                'title': valuespec.get('title', '')
            }
            
        elif vs_type in ['integer', 'float', 'percentage']:
            # Simple numeric types
            definitions['_value'] = {
                'type': vs_type,
                'unit': valuespec.get('unit', ''),
                'help': valuespec.get('help', ''),
                'title': valuespec.get('title', ''),
                'minvalue': valuespec.get('minvalue'),
                'maxvalue': valuespec.get('maxvalue')
            }
            
        else:
            # Generic handling
            definitions['_value'] = {
                'type': vs_type or 'unknown',
                'help': valuespec.get('help', ''),
                'title': valuespec.get('title', '')
            }
        
        return definitions
    
    async def validate_parameters(
        self,
        ruleset: str,
        parameters: Dict[str, Any],
        service_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[ValidationResult]:
        """
        Validate parameters against a ruleset schema.
        
        Args:
            ruleset: The ruleset name
            parameters: Parameters to validate
            service_name: Optional service name for handler selection
            context: Optional context for specialized validation
            
        Returns:
            ServiceResult containing validation result
        """
        async def _validate_operation():
            errors = []
            warnings = []
            normalized_params = parameters.copy()
            
            # Try specialized handlers first
            handler_used = None
            if service_name:
                handlers = self.handler_registry.get_handlers_for_service(service_name, limit=1)
                if not handlers:
                    handlers = self.handler_registry.get_handlers_for_ruleset(ruleset, limit=1)
                
                if handlers:
                    handler = handlers[0]
                    try:
                        handler_result = handler.validate_parameters(parameters, service_name or ruleset, context)
                        if handler_result.success:
                            # Convert handler result to ValidationResult format
                            handler_errors = [msg.message for msg in handler_result.errors]
                            handler_warnings = [msg.message for msg in handler_result.warnings]
                            
                            return ValidationResult(
                                is_valid=handler_result.is_valid,
                                errors=handler_errors,
                                warnings=handler_warnings,
                                normalized_parameters=handler_result.normalized_parameters
                            )
                        else:
                            warnings.append(f"Handler {handler.name} validation failed: {handler_result.error}")
                            handler_used = handler.name
                    except Exception as e:
                        self.logger.warning(f"Handler {handler.name} validation error: {e}")
                        warnings.append(f"Handler {handler.name} error: {str(e)}")
            
            # Fall back to schema-based validation
            schema_result = await self.get_parameter_schema(ruleset)
            if not schema_result.success:
                # If we can't get schema, do basic validation
                basic_validation = self._basic_parameter_validation(ruleset, parameters)
                if handler_used:
                    basic_validation.warnings.append(f"Used fallback validation (handler: {handler_used})")
                return basic_validation
            
            schema = schema_result.data
            param_defs = schema.get('parameter_definitions', {})
            
            # Validate based on schema
            if param_defs:
                # Dictionary-style parameters
                for param_name, param_def in param_defs.items():
                    if param_name == '_value':
                        # Special case for simple value parameters
                        validation = self._validate_parameter_value(
                            parameters, param_def, ruleset
                        )
                        errors.extend(validation.get('errors', []))
                        warnings.extend(validation.get('warnings', []))
                        if validation.get('normalized_value') is not None:
                            normalized_params = validation['normalized_value']
                    else:
                        # Named parameters
                        if param_def.get('required', False) and param_name not in parameters:
                            errors.append(f"Required parameter '{param_name}' is missing")
                        
                        if param_name in parameters:
                            validation = self._validate_parameter_value(
                                parameters[param_name], param_def, param_name
                            )
                            errors.extend(validation.get('errors', []))
                            warnings.extend(validation.get('warnings', []))
                            if validation.get('normalized_value') is not None:
                                normalized_params[param_name] = validation['normalized_value']
            
            # Special validation for known parameter types
            if 'temperature' in ruleset:
                temp_validation = self._validate_temperature_parameters(normalized_params)
                errors.extend(temp_validation.get('errors', []))
                warnings.extend(temp_validation.get('warnings', []))
            
            elif 'filesystem' in ruleset:
                fs_validation = self._validate_filesystem_parameters(normalized_params)
                errors.extend(fs_validation.get('errors', []))
                warnings.extend(fs_validation.get('warnings', []))
            
            # Add warnings for unknown parameters
            if param_defs:
                known_params = set(param_defs.keys())
                if '_value' not in known_params:
                    # Only check for unknown params in dictionary-style parameters
                    for param in parameters:
                        if param not in known_params:
                            warnings.append(f"Unknown parameter '{param}' for ruleset {ruleset}")
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                normalized_parameters=normalized_params if len(errors) == 0 else None
            )
        
        return await self._execute_with_error_handling(_validate_operation, f"validate_parameters_{ruleset}")
    
    def _validate_parameter_value(
        self,
        value: Any,
        param_def: Dict[str, Any],
        param_name: str
    ) -> Dict[str, Any]:
        """Validate a single parameter value against its definition."""
        errors = []
        warnings = []
        normalized_value = value
        
        param_type = param_def.get('type', 'unknown')
        
        if param_type == 'tuple':
            # Validate tuple parameters (common for thresholds)
            if not isinstance(value, (list, tuple)):
                errors.append(f"Parameter '{param_name}' must be a tuple/list, got {type(value).__name__}")
            else:
                elements = param_def.get('elements', [])
                if elements and len(value) != len(elements):
                    errors.append(f"Parameter '{param_name}' expects {len(elements)} values, got {len(value)}")
                else:
                    # Validate each element
                    normalized_tuple = []
                    for i, (val, expected_type) in enumerate(zip(value, elements)):
                        if expected_type in ['float', 'percentage']:
                            try:
                                normalized_tuple.append(float(val))
                            except (TypeError, ValueError):
                                errors.append(f"Element {i} of '{param_name}' must be a number")
                        elif expected_type == 'integer':
                            try:
                                normalized_tuple.append(int(val))
                            except (TypeError, ValueError):
                                errors.append(f"Element {i} of '{param_name}' must be an integer")
                        else:
                            normalized_tuple.append(val)
                    
                    if not errors:
                        normalized_value = tuple(normalized_tuple)
        
        elif param_type == 'choice':
            # Validate choice parameters
            choices = param_def.get('choices', [])
            if choices and value not in choices:
                errors.append(f"Parameter '{param_name}' must be one of {choices}, got '{value}'")
        
        elif param_type in ['integer', 'float', 'percentage']:
            # Validate numeric parameters
            try:
                if param_type == 'integer':
                    normalized_value = int(value)
                else:
                    normalized_value = float(value)
                
                # Check bounds
                if 'minvalue' in param_def and normalized_value < param_def['minvalue']:
                    errors.append(f"Parameter '{param_name}' must be >= {param_def['minvalue']}")
                if 'maxvalue' in param_def and normalized_value > param_def['maxvalue']:
                    errors.append(f"Parameter '{param_name}' must be <= {param_def['maxvalue']}")
                    
            except (TypeError, ValueError):
                errors.append(f"Parameter '{param_name}' must be a {'n integer' if param_type == 'integer' else ' number'}")
        
        elif param_type == 'boolean':
            # Validate boolean parameters
            if not isinstance(value, bool):
                # Try to normalize common boolean representations
                if str(value).lower() in ['true', '1', 'yes', 'on']:
                    normalized_value = True
                elif str(value).lower() in ['false', '0', 'no', 'off']:
                    normalized_value = False
                else:
                    errors.append(f"Parameter '{param_name}' must be a boolean")
        
        return {
            'errors': errors,
            'warnings': warnings,
            'normalized_value': normalized_value
        }
    
    def _validate_temperature_parameters(self, params: Dict[str, Any]) -> Dict[str, List[str]]:
        """Special validation for temperature parameters."""
        errors = []
        warnings = []
        
        # Validate temperature thresholds
        if 'levels' in params:
            warn, crit = params['levels']
            if warn >= crit:
                errors.append("Temperature warning threshold must be less than critical threshold")
            if crit > 100 and params.get('output_unit', 'c') == 'c':
                warnings.append(f"Critical temperature {crit}°C seems unusually high")
        
        if 'levels_lower' in params:
            warn, crit = params['levels_lower']
            if warn <= crit:
                errors.append("Lower temperature warning threshold must be greater than critical threshold")
            if crit < -50 and params.get('output_unit', 'c') == 'c':
                warnings.append(f"Critical lower temperature {crit}°C seems unusually low")
        
        # Validate trend parameters
        if 'trend_compute' in params:
            trend = params['trend_compute']
            if isinstance(trend, dict):
                if 'period' in trend and trend['period'] <= 0:
                    errors.append("Trend period must be positive")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_filesystem_parameters(self, params: Dict[str, Any]) -> Dict[str, List[str]]:
        """Special validation for filesystem parameters."""
        errors = []
        warnings = []
        
        # Validate filesystem thresholds
        if 'levels' in params:
            warn, crit = params['levels']
            if warn >= crit:
                errors.append("Filesystem warning threshold must be less than critical threshold")
            if warn > 100 or crit > 100:
                errors.append("Filesystem percentage thresholds cannot exceed 100%")
        
        if 'magic_normsize' in params and params['magic_normsize'] <= 0:
            errors.append("Magic normsize must be positive")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _basic_parameter_validation(self, ruleset: str, parameters: Dict[str, Any]) -> ValidationResult:
        """Basic parameter validation when schema is not available."""
        errors = []
        warnings = []
        
        # Basic validation for common patterns
        if 'levels' in parameters:
            if not isinstance(parameters['levels'], (list, tuple)) or len(parameters['levels']) != 2:
                errors.append("'levels' must be a tuple of (warning, critical) thresholds")
            else:
                try:
                    warn, crit = float(parameters['levels'][0]), float(parameters['levels'][1])
                    if warn >= crit:
                        errors.append("Warning threshold must be less than critical threshold")
                except (TypeError, ValueError):
                    errors.append("Threshold levels must be numeric")
        
        warnings.append(f"Could not retrieve schema for {ruleset}, using basic validation only")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_parameters=parameters if len(errors) == 0 else None
        )
    
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
        return fnmatch.fnmatch(text, pattern)
    
    async def update_parameter_rule(
        self,
        rule_id: str,
        parameters: Dict[str, Any],
        preserve_conditions: bool = True,
        rule_properties: Optional[Dict[str, Any]] = None,
        etag: Optional[str] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Update an existing parameter rule.
        
        Args:
            rule_id: ID of the rule to update
            parameters: New parameter values
            preserve_conditions: Whether to preserve existing conditions
            rule_properties: Optional rule properties to update
            etag: Optional etag for concurrent update handling
            
        Returns:
            ServiceResult containing update result
        """
        async def _update_rule_operation():
            # Validate parameters
            validation_errors = self._validate_required_params(
                {"rule_id": rule_id, "parameters": parameters},
                ["rule_id", "parameters"]
            )
            if validation_errors:
                raise ValueError(f"Validation errors: {', '.join(validation_errors)}")
            
            try:
                # Get existing rule to preserve conditions and properties
                existing_rule = await self.checkmk.get_rule(rule_id)
                
                # Validate etag if provided
                if etag and existing_rule.get('etag') != etag:
                    raise ValueError(
                        f"Rule has been modified by another user. "
                        f"Expected etag: {etag}, current etag: {existing_rule.get('etag')}"
                    )
                
                # Prepare update data
                update_data = {
                    'value_raw': parameters
                }
                
                # Preserve conditions if requested
                if preserve_conditions and 'conditions' in existing_rule:
                    update_data['conditions'] = existing_rule['conditions']
                
                # Handle rule properties
                if preserve_conditions and 'properties' in existing_rule:
                    properties = existing_rule['properties'].copy()
                    if rule_properties:
                        properties.update(rule_properties)
                    update_data['properties'] = properties
                elif rule_properties:
                    update_data['properties'] = rule_properties
                
                # Validate parameters against ruleset schema if possible
                ruleset = existing_rule.get('ruleset')
                if ruleset:
                    validation_result = await self.validate_parameters(ruleset, parameters)
                    if validation_result.success:
                        validation = validation_result.data
                        if not validation.is_valid:
                            raise ValueError(
                                f"Parameter validation failed: {'; '.join(validation.errors)}"
                            )
                        
                        # Use normalized parameters if available
                        if validation.normalized_parameters:
                            update_data['value_raw'] = validation.normalized_parameters
                        
                        # Log warnings
                        if validation.warnings:
                            for warning in validation.warnings:
                                self.logger.warning(f"Parameter warning: {warning}")
                
                # Update the rule
                updated_rule = await self.checkmk.update_rule(rule_id, **update_data)
                
                return {
                    'rule_id': rule_id,
                    'updated_rule': updated_rule,
                    'previous_parameters': existing_rule.get('value_raw', {}),
                    'new_parameters': parameters,
                    'preserved_conditions': preserve_conditions,
                    'message': f'Successfully updated rule {rule_id}'
                }
                
            except CheckmkAPIError as e:
                if 'not found' in str(e).lower():
                    raise ValueError(f"Rule {rule_id} not found")
                elif 'precondition failed' in str(e).lower():
                    raise ValueError(f"Rule {rule_id} has been modified by another user")
                else:
                    raise
        
        return await self._execute_with_error_handling(_update_rule_operation, f"update_parameter_rule_{rule_id}")
    
    async def find_parameter_rules(
        self,
        search_filter: RuleSearchFilter
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Find parameter rules with complex filtering.
        
        Args:
            search_filter: Filter criteria for finding rules
            
        Returns:
            ServiceResult containing matching rules
        """
        async def _find_rules_operation():
            all_rules = []
            
            # Get rules from specified rulesets or all rulesets
            if search_filter.rulesets:
                for ruleset in search_filter.rulesets:
                    try:
                        ruleset_rules = await self.checkmk.list_rules(ruleset_name=ruleset)
                        all_rules.extend(ruleset_rules)
                    except CheckmkAPIError as e:
                        self.logger.warning(f"Could not retrieve rules for ruleset {ruleset}: {e}")
            else:
                # Get all parameter rules (filter to checkgroup_parameters only)
                # Since list_rules requires a ruleset_name, we need to get all rulesets first
                try:
                    all_rulesets_response = await self.checkmk.list_rulesets()
                    all_rulesets = all_rulesets_response.get('value', []) if isinstance(all_rulesets_response, dict) else all_rulesets_response
                    
                    # Get all parameter-related rulesets
                    parameter_rulesets = [
                        ruleset.get('id', '') for ruleset in all_rulesets
                        if ruleset.get('id', '').startswith('checkgroup_parameters:')
                    ]
                    
                    # Collect rules from all parameter rulesets
                    all_rules = []
                    for ruleset_name in parameter_rulesets:
                        try:
                            ruleset_rules = await self.checkmk.list_rules(ruleset_name)
                            all_rules.extend(ruleset_rules)
                        except CheckmkAPIError as e:
                            self.logger.warning(f"Could not retrieve rules for ruleset {ruleset_name}: {e}")
                    
                except CheckmkAPIError as e:
                    self.logger.warning(f"Could not retrieve rulesets list: {e}")
                    # Fallback: try common parameter rulesets
                    common_parameter_rulesets = [
                        'checkgroup_parameters:cpu_utilization',
                        'checkgroup_parameters:memory_linux', 
                        'checkgroup_parameters:filesystem',
                        'checkgroup_parameters:if',
                        'checkgroup_parameters:temperature',
                        'checkgroup_parameters:disk_smart'
                    ]
                    all_rules = []
                    for ruleset_name in common_parameter_rulesets:
                        try:
                            ruleset_rules = await self.checkmk.list_rules(ruleset_name)
                            all_rules.extend(ruleset_rules)
                        except CheckmkAPIError as ruleset_error:
                            self.logger.debug(f"Ruleset {ruleset_name} not available: {ruleset_error}")
            
            # Apply filters
            filtered_rules = []
            for rule in all_rules:
                if self._rule_matches_search_filter(rule, search_filter):
                    filtered_rules.append(rule)
            
            return filtered_rules
        
        return await self._execute_with_error_handling(_find_rules_operation, "find_parameter_rules")
    
    async def set_bulk_parameters(
        self,
        operations: List[Dict[str, Any]],
        validate_all: bool = True,
        stop_on_error: bool = False
    ) -> ServiceResult[BulkOperationResult]:
        """
        Set parameters for multiple services in bulk.
        
        Args:
            operations: List of parameter operations, each containing:
                       {host_name, service_name, parameters, rule_properties}
            validate_all: Whether to validate all operations before executing
            stop_on_error: Whether to stop on first error
            
        Returns:
            ServiceResult containing bulk operation results
        """
        async def _bulk_operations():
            if validate_all:
                # Validate all operations first
                validation_errors = []
                for i, op in enumerate(operations):
                    # Basic validation
                    required_fields = ["host_name", "service_name", "parameters"]
                    missing_fields = [field for field in required_fields if field not in op]
                    if missing_fields:
                        validation_errors.append(f"Operation {i}: Missing fields: {missing_fields}")
                        continue
                    
                    # Try to determine ruleset and validate parameters
                    try:
                        service_type = self._determine_service_type(op["service_name"])
                        ruleset = self.PARAMETER_RULESETS.get(service_type)
                        
                        if not ruleset:
                            # Try dynamic discovery
                            discovery_result = await self.discover_ruleset_dynamic(op["service_name"])
                            if discovery_result.success and discovery_result.data:
                                ruleset = discovery_result.data.get('recommended_ruleset')
                        
                        if ruleset:
                            validation_result = await self.validate_parameters(ruleset, op["parameters"])
                            if validation_result.success and not validation_result.data.is_valid:
                                validation_errors.append(
                                    f"Operation {i} ({op['host_name']}/{op['service_name']}): "
                                    f"{'; '.join(validation_result.data.errors)}"
                                )
                    except Exception as e:
                        validation_errors.append(f"Operation {i}: Validation error: {str(e)}")
                
                if validation_errors:
                    raise ValueError(f"Bulk validation failed: {'; '.join(validation_errors)}")
            
            # Execute operations
            results = []
            successful = 0
            failed = 0
            errors = []
            
            for i, op in enumerate(operations):
                try:
                    result = await self.set_service_parameters(
                        host_name=op["host_name"],
                        service_name=op["service_name"],
                        parameters=op["parameters"],
                        rule_properties=op.get("rule_properties")
                    )
                    
                    if result.success:
                        successful += 1
                        results.append({
                            "operation_index": i,
                            "host_name": op["host_name"],
                            "service_name": op["service_name"],
                            "success": True,
                            "rule_id": result.data.rule_id,
                            "message": f"Success: {op['host_name']}/{op['service_name']}"
                        })
                    else:
                        failed += 1
                        error_msg = f"Operation {i} failed: {result.error}"
                        errors.append(error_msg)
                        results.append({
                            "operation_index": i,
                            "host_name": op["host_name"],
                            "service_name": op["service_name"],
                            "success": False,
                            "error": result.error,
                            "message": f"Failed: {op['host_name']}/{op['service_name']}"
                        })
                        
                        if stop_on_error:
                            break
                            
                except Exception as e:
                    failed += 1
                    error_msg = f"Operation {i} ({op['host_name']}/{op['service_name']}) exception: {str(e)}"
                    errors.append(error_msg)
                    results.append({
                        "operation_index": i,
                        "host_name": op["host_name"],
                        "service_name": op["service_name"],
                        "success": False,
                        "error": str(e),
                        "message": f"Error: {op['host_name']}/{op['service_name']}"
                    })
                    
                    if stop_on_error:
                        break
            
            return BulkOperationResult(
                total_operations=len(operations),
                successful_operations=successful,
                failed_operations=failed,
                results=results,
                errors=errors
            )
        
        return await self._execute_with_error_handling(_bulk_operations, "set_bulk_parameters")
    
    def _rule_matches_search_filter(self, rule: Dict[str, Any], search_filter: RuleSearchFilter) -> bool:
        """Check if a rule matches the search filter criteria."""
        # Check enabled status
        if search_filter.enabled_only:
            properties = rule.get('properties', {})
            if properties.get('disabled', False):
                return False
        
        conditions = rule.get('conditions', {})
        
        # Check host patterns
        if search_filter.host_patterns:
            rule_hosts = conditions.get('host_name', [])
            if not rule_hosts:
                return False  # Rule has no host conditions, skip
            
            # Check if any host pattern matches any rule host
            host_match = False
            for host_pattern in search_filter.host_patterns:
                for rule_host in rule_hosts:
                    if self._pattern_matches(rule_host, host_pattern) or self._pattern_matches(host_pattern, rule_host):
                        host_match = True
                        break
                if host_match:
                    break
            
            if not host_match:
                return False
        
        # Check service patterns
        if search_filter.service_patterns:
            rule_services = conditions.get('service_description', [])
            if not rule_services:
                return False  # Rule has no service conditions, skip
            
            # Check if any service pattern matches any rule service
            service_match = False
            for service_pattern in search_filter.service_patterns:
                for rule_service in rule_services:
                    if self._pattern_matches(rule_service, service_pattern) or self._pattern_matches(service_pattern, rule_service):
                        service_match = True
                        break
                if service_match:
                    break
            
            if not service_match:
                return False
        
        # Check parameter filters
        if search_filter.parameter_filters:
            rule_parameters = rule.get('value_raw', {})
            for param_key, expected_value in search_filter.parameter_filters.items():
                if param_key not in rule_parameters:
                    return False
                
                rule_value = rule_parameters[param_key]
                
                # Support different comparison types
                if isinstance(expected_value, dict) and 'operator' in expected_value:
                    op = expected_value['operator']
                    value = expected_value['value']
                    
                    if op == 'equals' and rule_value != value:
                        return False
                    elif op == 'contains' and str(value) not in str(rule_value):
                        return False
                    elif op == 'greater_than' and (not isinstance(rule_value, (int, float)) or rule_value <= value):
                        return False
                    elif op == 'less_than' and (not isinstance(rule_value, (int, float)) or rule_value >= value):
                        return False
                else:
                    # Direct equality check
                    if rule_value != expected_value:
                        return False
        
        # Check rule properties
        if search_filter.rule_properties:
            rule_props = rule.get('properties', {})
            for prop_key, expected_value in search_filter.rule_properties.items():
                if prop_key not in rule_props or rule_props[prop_key] != expected_value:
                    return False
        
        # Check rulesets (already filtered above, but double-check)
        if search_filter.rulesets:
            rule_ruleset = rule.get('ruleset')
            if rule_ruleset not in search_filter.rulesets:
                return False
        
        return True
    
    async def get_handler_info(self, service_name: str) -> ServiceResult[Dict[str, Any]]:
        """
        Get information about which handler can process a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            ServiceResult containing handler information
        """
        async def _get_handler_info_operation():
            handlers = self.handler_registry.get_handlers_for_service(service_name, limit=3)
            
            handler_info = {
                'service_name': service_name,
                'available_handlers': [],
                'best_handler': None,
                'handler_count': len(handlers)
            }
            
            for handler in handlers:
                info = {
                    'name': handler.name,
                    'description': getattr(handler, 'description', f'{handler.name} parameter handler'),
                    'service_patterns': handler.service_patterns,
                    'supported_rulesets': handler.supported_rulesets
                }
                handler_info['available_handlers'].append(info)
            
            if handlers:
                handler_info['best_handler'] = handlers[0].name
            
            return handler_info
        
        return await self._execute_with_error_handling(_get_handler_info_operation, f"get_handler_info_{service_name}")
    
    async def get_specialized_defaults(
        self, 
        service_name: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get specialized default parameters using handlers.
        
        Args:
            service_name: Name of the service
            context: Optional context for specialized defaults
            
        Returns:
            ServiceResult containing specialized defaults
        """
        async def _get_specialized_defaults_operation():
            handler = self.handler_registry.get_best_handler(service_name=service_name)
            
            if not handler:
                return {
                    'service_name': service_name,
                    'handler_used': None,
                    'parameters': {},
                    'message': f'No specialized handler found for service: {service_name}'
                }
            
            try:
                handler_result = handler.get_default_parameters(service_name, context)
                
                return {
                    'service_name': service_name,
                    'handler_used': handler.name,
                    'parameters': handler_result.parameters or {},
                    'handler_messages': [msg.message for msg in handler_result.validation_messages] if handler_result.validation_messages else [],
                    'success': handler_result.success,
                    'message': f'Generated specialized defaults using {handler.name} handler'
                }
            except Exception as e:
                self.logger.error(f"Handler {handler.name} failed for service {service_name}: {e}")
                return {
                    'service_name': service_name,
                    'handler_used': handler.name,
                    'parameters': {},
                    'error': str(e),
                    'message': f'Handler {handler.name} failed: {str(e)}'
                }
        
        return await self._execute_with_error_handling(_get_specialized_defaults_operation, f"get_specialized_defaults_{service_name}")
    
    async def validate_with_handler(
        self,
        service_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Validate parameters using specialized handlers.
        
        Args:
            service_name: Name of the service
            parameters: Parameters to validate
            context: Optional context for validation
            
        Returns:
            ServiceResult containing validation results
        """
        async def _validate_with_handler_operation():
            handler = self.handler_registry.get_best_handler(service_name=service_name)
            
            if not handler:
                return {
                    'service_name': service_name,
                    'handler_used': None,
                    'is_valid': False,
                    'errors': [f'No specialized handler found for service: {service_name}'],
                    'warnings': [],
                    'normalized_parameters': parameters
                }
            
            try:
                handler_result = handler.validate_parameters(parameters, service_name, context)
                
                return {
                    'service_name': service_name,
                    'handler_used': handler.name,
                    'is_valid': handler_result.is_valid,
                    'errors': [msg.message for msg in handler_result.errors],
                    'warnings': [msg.message for msg in handler_result.warnings],
                    'info_messages': [msg.message for msg in handler_result.validation_messages 
                                    if msg.severity == ValidationSeverity.INFO],
                    'normalized_parameters': handler_result.normalized_parameters or parameters,
                    'success': handler_result.success,
                    'suggestions': [msg.suggestion for msg in handler_result.validation_messages 
                                  if msg.suggestion] if handler_result.validation_messages else []
                }
            except Exception as e:
                self.logger.error(f"Handler {handler.name} validation failed for service {service_name}: {e}")
                return {
                    'service_name': service_name,
                    'handler_used': handler.name,
                    'is_valid': False,
                    'errors': [f'Handler validation failed: {str(e)}'],
                    'warnings': [],
                    'normalized_parameters': parameters,
                    'error': str(e)
                }
        
        return await self._execute_with_error_handling(_validate_with_handler_operation, f"validate_with_handler_{service_name}")
    
    async def get_parameter_suggestions(
        self,
        service_name: str,
        current_parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get parameter optimization suggestions using handlers.
        
        Args:
            service_name: Name of the service
            current_parameters: Current parameter values
            context: Optional context for suggestions
            
        Returns:
            ServiceResult containing parameter suggestions
        """
        async def _get_suggestions_operation():
            handler = self.handler_registry.get_best_handler(service_name=service_name)
            
            if not handler:
                return []
            
            try:
                suggestions = handler.suggest_parameters(service_name, current_parameters, context)
                
                # Enhance suggestions with additional metadata
                enhanced_suggestions = []
                for suggestion in suggestions:
                    enhanced_suggestion = suggestion.copy()
                    enhanced_suggestion['handler_name'] = handler.name
                    enhanced_suggestion['service_name'] = service_name
                    enhanced_suggestions.append(enhanced_suggestion)
                
                return enhanced_suggestions
            except Exception as e:
                self.logger.error(f"Handler {handler.name} suggestions failed for service {service_name}: {e}")
                return []
        
        return await self._execute_with_error_handling(_get_suggestions_operation, f"get_parameter_suggestions_{service_name}")
    
    async def list_available_handlers(self) -> ServiceResult[Dict[str, Any]]:
        """
        List all available parameter handlers.
        
        Returns:
            ServiceResult containing handler information
        """
        async def _list_handlers_operation():
            handlers_info = self.handler_registry.list_handlers(enabled_only=True)
            
            return {
                'total_handlers': len(handlers_info),
                'handlers': handlers_info,
                'registry_info': {
                    'service_cache_size': len(self.handler_registry._service_cache),
                    'ruleset_cache_size': len(self.handler_registry._ruleset_cache)
                }
            }
        
        return await self._execute_with_error_handling(_list_handlers_operation, "list_available_handlers")