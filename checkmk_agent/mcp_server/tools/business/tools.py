"""Business Intelligence tools for the Checkmk MCP server.

This module contains all business intelligence-related MCP tools extracted from the main server.
"""

import logging
from typing import Any, Dict, Optional, List, TYPE_CHECKING
from mcp.types import Tool

if TYPE_CHECKING:
    pass  # BI service would be imported here

logger = logging.getLogger(__name__)


class BusinessTools:
    """Business Intelligence tools for MCP server."""
    
    def __init__(self, bi_service=None, server=None):
        """Initialize business tools with required services.
        
        Args:
            bi_service: BI service for business intelligence operations
            server: MCP server instance for service access
        """
        self.bi_service = bi_service
        self.server = server
        self._tool_handlers: Dict[str, Any] = {}
        self._tools: Dict[str, Tool] = {}
        
    def get_tools(self) -> Dict[str, Tool]:
        """Get all business tool definitions."""
        return self._tools.copy()
        
    def get_handlers(self) -> Dict[str, Any]:
        """Get all business tool handlers."""
        return self._tool_handlers.copy()
        
    def _get_service(self, service_name: str):
        """Helper to get service from server."""
        if self.server and hasattr(self.server, '_get_service'):
            return self.server._get_service(service_name)
        return None
        
    def register_tools(self) -> None:
        """Register all business tools and handlers."""
        from ...utils.errors import sanitize_error
        
        # Get business status summary tool
        self._tools["get_business_status_summary"] = Tool(
            name="get_business_status_summary",
            description="Get business-level status summary from BI aggregations",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_groups": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by group names",
                    }
                },
            },
        )

        async def get_business_status_summary(filter_groups=None):
            try:
                bi_service = self._get_service("bi")
                if not bi_service:
                    return {
                        "success": False,
                        "error": "BI service not available"
                    }
                    
                result = await bi_service.get_business_status_summary(filter_groups)

                if result.success:
                    return {"success": True, "business_summary": result.data}
                else:
                    return {
                        "success": False,
                        "error": result.error or "BI operation failed",
                    }
            except Exception as e:
                logger.exception("Error getting business status summary")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["get_business_status_summary"] = get_business_status_summary

        # Get critical business services tool
        self._tools["get_critical_business_services"] = Tool(
            name="get_critical_business_services",
            description="Get list of critical business services from BI aggregations",
            inputSchema={"type": "object", "properties": {}},
        )

        async def get_critical_business_services():
            try:
                bi_service = self._get_service("bi")
                if not bi_service:
                    return {
                        "success": False,
                        "error": "BI service not available"
                    }
                    
                result = await bi_service.get_critical_business_services()

                if result.success:
                    return {
                        "success": True,
                        "critical_services": result.data,
                        "count": len(result.data),
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error or "BI operation failed",
                    }
            except Exception as e:
                logger.exception("Error getting critical business services")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["get_critical_business_services"] = (
            get_critical_business_services
        )