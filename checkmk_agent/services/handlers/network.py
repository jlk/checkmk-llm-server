"""
Specialized parameter handler for network service monitoring.

Handles HTTP/HTTPS, TCP, DNS, SSH monitoring parameters with SSL certificate
monitoring, response time thresholds, and availability checks.
"""

import re
import ipaddress
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from urllib.parse import urlparse

from .base import BaseParameterHandler, HandlerResult, ValidationSeverity


@dataclass
class NetworkServiceProfile:
    """Profile for different network service types."""
    service_type: str
    description: str
    default_port: Optional[int]
    default_timeout: int
    common_parameters: Dict[str, Any]
    required_parameters: List[str]
    optional_parameters: List[str]


class NetworkServiceParameterHandler(BaseParameterHandler):
    """
    Specialized handler for network service monitoring parameters.
    
    Supports:
    - HTTP/HTTPS monitoring with SSL certificates
    - TCP connection monitoring
    - DNS query monitoring  
    - SSH service monitoring
    - Response time and availability thresholds
    - Complex service checks with multiple parameters
    - URL validation and SSL certificate expiry monitoring
    """
    
    # Network service profiles
    NETWORK_SERVICE_PROFILES = {
        'http': NetworkServiceProfile(
            service_type='http',
            description='HTTP service monitoring',
            default_port=80,
            default_timeout=10,
            common_parameters={
                'response_time': (1.0, 2.0),  # Response time thresholds in seconds
                'timeout': 10,
                'expected_response_codes': [200],
                'follow_redirects': True,
                'max_redirects': 5,
                'user_agent': 'Checkmk-HTTP-Check',
                'method': 'GET'
            },
            required_parameters=['url'],
            optional_parameters=['expected_string', 'headers', 'post_data', 'auth_user', 'auth_password']
        ),
        'https': NetworkServiceProfile(
            service_type='https',
            description='HTTPS service monitoring with SSL certificate checks',
            default_port=443,
            default_timeout=15,
            common_parameters={
                'response_time': (2.0, 5.0),  # HTTPS typically slower
                'timeout': 15,
                'expected_response_codes': [200],
                'follow_redirects': True,
                'max_redirects': 5,
                'user_agent': 'Checkmk-HTTPS-Check',
                'method': 'GET',
                'ssl_cert_age': (30, 7),  # Certificate expiry warning/critical days
                'ssl_verify': True,
                'ssl_min_version': 'TLSv1.2'
            },
            required_parameters=['url'],
            optional_parameters=['expected_string', 'headers', 'post_data', 'auth_user', 'auth_password', 'client_cert']
        ),
        'tcp': NetworkServiceProfile(
            service_type='tcp',
            description='TCP connection monitoring',
            default_port=None,
            default_timeout=10,
            common_parameters={
                'response_time': (0.5, 1.0),  # Connection time thresholds
                'timeout': 10,
                'port': None,  # Must be specified
                'refuse_state': 'critical'  # State when connection refused
            },
            required_parameters=['hostname', 'port'],
            optional_parameters=['expected_string', 'send_string', 'escape_send_string']
        ),
        'dns': NetworkServiceProfile(
            service_type='dns',
            description='DNS query monitoring',
            default_port=53,
            default_timeout=10,
            common_parameters={
                'response_time': (0.1, 0.5),  # DNS should be fast
                'timeout': 10,
                'query_type': 'A',
                'server': None,  # DNS server to query
                'expected_address': None  # Expected IP address
            },
            required_parameters=['hostname'],
            optional_parameters=['server', 'expected_address', 'accept_cname']
        ),
        'ssh': NetworkServiceProfile(
            service_type='ssh',
            description='SSH service monitoring',
            default_port=22,
            default_timeout=10,
            common_parameters={
                'response_time': (1.0, 3.0),  # SSH connection time
                'timeout': 10,
                'port': 22,
                'protocol_version': '2'
            },
            required_parameters=['hostname'],
            optional_parameters=['username', 'command', 'expected_string']
        ),
        'smtp': NetworkServiceProfile(
            service_type='smtp',
            description='SMTP service monitoring',
            default_port=25,
            default_timeout=15,
            common_parameters={
                'response_time': (2.0, 5.0),
                'timeout': 15,
                'port': 25,
                'expected_response': '220',
                'starttls': False
            },
            required_parameters=['hostname'],
            optional_parameters=['from_address', 'to_address', 'auth_user', 'auth_password']
        ),
        'ftp': NetworkServiceProfile(
            service_type='ftp',
            description='FTP service monitoring',
            default_port=21,
            default_timeout=15,
            common_parameters={
                'response_time': (2.0, 5.0),
                'timeout': 15,
                'port': 21,
                'passive': True,
                'expected_response': '220'
            },
            required_parameters=['hostname'],
            optional_parameters=['username', 'password', 'directory']
        )
    }
    
    @property
    def name(self) -> str:
        """Unique name for this handler."""
        return "network_services"
    
    @property
    def service_patterns(self) -> List[str]:
        """Regex patterns that match network services."""
        return [
            r'.*http.*',
            r'.*https.*',
            r'.*tcp.*',
            r'.*dns.*',
            r'.*ssh.*',
            r'.*smtp.*',
            r'.*ftp.*',
            r'.*ssl.*cert.*',
            r'.*certificate.*',
            r'.*web.*',
            r'.*port.*\d+.*',
            r'.*connect.*',
            r'.*response.*time.*'
        ]
    
    @property
    def supported_rulesets(self) -> List[str]:
        """Rulesets this handler supports."""
        return [
            'checkgroup_parameters:http',
            'checkgroup_parameters:https',
            'checkgroup_parameters:tcp_connections',
            'checkgroup_parameters:dns',
            'checkgroup_parameters:ssh',
            'checkgroup_parameters:smtp',
            'checkgroup_parameters:ssl_certificates',
            'checkgroup_parameters:tcp_conn_stats'
        ]
    
    def get_default_parameters(self, service_name: str, context: Optional[Dict[str, Any]] = None) -> HandlerResult:
        """
        Get network service-specific default parameters.
        
        Args:
            service_name: Name of the network service
            context: Optional context (URL, hostname, port, etc.)
            
        Returns:
            HandlerResult with network service defaults
        """
        # Determine service type
        service_type = self._detect_service_type(service_name, context)
        profile = self.NETWORK_SERVICE_PROFILES.get(service_type)
        
        if not profile:
            # Generic network service defaults
            parameters = {
                'response_time': (1.0, 3.0),
                'timeout': 10,
                'retry_count': 3
            }
            messages = [
                self._create_validation_message(
                    ValidationSeverity.WARNING,
                    f"Unknown network service type '{service_type}', using generic defaults"
                )
            ]
        else:
            parameters = profile.common_parameters.copy()
            
            # Add service-specific defaults based on context
            if context:
                # Extract URL components for HTTP/HTTPS
                if service_type in ['http', 'https'] and context.get('url'):
                    url_info = self._parse_url(context['url'])
                    if url_info:
                        parameters.update(url_info)
                
                # Extract hostname and port for TCP services
                elif context.get('hostname'):
                    parameters['hostname'] = context['hostname']
                    if context.get('port'):
                        parameters['port'] = context['port']
                    elif profile.default_port:
                        parameters['port'] = profile.default_port
                
                # Environment-specific adjustments
                if context.get('environment') == 'production':
                    # More conservative timeouts for production
                    parameters['timeout'] = min(parameters.get('timeout', 10), 30)
                    
                    # Tighter response time thresholds
                    if 'response_time' in parameters:
                        warn, crit = parameters['response_time']
                        parameters['response_time'] = (warn * 0.8, crit * 0.8)
                
                # Network condition adjustments
                if context.get('network_condition') == 'slow':
                    # Relax thresholds for slow networks
                    if 'response_time' in parameters:
                        warn, crit = parameters['response_time']
                        parameters['response_time'] = (warn * 2, crit * 2)
                    parameters['timeout'] = parameters.get('timeout', 10) * 2
            
            messages = [
                self._create_validation_message(
                    ValidationSeverity.INFO,
                    f"Using {profile.description} profile"
                ),
                self._create_validation_message(
                    ValidationSeverity.INFO,
                    f"Default timeout: {parameters.get('timeout', 10)}s"
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
        Validate network service monitoring parameters.
        
        Args:
            parameters: Parameters to validate
            service_name: Name of the network service
            context: Optional context information
            
        Returns:
            HandlerResult with validation results
        """
        messages = []
        normalized_params = parameters.copy()
        
        # Determine service type for context-aware validation
        service_type = self._detect_service_type(service_name, context)
        profile = self.NETWORK_SERVICE_PROFILES.get(service_type)
        
        # Validate common network parameters
        
        # Validate response time thresholds
        if 'response_time' in parameters:
            response_messages = self._validate_threshold_tuple(
                parameters['response_time'],
                'response_time',
                numeric_type=float
            )
            messages.extend(response_messages)
            
            if not response_messages:
                warn, crit = parameters['response_time']
                if warn <= 0 or crit <= 0:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.ERROR,
                        "Response time thresholds must be positive",
                        'response_time'
                    ))  
                elif warn > 60 or crit > 60:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.WARNING,
                        f"Response time thresholds seem very high ({warn}s, {crit}s)",
                        'response_time'
                    ))
                
                normalized_params['response_time'] = (float(warn), float(crit))
        
        # Validate timeout
        if 'timeout' in parameters:
            timeout_messages = self._validate_positive_number(
                parameters['timeout'],
                'timeout',
                int
            )
            messages.extend(timeout_messages)
            
            try:
                timeout = int(parameters['timeout'])
                if timeout < 1:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.ERROR,
                        "Timeout must be at least 1 second",
                        'timeout'
                    ))
                elif timeout > 300:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.WARNING,
                        "Timeout longer than 5 minutes may cause monitoring delays",
                        'timeout'
                    ))
                
                # Check timeout vs response time consistency
                if 'response_time' in parameters:
                    _, crit_response = parameters['response_time']
                    if timeout <= crit_response:
                        messages.append(self._create_validation_message(
                            ValidationSeverity.WARNING,
                            f"Timeout ({timeout}s) should be greater than critical response time ({crit_response}s)",
                            'timeout'
                        ))
                
                normalized_params['timeout'] = timeout
            except (TypeError, ValueError):
                pass
        
        # Service-specific validation
        if profile:
            if service_type in ['http', 'https']:
                http_messages = self._validate_http_parameters(parameters, service_type)
                messages.extend(http_messages)
            elif service_type == 'tcp':
                tcp_messages = self._validate_tcp_parameters(parameters)
                messages.extend(tcp_messages)
            elif service_type == 'dns':
                dns_messages = self._validate_dns_parameters(parameters)
                messages.extend(dns_messages)
            elif service_type == 'ssh':
                ssh_messages = self._validate_ssh_parameters(parameters)
                messages.extend(ssh_messages)
            
            # Check required parameters
            for required_param in profile.required_parameters:
                if required_param not in parameters:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.ERROR,
                        f"Required parameter '{required_param}' is missing for {service_type} check",
                        required_param
                    ))
        
        # Validate common network identifiers
        if 'hostname' in parameters:
            hostname_messages = self._validate_hostname(parameters['hostname'])
            messages.extend(hostname_messages)
        
        if 'port' in parameters:
            port_messages = self._validate_port(parameters['port'])
            messages.extend(port_messages)
        
        if 'url' in parameters:
            url_messages = self._validate_url(parameters['url'])
            messages.extend(url_messages)
        
        return HandlerResult(
            success=len([m for m in messages if m.severity == ValidationSeverity.ERROR]) == 0,
            parameters=parameters,
            normalized_parameters=normalized_params,
            validation_messages=messages
        )
    
    def get_parameter_info(self, parameter_name: str) -> Optional[Dict[str, Any]]:
        """Get information about network service parameters."""
        parameter_info = {
            'response_time': {
                'description': 'Response time thresholds in seconds',
                'type': 'tuple',
                'elements': ['float', 'float'],
                'example': '(1.0, 3.0)',
                'help': 'Warning and critical thresholds for response time'
            },
            'timeout': {
                'description': 'Connection/request timeout in seconds',
                'type': 'integer',
                'default': 10,
                'min_value': 1,
                'max_value': 300,
                'help': 'Maximum time to wait for connection or response'
            },
            'url': {
                'description': 'URL to monitor for HTTP/HTTPS checks',
                'type': 'string',
                'example': 'https://example.com/health',
                'help': 'Full URL including protocol, hostname, and path'
            },
            'hostname': {
                'description': 'Hostname or IP address to connect to',
                'type': 'string',
                'example': 'example.com or 192.168.1.1',
                'help': 'Target hostname or IP address'
            },
            'port': {
                'description': 'TCP port number to connect to',
                'type': 'integer',
                'min_value': 1,
                'max_value': 65535,
                'example': '80, 443, 22',
                'help': 'Target port number'
            },
            'expected_response_codes': {
                'description': 'List of acceptable HTTP response codes',
                'type': 'list',
                'elements': 'integer',
                'default': [200],
                'example': '[200, 301, 302]',
                'help': 'HTTP status codes that indicate success'
            },
            'expected_string': {
                'description': 'String that must be present in response',
                'type': 'string',
                'example': 'Welcome to our service',
                'help': 'Text that must appear in the response body'
            },
            'ssl_cert_age': {
                'description': 'SSL certificate expiry thresholds in days',
                'type': 'tuple',
                'elements': ['integer', 'integer'],
                'default': (30, 7),
                'example': '(30, 7)',
                'help': 'Warning and critical days before certificate expires'
            },
            'ssl_verify': {
                'description': 'Whether to verify SSL certificate validity',
                'type': 'boolean',
                'default': True,
                'help': 'Enable SSL certificate verification'
            },
            'follow_redirects': {
                'description': 'Whether to follow HTTP redirects',
                'type': 'boolean',
                'default': True,
                'help': 'Follow HTTP 3xx redirect responses'
            },
            'max_redirects': {
                'description': 'Maximum number of redirects to follow',
                'type': 'integer',
                'default': 5,
                'min_value': 0,
                'max_value': 20,
                'help': 'Limit on redirect chain length'
            },
            'user_agent': {
                'description': 'HTTP User-Agent header value',
                'type': 'string',
                'default': 'Checkmk-HTTP-Check',
                'help': 'User-Agent string sent with HTTP requests'
            },
            'method': {
                'description': 'HTTP request method',
                'type': 'choice',
                'choices': ['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'],
                'default': 'GET',
                'help': 'HTTP method to use for requests'
            },
            'headers': {
                'description': 'Additional HTTP headers to send',
                'type': 'dict',
                'example': '{"Authorization": "Bearer token123"}',
                'help': 'Dictionary of HTTP headers'
            },
            'post_data': {
                'description': 'Data to send with POST requests',
                'type': 'string',
                'help': 'Request body for POST/PUT requests'
            },
            'query_type': {
                'description': 'DNS query type',
                'type': 'choice',
                'choices': ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'PTR', 'SOA', 'TXT'],
                'default': 'A',
                'help': 'Type of DNS record to query'
            },
            'server': {
                'description': 'DNS server to query',
                'type': 'string',
                'example': '8.8.8.8',
                'help': 'DNS server IP address (default: system resolver)'
            },
            'expected_address': {
                'description': 'Expected IP address from DNS query',
                'type': 'string',
                'example': '192.168.1.1',
                'help': 'IP address that DNS query should return'
            }
        }
        
        return parameter_info.get(parameter_name)
    
    def suggest_parameters(
        self, 
        service_name: str, 
        current_parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Suggest network service parameter optimizations."""
        suggestions = []
        
        current = current_parameters or {}
        service_type = self._detect_service_type(service_name, context)
        profile = self.NETWORK_SERVICE_PROFILES.get(service_type)
        
        if not profile:
            return suggestions
        
        # Suggest SSL certificate monitoring for HTTPS
        if service_type == 'https' and 'ssl_cert_age' not in current:
            suggestions.append({
                'parameter': 'ssl_cert_age',
                'current_value': None,
                'suggested_value': (30, 7),
                'reason': 'Monitor SSL certificate expiry for HTTPS services',
                'impact': 'Prevent service outages due to expired certificates'
            })
        
        # Suggest response time monitoring if not configured
        if 'response_time' not in current:
            default_thresholds = profile.common_parameters.get('response_time', (1.0, 3.0))
            suggestions.append({
                'parameter': 'response_time',
                'current_value': None,
                'suggested_value': default_thresholds,
                'reason': f'Monitor response time for {service_type} service',
                'impact': 'Detect performance degradation early'
            })
        
        # Suggest expected string validation for critical services
        if 'critical' in service_name.lower() and 'expected_string' not in current:
            suggestions.append({
                'parameter': 'expected_string',
                'current_value': None,
                'suggested_value': 'OK',
                'reason': 'Add content validation for critical services',
                'impact': 'Detect partial failures and content issues'
            })
        
        # Suggest retry configuration for important services  
        if 'retry_count' not in current and any(keyword in service_name.lower() for keyword in ['prod', 'critical', 'important']):
            suggestions.append({
                'parameter': 'retry_count',
                'current_value': None,
                'suggested_value': 3,
                'reason': 'Add retry logic for important network services',
                'impact': 'Reduce false alerts from transient network issues'
            })
        
        # Service-specific suggestions
        if service_type == 'http' and current.get('method') == 'GET' and 'health' in service_name.lower():
            suggestions.append({
                'parameter': 'expected_response_codes',
                'current_value': current.get('expected_response_codes'),
                'suggested_value': [200, 204],
                'reason': 'Health checks commonly return 200 or 204',
                'impact': 'More accurate health check monitoring'
            })
        
        return suggestions
    
    def _detect_service_type(self, service_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Detect network service type from service name and context."""
        service_lower = service_name.lower()
        
        # Check context first
        if context and context.get('service_type'):
            return context['service_type']
        
        # Detect from service name patterns
        if 'https' in service_lower or 'ssl' in service_lower:
            return 'https'
        elif 'http' in service_lower or 'web' in service_lower:
            return 'http'
        elif 'tcp' in service_lower or re.search(r'port.*\d+', service_lower):
            return 'tcp'
        elif 'dns' in service_lower:
            return 'dns'
        elif 'ssh' in service_lower:
            return 'ssh'
        elif 'smtp' in service_lower or 'mail' in service_lower:
            return 'smtp'
        elif 'ftp' in service_lower:
            return 'ftp'
        
        # Check context for URL or port hints
        if context:
            if context.get('url'):
                url = context['url'].lower()
                if url.startswith('https'):
                    return 'https'
                elif url.startswith('http'):
                    return 'http'
            
            port = context.get('port')
            if port:
                port_service_map = {
                    80: 'http',
                    443: 'https',
                    22: 'ssh',
                    25: 'smtp',
                    53: 'dns',
                    21: 'ftp'
                }
                return port_service_map.get(port, 'tcp')
        
        return 'tcp'  # Default fallback
    
    def _validate_http_parameters(self, parameters: Dict[str, Any], service_type: str) -> List:
        """Validate HTTP/HTTPS-specific parameters."""
        messages = []
        
        # Validate URL
        if 'url' in parameters:
            url_messages = self._validate_url(parameters['url'])
            messages.extend(url_messages)
            
            # Check URL protocol matches service type
            if not url_messages:
                parsed = urlparse(parameters['url'])
                expected_scheme = service_type
                if parsed.scheme != expected_scheme:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.WARNING,
                        f"URL scheme '{parsed.scheme}' doesn't match service type '{service_type}'",
                        'url'
                    ))
        
        # Validate response codes
        if 'expected_response_codes' in parameters:
            codes = parameters['expected_response_codes']
            if not isinstance(codes, list):
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "expected_response_codes must be a list",
                    'expected_response_codes'
                ))
            else:
                for code in codes:
                    if not isinstance(code, int) or not 100 <= code <= 599:
                        messages.append(self._create_validation_message(
                            ValidationSeverity.ERROR,
                            f"Invalid HTTP response code: {code}",
                            'expected_response_codes'
                        ))
        
        # Validate method
        if 'method' in parameters:
            valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH']
            method_messages = self._validate_choice(
                parameters['method'],
                'method',
                valid_methods
            )
            messages.extend(method_messages)
        
        # Validate SSL-specific parameters for HTTPS
        if service_type == 'https':
            if 'ssl_cert_age' in parameters:
                cert_messages = self._validate_threshold_tuple(
                    parameters['ssl_cert_age'],
                    'ssl_cert_age',
                    numeric_type=int
                )
                messages.extend(cert_messages)
                
                if not cert_messages:
                    warn, crit = parameters['ssl_cert_age']
                    if warn <= crit:
                        messages.append(self._create_validation_message(
                            ValidationSeverity.ERROR,
                            "SSL certificate warning days must be greater than critical days",
                            'ssl_cert_age',
                            "Certificate expiry: more days = earlier warning"
                        ))
            
            if 'ssl_min_version' in parameters:
                valid_versions = ['SSLv3', 'TLSv1', 'TLSv1.1', 'TLSv1.2', 'TLSv1.3']
                ssl_version_messages = self._validate_choice(
                    parameters['ssl_min_version'],
                    'ssl_min_version',
                    valid_versions
                )
                messages.extend(ssl_version_messages)
        
        # Validate headers
        if 'headers' in parameters:
            headers = parameters['headers']
            if not isinstance(headers, dict):
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "headers must be a dictionary",
                    'headers'
                ))
            else:
                for header_name, header_value in headers.items():
                    if not isinstance(header_name, str) or not isinstance(header_value, str):
                        messages.append(self._create_validation_message(
                            ValidationSeverity.ERROR,
                            f"Header name and value must be strings: {header_name}",
                            'headers'
                        ))
        
        return messages
    
    def _validate_tcp_parameters(self, parameters: Dict[str, Any]) -> List:
        """Validate TCP-specific parameters."""
        messages = []
        
        # TCP checks require port
        if 'port' not in parameters:
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                "TCP checks require a port parameter",
                'port'
            ))
        
        # Validate refuse_state
        if 'refuse_state' in parameters:
            valid_states = ['ok', 'warning', 'critical', 'unknown']
            refuse_messages = self._validate_choice(
                parameters['refuse_state'].lower() if isinstance(parameters['refuse_state'], str) else parameters['refuse_state'],
                'refuse_state',
                valid_states
            )
            messages.extend(refuse_messages)
        
        return messages
    
    def _validate_dns_parameters(self, parameters: Dict[str, Any]) -> List:
        """Validate DNS-specific parameters."""
        messages = []
        
        # Validate query type
        if 'query_type' in parameters:
            valid_types = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'PTR', 'SOA', 'TXT', 'ANY']
            type_messages = self._validate_choice(
                parameters['query_type'].upper() if isinstance(parameters['query_type'], str) else parameters['query_type'],
                'query_type',
                valid_types
            )
            messages.extend(type_messages)
        
        # Validate DNS server
        if 'server' in parameters:
            server = parameters['server']
            if server:  # Allow None/empty for system default
                try:
                    ipaddress.ip_address(server)
                except ValueError:
                    # Could be hostname, validate as hostname
                    hostname_messages = self._validate_hostname(server)
                    if hostname_messages:
                        messages.append(self._create_validation_message(
                            ValidationSeverity.ERROR,
                            f"DNS server must be a valid IP address or hostname: {server}",
                            'server'
                        ))
        
        # Validate expected address
        if 'expected_address' in parameters:
            addr = parameters['expected_address']
            if addr:
                try:
                    ipaddress.ip_address(addr)
                except ValueError:
                    messages.append(self._create_validation_message(
                        ValidationSeverity.ERROR,
                        f"expected_address must be a valid IP address: {addr}",
                        'expected_address'
                    ))
        
        return messages
    
    def _validate_ssh_parameters(self, parameters: Dict[str, Any]) -> List:
        """Validate SSH-specific parameters."""
        messages = []
        
        # Validate protocol version
        if 'protocol_version' in parameters:
            version = str(parameters['protocol_version'])
            if version not in ['1', '2', '1,2', '2,1']:
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    f"Invalid SSH protocol version: {version}",
                    'protocol_version',
                    "Use '1', '2', or '1,2'"
                ))
        
        return messages
    
    def _validate_hostname(self, hostname: str) -> List:
        """Validate hostname or IP address."""
        messages = []
        
        if not isinstance(hostname, str) or not hostname.strip():
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                "hostname must be a non-empty string",
                'hostname'
            ))
            return messages
        
        hostname = hostname.strip()
        
        # Try to parse as IP address first
        try:
            ipaddress.ip_address(hostname)
            return messages  # Valid IP address
        except ValueError:
            pass
        
        # Validate as hostname
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', hostname):
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"Invalid hostname format: {hostname}",
                'hostname'
            ))
        elif len(hostname) > 253:
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"Hostname too long: {len(hostname)} characters (max 253)",
                'hostname'
            ))
        
        return messages
    
    def _validate_port(self, port: Any) -> List:
        """Validate port number."""
        messages = []
        
        try:
            port_num = int(port)
            if not 1 <= port_num <= 65535:
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    f"Port must be between 1 and 65535, got {port_num}",
                    'port'
                ))
        except (TypeError, ValueError):
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"Port must be an integer, got {type(port).__name__}",
                'port'
            ))
        
        return messages
    
    def _validate_url(self, url: str) -> List:
        """Validate URL format."""
        messages = []
        
        if not isinstance(url, str) or not url.strip():
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                "URL must be a non-empty string",
                'url'
            ))
            return messages
        
        try:
            parsed = urlparse(url)
            
            if not parsed.scheme:
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "URL must include a scheme (http:// or https://)",
                    'url'
                ))
            elif parsed.scheme not in ['http', 'https']:
                messages.append(self._create_validation_message(
                    ValidationSeverity.WARNING,
                    f"Unusual URL scheme: {parsed.scheme}",
                    'url'
                ))
            
            if not parsed.netloc:
                messages.append(self._create_validation_message(
                    ValidationSeverity.ERROR,
                    "URL must include a hostname",
                    'url'
                ))
            
        except Exception as e:
            messages.append(self._create_validation_message(
                ValidationSeverity.ERROR,
                f"Invalid URL format: {e}",
                'url'
            ))
        
        return messages
    
    def _parse_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Parse URL and extract components for parameters."""
        try:
            parsed = urlparse(url)
            result = {
                'url': url,
                'hostname': parsed.hostname,
                'scheme': parsed.scheme
            }
            
            if parsed.port:
                result['port'] = parsed.port
            elif parsed.scheme == 'https':
                result['port'] = 443
            elif parsed.scheme == 'http':
                result['port'] = 80
            
            return result
        except Exception:
            return None