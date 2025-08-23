"""Monitoring and status tools for the Checkmk MCP server.

This module contains all monitoring-related MCP tools extracted from the main server.
"""

import logging
from typing import Any, Dict, Optional, List, TYPE_CHECKING
from mcp.types import Tool

if TYPE_CHECKING:
    from ...services.status_service import StatusService

logger = logging.getLogger(__name__)


class MonitoringTools:
    """Monitoring and status tools for MCP server."""
    
    def __init__(self, status_service: "StatusService"):
        """Initialize monitoring tools with required services.
        
        Args:
            status_service: Status service for monitoring operations
        """
        self.status_service = status_service
        self._tool_handlers: Dict[str, Any] = {}
        self._tools: Dict[str, Tool] = {}
        
    def get_tools(self) -> Dict[str, Tool]:
        """Get all monitoring tool definitions."""
        return self._tools.copy()
        
    def get_handlers(self) -> Dict[str, Any]:
        """Get all monitoring tool handlers."""
        return self._tool_handlers.copy()
        
    def register_tools(self) -> None:
        """Register all monitoring tools and handlers."""
        from ...utils.errors import sanitize_error
        
        # Get health dashboard tool
        self._tools["get_health_dashboard"] = Tool(
            name="get_health_dashboard",
            description="Get comprehensive infrastructure health dashboard with aggregated status metrics and key performance indicators. When to use: Getting overall system health overview, generating status reports, identifying infrastructure-wide trends or issues. Best for: Daily operational reviews, management reporting, identifying systemic problems across the monitoring environment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_services": {
                        "type": "boolean",
                        "description": "Include service statistics",
                        "default": True,
                    },
                    "include_metrics": {
                        "type": "boolean",
                        "description": "Include performance metrics",
                        "default": True,
                    },
                },
            },
        )

        async def get_health_dashboard(**kwargs):
            try:
                # Note: The service method doesn't accept parameters, ignore any passed
                result = await self.status_service.get_health_dashboard()
                if result.success:
                    # Handle both dict and Pydantic model data
                    data = (
                        result.data.model_dump() if result.data else {}
                        if hasattr(result.data, "model_dump")
                        else result.data
                    )
                    return {"success": True, "data": data}
                else:
                    return {
                        "success": False,
                        "error": result.error or "Health dashboard operation failed",
                    }
            except Exception as e:
                logger.exception("Error getting health dashboard")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["get_health_dashboard"] = get_health_dashboard

        # Get critical problems tool
        self._tools["get_critical_problems"] = Tool(
            name="get_critical_problems",
            description="Retrieve all critical issues requiring immediate attention, filtered by severity and category. When to use: Incident response, priority-based problem resolution, emergency escalation procedures. Prerequisites: None required, filters help narrow results. Workflow: Get critical problems → prioritize by business impact → acknowledge → assign to teams for resolution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by severity levels",
                    },
                    "category_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by problem categories",
                    },
                    "include_acknowledged": {
                        "type": "boolean",
                        "description": "Include acknowledged problems",
                        "default": False,
                    },
                },
            },
        )

        async def get_critical_problems(
            severity_filter=None, category_filter=None, include_acknowledged=False
        ):
            try:
                result = await self.status_service.get_critical_problems(
                    severity_filter=severity_filter,
                    category_filter=category_filter,
                    include_acknowledged=include_acknowledged,
                )
                if result.success:
                    # Handle both dict and Pydantic model data
                    data = result.data if result.data else {}
                    return {"success": True, "data": data}
                else:
                    return {
                        "success": False,
                        "error": result.error or "Critical problems operation failed",
                    }
            except Exception as e:
                logger.exception("Error getting critical problems")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["get_critical_problems"] = get_critical_problems

        # Analyze host health tool
        self._tools["analyze_host_health"] = Tool(
            name="analyze_host_health",
            description="Perform comprehensive health analysis for a specific host including service status, performance trends, and actionable recommendations. When to use: Investigating host-specific performance issues, preparing health reports for specific systems, proactive maintenance planning. Prerequisites: Host must exist and have monitoring data. Returns: Health score, problem analysis, and optimization recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {
                        "type": "string",
                        "description": "Name of the host to analyze",
                    },
                    "include_grade": {
                        "type": "boolean",
                        "description": "Include health grade (A+ through F)",
                        "default": True,
                    },
                    "include_recommendations": {
                        "type": "boolean",
                        "description": "Include maintenance recommendations",
                        "default": True,
                    },
                    "compare_to_peers": {
                        "type": "boolean",
                        "description": "Compare to infrastructure peers",
                        "default": False,
                    },
                },
                "required": ["host_name"],
            },
        )

        async def analyze_host_health(
            host_name,
            include_grade=True,
            include_recommendations=True,
            compare_to_peers=False,
        ):
            result = await self.status_service.analyze_host_health(
                host_name=host_name,
                include_grade=include_grade,
                include_recommendations=include_recommendations,
                compare_to_peers=compare_to_peers,
            )
            if result.success:
                return {"success": True, "data": result.data}
            else:
                return {
                    "success": False,
                    "error": result.error or "Event Console operation failed",
                }

        self._tool_handlers["analyze_host_health"] = analyze_host_health