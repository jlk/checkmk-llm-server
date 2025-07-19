"""Enhanced command parsing with fuzzy matching and intent detection."""

import re
import difflib
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass


@dataclass
class CommandIntent:
    """Represents a parsed command intent."""
    command: str
    confidence: float
    parameters: Dict[str, Any]
    suggestions: List[str]
    is_help_request: bool = False
    help_topic: Optional[str] = None


class CommandParser:
    """Enhanced command parser with fuzzy matching and intent detection."""
    
    def __init__(self):
        """Initialize the command parser."""
        self.command_aliases = {
            'ls': 'list',
            'rm': 'delete',
            'del': 'delete',
            'show': 'list',
            'display': 'list',
            'find': 'list',
            'search': 'list',
            'like': 'list',
            'containing': 'list',
            'matching': 'list',
            'similar': 'list',
            'create': 'create',
            'add': 'create',
            'new': 'create',
            'remove': 'delete',
            'destroy': 'delete',
            'ack': 'acknowledge',
            'downtime': 'downtime',
            'dt': 'downtime',
            'discover': 'discover',
            'scan': 'discover',
            'stats': 'stats',
            'statistics': 'stats',
            'info': 'get',
            'details': 'get',
            'test': 'test',
            'check': 'test',
            'help': 'help',
            'h': 'help',
            '?': 'help',
            'man': 'help',
            'quit': 'quit',
            'exit': 'quit',
            'q': 'quit',
        }
        
        self.host_commands = {
            'list', 'create', 'delete', 'get', 'show', 'display', 'stats', 'test', 'find', 'search'
        }
        
        self.service_commands = {
            'list', 'status', 'acknowledge', 'downtime', 'discover', 'stats', 'ack', 'dt'
        }
        
        self.help_patterns = [
            r'^\?$',  # Just ?
            r'^\?\s+(.+)$',  # ? command
            r'^help$',  # help
            r'^help\s+(.+)$',  # help command
            r'^h$',  # h
            r'^h\s+(.+)$',  # h command
            r'^man\s+(.+)$',  # man command
        ]
    
    def parse_command(self, user_input: str) -> CommandIntent:
        """Parse user input into a command intent.
        
        Args:
            user_input: Raw user input string
            
        Returns:
            CommandIntent object with parsed information
        """
        user_input = user_input.strip()
        
        if not user_input:
            return CommandIntent(
                command='',
                confidence=0.0,
                parameters={},
                suggestions=[]
            )
        
        # Check for help requests first
        help_result = self._parse_help_request(user_input)
        if help_result:
            return help_result
        
        # Handle special commands
        if user_input.lower() in ['exit', 'quit', 'q']:
            return CommandIntent(
                command='quit',
                confidence=1.0,
                parameters={},
                suggestions=[]
            )
        
        # Handle theme commands
        if user_input.lower().startswith('theme'):
            return CommandIntent(
                command=user_input.lower(),
                confidence=1.0,
                parameters={},
                suggestions=[]
            )
        
        # Handle color commands
        if user_input.lower().startswith('colors') or user_input.lower().startswith('color '):
            return CommandIntent(
                command=user_input.lower(),
                confidence=1.0,
                parameters={},
                suggestions=[]
            )
        
        # Parse natural language command
        return self._parse_natural_language(user_input)
    
    def _parse_help_request(self, user_input: str) -> Optional[CommandIntent]:
        """Parse help request patterns.
        
        Args:
            user_input: User input string
            
        Returns:
            CommandIntent for help request or None if not a help request
        """
        for pattern in self.help_patterns:
            match = re.match(pattern, user_input, re.IGNORECASE)
            if match:
                help_topic = match.group(1) if match.lastindex else None
                
                return CommandIntent(
                    command='help',
                    confidence=1.0,
                    parameters={'topic': help_topic},
                    suggestions=[],
                    is_help_request=True,
                    help_topic=help_topic
                )
        
        return None
    
    def _parse_natural_language(self, user_input: str) -> CommandIntent:
        """Parse natural language commands.
        
        Args:
            user_input: User input string
            
        Returns:
            CommandIntent object
        """
        tokens = user_input.lower().split()
        
        # Extract command from tokens
        command, confidence = self._extract_command(tokens)
        
        # Extract parameters
        parameters = self._extract_parameters(user_input, tokens, command)
        
        # Generate suggestions for low confidence commands
        suggestions = []
        if confidence < 0.8:
            suggestions = self._generate_suggestions(user_input, tokens)
        
        return CommandIntent(
            command=command,
            confidence=confidence,
            parameters=parameters,
            suggestions=suggestions
        )
    
    def _extract_command(self, tokens: List[str]) -> Tuple[str, float]:
        """Extract command from tokens with confidence scoring.
        
        Args:
            tokens: List of input tokens
            
        Returns:
            Tuple of (command, confidence_score)
        """
        if not tokens:
            return '', 0.0
        
        # Check for direct command matches
        for token in tokens:
            if token in self.command_aliases:
                return self.command_aliases[token], 1.0
        
        # Check for search patterns that should map to list even if 'called' isn't in aliases
        if any(token in ['called', 'named'] for token in tokens):
            return 'list', 0.9
        
        # Check for fuzzy matches
        all_commands = set(self.command_aliases.keys()) | set(self.command_aliases.values())
        
        for token in tokens:
            matches = difflib.get_close_matches(token, all_commands, n=1, cutoff=0.6)
            if matches:
                matched_command = matches[0]
                confidence = difflib.SequenceMatcher(None, token, matched_command).ratio()
                
                # Resolve alias if needed
                if matched_command in self.command_aliases:
                    matched_command = self.command_aliases[matched_command]
                
                return matched_command, confidence
        
        # Check for action patterns
        text = ' '.join(tokens)
        
        # Host operations
        if any(word in text for word in ['host', 'server', 'machine']):
            if any(word in text for word in ['list', 'show', 'display', 'all', 'like', 'containing', 'matching', 'similar', 'find', 'search']):
                return 'list', 0.8
            elif any(word in text for word in ['create', 'add', 'new']):
                return 'create', 0.8
            elif any(word in text for word in ['delete', 'remove', 'destroy']):
                return 'delete', 0.8
            elif any(word in text for word in ['details', 'info', 'get']):
                return 'get', 0.8
        
        # Search operations (even without explicit host/server keywords)
        if any(word in text for word in ['like', 'containing', 'matching', 'similar', 'find', 'search']):
            return 'list', 0.7
        
        # Service operations
        if any(word in text for word in ['service', 'services']):
            if any(word in text for word in ['list', 'show', 'display']):
                return 'list', 0.8
            elif any(word in text for word in ['acknowledge', 'ack']):
                return 'acknowledge', 0.8
            elif any(word in text for word in ['downtime', 'dt']):
                return 'downtime', 0.8
            elif any(word in text for word in ['discover', 'find', 'scan']):
                return 'discover', 0.8
        
        # Default to first token as command
        return tokens[0], 0.3
    
    def _extract_parameters(self, user_input: str, tokens: List[str], command: str) -> Dict[str, Any]:
        """Extract parameters from user input.
        
        Args:
            user_input: Original user input
            tokens: Tokenized input
            command: Detected command
            
        Returns:
            Dictionary of extracted parameters
        """
        parameters = {}
        text = user_input.lower()
        
        # Extract host names (look for server names, IP addresses)
        host_pattern = r'(?:host|server|machine)\s+(\w+)'
        host_match = re.search(host_pattern, text)
        if host_match:
            parameters['host_name'] = host_match.group(1)
        
        # Extract search terms from "like", "containing", "matching", "similar to" patterns
        search_patterns = [
            r'(?:hosts?|servers?|machines?)\s+(?:like|containing|matching|similar\s+to)\s+([\w\-\.]+)',
            r'(?:like|containing|matching|similar\s+to)\s+([\w\-\.]+)',
            r'(?:with|named?)\s+([\w\-\.]+)',
            r'(?:called|named)\s+([\w\-\.]+)',
            r'(?:with\s+name)\s+([\w\-\.]+)'
        ]
        
        for pattern in search_patterns:
            search_match = re.search(pattern, text, re.IGNORECASE)
            if search_match:
                parameters['search_term'] = search_match.group(1)
                break
        
        # Extract service names (look for service descriptions)
        service_pattern = r'(?:service|services)\s+(.+?)(?:\s+(?:on|for|of)\s+|$)'
        service_match = re.search(service_pattern, text)
        if service_match:
            parameters['service_description'] = service_match.group(1).strip()
        
        # Extract service names from parameter patterns like "parameters for X on Y" or "parameters for X for Y"
        param_patterns = [
            r'(?:parameters?|thresholds?)\s+for\s+["\']?([^"\']+?)["\']?\s+on\s+([\w\-\.]+)',
            r'(?:parameters?|thresholds?)\s+for\s+["\']?([^"\']+?)["\']?\s+for\s+([\w\-\.]+)',
            r'(?:parameters?|thresholds?)\s+(?:values?\s+)?for\s+([\w\s]+?)\s+on\s+([\w\-\.]+)',
            r'(?:parameters?|thresholds?)\s+(?:values?\s+)?for\s+([\w\s]+?)\s+for\s+([\w\-\.]+)'
        ]
        
        for pattern in param_patterns:
            param_match = re.search(pattern, text, re.IGNORECASE)
            if param_match:
                parameters['service_description'] = param_match.group(1).strip()
                parameters['host_name'] = param_match.group(2).strip()
                break
        
        # Extract folder paths
        folder_pattern = r'(?:folder|path)\s+([/\w]+)'
        folder_match = re.search(folder_pattern, text)
        if folder_match:
            parameters['folder'] = folder_match.group(1)
        
        # Extract IP addresses
        ip_pattern = r'(?:ip|address)\s+(\d+\.\d+\.\d+\.\d+)'
        ip_match = re.search(ip_pattern, text)
        if ip_match:
            parameters['ip'] = ip_match.group(1)
        
        # Extract time durations
        time_pattern = r'(\d+)\s+(?:hour|hours|hr|hrs|h)'
        time_match = re.search(time_pattern, text)
        if time_match:
            parameters['hours'] = int(time_match.group(1))
        
        # Extract comments
        comment_pattern = r'(?:comment|note|message)\s+["\'](.+?)["\']'
        comment_match = re.search(comment_pattern, text)
        if comment_match:
            parameters['comment'] = comment_match.group(1)
        
        # Extract specific service names from common patterns
        if 'cpu' in text:
            parameters['service_description'] = 'CPU utilization'
        elif 'memory' in text:
            parameters['service_description'] = 'Memory'
        elif 'disk' in text:
            parameters['service_description'] = 'Filesystem /'
        elif 'network' in text:
            parameters['service_description'] = 'Network Interface'
        
        return parameters
    
    def _generate_suggestions(self, user_input: str, tokens: List[str]) -> List[str]:
        """Generate command suggestions for unclear input.
        
        Args:
            user_input: Original user input
            tokens: Tokenized input
            
        Returns:
            List of suggested commands
        """
        suggestions = []
        
        # Get close matches for all tokens
        all_commands = set(self.command_aliases.keys()) | set(self.command_aliases.values())
        
        for token in tokens:
            matches = difflib.get_close_matches(token, all_commands, n=3, cutoff=0.4)
            for match in matches:
                if match in self.command_aliases:
                    match = self.command_aliases[match]
                if match not in suggestions:
                    suggestions.append(match)
        
        # Add context-based suggestions
        text = user_input.lower()
        
        if any(word in text for word in ['host', 'server', 'machine']):
            suggestions.extend(['list hosts', 'create host', 'delete host', 'get host'])
        
        if any(word in text for word in ['service', 'services']):
            suggestions.extend(['list services', 'acknowledge service', 'downtime service', 'discover services'])
        
        return suggestions[:5]  # Limit to 5 suggestions
    
    def get_command_type(self, command: str, parameters: dict = None, original_input: str = "") -> str:
        """Determine if command is host or service related based on command and context.
        
        Args:
            command: Command string
            parameters: Command parameters (may contain service_description)
            original_input: Original user input for context
            
        Returns:
            'host', 'service', or 'general'
        """
        # Check parameters for service indicators
        if parameters and 'service_description' in parameters:
            return 'service'
        
        # Check original input for explicit keywords
        if original_input:
            original_lower = original_input.lower()
            
            # Check for explicit service keywords
            service_keywords = ['service', 'services', 'acknowledge', 'downtime', 'discover', 'cpu', 'disk', 'memory', 'load', 'parameters', 'parameter', 'threshold', 'thresholds']
            if any(keyword in original_lower for keyword in service_keywords):
                return 'service'
            
            # Check for explicit host keywords
            host_keywords = ['host', 'hosts', 'server', 'servers', 'machine', 'machines']
            if any(keyword in original_lower for keyword in host_keywords):
                return 'host'
        
        # For ambiguous commands (like 'list'), use context to decide
        if command == 'list':
            # If no specific context, default to host for 'list' commands
            # This handles cases like "list hosts" vs "list services"
            if original_input:
                original_lower = original_input.lower()
                if 'service' in original_lower:
                    return 'service'
                elif 'host' in original_lower or not any(s in original_lower for s in ['service']):
                    return 'host'
            return 'host'  # Default 'list' to host operations
        
        # Check command against defined sets (service-specific commands first)
        service_only_commands = {'acknowledge', 'downtime', 'discover', 'ack', 'dt'}
        if command in service_only_commands:
            return 'service'
        elif command in self.host_commands:
            return 'host'
        else:
            return 'general'