"""LLM-based command analysis and parsing."""

import json
import logging
import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from .base import CommandContext
from ..llm_client import LLMClient


@dataclass
class AnalysisResult:
    """Result of command analysis."""
    action: str
    parameters: Dict[str, Any]
    confidence: float = 1.0
    source: str = "llm"  # 'llm', 'pattern', 'cache'
    raw_response: Optional[str] = None


class LLMResponseValidator:
    """Validates LLM responses for command analysis."""
    
    REQUIRED_FIELDS = ['action', 'parameters']
    VALID_ACTIONS = [
        # Service operations
        'list_services', 'show_services', 'get_services',
        'get_service_status', 'service_status', 'check_service',
        'acknowledge_service', 'ack_service', 'acknowledge',
        'create_downtime', 'schedule_downtime', 'downtime',
        'discover_services', 'service_discovery', 'discover',
        'get_service_statistics', 'service_stats', 'stats',
        
        # Parameter operations
        'view_default_parameters', 'show_default_parameters', 'default_parameters',
        'view_service_parameters', 'show_service_parameters', 'service_parameters', 'show_parameters',
        'set_service_parameters', 'override_parameters', 'set_parameters', 'override_service',
        'create_parameter_rule', 'create_rule',
        'list_parameter_rules', 'show_rules', 'list_rules',
        'delete_parameter_rule', 'delete_rule',
        'discover_ruleset', 'find_ruleset',
        
        # Utility operations
        'get_instructions', 'instructions', 'help', 'how_to',
        'test_connection', 'test', 'ping'
    ]
    
    def validate(self, response: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate LLM response structure and content.
        
        Args:
            response: LLM response dictionary
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in response:
                return False, f"Missing required field: {field}"
        
        # Validate action
        action = response.get('action')
        if action not in self.VALID_ACTIONS:
            return False, f"Invalid action: {action}"
        
        # Validate parameters structure
        parameters = response.get('parameters', {})
        if not isinstance(parameters, dict):
            return False, "Parameters must be a dictionary"
        
        return True, None


class PatternMatcher:
    """Pattern-based command matching for common commands."""
    
    def __init__(self):
        self.patterns = [
            # Service operations
            (r'list services(?:\s+for\s+(\w+))?', 'list_services', {'host_name': 1}),
            (r'show services(?:\s+for\s+(\w+))?', 'list_services', {'host_name': 1}),
            (r'get services(?:\s+for\s+(\w+))?', 'list_services', {'host_name': 1}),
            
            (r'(?:check|status)\s+(.+?)\s+on\s+(\w+)', 'get_service_status', 
             {'service_description': 1, 'host_name': 2}),
            
            (r'acknowledge\s+(.+?)\s+on\s+(\w+)(?:\s+(?:with\s+)?comment\s+["\']([^"\']+)["\'])?',
             'acknowledge_service', 
             {'service_description': 1, 'host_name': 2, 'comment': 3}),
            
            (r'ack\s+(.+?)\s+on\s+(\w+)(?:\s+(?:with\s+)?comment\s+["\']([^"\']+)["\'])?',
             'acknowledge_service',
             {'service_description': 1, 'host_name': 2, 'comment': 3}),
            
            (r'(?:create|schedule)\s+(\d+)\s+hour[s]?\s+downtime\s+for\s+(.+?)\s+on\s+(\w+)',
             'create_downtime',
             {'duration_hours': 1, 'service_description': 2, 'host_name': 3}),
            
            (r'discover\s+services\s+on\s+(\w+)', 'discover_services', {'host_name': 1}),
            
            (r'(?:service\s+)?(?:stats|statistics)', 'get_service_statistics', {}),
            
            # Parameter operations  
            (r'show\s+default\s+(\w+)\s+parameters', 'view_default_parameters', {'service_type': 1}),
            (r'(?:show|view)\s+parameters\s+for\s+(.+?)\s+on\s+(\w+)', 'view_service_parameters',
             {'service_description': 1, 'host_name': 2}),
            
            (r'set\s+(\w+)\s+warning\s+to\s+(\d+)%?\s+for\s+(\w+)', 'set_service_parameters',
             {'service_description': 1, 'warning_value': 2, 'host_name': 3, 'parameter_type': 'warning'}),
            
            (r'set\s+(\w+)\s+critical\s+to\s+(\d+)%?\s+for\s+(\w+)', 'set_service_parameters',
             {'service_description': 1, 'critical_value': 2, 'host_name': 3, 'parameter_type': 'critical'}),
            
            # Utility operations
            (r'(?:test|ping)\s+connection', 'test_connection', {}),
            (r'help(?:\s+(\w+))?', 'help', {'command_name': 1}),
        ]
    
    def match(self, user_input: str) -> Optional[AnalysisResult]:
        """Try to match user input against known patterns.
        
        Args:
            user_input: User's input string
            
        Returns:
            AnalysisResult if matched, None otherwise
        """
        user_input_lower = user_input.lower().strip()
        
        for pattern, action, param_mapping in self.patterns:
            match = re.match(pattern, user_input_lower)
            if match:
                parameters = {}
                
                for param_name, group_index in param_mapping.items():
                    if isinstance(group_index, int) and group_index <= len(match.groups()):
                        value = match.group(group_index)
                        if value:
                            # Type conversion for numeric parameters
                            if param_name in ['duration_hours', 'warning_value', 'critical_value']:
                                try:
                                    value = float(value)
                                except ValueError:
                                    pass
                            parameters[param_name] = value
                    elif isinstance(group_index, str):
                        parameters[param_name] = group_index
                
                return AnalysisResult(
                    action=action,
                    parameters=parameters,
                    confidence=0.9,
                    source="pattern"
                )
        
        return None


class LLMCommandAnalyzer:
    """Analyzes user commands using LLM with caching and fallback strategies."""
    
    def __init__(self, llm_client: LLMClient, cache_ttl: int = 300):
        """Initialize the analyzer.
        
        Args:
            llm_client: LLM client for analysis
            cache_ttl: Cache time-to-live in seconds
        """
        self.llm_client = llm_client
        self.cache_ttl = cache_ttl
        self.logger = logging.getLogger(__name__)
        
        # Components
        self.validator = LLMResponseValidator()
        self.pattern_matcher = PatternMatcher()
        
        # Cache for analysis results
        self._cache: Dict[str, Tuple[AnalysisResult, datetime]] = {}
    
    def analyze_command(self, user_input: str) -> AnalysisResult:
        """Analyze user command with multiple strategies.
        
        Args:
            user_input: User's input string
            
        Returns:
            AnalysisResult with action and parameters
        """
        user_input = user_input.strip()
        
        # 1. Check cache first
        cached_result = self._get_cached_result(user_input)
        if cached_result:
            self.logger.debug(f"Cache hit for: {user_input}")
            return cached_result
        
        # 2. Try pattern matching
        pattern_result = self.pattern_matcher.match(user_input)
        if pattern_result:
            self.logger.debug(f"Pattern match for: {user_input}")
            self._cache_result(user_input, pattern_result)
            return pattern_result
        
        # 3. Fall back to LLM analysis
        llm_result = self._analyze_with_llm(user_input)
        self._cache_result(user_input, llm_result)
        return llm_result
    
    def _get_cached_result(self, user_input: str) -> Optional[AnalysisResult]:
        """Get cached analysis result if valid.
        
        Args:
            user_input: User's input string
            
        Returns:
            Cached AnalysisResult if valid, None otherwise
        """
        if user_input not in self._cache:
            return None
        
        result, timestamp = self._cache[user_input]
        
        # Check if cache entry is still valid
        if datetime.now() - timestamp > timedelta(seconds=self.cache_ttl):
            del self._cache[user_input]
            return None
        
        # Return copy with updated source
        result.source = "cache"
        return result
    
    def _cache_result(self, user_input: str, result: AnalysisResult) -> None:
        """Cache an analysis result.
        
        Args:
            user_input: User's input string
            result: Analysis result to cache
        """
        self._cache[user_input] = (result, datetime.now())
        
        # Limit cache size
        if len(self._cache) > 100:
            # Remove oldest entries
            oldest_keys = sorted(self._cache.keys(), 
                               key=lambda k: self._cache[k][1])[:20]
            for key in oldest_keys:
                del self._cache[key]
    
    def _analyze_with_llm(self, user_input: str) -> AnalysisResult:
        """Analyze command using LLM.
        
        Args:
            user_input: User's input string
            
        Returns:
            AnalysisResult from LLM analysis
        """
        prompt = self._build_analysis_prompt(user_input)
        
        try:
            response = self.llm_client.chat_completion(prompt)
            parsed_response = self._parse_llm_response(response)
            
            # Validate response
            is_valid, error_msg = self.validator.validate(parsed_response)
            if not is_valid:
                self.logger.warning(f"Invalid LLM response: {error_msg}")
                return self._create_fallback_result(user_input, error_msg)
            
            return AnalysisResult(
                action=parsed_response['action'],
                parameters=parsed_response.get('parameters', {}),
                confidence=0.8,
                source="llm",
                raw_response=response
            )
            
        except Exception as e:
            self.logger.error(f"LLM analysis failed: {e}")
            return self._create_fallback_result(user_input, str(e))
    
    def _build_analysis_prompt(self, user_input: str) -> str:
        """Build prompt for LLM analysis.
        
        Args:
            user_input: User's input string
            
        Returns:
            Formatted prompt string
        """
        return f"""
        Analyze this service-related command and extract the intent and parameters. You must return ONLY valid JSON.
        
        Command: "{user_input}"
        
        IMPORTANT: Determine if the user wants to PERFORM an action or GET INFORMATION/INSTRUCTIONS.
        
        Use EXACTLY one of these actions:
        - list_services: List services for a host or all services  
        - get_service_status: Get status of specific services
        - acknowledge_service: Acknowledge service problems
        - create_downtime: Create/schedule downtime for services
        - discover_services: ONLY when user explicitly wants to run discovery
        - get_service_statistics: Get service statistics
        - view_default_parameters: View default parameters for a service type
        - view_service_parameters: View effective parameters for a specific service
        - set_service_parameters: Set/override parameters for a service
        - create_parameter_rule: Create a new parameter rule
        - list_parameter_rules: List existing parameter rules
        - delete_parameter_rule: Delete a parameter rule
        - discover_ruleset: Find the appropriate ruleset for a service
        - get_instructions: When user asks HOW TO do something or wants instructions
        - test_connection: Test API connection
        - help: Show help information
        
        Return ONLY this JSON format:
        {{
            "action": "one_of_the_exact_actions_above",
            "parameters": {{
                "host_name": "hostname or null",
                "service_description": "service name or null",
                "comment": "comment text or null",
                "duration_hours": number_or_null,
                "mode": "discovery mode or null",
                "instruction_type": "what they want to know how to do or null",
                "service_type": "cpu|memory|disk|filesystem|network or null",
                "parameter_type": "warning|critical|both or null",
                "threshold_value": number_or_null,
                "warning_value": number_or_null,
                "critical_value": number_or_null,
                "ruleset_name": "specific ruleset or null",
                "rule_id": "rule_id or null",
                "command_name": "command for help or null",
                "category": "category for help or null"
            }}
        }}
        
        Examples:
        - "list services for server01" -> {{"action": "list_services", "parameters": {{"host_name": "server01"}}}}
        - "acknowledge CPU load on server01" -> {{"action": "acknowledge_service", "parameters": {{"host_name": "server01", "service_description": "CPU load", "comment": "Working on it"}}}}
        - "set CPU warning to 85% for server01" -> {{"action": "set_service_parameters", "parameters": {{"host_name": "server01", "service_description": "CPU utilization", "parameter_type": "warning", "warning_value": 85}}}}
        """
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response and extract JSON.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Parsed dictionary
            
        Raises:
            json.JSONDecodeError: If JSON cannot be parsed
        """
        response_clean = response.strip()
        
        # If response contains markdown code blocks, extract the JSON
        if '```json' in response_clean:
            start = response_clean.find('```json') + 7
            end = response_clean.find('```', start)
            if end != -1:
                response_clean = response_clean[start:end].strip()
        elif '```' in response_clean:
            start = response_clean.find('```') + 3
            end = response_clean.find('```', start)
            if end != -1:
                response_clean = response_clean[start:end].strip()
        
        # Try to find JSON object in the response
        if not response_clean.startswith('{'):
            # Look for the first { and last }
            start = response_clean.find('{')
            end = response_clean.rfind('}')
            if start != -1 and end != -1 and end > start:
                response_clean = response_clean[start:end+1]
        
        return json.loads(response_clean)
    
    def _create_fallback_result(self, user_input: str, error: str) -> AnalysisResult:
        """Create a fallback result when analysis fails.
        
        Args:
            user_input: Original user input
            error: Error message
            
        Returns:
            Fallback AnalysisResult
        """
        # Try to extract some basic info from the input
        if any(word in user_input.lower() for word in ['list', 'show', 'get']):
            action = 'list_services'
        elif any(word in user_input.lower() for word in ['acknowledge', 'ack']):
            action = 'acknowledge_service'
        elif any(word in user_input.lower() for word in ['downtime', 'schedule']):
            action = 'create_downtime'
        elif any(word in user_input.lower() for word in ['help', '?']):
            action = 'help'
        else:
            action = 'get_instructions'
        
        return AnalysisResult(
            action=action,
            parameters={'instruction_type': 'general', 'error': error},
            confidence=0.1,
            source="fallback"
        )
    
    def clear_cache(self) -> None:
        """Clear the analysis cache."""
        self._cache.clear()
        self.logger.debug("Cleared analysis cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        valid_entries = 0
        expired_entries = 0
        now = datetime.now()
        
        for _, (_, timestamp) in self._cache.items():
            if now - timestamp <= timedelta(seconds=self.cache_ttl):
                valid_entries += 1
            else:
                expired_entries += 1
        
        return {
            'total_entries': len(self._cache),
            'valid_entries': valid_entries,
            'expired_entries': expired_entries,
            'cache_ttl': self.cache_ttl
        }