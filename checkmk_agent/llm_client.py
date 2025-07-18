"""LLM client for natural language processing of Checkmk operations."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple, cast
from enum import Enum

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from .config import LLMConfig


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class HostOperation(Enum):
    """Supported operations (kept for backward compatibility)."""
    LIST = "list"
    CREATE = "create"
    DELETE = "delete"
    GET = "get"
    UPDATE = "update"
    SYNTAX_ERROR = "syntax_error"
    # Rule operations
    LIST_RULES = "list_rules"
    CREATE_RULE = "create_rule"
    DELETE_RULE = "delete_rule"
    GET_RULE = "get_rule"
    MOVE_RULE = "move_rule"


class ParsedCommand:
    """Parsed natural language command."""
    
    def __init__(self, operation: HostOperation, parameters: Dict[str, Any], 
                 confidence: float = 1.0, raw_text: str = ""):
        self.operation = operation
        self.parameters = parameters
        self.confidence = confidence
        self.raw_text = raw_text
    
    def __repr__(self):
        return f"ParsedCommand(operation={self.operation}, parameters={self.parameters})"


class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    @abstractmethod
    def parse_command(self, user_input: str) -> ParsedCommand:
        """Parse natural language input into a structured command."""
        pass
    
    @abstractmethod
    def format_response(self, operation: HostOperation, data: Any, 
                       success: bool = True, error: Optional[str] = None) -> str:
        """Format API response for human consumption."""
        pass
    
    @abstractmethod
    def chat_completion(self, prompt: str) -> str:
        """Get a direct chat completion response for the given prompt."""
        pass


class OpenAIClient(LLMClient):
    """OpenAI-based LLM client."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not installed. Run: pip install openai")
        
        if not config.openai_api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.client = openai.OpenAI(api_key=config.openai_api_key)
        self.model = config.default_model
    
    def parse_command(self, user_input: str) -> ParsedCommand:
        """Parse natural language input using OpenAI."""
        system_prompt = """You are a Checkmk management assistant. Parse user commands into structured operations for hosts and rules.

Available operations:
Host operations:
- list: List all hosts or search for specific hosts (supports search_term for filtering with patterns like "hosts like X", "hosts containing Y", "find hosts matching Z")
- create: Create a new host (requires folder and host_name)
- delete: Delete an existing host (requires host_name)
- get: Get details of a specific host (requires host_name)
- update: Update host configuration (requires host_name and attributes)

Rule operations:
- list_rules: List rules in a ruleset (requires ruleset_name)
- create_rule: Create a new rule (requires ruleset, folder, value_raw)
- delete_rule: Delete a rule (requires rule_id)
- get_rule: Get details of a specific rule (requires rule_id)
- move_rule: Move a rule position (requires rule_id, position)

IMPORTANT VALIDATION RULES:
- For "list" operations, the command must explicitly mention "hosts", "host", "servers", "machines", or be clearly about listing hosts
- Commands like "list asdflkjasdf", "list invalid_thing", "show potato salad" are INVALID and should return "syntax_error"
- Only return "list" operation for commands that are clearly about listing hosts or have valid search terms
- If the command doesn't make sense or mentions invalid/nonsensical targets, return "syntax_error"

Parse the user input and respond with JSON in this format:
{
    "operation": "list|create|delete|get|update|list_rules|create_rule|delete_rule|get_rule|move_rule|syntax_error",
    "parameters": {
        "host_name": "hostname (for host operations)",
        "rule_id": "rule ID (for rule operations)",
        "ruleset_name": "ruleset name (for list_rules, create_rule)",
        "folder": "folder path (default: /)",
        "value_raw": "rule value as JSON string (for create_rule)",
        "conditions": {"key": "value"} (for create_rule),
        "properties": {"key": "value"} (for create_rule),
        "position": "position (for move_rule: top_of_folder, bottom_of_folder, before, after)",
        "attributes": {"key": "value"} (for host create/update),
        "search_term": "search term (for list)"
    },
    "confidence": 0.0-1.0
}

Examples:
VALID commands:
- "list all hosts" -> {"operation": "list", "parameters": {}, "confidence": 0.9}
- "list hosts" -> {"operation": "list", "parameters": {}, "confidence": 0.9}
- "show hosts like piaware" -> {"operation": "list", "parameters": {"search_term": "piaware"}, "confidence": 0.9}
- "find hosts containing web" -> {"operation": "list", "parameters": {"search_term": "web"}, "confidence": 0.9}
- "search hosts matching db" -> {"operation": "list", "parameters": {"search_term": "db"}, "confidence": 0.9}
- "create host server01 in folder /web" -> {"operation": "create", "parameters": {"host_name": "server01", "folder": "/web"}, "confidence": 0.95}
- "delete host server01" -> {"operation": "delete", "parameters": {"host_name": "server01"}, "confidence": 0.9}

INVALID commands that should return syntax_error:
- "list asdflkjasdf" -> {"operation": "syntax_error", "parameters": {}, "confidence": 0.1}
- "list invalid_thing" -> {"operation": "syntax_error", "parameters": {}, "confidence": 0.1}
- "show potato salad" -> {"operation": "syntax_error", "parameters": {}, "confidence": 0.1}
- "list nonexistent_resource" -> {"operation": "syntax_error", "parameters": {}, "confidence": 0.1}

RULE examples:
- "list rules in host_groups" -> {"operation": "list_rules", "parameters": {"ruleset_name": "host_groups"}, "confidence": 0.9}
- "create rule for web servers" -> {"operation": "create_rule", "parameters": {"ruleset": "host_groups", "folder": "/", "value_raw": "{\"group_name\": \"web_servers\"}"}, "confidence": 0.8}
- "delete rule abc123" -> {"operation": "delete_rule", "parameters": {"rule_id": "abc123"}, "confidence": 0.9}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content:
                raise ValueError("OpenAI response content is not a non-empty string.")
            result = json.loads(content)
            
            operation = HostOperation(result["operation"])
            parameters = result.get("parameters", {})
            confidence = result.get("confidence", 0.8)
            
            return ParsedCommand(operation, parameters, confidence, user_input)
            
        except Exception as e:
            self.logger.error(f"Failed to parse command: {e}")
            # Fallback to simple keyword matching
            return self._fallback_parse(user_input)
    
    def format_response(self, operation: HostOperation, data: Any, 
                       success: bool = True, error: Optional[str] = None) -> str:
        """Format response using OpenAI."""
        if not success:
            return f"Error: {error}"
        
        if operation == HostOperation.LIST:
            if isinstance(data, list):
                if not data:
                    return "No hosts found."
                
                host_list = []
                for host in data:
                    host_id = host.get("id", "Unknown")
                    extensions = host.get("extensions", {})
                    folder = extensions.get("folder", "Unknown")
                    host_list.append(f"- {host_id} (folder: {folder})")
                
                return f"Found {len(data)} hosts:\n" + "\n".join(host_list)
        
        elif operation == HostOperation.CREATE:
            host_id = data.get("id", "Unknown") if isinstance(data, dict) else "Unknown"
            return f"Successfully created host: {host_id}"
        
        elif operation == HostOperation.DELETE:
            return "Host deleted successfully."
        
        elif operation == HostOperation.GET:
            if isinstance(data, dict):
                host_id = data.get("id", "Unknown")
                extensions = data.get("extensions", {})
                folder = extensions.get("folder", "Unknown")
                attributes = extensions.get("attributes", {})
                ip_address = attributes.get("ipaddress", "Not set")
                
                return f"""Host Details:
- Name: {host_id}
- Folder: {folder}
- IP Address: {ip_address}
- Cluster: {'Yes' if extensions.get('is_cluster') else 'No'}
- Offline: {'Yes' if extensions.get('is_offline') else 'No'}"""
        
        elif operation == HostOperation.LIST_RULES:
            if isinstance(data, list):
                if not data:
                    return "No rules found."
                
                rule_list = []
                for rule in data:
                    rule_id = rule.get("id", "Unknown")
                    extensions = rule.get("extensions", {})
                    folder = extensions.get("folder", "Unknown")
                    ruleset = extensions.get("ruleset", "Unknown")
                    rule_list.append(f"- {rule_id} (ruleset: {ruleset}, folder: {folder})")
                
                return f"Found {len(data)} rules:\n" + "\n".join(rule_list)
        
        elif operation == HostOperation.CREATE_RULE:
            rule_id = data.get("id", "Unknown") if isinstance(data, dict) else "Unknown"
            return f"Successfully created rule: {rule_id}"
        
        elif operation == HostOperation.DELETE_RULE:
            return "Rule deleted successfully."
        
        elif operation == HostOperation.GET_RULE:
            if isinstance(data, dict):
                rule_id = data.get("id", "Unknown")
                extensions = data.get("extensions", {})
                folder = extensions.get("folder", "Unknown")
                ruleset = extensions.get("ruleset", "Unknown")
                properties = extensions.get("properties", {})
                
                return f"""Rule Details:
- ID: {rule_id}
- Ruleset: {ruleset}
- Folder: {folder}
- Disabled: {'Yes' if properties.get('disabled') else 'No'}
- Description: {properties.get('description', 'None')}"""
        
        elif operation == HostOperation.MOVE_RULE:
            return "Rule moved successfully."
        
        return f"Operation {operation.value} completed successfully."
    
    def _fallback_parse(self, user_input: str) -> ParsedCommand:
        """Fallback parsing using simple keyword matching."""
        user_input_lower = user_input.lower()
        
        # Simple keyword matching
        if any(keyword in user_input_lower for keyword in ["list", "show", "find", "search", "like", "containing", "matching", "similar", "called", "named"]):
            # Try to extract search term for filtering
            search_term = None
            search_patterns = [
                r'(?:hosts?|servers?|machines?)\s+(?:like|containing|matching|similar\s+to)\s+([\w\-\.]+)',
                r'(?:like|containing|matching|similar\s+to)\s+([\w\-\.]+)',
                r'(?:with|named?)\s+([\w\-\.]+)',
                r'(?:called|named)\s+([\w\-\.]+)',
                r'(?:with\s+name)\s+([\w\-\.]+)'
            ]
            
            for pattern in search_patterns:
                import re
                search_match = re.search(pattern, user_input_lower, re.IGNORECASE)
                if search_match:
                    search_term = search_match.group(1)
                    break
            
            params = {}
            if search_term:
                params["search_term"] = search_term
            
            return ParsedCommand(HostOperation.LIST, params, 0.6, user_input)
        elif "create" in user_input_lower or "add" in user_input_lower:
            # Try to extract host name
            words = user_input.split()
            host_name = None
            folder = "/"
            
            # Look for patterns like "create host server01" or "add server01"
            for i, word in enumerate(words):
                if word.lower() in ["host", "server"] and i + 1 < len(words):
                    host_name = words[i + 1]
                    break
            
            if not host_name and len(words) > 1:
                # Last word might be the hostname
                host_name = words[-1]
            
            params = {"folder": folder}
            if host_name:
                params["host_name"] = host_name
            
            return ParsedCommand(HostOperation.CREATE, params, 0.7, user_input)
        elif "delete" in user_input_lower or "remove" in user_input_lower:
            # Try to extract host name
            words = user_input.split()
            host_name = None
            
            for i, word in enumerate(words):
                if word.lower() in ["host", "server"] and i + 1 < len(words):
                    host_name = words[i + 1]
                    break
            
            if not host_name and len(words) > 1:
                host_name = words[-1]
            
            params = {}
            if host_name:
                params["host_name"] = host_name
            
            return ParsedCommand(HostOperation.DELETE, params, 0.7, user_input)
        
        # Default to syntax error for unrecognized commands
        return ParsedCommand(HostOperation.SYNTAX_ERROR, {}, 0.1, user_input)
    
    def chat_completion(self, prompt: str) -> str:
        """Get a direct chat completion response using OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content:
                raise ValueError("OpenAI response content is not a non-empty string.")
            
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to get chat completion: {e}")
            return '{"action": "unknown", "parameters": {}}'


class AnthropicClient(LLMClient):
    """Anthropic Claude-based LLM client."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic library not installed. Run: pip install anthropic")
        
        if not config.anthropic_api_key:
            raise ValueError("Anthropic API key not provided")
        
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.model = "claude-3-haiku-20240307"  # Fast model for parsing
    
    def parse_command(self, user_input: str) -> ParsedCommand:
        """Parse natural language input using Anthropic Claude."""
        system_prompt = """You are a Checkmk management assistant. Parse user commands into structured operations for hosts and rules.

Available operations:
Host operations:
- list: List all hosts or search for specific hosts (supports search_term for filtering with patterns like "hosts like X", "hosts containing Y", "find hosts matching Z")
- create: Create a new host (requires folder and host_name)
- delete: Delete an existing host (requires host_name)
- get: Get details of a specific host (requires host_name)
- update: Update host configuration (requires host_name and attributes)

Rule operations:
- list_rules: List rules in a ruleset (requires ruleset_name)
- create_rule: Create a new rule (requires ruleset, folder, value_raw)
- delete_rule: Delete a rule (requires rule_id)
- get_rule: Get details of a specific rule (requires rule_id)
- move_rule: Move a rule position (requires rule_id, position)

IMPORTANT VALIDATION RULES:
- For "list" operations, the command must explicitly mention "hosts", "host", "servers", "machines", or be clearly about listing hosts
- Commands like "list asdflkjasdf", "list invalid_thing", "show potato salad" are INVALID and should return "syntax_error"
- Only return "list" operation for commands that are clearly about listing hosts or have valid search terms
- If the command doesn't make sense or mentions invalid/nonsensical targets, return "syntax_error"

Parse the user input and respond with JSON in this format:
{
    "operation": "list|create|delete|get|update|list_rules|create_rule|delete_rule|get_rule|move_rule|syntax_error",
    "parameters": {
        "host_name": "hostname (for host operations)",
        "rule_id": "rule ID (for rule operations)",
        "ruleset_name": "ruleset name (for list_rules, create_rule)",
        "folder": "folder path (default: /)",
        "value_raw": "rule value as JSON string (for create_rule)",
        "conditions": {"key": "value"} (for create_rule),
        "properties": {"key": "value"} (for create_rule),
        "position": "position (for move_rule: top_of_folder, bottom_of_folder, before, after)",
        "attributes": {"key": "value"} (for host create/update),
        "search_term": "search term (for list)"
    },
    "confidence": 0.0-1.0
}

Examples:
VALID commands:
- "list all hosts" -> {"operation": "list", "parameters": {}, "confidence": 0.9}
- "list hosts" -> {"operation": "list", "parameters": {}, "confidence": 0.9}
- "show hosts like piaware" -> {"operation": "list", "parameters": {"search_term": "piaware"}, "confidence": 0.9}
- "find hosts containing web" -> {"operation": "list", "parameters": {"search_term": "web"}, "confidence": 0.9}
- "search hosts matching db" -> {"operation": "list", "parameters": {"search_term": "db"}, "confidence": 0.9}
- "create host server01 in folder /web" -> {"operation": "create", "parameters": {"host_name": "server01", "folder": "/web"}, "confidence": 0.95}
- "delete host server01" -> {"operation": "delete", "parameters": {"host_name": "server01"}, "confidence": 0.9}

INVALID commands that should return syntax_error:
- "list asdflkjasdf" -> {"operation": "syntax_error", "parameters": {}, "confidence": 0.1}
- "list invalid_thing" -> {"operation": "syntax_error", "parameters": {}, "confidence": 0.1}
- "show potato salad" -> {"operation": "syntax_error", "parameters": {}, "confidence": 0.1}
- "list nonexistent_resource" -> {"operation": "syntax_error", "parameters": {}, "confidence": 0.1}
"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.1,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_input}
                ]
            )
            
            # Extract text from Anthropic response with proper error handling
            if not response.content:
                raise ValueError("Anthropic response has no content")
            
            content_block = response.content[0]
            if not hasattr(content_block, 'text'):
                raise ValueError("Anthropic response content block has no text attribute")
            
            content_text = content_block.text
            if not content_text:
                raise ValueError("Anthropic response content text is empty")
            
            result = json.loads(content_text)
            
            operation = HostOperation(result["operation"])
            parameters = result.get("parameters", {})
            confidence = result.get("confidence", 0.8)
            
            return ParsedCommand(operation, parameters, confidence, user_input)
            
        except Exception as e:
            self.logger.error(f"Failed to parse command: {e}")
            # Fallback to simple keyword matching
            return self._fallback_parse(user_input)
    
    def format_response(self, operation: HostOperation, data: Any, 
                       success: bool = True, error: Optional[str] = None) -> str:
        """Format response using Anthropic Claude."""
        # Same implementation as OpenAI for now
        if not success:
            return f"Error: {error}"
        
        if operation == HostOperation.LIST:
            if isinstance(data, list):
                if not data:
                    return "No hosts found."
                
                host_list = []
                for host in data:
                    host_id = host.get("id", "Unknown")
                    extensions = host.get("extensions", {})
                    folder = extensions.get("folder", "Unknown")
                    host_list.append(f"- {host_id} (folder: {folder})")
                
                return f"Found {len(data)} hosts:\n" + "\n".join(host_list)
        
        elif operation == HostOperation.CREATE:
            host_id = data.get("id", "Unknown") if isinstance(data, dict) else "Unknown"
            return f"Successfully created host: {host_id}"
        
        elif operation == HostOperation.DELETE:
            return "Host deleted successfully."
        
        elif operation == HostOperation.GET:
            if isinstance(data, dict):
                host_id = data.get("id", "Unknown")
                extensions = data.get("extensions", {})
                folder = extensions.get("folder", "Unknown")
                attributes = extensions.get("attributes", {})
                ip_address = attributes.get("ipaddress", "Not set")
                
                return f"""Host Details:
- Name: {host_id}
- Folder: {folder}
- IP Address: {ip_address}
- Cluster: {'Yes' if extensions.get('is_cluster') else 'No'}
- Offline: {'Yes' if extensions.get('is_offline') else 'No'}"""
        
        elif operation == HostOperation.LIST_RULES:
            if isinstance(data, list):
                if not data:
                    return "No rules found."
                
                rule_list = []
                for rule in data:
                    rule_id = rule.get("id", "Unknown")
                    extensions = rule.get("extensions", {})
                    folder = extensions.get("folder", "Unknown")
                    ruleset = extensions.get("ruleset", "Unknown")
                    rule_list.append(f"- {rule_id} (ruleset: {ruleset}, folder: {folder})")
                
                return f"Found {len(data)} rules:\n" + "\n".join(rule_list)
        
        elif operation == HostOperation.CREATE_RULE:
            rule_id = data.get("id", "Unknown") if isinstance(data, dict) else "Unknown"
            return f"Successfully created rule: {rule_id}"
        
        elif operation == HostOperation.DELETE_RULE:
            return "Rule deleted successfully."
        
        elif operation == HostOperation.GET_RULE:
            if isinstance(data, dict):
                rule_id = data.get("id", "Unknown")
                extensions = data.get("extensions", {})
                folder = extensions.get("folder", "Unknown")
                ruleset = extensions.get("ruleset", "Unknown")
                properties = extensions.get("properties", {})
                
                return f"""Rule Details:
- ID: {rule_id}
- Ruleset: {ruleset}
- Folder: {folder}
- Disabled: {'Yes' if properties.get('disabled') else 'No'}
- Description: {properties.get('description', 'None')}"""
        
        elif operation == HostOperation.MOVE_RULE:
            return "Rule moved successfully."
        
        return f"Operation {operation.value} completed successfully."
    
    def _fallback_parse(self, user_input: str) -> ParsedCommand:
        """Fallback parsing using simple keyword matching."""
        # Same implementation as OpenAI
        user_input_lower = user_input.lower()
        
        if "list" in user_input_lower or "show" in user_input_lower:
            return ParsedCommand(HostOperation.LIST, {}, 0.6, user_input)
        elif "create" in user_input_lower or "add" in user_input_lower:
            words = user_input.split()
            host_name = None
            folder = "/"
            
            for i, word in enumerate(words):
                if word.lower() in ["host", "server"] and i + 1 < len(words):
                    host_name = words[i + 1]
                    break
            
            if not host_name and len(words) > 1:
                host_name = words[-1]
            
            params = {"folder": folder}
            if host_name:
                params["host_name"] = host_name
            
            return ParsedCommand(HostOperation.CREATE, params, 0.7, user_input)
        elif "delete" in user_input_lower or "remove" in user_input_lower:
            words = user_input.split()
            host_name = None
            
            for i, word in enumerate(words):
                if word.lower() in ["host", "server"] and i + 1 < len(words):
                    host_name = words[i + 1]
                    break
            
            if not host_name and len(words) > 1:
                host_name = words[-1]
            
            params = {}
            if host_name:
                params["host_name"] = host_name
            
            return ParsedCommand(HostOperation.DELETE, params, 0.7, user_input)
        
        # Default to syntax error for unrecognized commands
        return ParsedCommand(HostOperation.SYNTAX_ERROR, {}, 0.1, user_input)
    
    def chat_completion(self, prompt: str) -> str:
        """Get a direct chat completion response using Anthropic Claude."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.1,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract text from Anthropic response with proper error handling
            if not response.content:
                raise ValueError("Anthropic response has no content")
            
            content_block = response.content[0]
            if not hasattr(content_block, 'text'):
                raise ValueError("Anthropic response content block has no text attribute")
            
            content_text = content_block.text
            if not content_text:
                raise ValueError("Anthropic response content text is empty")
            
            return content_text
            
        except Exception as e:
            self.logger.error(f"Failed to get chat completion: {e}")
            return '{"action": "unknown", "parameters": {}}'


def create_llm_client(config: LLMConfig, provider: Optional[LLMProvider] = None) -> LLMClient:
    """Factory function to create appropriate LLM client."""
    if provider is None:
        # Auto-detect based on available API keys
        if config.openai_api_key:
            provider = LLMProvider.OPENAI
        elif config.anthropic_api_key:
            provider = LLMProvider.ANTHROPIC
        else:
            raise ValueError("No LLM API key provided")
    
    if provider == LLMProvider.OPENAI:
        return OpenAIClient(config)
    elif provider == LLMProvider.ANTHROPIC:
        return AnthropicClient(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")