"""Tool registry for MCP server - manages tool registration and discovery."""

import logging
from typing import Dict, List, Callable, Awaitable, Any, Optional

from mcp.types import Tool
from mcp.server import Server

from ...utils.request_context import (
    generate_request_id,
    set_request_id,
)
from ..utils.serialization import safe_json_dumps

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Manages tool registration, discovery, and metadata for the MCP server.
    
    This class centralizes all tool management functionality, providing:
    - Tool registration system
    - Tool discovery and enumeration
    - Tool metadata management
    - Handler function mapping
    """

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, Tool] = {}
        self._tool_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._tool_metadata: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, name: str, tool: Tool, handler: Callable[..., Awaitable[Any]], metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Register a tool with its handler and optional metadata.
        
        Args:
            name: Tool name/identifier
            tool: MCP Tool definition
            handler: Async function to handle tool calls
            metadata: Optional metadata for the tool (category, priority, etc.)
        """
        if name in self._tools:
            logger.warning(f"Tool '{name}' is already registered, overwriting")
        
        self._tools[name] = tool
        self._tool_handlers[name] = handler
        self._tool_metadata[name] = metadata or {}
        
        logger.debug(f"Registered tool: {name}")

    def unregister_tool(self, name: str) -> bool:
        """
        Unregister a tool by name.
        
        Args:
            name: Tool name to unregister
            
        Returns:
            bool: True if tool was found and removed, False otherwise
        """
        if name not in self._tools:
            return False
            
        del self._tools[name]
        del self._tool_handlers[name]
        del self._tool_metadata[name]
        
        logger.debug(f"Unregistered tool: {name}")
        return True

    def get_tool_handler(self, name: str) -> Optional[Callable[..., Awaitable[Any]]]:
        """
        Get the handler function for a tool.
        
        Args:
            name: Tool name
            
        Returns:
            Callable or None: Handler function if found
        """
        return self._tool_handlers.get(name)

    def get_tool_definition(self, name: str) -> Optional[Tool]:
        """
        Get the MCP tool definition for a tool.
        
        Args:
            name: Tool name
            
        Returns:
            Tool or None: Tool definition if found
        """
        return self._tools.get(name)

    def get_tool_metadata(self, name: str) -> Dict[str, Any]:
        """
        Get metadata for a tool.
        
        Args:
            name: Tool name
            
        Returns:
            Dict: Tool metadata (empty dict if not found)
        """
        return self._tool_metadata.get(name, {})

    def list_tools(self) -> List[Tool]:
        """
        Get all registered tool definitions.
        
        Returns:
            List[Tool]: List of all registered MCP tools
        """
        return list(self._tools.values())

    def list_tool_names(self) -> List[str]:
        """
        Get all registered tool names.
        
        Returns:
            List[str]: List of all registered tool names
        """
        return list(self._tools.keys())

    def get_tools_by_category(self, category: str) -> List[str]:
        """
        Get tool names by category from metadata.
        
        Args:
            category: Category to filter by
            
        Returns:
            List[str]: List of tool names in the category
        """
        return [
            name for name, metadata in self._tool_metadata.items()
            if metadata.get('category') == category
        ]

    def get_tool_count(self) -> int:
        """
        Get the total number of registered tools.
        
        Returns:
            int: Number of registered tools
        """
        return len(self._tools)

    def has_tool(self, name: str) -> bool:
        """
        Check if a tool is registered.
        
        Args:
            name: Tool name to check
            
        Returns:
            bool: True if tool is registered
        """
        return name in self._tools

    def get_tool_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics and summary information.
        
        Returns:
            Dict: Statistics about registered tools
        """
        categories = {}
        for metadata in self._tool_metadata.values():
            category = metadata.get('category', 'uncategorized')
            categories[category] = categories.get(category, 0) + 1

        return {
            'total_tools': len(self._tools),
            'categories': categories,
            'tool_names': list(self._tools.keys())
        }

    def register_mcp_handlers(self, server: Server, services_check_func: Callable[[], bool]) -> None:
        """
        Register MCP protocol handlers with the server.
        
        Args:
            server: MCP server instance
            services_check_func: Function to check if services are initialized
        """
        
        @server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available MCP tools."""
            return self.list_tools()

        @server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """Handle MCP tool calls with request ID tracking."""
            # Generate unique request ID for this tool call
            request_id = generate_request_id()
            set_request_id(request_id)

            logger.info(
                f"[{request_id}] MCP tool call: {name} with arguments: {arguments}"
            )

            if not services_check_func():
                raise RuntimeError("Services not initialized")

            handler = self.get_tool_handler(name)
            if not handler:
                raise ValueError(f"Unknown tool: {name}")

            try:
                result = await handler(**arguments)

                # Add request ID to result if possible
                if isinstance(result, dict):
                    result["request_id"] = request_id

                logger.info(f"[{request_id}] MCP tool '{name}' completed successfully")

                # Return raw dict to avoid MCP framework tuple construction bug
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": safe_json_dumps(result),
                            "annotations": None,
                            "meta": {"request_id": request_id},
                        }
                    ],
                    "isError": False,
                    "meta": {"request_id": request_id},
                    "structuredContent": None,
                }
            except Exception as e:
                logger.exception(f"[{request_id}] Error calling tool {name}")

                # Return raw dict for error case too
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": str(e),
                            "annotations": None,
                            "meta": {"request_id": request_id},
                        }
                    ],
                    "isError": True,
                    "meta": {"request_id": request_id},
                    "structuredContent": None,
                }

    def clear_registry(self) -> None:
        """Clear all registered tools (useful for testing)."""
        self._tools.clear()
        self._tool_handlers.clear()
        self._tool_metadata.clear()
        logger.debug("Cleared tool registry")