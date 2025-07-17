"""Service parameter management for Checkmk LLM Agent."""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from .api_client import CheckmkClient, CheckmkAPIError
from .config import AppConfig


class ServiceParameterManager:
    """Manager for service parameter operations with rule-based configuration."""
    
    # Common parameter rulesets mapping
    PARAMETER_RULESETS = {
        'cpu': {
            'linux': 'cpu_utilization_linux',
            'windows': 'cpu_utilization_simple', 
            'default': 'cpu_utilization_linux'
        },
        'memory': {
            'linux': 'memory_linux',
            'windows': 'memory_level_windows',
            'default': 'memory_linux'
        },
        'filesystem': {
            'all': 'filesystems',
            'default': 'filesystems'
        },
        'disk': {
            'io': 'disk_io',
            'stats': 'diskstat',
            'default': 'disk_io'
        },
        'network': {
            'interfaces': 'interfaces',
            'if64': 'if64',
            'default': 'interfaces'
        }
    }
    
    # Default parameter templates
    DEFAULT_TEMPLATES = {
        'cpu_utilization_linux': {
            'levels': (80.0, 90.0),
            'average': 15,
            'horizon': 90
        },
        'cpu_utilization_simple': {
            'levels': (80.0, 90.0),
            'average': 15
        },
        'memory_linux': {
            'levels': (80.0, 90.0),
            'average': 3,
            'handle_zero': True
        },
        'memory_level_windows': {
            'levels': (80.0, 90.0),
            'average': 3
        },
        'filesystems': {
            'levels': (80.0, 90.0),
            'magic_normsize': 20,
            'magic': 0.8,
            'trend_range': 24
        },
        'interfaces': {
            'speed': 'auto',
            'levels': (80.0, 90.0),
            'unit': 'percent'
        }
    }
    
    def __init__(self, checkmk_client: CheckmkClient, config: AppConfig):
        self.checkmk_client = checkmk_client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._ruleset_cache = {}
        self._cache_timestamp = None
        self._cache_ttl = 900  # 15 minutes
    
    def list_parameter_rulesets(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available parameter rulesets.
        
        Args:
            category: Optional category filter (cpu, memory, filesystem, etc.)
            
        Returns:
            List of ruleset information
        """
        try:
            # Check cache first
            if self._is_cache_valid():
                all_rulesets = self._ruleset_cache
            else:
                all_rulesets = self.checkmk_client.list_rulesets()
                self._update_cache(all_rulesets)
            
            # Filter by category if specified
            if category:
                category_rulesets = self.PARAMETER_RULESETS.get(category, {})
                filtered = []
                for ruleset in all_rulesets:
                    if ruleset.get('id') in category_rulesets.values():
                        filtered.append(ruleset)
                return filtered
            
            # Return service monitoring related rulesets
            service_rulesets = []
            known_rulesets = set()
            for cat_rules in self.PARAMETER_RULESETS.values():
                known_rulesets.update(cat_rules.values())
            
            for ruleset in all_rulesets:
                if ruleset.get('id') in known_rulesets:
                    service_rulesets.append(ruleset)
            
            return service_rulesets
            
        except CheckmkAPIError as e:
            self.logger.error(f"Error listing parameter rulesets: {e}")
            raise
    
    def get_ruleset_schema(self, ruleset_name: str) -> Dict[str, Any]:
        """
        Get schema information for a specific ruleset.
        
        Args:
            ruleset_name: Name of the ruleset
            
        Returns:
            Ruleset schema information
        """
        try:
            return self.checkmk_client.get_ruleset_info(ruleset_name)
        except CheckmkAPIError as e:
            self.logger.error(f"Error getting ruleset schema for {ruleset_name}: {e}")
            raise
    
    def get_default_parameters(self, service_type: str, os_type: str = 'linux') -> Dict[str, Any]:
        """
        Get default parameters for a service type.
        
        Args:
            service_type: Type of service (cpu, memory, filesystem, etc.)
            os_type: Operating system type (linux, windows)
            
        Returns:
            Default parameter values
        """
        # Determine the correct ruleset
        ruleset_map = self.PARAMETER_RULESETS.get(service_type, {})
        ruleset_name = ruleset_map.get(os_type, ruleset_map.get('default'))
        
        if not ruleset_name:
            self.logger.warning(f"No default ruleset found for service type: {service_type}")
            return {}
        
        # Return a copy to prevent modifications to the class variable
        template = self.DEFAULT_TEMPLATES.get(ruleset_name, {})
        return template.copy() if template else {}
    
    def create_parameter_rule(self, ruleset: str, host_name: str, service_pattern: str, 
                            parameters: Dict[str, Any], folder: str = "~",
                            comment: Optional[str] = None) -> str:
        """
        Create a new parameter rule for a specific host and service.
        
        Args:
            ruleset: The ruleset name
            host_name: Target hostname
            service_pattern: Service description pattern
            parameters: Parameter values to set
            folder: Folder path for the rule
            comment: Optional comment for the rule
            
        Returns:
            Created rule ID
        """
        try:
            # Validate parameters
            if not self.validate_parameters(ruleset, parameters):
                raise ValueError(f"Invalid parameters for ruleset {ruleset}")
            
            # Convert parameters to value_raw format
            value_raw = json.dumps(parameters, separators=(',', ':'))
            
            # Create rule conditions
            conditions = {
                "host_name": [host_name],
                "service_description": [service_pattern]
            }
            
            # Set rule properties
            properties = {
                "disabled": False
            }
            if comment:
                properties["description"] = comment
            else:
                properties["description"] = f"Custom parameters for {service_pattern} on {host_name}"
            
            # Create the rule
            response = self.checkmk_client.create_rule(
                ruleset=ruleset,
                folder=folder,
                value_raw=value_raw,
                conditions=conditions,
                properties=properties
            )
            
            rule_id = response.get('id')
            self.logger.info(f"Created parameter rule {rule_id} for {host_name}/{service_pattern}")
            return rule_id
            
        except (CheckmkAPIError, ValueError) as e:
            self.logger.error(f"Error creating parameter rule: {e}")
            raise
    
    def update_service_parameters(self, rule_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update parameters for an existing rule.
        
        Args:
            rule_id: ID of the rule to update
            parameters: New parameter values
            
        Returns:
            Updated rule information
        """
        try:
            # Get existing rule to preserve conditions and properties
            existing_rule = self.checkmk_client.get_rule(rule_id)
            
            # Validate new parameters
            ruleset = existing_rule.get('extensions', {}).get('ruleset')
            if not self.validate_parameters(ruleset, parameters):
                raise ValueError(f"Invalid parameters for ruleset {ruleset}")
            
            # Convert parameters to value_raw format
            value_raw = json.dumps(parameters, separators=(',', ':'))
            
            # Update the rule (Note: This would need a PUT endpoint in the API client)
            # For now, we'll delete and recreate the rule
            self.logger.warning("Rule update not directly supported, will recreate rule")
            
            # Get rule details for recreation
            conditions = existing_rule.get('extensions', {}).get('conditions', {})
            properties = existing_rule.get('extensions', {}).get('properties', {})
            folder = existing_rule.get('extensions', {}).get('folder', '~')
            
            # Delete old rule
            self.checkmk_client.delete_rule(rule_id)
            
            # Create new rule with updated parameters
            response = self.checkmk_client.create_rule(
                ruleset=ruleset,
                folder=folder,
                value_raw=value_raw,
                conditions=conditions,
                properties=properties
            )
            
            new_rule_id = response.get('id')
            self.logger.info(f"Updated parameter rule: {rule_id} -> {new_rule_id}")
            return response
            
        except CheckmkAPIError as e:
            self.logger.error(f"Error updating parameter rule {rule_id}: {e}")
            raise
    
    def get_service_parameters(self, host_name: str, service_name: str) -> Dict[str, Any]:
        """
        Get effective parameters for a specific service.
        
        Args:
            host_name: The hostname
            service_name: The service description
            
        Returns:
            Effective parameter values and rule information
        """
        try:
            # Get all rules that might affect this service
            affecting_rules = self.checkmk_client.search_rules_by_host_service(host_name, service_name)
            
            if not affecting_rules:
                return {
                    'parameters': {},
                    'source': 'default',
                    'rules': []
                }
            
            # Sort rules by precedence (most specific first)
            sorted_rules = self._sort_rules_by_precedence(affecting_rules, host_name, service_name)
            
            # Get effective parameters from highest precedence rule
            effective_rule = sorted_rules[0] if sorted_rules else None
            effective_params = {}
            
            if effective_rule:
                value_raw = effective_rule.get('extensions', {}).get('value_raw', '{}')
                try:
                    effective_params = json.loads(value_raw)
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse rule parameters: {value_raw}")
            
            return {
                'parameters': effective_params,
                'source': 'rule' if effective_rule else 'default',
                'primary_rule': effective_rule,
                'all_rules': sorted_rules
            }
            
        except CheckmkAPIError as e:
            self.logger.error(f"Error getting service parameters for {host_name}/{service_name}: {e}")
            raise
    
    def delete_parameter_rule(self, rule_id: str) -> None:
        """
        Delete a parameter rule.
        
        Args:
            rule_id: ID of the rule to delete
        """
        try:
            self.checkmk_client.delete_rule(rule_id)
            self.logger.info(f"Deleted parameter rule: {rule_id}")
        except CheckmkAPIError as e:
            self.logger.error(f"Error deleting parameter rule {rule_id}: {e}")
            raise
    
    def validate_parameters(self, ruleset: str, parameters: Dict[str, Any]) -> bool:
        """
        Validate parameters for a specific ruleset.
        
        Args:
            ruleset: The ruleset name
            parameters: Parameters to validate
            
        Returns:
            True if parameters are valid
        """
        try:
            # Basic validation for common parameter patterns
            if 'levels' in parameters:
                levels = parameters['levels']
                if isinstance(levels, (list, tuple)) and len(levels) == 2:
                    warning, critical = levels
                    if not (0 <= warning <= 100 and 0 <= critical <= 100):
                        return False
                    if warning >= critical:
                        return False
            
            # Filesystem-specific validation
            if ruleset == 'filesystems':
                if 'magic_normsize' in parameters:
                    if not isinstance(parameters['magic_normsize'], (int, float)) or parameters['magic_normsize'] <= 0:
                        return False
                if 'magic' in parameters:
                    if not isinstance(parameters['magic'], (int, float)) or not (0 < parameters['magic'] <= 1):
                        return False
            
            # CPU-specific validation
            if 'cpu_utilization' in ruleset:
                if 'average' in parameters:
                    if not isinstance(parameters['average'], (int, float)) or parameters['average'] <= 0:
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating parameters: {e}")
            return False
    
    def discover_service_ruleset(self, host_name: str, service_name: str) -> Optional[str]:
        """
        Discover the appropriate ruleset for a service.
        
        Args:
            host_name: The hostname
            service_name: The service description
            
        Returns:
            Ruleset name if found
        """
        # Simple heuristic based on service name patterns
        service_lower = service_name.lower()
        
        if 'cpu' in service_lower or 'processor' in service_lower:
            # Try to determine OS type from host or use default
            return self.PARAMETER_RULESETS['cpu']['default']
        elif 'memory' in service_lower or 'ram' in service_lower:
            return self.PARAMETER_RULESETS['memory']['default']
        elif 'filesystem' in service_lower or 'disk' in service_lower or 'mount' in service_lower:
            return self.PARAMETER_RULESETS['filesystem']['default']
        elif 'interface' in service_lower or 'network' in service_lower or 'eth' in service_lower:
            return self.PARAMETER_RULESETS['network']['default']
        
        return None
    
    def create_simple_override(self, host_name: str, service_name: str, 
                             warning: Union[int, float], critical: Union[int, float],
                             comment: Optional[str] = None) -> str:
        """
        Create a simple parameter override for warning/critical thresholds.
        
        Args:
            host_name: Target hostname
            service_name: Service description
            warning: Warning threshold
            critical: Critical threshold
            comment: Optional comment
            
        Returns:
            Created rule ID
        """
        # Discover the appropriate ruleset
        ruleset = self.discover_service_ruleset(host_name, service_name)
        if not ruleset:
            raise ValueError(f"Could not determine ruleset for service: {service_name}")
        
        # Get default parameters and update with new thresholds
        parameters = self.get_default_parameters('cpu' if 'cpu_utilization' in ruleset else 'filesystem')
        parameters['levels'] = (float(warning), float(critical))
        
        # Create the rule
        if not comment:
            comment = f"Override thresholds for {service_name} on {host_name}"
        
        return self.create_parameter_rule(
            ruleset=ruleset,
            host_name=host_name,
            service_pattern=service_name,
            parameters=parameters,
            comment=comment
        )
    
    def _is_cache_valid(self) -> bool:
        """Check if the ruleset cache is still valid."""
        if not self._cache_timestamp or not self._ruleset_cache:
            return False
        
        cache_age = (datetime.now() - self._cache_timestamp).total_seconds()
        return cache_age < self._cache_ttl
    
    def _update_cache(self, rulesets: List[Dict[str, Any]]) -> None:
        """Update the ruleset cache."""
        self._ruleset_cache = rulesets
        self._cache_timestamp = datetime.now()
    
    def _sort_rules_by_precedence(self, rules: List[Dict[str, Any]], 
                                host_name: str, service_name: str) -> List[Dict[str, Any]]:
        """
        Sort rules by precedence for a specific host/service combination.
        
        Args:
            rules: List of rules to sort
            host_name: Target hostname
            service_name: Target service name
            
        Returns:
            Rules sorted by precedence (highest first)
        """
        def rule_precedence_score(rule):
            """Calculate precedence score for a rule (higher = more specific)."""
            score = 0
            conditions = rule.get('extensions', {}).get('conditions', {})
            
            # Host-specific rules have highest precedence
            host_names = conditions.get('host_name', [])
            if host_name in host_names:
                score += 1000
            elif any(name.startswith('~') for name in host_names):
                # Regex patterns have medium precedence
                score += 500
            
            # Service-specific rules
            service_descriptions = conditions.get('service_description', [])
            if service_name in service_descriptions:
                score += 100
            elif any(desc.startswith('~') for desc in service_descriptions):
                # Service regex patterns
                score += 50
            
            # Host tags and labels add some precedence
            if conditions.get('host_tags'):
                score += 10
            if conditions.get('host_labels'):
                score += 5
            
            return score
        
        return sorted(rules, key=rule_precedence_score, reverse=True)