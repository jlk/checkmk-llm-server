"""Tab completion functionality for interactive mode."""

import os
from typing import List, Optional, Callable, Dict, Any
from functools import lru_cache


class TabCompleter:
    """Tab completion handler for interactive mode."""
    
    def __init__(self, checkmk_client=None, help_system=None):
        """Initialize tab completer.
        
        Args:
            checkmk_client: CheckmkClient instance for dynamic completions
            help_system: HelpSystem instance for command completions
        """
        self.checkmk_client = checkmk_client
        self.help_system = help_system
        
        # Static completions
        self.base_commands = [
            'help', 'h', '?', 'man',
            'list', 'show', 'display', 'ls',
            'create', 'add', 'new',
            'delete', 'remove', 'destroy', 'rm', 'del',
            'get', 'info', 'details',
            'acknowledge', 'ack',
            'downtime', 'dt',
            'discover', 'find', 'scan',
            'stats', 'statistics',
            'test', 'check',
            'exit', 'quit', 'q'
        ]
        
        self.host_related = [
            'hosts', 'host', 'server', 'machine', 'servers', 'machines'
        ]
        
        self.service_related = [
            'services', 'service', 'svc'
        ]
        
        self.common_services = [
            'CPU utilization', 'Memory', 'Filesystem /', 'Network Interface',
            'Disk IO', 'Load', 'Uptime', 'Process', 'Temperature'
        ]
        
        self.common_folders = [
            '/', '/web', '/database', '/applications', '/network', '/servers'
        ]
        
        self.prepositions = [
            'on', 'for', 'in', 'with', 'from', 'to', 'of', 'at', 'by'
        ]
        
        self.time_units = [
            'hour', 'hours', 'hr', 'hrs', 'h',
            'minute', 'minutes', 'min', 'mins', 'm',
            'second', 'seconds', 'sec', 'secs', 's'
        ]
        
        # Cache for dynamic completions
        self._host_cache = None
        self._service_cache = {}
        self._cache_timeout = 300  # 5 minutes
        self._last_cache_time = 0
    
    def complete(self, text: str, state: int) -> Optional[str]:
        """Main completion function for readline.
        
        Args:
            text: Current text to complete
            state: Completion state (0 for first call, 1+ for subsequent)
            
        Returns:
            Completion suggestion or None
        """
        if state == 0:
            # First call - generate all completions
            self.matches = self._generate_completions(text)
        
        try:
            return self.matches[state]
        except IndexError:
            return None
    
    def _generate_completions(self, text: str) -> List[str]:
        """Generate all possible completions for the given text.
        
        Args:
            text: Text to complete
            
        Returns:
            List of completion suggestions
        """
        import readline
        
        # Get the full line to understand context
        line = readline.get_line_buffer()
        begin_idx = readline.get_begidx()
        end_idx = readline.get_endidx()
        
        # Split line into tokens
        tokens = line[:begin_idx].split()
        current_token = text
        
        # Determine what type of completion to provide
        if not tokens:
            # First word - complete commands
            return self._complete_commands(current_token)
        
        # Context-aware completion based on previous tokens
        return self._complete_contextual(tokens, current_token)
    
    def _complete_commands(self, text: str) -> List[str]:
        """Complete command names.
        
        Args:
            text: Partial command text
            
        Returns:
            List of matching commands
        """
        matches = []
        
        # Base commands
        for cmd in self.base_commands:
            if cmd.startswith(text):
                matches.append(cmd)
        
        # Host and service related words
        for word in self.host_related + self.service_related:
            if word.startswith(text):
                matches.append(word)
        
        # Help system suggestions
        if self.help_system:
            help_suggestions = self.help_system.get_command_suggestions(text)
            for suggestion in help_suggestions:
                if suggestion not in matches:
                    matches.append(suggestion)
        
        return sorted(matches)
    
    def _complete_contextual(self, tokens: List[str], text: str) -> List[str]:
        """Complete based on context from previous tokens.
        
        Args:
            tokens: Previous tokens in the command
            text: Current text to complete
            
        Returns:
            List of contextual completions
        """
        matches = []
        
        # Convert tokens to lowercase for matching
        lower_tokens = [t.lower() for t in tokens]
        
        # Help command completions
        if lower_tokens[0] in ['help', 'h', '?', 'man']:
            return self._complete_help_topics(text)
        
        # Host-related completions
        if any(word in lower_tokens for word in ['host', 'hosts', 'server', 'servers']):
            matches.extend(self._complete_host_context(lower_tokens, text))
        
        # Service-related completions
        if any(word in lower_tokens for word in ['service', 'services', 'svc']):
            matches.extend(self._complete_service_context(lower_tokens, text))
        
        # Folder completions
        if 'folder' in lower_tokens or 'path' in lower_tokens:
            matches.extend(self._complete_folders(text))
        
        # Time completions
        if any(word in lower_tokens for word in ['downtime', 'dt']) or text.isdigit():
            matches.extend(self._complete_time_units(text))
        
        # Preposition completions
        if not text or text.isspace():
            matches.extend(self.prepositions)
        
        # Common word completions
        matches.extend(self._complete_common_words(lower_tokens, text))
        
        return sorted(list(set(matches)))
    
    def _complete_help_topics(self, text: str) -> List[str]:
        """Complete help topics.
        
        Args:
            text: Partial topic text
            
        Returns:
            List of matching help topics
        """
        if not self.help_system:
            return []
        
        return self.help_system.get_command_suggestions(text)
    
    def _complete_host_context(self, tokens: List[str], text: str) -> List[str]:
        """Complete in host-related context.
        
        Args:
            tokens: Previous tokens
            text: Current text to complete
            
        Returns:
            List of host-related completions
        """
        matches = []
        
        # Host names
        if 'on' in tokens or 'for' in tokens or not text.startswith('/'):
            matches.extend(self._get_host_names(text))
        
        # Folder paths
        if 'folder' in tokens or 'in' in tokens or text.startswith('/'):
            matches.extend(self._complete_folders(text))
        
        # IP addresses (placeholder)
        if 'ip' in tokens or 'address' in tokens:
            matches.extend(['192.168.1.', '10.0.0.', '172.16.0.'])
        
        return matches
    
    def _complete_service_context(self, tokens: List[str], text: str) -> List[str]:
        """Complete in service-related context.
        
        Args:
            tokens: Previous tokens
            text: Current text to complete
            
        Returns:
            List of service-related completions
        """
        matches = []
        
        # Service names
        if 'on' in tokens or 'for' in tokens:
            # Look for host name in tokens
            host_name = None
            for i, token in enumerate(tokens):
                if token in ['on', 'for'] and i + 1 < len(tokens):
                    host_name = tokens[i + 1]
                    break
            
            if host_name:
                matches.extend(self._get_service_names(host_name, text))
            else:
                matches.extend(self._complete_common_services(text))
        
        # Host names when completing "service on <host>"
        if tokens and tokens[-1] in ['on', 'for']:
            matches.extend(self._get_host_names(text))
        
        return matches
    
    def _complete_folders(self, text: str) -> List[str]:
        """Complete folder paths.
        
        Args:
            text: Partial folder path
            
        Returns:
            List of matching folder paths
        """
        matches = []
        
        # Common folders
        for folder in self.common_folders:
            if folder.startswith(text):
                matches.append(folder)
        
        # File system completion for paths starting with /
        if text.startswith('/'):
            matches.extend(self._complete_file_path(text))
        
        return matches
    
    def _complete_time_units(self, text: str) -> List[str]:
        """Complete time units.
        
        Args:
            text: Partial time unit
            
        Returns:
            List of matching time units
        """
        matches = []
        
        for unit in self.time_units:
            if unit.startswith(text):
                matches.append(unit)
        
        return matches
    
    def _complete_common_words(self, tokens: List[str], text: str) -> List[str]:
        """Complete common words based on context.
        
        Args:
            tokens: Previous tokens
            text: Current text to complete
            
        Returns:
            List of common word completions
        """
        matches = []
        
        # Action words
        if not tokens:
            action_words = ['list', 'show', 'create', 'delete', 'acknowledge', 'downtime']
            matches.extend([w for w in action_words if w.startswith(text)])
        
        # Object words
        if tokens and tokens[-1] in ['list', 'show', 'create', 'delete']:
            object_words = ['hosts', 'services', 'host', 'service']
            matches.extend([w for w in object_words if w.startswith(text)])
        
        return matches
    
    def _complete_common_services(self, text: str) -> List[str]:
        """Complete common service names.
        
        Args:
            text: Partial service name
            
        Returns:
            List of matching service names
        """
        matches = []
        
        for service in self.common_services:
            if service.lower().startswith(text.lower()):
                matches.append(service)
        
        return matches
    
    def _complete_file_path(self, text: str) -> List[str]:
        """Complete file system paths.
        
        Args:
            text: Partial file path
            
        Returns:
            List of matching paths
        """
        matches = []
        
        try:
            # Get directory part
            if text.endswith('/'):
                directory = text
                prefix = ''
            else:
                directory = os.path.dirname(text)
                prefix = os.path.basename(text)
            
            if not directory:
                directory = '/'
            
            # List directory contents
            if os.path.isdir(directory):
                for item in os.listdir(directory):
                    if item.startswith(prefix):
                        full_path = os.path.join(directory, item)
                        if os.path.isdir(full_path):
                            matches.append(full_path + '/')
                        else:
                            matches.append(full_path)
        
        except (OSError, PermissionError):
            # Ignore errors and return empty list
            pass
        
        return matches
    
    @lru_cache(maxsize=128)
    def _get_host_names(self, prefix: str = '') -> List[str]:
        """Get host names from Checkmk API.
        
        Args:
            prefix: Optional prefix to filter hosts
            
        Returns:
            List of matching host names
        """
        if not self.checkmk_client:
            return []
        
        try:
            # Use cached hosts if available and recent
            import time
            current_time = time.time()
            
            if (self._host_cache is None or 
                current_time - self._last_cache_time > self._cache_timeout):
                
                hosts = self.checkmk_client.list_hosts()
                self._host_cache = [host.get('id', '') for host in hosts]
                self._last_cache_time = current_time
            
            # Filter by prefix
            if prefix:
                return [host for host in self._host_cache if host.startswith(prefix)]
            else:
                return self._host_cache
        
        except Exception:
            # Return empty list on error
            return []
    
    def _get_service_names(self, host_name: str, prefix: str = '') -> List[str]:
        """Get service names for a specific host.
        
        Args:
            host_name: Host name to get services for
            prefix: Optional prefix to filter services
            
        Returns:
            List of matching service names
        """
        if not self.checkmk_client:
            return self._complete_common_services(prefix)
        
        try:
            # Use cached services if available and recent
            import time
            current_time = time.time()
            
            cache_key = host_name
            if (cache_key not in self._service_cache or 
                current_time - self._service_cache[cache_key]['time'] > self._cache_timeout):
                
                services = self.checkmk_client.list_host_services(host_name)
                service_names = []
                
                for service in services:
                    extensions = service.get('extensions', {})
                    service_desc = extensions.get('description', '')
                    if service_desc:
                        service_names.append(service_desc)
                
                self._service_cache[cache_key] = {
                    'services': service_names,
                    'time': current_time
                }
            
            services = self._service_cache[cache_key]['services']
            
            # Filter by prefix
            if prefix:
                return [svc for svc in services if svc.lower().startswith(prefix.lower())]
            else:
                return services
        
        except Exception:
            # Fallback to common services
            return self._complete_common_services(prefix)
    
    def clear_cache(self) -> None:
        """Clear completion cache."""
        self._host_cache = None
        self._service_cache.clear()
        self._last_cache_time = 0
    
    def set_checkmk_client(self, client) -> None:
        """Set the Checkmk client for dynamic completions.
        
        Args:
            client: CheckmkClient instance
        """
        self.checkmk_client = client
        self.clear_cache()
    
    def set_help_system(self, help_system) -> None:
        """Set the help system for command completions.
        
        Args:
            help_system: HelpSystem instance
        """
        self.help_system = help_system