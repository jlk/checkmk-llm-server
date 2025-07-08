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
    """Supported host operations."""
    LIST = "list"
    CREATE = "create"
    DELETE = "delete"
    GET = "get"
    UPDATE = "update"


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
        system_prompt = """You are a Checkmk host management assistant. Parse user commands into structured operations.

Available operations:
- list: List all hosts or search for specific hosts
- create: Create a new host (requires folder and host_name)
- delete: Delete an existing host (requires host_name)
- get: Get details of a specific host (requires host_name)
- update: Update host configuration (requires host_name and attributes)

Parse the user input and respond with JSON in this format:
{
    "operation": "list|create|delete|get|update",
    "parameters": {
        "host_name": "hostname (if applicable)",
        "folder": "folder path (default: /)",
        "attributes": {"key": "value"} (for create/update),
        "search_term": "search term (for list)"
    },
    "confidence": 0.0-1.0
}

Examples:
- "list all hosts" -> {"operation": "list", "parameters": {}, "confidence": 0.9}
- "create host server01 in folder /web" -> {"operation": "create", "parameters": {"host_name": "server01", "folder": "/web"}, "confidence": 0.95}
- "delete host server01" -> {"operation": "delete", "parameters": {"host_name": "server01"}, "confidence": 0.9}
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
        
        return f"Operation {operation.value} completed successfully."
    
    def _fallback_parse(self, user_input: str) -> ParsedCommand:
        """Fallback parsing using simple keyword matching."""
        user_input_lower = user_input.lower()
        
        # Simple keyword matching
        if "list" in user_input_lower or "show" in user_input_lower:
            return ParsedCommand(HostOperation.LIST, {}, 0.6, user_input)
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
        
        # Default to list
        return ParsedCommand(HostOperation.LIST, {}, 0.5, user_input)


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
        system_prompt = """You are a Checkmk host management assistant. Parse user commands into structured operations.

Available operations:
- list: List all hosts or search for specific hosts
- create: Create a new host (requires folder and host_name)
- delete: Delete an existing host (requires host_name)
- get: Get details of a specific host (requires host_name)
- update: Update host configuration (requires host_name and attributes)

Parse the user input and respond with JSON in this format:
{
    "operation": "list|create|delete|get|update",
    "parameters": {
        "host_name": "hostname (if applicable)",
        "folder": "folder path (default: /)",
        "attributes": {"key": "value"} (for create/update),
        "search_term": "search term (for list)"
    },
    "confidence": 0.0-1.0
}"""
        
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
            
            content_block = response.content[0] if response.content else None
            if not (isinstance(content_block, str) and content_block):
                raise ValueError("Anthropic response content is not a non-empty string.")
            content_str = cast(str, content_block)
            result = json.loads(content_str)
            
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
        
        return ParsedCommand(HostOperation.LIST, {}, 0.5, user_input)


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