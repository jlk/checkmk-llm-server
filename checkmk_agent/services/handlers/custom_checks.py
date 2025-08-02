"""
Specialized parameter handler for custom check monitoring services.

Handles local checks, MRPE checks, and custom monitoring scripts with
dynamic parameter discovery and flexible schema support.
"""

import re
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass

from .base import BaseParameterHandler, HandlerResult, ValidationSeverity


@dataclass
class CustomCheckProfile:
    """Profile for different types of custom checks."""
    check_type: str
    description: str
    common_parameters: Dict[str, Any]
    parameter_patterns: Dict[str, str]  # Parameter name -> regex pattern for values


class CustomCheckParameterHandler(BaseParameterHandler):
    """
    Specialized handler for custom check parameters.
    
    Supports:
    - Local checks executed by agents
    - MRPE (MK's Remote Plugin Executor) checks
    - Custom scripts and plugins
    - Dynamic parameter discovery from check output
    - Flexible parameter schemas for arbitrary checks
    - Performance data handling
    """
    
    # Profiles for different custom check types
    CUSTOM_CHECK_PROFILES = {
        'local': CustomCheckProfile(
            check_type='local',
            description='Local checks executed by Checkmk agent',
            common_parameters={
                'levels': (0, 0),  # Default: no thresholds
                'perfdata': True,
                'inventory': 'always',
                'expected_match': None
            },
            parameter_patterns={
                'levels': r'^\(?\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)?$',
                'expected_match': r'^[a-zA-Z0-9_\-\s]+$'
            }
        ),
        'mrpe': CustomCheckProfile(
            check_type='mrpe',
            description='MRPE (MK Remote Plugin Executor) checks',
            common_parameters={
                'service_description': None,
                'command_line': None,
                'performance_data': True,
                'check_interval': 60,
                'retry_count': 3,
                'state_translation': {}
            },
            parameter_patterns={
                'command_line': r'^[a-zA-Z0-9_\-\.\s\/\$\{\}]+$',
                'check_interval': r'^\d+$',
                'retry_count': r'^[1-9]\d*$'
            }
        ),
        'script': CustomCheckProfile(
            check_type='script',
            description='Custom monitoring scripts',
            common_parameters={
                'timeout': 60,
                'environment_vars': {},
                'working_directory': None,
                'user': None,
                'perfdata_regex': None,
                'output_format': 'text'
            },
            parameter_patterns={
                'timeout': r'^\d+$',
                'user': r'^[a-zA-Z0-9_\-]+$',
                'perfdata_regex': r'^.+$'
            }
        ),
        'nagios_plugin': CustomCheckProfile(
            check_type='nagios_plugin',
            description='Nagios-compatible plugins',
            common_parameters={
                'command': None,
                'arguments': [],
                'warning_threshold': None,
                'critical_threshold': None,
                'timeout': 30,
                'state_mapping': {0: 'OK', 1: 'WARN', 2: 'CRIT', 3: 'UNKNOWN'}
            },
            parameter_patterns={
                'warning_threshold': r'^[\d\.\-\:@~]+$',
                'critical_threshold': r'^[\d\.\-\:@~]+$',
                'timeout': r'^\d+$'
            }
        )
    }
    
    @property
    def name(self) -> str:
        """Unique name for this handler."""
        return "custom_checks"
    
    @property
    def service_patterns(self) -> List[str]:
        """Regex patterns that match custom check services."""
        return [
            r'.*local.*',
            r'.*mrpe.*',
            r'.*custom.*',
            r'.*script.*',
            r'.*nagios.*',
            r'.*check_.*',  # Common Nagios plugin naming
            r'.*plugin.*',
            r'.*external.*'
        ]
    
    @property
    def supported_rulesets(self) -> List[str]:
        """Rulesets this handler supports."""
        return [
            'checkgroup_parameters:custom_checks',
            'checkgroup_parameters:local',
            'checkgroup_parameters:mrpe',
            'checkgroup_parameters:nagios_plugins'
        ]
    
    def get_default_parameters(self, service_name: str, context: Optional[Dict[str, Any]] = None) -> HandlerResult:
        """
        Get default parameters for custom checks.
        
        Args:
            service_name: Name of the custom check service
            context: Optional context (check type, command info, etc.)
            
        Returns:
            HandlerResult with custom check defaults
        """
        # Determine check type from service name and context
        check_type = self._detect_check_type(service_name, context)
        profile = self.CUSTOM_CHECK_PROFILES.get(check_type, self.CUSTOM_CHECK_PROFILES['local'])
        
        # Start with profile defaults
        parameters = profile.common_parameters.copy()
        
        # Add service-specific defaults based on detected type (don't override detection)
        if check_type == 'nagios_plugin':
            parameters.update({
                'timeout': 30,
                'perfdata': True,
                'check_type': 'nagios_plugin'
            })
        elif check_type == 'local':
            parameters.update({
                'inventory': 'always',
                'cache_period': 0,  # No caching for local checks
                'check_type': 'local'
            })
        elif check_type == 'mrpe':
            parameters.update({
                'check_interval': 60,
                'timeout': 60,
                'check_type': 'mrpe'
            })
        elif check_type == 'script':
            parameters.update({
                'timeout': 60,
                'check_type': 'script'
            })
        
        # Apply context-based adjustments
        if context:
            # If we have command information, adjust timeouts
            if context.get('command_info'):
                cmd_info = context['command_info']
                if 'slow' in str(cmd_info).lower() or 'long' in str(cmd_info).lower():
                    parameters['timeout'] = 120
                elif 'fast' in str(cmd_info).lower() or 'quick' in str(cmd_info).lower():
                    parameters['timeout'] = 15
            
            # If we have performance data examples, configure perfdata handling
            if context.get('sample_perfdata'):
                parameters['perfdata'] = True
                parameters['perfdata_regex'] = self._generate_perfdata_regex(context['sample_perfdata'])
            
            # Environment-specific adjustments
            if context.get('environment') == 'production':
                # More conservative settings for production
                parameters['retry_count'] = 3
                parameters['timeout'] = min(parameters.get('timeout', 60), 60)
        
        messages = [
            self._create_validation_message(
                ValidationSeverity.INFO,
                f"Using {profile.description} profile for custom check"
            ),
            self._create_validation_message(
                ValidationSeverity.INFO,
                f"Default check type: {check_type}"
            )
        ]
        
        return HandlerResult(
            success=True,
            parameters=parameters,
            validation_messages=messages
        )
    
    def validate_parameters(
        self, 
        parameters: Dict[str, Any], 
        service_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> HandlerResult:
        """
        Validate custom check parameters.
        
        Args:
            parameters: Parameters to validate
            service_name: Name of the custom check service
            context: Optional context information
            
        Returns:
            HandlerResult with validation results
        """
        messages = []
        normalized_params = parameters.copy()
        
        # Determine check type for context-aware validation
        check_type = self._detect_check_type(service_name, context)
        profile = self.CUSTOM_CHECK_PROFILES.get(check_type, self.CUSTOM_CHECK_PROFILES['local'])
        
        # Validate common parameters
        
        # Validate timeout
        if 'timeout' in parameters:
            timeout_messages = self._validate_positive_number(
                parameters['timeout'], 
                'timeout',
                int
            )
            messages.extend(timeout_messages)
            
            # Check for reasonable timeout values
            try:
                timeout = int(parameters['timeout'])
                if timeout < 5:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.WARNING,
                        "Timeout less than 5 seconds may be too short for most checks",
                        'timeout'
                    ))
                elif timeout > 300:  # 5 minutes
                    messages.append(self._create_validation_message(
                        ValidationSeverity.WARNING,
                        "Timeout longer than 5 minutes may cause monitoring delays",
                        'timeout'
                    ))
                
                normalized_params['timeout'] = timeout
            except (TypeError, ValueError):
                pass
        
        # Validate performance data settings
        if 'perfdata' in parameters:
            if not isinstance(parameters['perfdata'], bool):
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "perfdata must be a boolean value",
                    'perfdata'
                ))
            else:
                normalized_params['perfdata'] = parameters['perfdata']
        
        # Validate levels (if present)
        if 'levels' in parameters:
            levels_messages = self._validate_threshold_tuple(
                parameters['levels'],
                'levels',
                min_values=2,
                max_values=4,  # Some custom checks support 4-level thresholds
                numeric_type=float
            )
            messages.extend(levels_messages)
        
        # Type-specific validation
        if check_type == 'mrpe':
            mrpe_messages = self._validate_mrpe_parameters(parameters)
            messages.extend(mrpe_messages)
        elif check_type == 'nagios_plugin':
            nagios_messages = self._validate_nagios_plugin_parameters(parameters)
            messages.extend(nagios_messages)
        elif check_type == 'script':
            script_messages = self._validate_script_parameters(parameters)
            messages.extend(script_messages)
        
        # Validate performance data regex if present
        if 'perfdata_regex' in parameters:
            regex_messages = self._validate_regex_parameter(
                parameters['perfdata_regex'],
                'perfdata_regex'
            )
            messages.extend(regex_messages)
        
        # Validate state translations/mappings
        if 'state_translation' in parameters or 'state_mapping' in parameters:
            state_param = 'state_translation' if 'state_translation' in parameters else 'state_mapping'
            state_messages = self._validate_state_mapping(
                parameters[state_param],
                state_param
            )
            messages.extend(state_messages)
        
        # Validate command line or command parameters
        for cmd_param in ['command_line', 'command']:
            if cmd_param in parameters:
                cmd_messages = self._validate_command_parameter(
                    parameters[cmd_param],
                    cmd_param
                )
                messages.extend(cmd_messages)
        
        # Add type-specific recommendations
        if check_type != 'local':  # Not detected as specific type
            messages.append(self._create_validation_message(
                ValidationSeverity.INFO,
                f"Consider specifying check_type parameter for better validation and defaults"
            ))
        
        return HandlerResult(
            success=len([m for m in messages if m.severity == ValidationSeverity.ERROR]) == 0,
            parameters=parameters,
            normalized_parameters=normalized_params,
            validation_messages=messages
        )
    
    def get_parameter_info(self, parameter_name: str) -> Optional[Dict[str, Any]]:
        """Get information about custom check parameters."""
        parameter_info = {
            'levels': {
                'description': 'Threshold levels for numeric checks',
                'type': 'tuple',
                'elements': ['float', 'float', 'float?', 'float?'],
                'example': '(80.0, 90.0) or (10, 20, 30, 40)',
                'help': 'Can be 2-tuple (warn, crit) or 4-tuple (warn_low, warn_high, crit_low, crit_high)'
            },
            'timeout': {
                'description': 'Maximum execution time for the check in seconds',
                'type': 'integer',
                'default': 60,
                'min_value': 1,
                'max_value': 3600,
                'example': '30'
            },
            'perfdata': {
                'description': 'Whether to collect and display performance data',
                'type': 'boolean',
                'default': True,
                'help': 'Enable collection of metrics from check output'
            },
            'perfdata_regex': {
                'description': 'Regular expression to extract performance data',
                'type': 'string',
                'example': r"'([^=]+)=([0-9.]+)([^;]*);?([0-9.]*);?([0-9.]*);?([0-9.]*);?([0-9.]*)'",
                'help': 'Used to parse custom performance data formats'
            },
            'command_line': {
                'description': 'Command line for MRPE checks',
                'type': 'string',
                'example': 'check_disk -w 80% -c 90% /var',
                'help': 'Full command line including arguments'
            },
            'command': {
                'description': 'Command or script path for custom checks',
                'type': 'string',
                'example': '/usr/local/bin/check_custom_metric.sh',
                'help': 'Path to executable or script'
            },
            'arguments': {
                'description': 'Command line arguments',
                'type': 'list',
                'elements': 'string',
                'example': '["-w", "80", "-c", "90"]',
                'help': 'List of command line arguments'
            },
            'environment_vars': {
                'description': 'Environment variables for the check',
                'type': 'dict',
                'example': '{"PATH": "/usr/local/bin", "TIMEOUT": "30"}',
                'help': 'Dictionary of environment variables to set'
            },
            'working_directory': {
                'description': 'Working directory for check execution',
                'type': 'string',
                'example': '/opt/monitoring',
                'help': 'Directory to change to before executing check'
            },
            'user': {
                'description': 'User account to run the check as',
                'type': 'string',
                'example': 'monitoring',
                'help': 'Username for check execution (requires appropriate sudo configuration)'
            },
            'check_interval': {
                'description': 'Check execution interval in seconds',
                'type': 'integer',
                'default': 60,
                'min_value': 1,
                'help': 'How often to execute the check'
            },
            'retry_count': {
                'description': 'Number of retries on check failure',
                'type': 'integer',
                'default': 3,
                'min_value': 0,
                'max_value': 10,
                'help': 'Number of times to retry failed checks'
            },
            'state_translation': {
                'description': 'Mapping of exit codes to monitoring states',
                'type': 'dict',
                'example': '{0: "OK", 1: "WARN", 2: "CRIT", 3: "UNKNOWN"}',
                'help': 'Translate numeric exit codes to monitoring states'
            },
            'inventory': {
                'description': 'When to include this check in service discovery',
                'type': 'choice',
                'choices': ['always', 'never', 'if_available'],
                'default': 'always',
                'help': 'Control automatic service discovery behavior'
            }
        }
        
        return parameter_info.get(parameter_name)
    
    def suggest_parameters(
        self, 
        service_name: str, 
        current_parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Suggest custom check parameter optimizations."""
        suggestions = []
        
        current = current_parameters or {}
        check_type = self._detect_check_type(service_name, context)
        
        # Suggest performance data collection if not configured
        if current.get('perfdata') is None:
            suggestions.append({
                'parameter': 'perfdata',
                'current_value': None,
                'suggested_value': True,
                'reason': 'Enable performance data collection for better monitoring insights',
                'impact': 'Collect metrics and trends from check output'
            })
        
        # Suggest appropriate timeout based on check type
        current_timeout = current.get('timeout')
        if check_type == 'nagios_plugin' and (current_timeout is None or current_timeout > 60):
            suggestions.append({
                'parameter': 'timeout',
                'current_value': current_timeout,
                'suggested_value': 30,
                'reason': 'Nagios plugins typically complete quickly',
                'impact': 'Faster detection of check failures'
            })
        elif check_type == 'script' and (current_timeout is None or current_timeout < 60):
            suggestions.append({
                'parameter': 'timeout',
                'current_value': current_timeout,
                'suggested_value': 120,
                'reason': 'Custom scripts may need more time to execute',
                'impact': 'Prevent premature timeout of legitimate checks'
            })
        
        # Suggest retry configuration for important checks
        if 'retry_count' not in current and 'critical' in service_name.lower():
            suggestions.append({
                'parameter': 'retry_count',
                'current_value': None,
                'suggested_value': 3,
                'reason': 'Add retry logic for critical custom checks',
                'impact': 'Reduce false alerts from transient issues'
            })
        
        # Suggest environment variables for security
        if check_type == 'script' and 'environment_vars' not in current:
            suggestions.append({
                'parameter': 'environment_vars',
                'current_value': None,
                'suggested_value': {"PATH": "/usr/local/bin:/usr/bin:/bin"},
                'reason': 'Set explicit PATH for security and reliability',
                'impact': 'Prevent issues with missing executables and improve security'
            })
        
        return suggestions
    
    def _detect_check_type(self, service_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Detect the type of custom check from service name and context."""
        service_lower = service_name.lower()
        
        # Check context first
        if context and context.get('check_type'):
            return context['check_type']
        
        # Analyze service name patterns
        if 'mrpe' in service_lower:
            return 'mrpe'
        elif 'local' in service_lower:
            return 'local'
        elif any(pattern in service_lower for pattern in ['check_', 'nagios', 'plugin']):
            return 'nagios_plugin'
        elif any(pattern in service_lower for pattern in ['script', 'custom']):
            return 'script'
        else:
            return 'local'  # Default fallback
    
    def _validate_mrpe_parameters(self, parameters: Dict[str, Any]) -> List:
        """Validate MRPE-specific parameters."""
        messages = []
        
        # MRPE checks should have command_line
        if 'command_line' not in parameters:
            messages.append(self._create_validation_message(
                ValidationSeverity.WARNING,
                "MRPE checks typically require a command_line parameter",
                suggestion="Add 'command_line' with the full check command"
            ))
        
        # Validate check interval
        if 'check_interval' in parameters:
            interval_messages = self._validate_positive_number(
                parameters['check_interval'],
                'check_interval',
                int
            )
            messages.extend(interval_messages)
        
        return messages
    
    def _validate_nagios_plugin_parameters(self, parameters: Dict[str, Any]) -> List:
        """Validate Nagios plugin-specific parameters."""
        messages = []
        
        # Validate Nagios-style thresholds
        for threshold_param in ['warning_threshold', 'critical_threshold']:
            if threshold_param in parameters:
                threshold_value = parameters[threshold_param]
                if not self._is_valid_nagios_threshold(threshold_value):
                    messages.append(self._create_validation_message(
                        ValidationSeverity.ERROR,
                        f"{threshold_param} is not a valid Nagios threshold format",
                        threshold_param,
                        "Use format like '80', '80:', '@10:90', or '~:80'"
                    ))
        
        # Validate state mapping
        if 'state_mapping' in parameters:
            state_map = parameters['state_mapping']
            if not isinstance(state_map, dict):
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "state_mapping must be a dictionary",
                    'state_mapping'
                ))
            else:
                # Check for standard Nagios exit codes
                expected_codes = {0, 1, 2, 3}
                provided_codes = set(state_map.keys())
                if not expected_codes.issubset(provided_codes):
                    missing = expected_codes - provided_codes
                    messages.append(self._create_validation_message(
                        ValidationSeverity.WARNING,
                        f"Missing standard exit codes in state_mapping: {missing}",
                        'state_mapping'
                    ))
        
        return messages
    
    def _validate_script_parameters(self, parameters: Dict[str, Any]) -> List:
        """Validate custom script-specific parameters."""
        messages = []
        
        # Validate working directory
        if 'working_directory' in parameters:
            work_dir = parameters['working_directory']
            if not isinstance(work_dir, str) or not work_dir.startswith('/'):
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "working_directory must be an absolute path",
                    'working_directory'
                ))
        
        # Validate user parameter
        if 'user' in parameters:
            user = parameters['user']
            if not isinstance(user, str) or not re.match(r'^[a-zA-Z0-9_\-]+$', user):
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "user must be a valid username (alphanumeric, underscore, hyphen only)",
                    'user'
                ))
        
        # Validate environment variables
        if 'environment_vars' in parameters:
            env_vars = parameters['environment_vars']
            if not isinstance(env_vars, dict):
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "environment_vars must be a dictionary",
                    'environment_vars'
                ))
            else:
                for key, value in env_vars.items():
                    if not isinstance(key, str) or not re.match(r'^[A-Z_][A-Z0-9_]*$', key):
                        messages.append(self._create_validation_message(
                            ValidationSeverity.WARNING,
                            f"Environment variable name '{key}' doesn't follow convention (uppercase, underscores)",
                            'environment_vars'
                        ))
        
        return messages
    
    def _validate_regex_parameter(self, regex_pattern: str, field_name: str) -> List:
        """Validate a regular expression parameter."""
        messages = []
        
        if not isinstance(regex_pattern, str):
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} must be a string",
                field_name
            ))
            return messages
        
        try:
            re.compile(regex_pattern)
        except re.error as e:
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} is not a valid regular expression: {e}",
                field_name
            ))
        
        return messages
    
    def _validate_state_mapping(self, state_mapping: Any, field_name: str) -> List:
        """Validate state mapping/translation parameters."""
        messages = []
        
        if not isinstance(state_mapping, dict):
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} must be a dictionary",
                field_name
            ))
            return messages
        
        valid_states = {'OK', 'WARN', 'CRIT', 'UNKNOWN', 'PENDING'}
        
        for exit_code, state in state_mapping.items():
            # Validate exit code
            if not isinstance(exit_code, int) or exit_code < 0 or exit_code > 255:
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    f"Exit code {exit_code} must be an integer between 0 and 255",
                    field_name
                ))
            
            # Validate state name
            if isinstance(state, str):
                state_upper = state.upper()
                if state_upper not in valid_states:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.WARNING,
                        f"State '{state}' is not a standard monitoring state",
                        field_name,
                        f"Consider using one of: {', '.join(valid_states)}"
                    ))
            elif not isinstance(state, int):
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    f"State value must be a string or integer, got {type(state).__name__}",
                    field_name
                ))
        
        return messages
    
    def _validate_command_parameter(self, command: Any, field_name: str) -> List:
        """Validate command or command_line parameters."""
        messages = []
        
        if not isinstance(command, str):
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} must be a string",
                field_name
            ))
            return messages
        
        # Basic command validation
        if not command.strip():
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"{field_name} cannot be empty",
                field_name
            ))
        
        # Check for potentially dangerous patterns
        dangerous_patterns = [
            (r'[;&|]', 'command chaining characters (;, &, |)'),
            (r'`[^`]*`', 'command substitution (backticks)'),
            (r'\$\([^)]*\)', 'command substitution ($())'),
            (r'\$\{[^}]*\}', 'variable expansion (${})')
        ]
        
        for pattern, description in dangerous_patterns:
            if re.search(pattern, command):
                messages.append(self._create_validation_message(
                    ValidationSeverity.WARNING,
                    f"{field_name} contains potentially dangerous {description}",
                    field_name,
                    "Ensure command is properly escaped and validated"
                ))
        
        return messages
    
    def _is_valid_nagios_threshold(self, threshold: Any) -> bool:
        """Check if a value is a valid Nagios threshold format."""
        if not isinstance(threshold, str) or not threshold.strip():
            return False
        
        # Nagios threshold formats:
        # 10      - critical if > 10
        # 10:     - critical if < 10
        # ~:10    - critical if > 10
        # 10:20   - critical if < 10 or > 20
        # @10:20  - critical if between 10 and 20
        
        # Must have at least one meaningful component
        threshold = threshold.strip()
        
        # Check for obviously invalid patterns
        if threshold in ["@", ":", ""] or "::" in threshold or threshold.count("@") > 1:
            return False
        
        # Check for @ in wrong position (not at start)
        if "@" in threshold and not threshold.startswith("@"):
            return False
        
        # Remove @ prefix for further parsing
        inverted = threshold.startswith("@")
        if inverted:
            threshold = threshold[1:]
        
        # Parse the threshold
        if ":" in threshold:
            parts = threshold.split(":")
            if len(parts) != 2:
                return False
            
            start_part, end_part = parts
            
            # Validate start part
            if start_part and start_part != "~":
                try:
                    start_val = float(start_part)
                except ValueError:
                    return False
            else:
                start_val = None
            
            # Validate end part
            if end_part:
                try:
                    end_val = float(end_part)
                except ValueError:
                    return False
            else:
                end_val = None
            
            # Check range validity (start should be <= end)
            if start_val is not None and end_val is not None and start_val > end_val:
                return False
                
        else:
            # Single value - must be numeric or "~"
            if threshold != "~":
                try:
                    float(threshold)
                except ValueError:
                    return False
        
        return True
    
    def _generate_perfdata_regex(self, sample_perfdata: str) -> str:
        """Generate a regex pattern from sample performance data."""
        # This is a simplified approach - in practice, you might want more sophisticated analysis
        # Sample perfdata might look like: "load1=0.5;1;2;0; load5=0.3;1;2;0; load15=0.2;1;2;0;"
        
        # Default regex for Nagios-style perfdata
        return r"'([^=]+)=([0-9.]+)([^;]*);?([0-9.]*);?([0-9.]*);?([0-9.]*);?([0-9.]*)"