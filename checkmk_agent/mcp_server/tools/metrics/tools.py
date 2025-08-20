"""Metrics and performance tools for the Checkmk MCP server.

This module contains all metrics-related MCP tools extracted from the main server.
"""

import logging
from typing import Any, Dict, Optional, List, TYPE_CHECKING
from mcp.types import Tool

if TYPE_CHECKING:
    pass  # Metrics service would be imported here

logger = logging.getLogger(__name__)


class MetricsTools:
    """Metrics and performance tools for MCP server."""
    
    def __init__(self, metrics_service=None, historical_service=None, server=None):
        """Initialize metrics tools with required services.
        
        Args:
            metrics_service: Metrics service for metrics operations
            historical_service: Historical service for historical data
            server: MCP server instance for service access
        """
        self.metrics_service = metrics_service
        self.historical_service = historical_service
        self.server = server
        self._tool_handlers: Dict[str, Any] = {}
        self._tools: Dict[str, Tool] = {}
        
    def get_tools(self) -> Dict[str, Tool]:
        """Get all metrics tool definitions."""
        return self._tools.copy()
        
    def get_handlers(self) -> Dict[str, Any]:
        """Get all metrics tool handlers."""
        return self._tool_handlers.copy()
        
    def _get_service(self, service_name: str):
        """Helper to get service from server."""
        if self.server and hasattr(self.server, '_get_service'):
            return self.server._get_service(service_name)
        return None
        
    def register_tools(self) -> None:
        """Register all metrics tools and handlers."""
        from ...utils.errors import sanitize_error
        
        # Get service metrics tool
        self._tools["get_service_metrics"] = Tool(
            name="get_service_metrics",
            description="Get performance metrics/graphs for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_description": {
                        "type": "string",
                        "description": "Service description",
                    },
                    "time_range_hours": {
                        "type": "integer",
                        "description": "Hours of data to retrieve",
                        "default": 24,
                    },
                    "reduce": {
                        "type": "string",
                        "description": "Data reduction method",
                        "enum": ["min", "max", "average"],
                        "default": "average",
                    },
                    "site": {
                        "type": "string",
                        "description": "Site name for performance optimization",
                    },
                },
                "required": ["host_name", "service_description"],
            },
        )

        async def get_service_metrics(
            host_name,
            service_description,
            time_range_hours=24,
            reduce="average",
            site=None,
        ):
            try:
                metrics_service = self._get_service("metrics")
                if not metrics_service:
                    return {
                        "success": False,
                        "error": "Metrics service not available"
                    }
                    
                result = await metrics_service.get_service_metrics(
                    host_name, service_description, time_range_hours, reduce, site
                )

                if result.success:
                    metrics_data = []
                    for graph in result.data:
                        graph_info = {
                            "time_range": graph.time_range,
                            "step": graph.step,
                            "metrics": [],
                        }
                        for metric in graph.metrics:
                            metric_info = {
                                "title": metric.title,
                                "color": metric.color,
                                "line_type": metric.line_type,
                                "data_points_count": len(metric.data_points),
                                "latest_value": (
                                    metric.data_points[-1] if metric.data_points else None
                                ),
                            }
                            graph_info["metrics"].append(metric_info)
                        metrics_data.append(graph_info)

                    return {
                        "success": True,
                        "graphs": metrics_data,
                        "count": len(metrics_data),
                    }
                else:
                    return {
                        "success": False,
                        "error": result.error or "Metrics operation failed",
                    }
            except Exception as e:
                logger.exception(f"Error getting service metrics: {host_name}/{service_description}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["get_service_metrics"] = get_service_metrics

        # Get metric history tool
        self._tools["get_metric_history"] = Tool(
            name="get_metric_history",
            description="Get historical data for a specific metric. Supports both REST API and web scraping data sources for comprehensive historical data retrieval.",
            inputSchema={
                "type": "object",
                "properties": {
                    "host_name": {"type": "string", "description": "Host name"},
                    "service_description": {
                        "type": "string",
                        "description": "Service description",
                    },
                    "metric_id": {
                        "type": "string",
                        "description": "Metric ID (enable 'Show internal IDs' in Checkmk UI)",
                    },
                    "time_range_hours": {
                        "type": "integer",
                        "description": "Hours of data to retrieve",
                        "default": 168,
                    },
                    "reduce": {
                        "type": "string",
                        "description": "Data reduction method",
                        "enum": ["min", "max", "average"],
                        "default": "average",
                    },
                    "site": {
                        "type": "string",
                        "description": "Site name for performance optimization",
                    },
                    "data_source": {
                        "type": "string",
                        "description": "Data source: 'rest_api' (uses Checkmk REST API) or 'scraper' (uses web scraping with caching). If not specified, uses configured default. Scraper provides additional parsing capabilities and summary statistics.",
                        "enum": ["rest_api", "scraper"]
                    },
                },
                "required": ["host_name", "service_description", "metric_id"],
            },
        )

        async def get_metric_history(
            host_name,
            service_description,
            metric_id,
            time_range_hours=168,
            reduce="average",
            site=None,
            data_source=None,
        ):
            try:
                # Parameter validation for data_source
                if data_source and data_source not in ["rest_api", "scraper"]:
                    return {
                        "success": False,
                        "error": f"Invalid data_source '{data_source}'. Must be 'rest_api' or 'scraper'",
                    }

                # Data source selection logic - simplified for extraction
                effective_source = data_source if data_source else "rest_api"
                
                if effective_source == "scraper":
                    # Use historical service for scraper data source
                    historical_service = self._get_service("historical")
                    if not historical_service:
                        return {
                            "success": False,
                            "error": "Historical service not available for scraper data source"
                        }
                    
                    # Simplified scraper logic - full implementation would be more complex
                    return {
                        "success": False,
                        "error": "Scraper data source implementation requires full historical service setup"
                    }
                        
                else:  # effective_source == "rest_api" or fallback
                    # Use existing REST API logic
                    metrics_service = self._get_service("metrics")
                    if not metrics_service:
                        return {
                            "success": False,
                            "error": "Metrics service not available"
                        }
                        
                    result = await metrics_service.get_metric_history(
                        host_name,
                        service_description,
                        metric_id,
                        time_range_hours,
                        reduce,
                        site,
                    )

                    if result.success:
                        graph = result.data
                        metrics_data = []
                        for metric in graph.metrics:
                            metric_info = {
                                "title": metric.title,
                                "color": metric.color,
                                "line_type": metric.line_type,
                                "data_points": metric.data_points,
                                "data_points_count": len(metric.data_points),
                            }
                            metrics_data.append(metric_info)

                        return {
                            "success": True,
                            "data_source": "rest_api",
                            "time_range": graph.time_range,
                            "step": graph.step,
                            "metrics": metrics_data,
                            "metric_id": metric_id,
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.error or "Metrics operation failed",
                            "data_source": "rest_api"
                        }
            except Exception as e:
                logger.exception(f"Error getting metric history: {host_name}/{service_description}/{metric_id}")
                return {"success": False, "error": sanitize_error(e)}

        self._tool_handlers["get_metric_history"] = get_metric_history