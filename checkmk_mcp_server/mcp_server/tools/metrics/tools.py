"""Metrics and performance tools for the Checkmk MCP server.

This module contains all metrics-related MCP tools extracted from the main server.
"""

import logging
from typing import Any, Dict, TYPE_CHECKING
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
                if not self.metrics_service:
                    return {
                        "success": False,
                        "error": "Metrics service not available"
                    }
                    
                result = await self.metrics_service.get_service_metrics(
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
                    if not self.historical_service:
                        return {
                            "success": False,
                            "error": "Historical service not available for scraper data source",
                            "data_source": "scraper"
                        }
                    
                    # Use historical service to get metric history via scraper
                    try:
                        from ....services.models.historical import HistoricalDataRequest
                        
                        # Map time_range_hours to period format expected by scraper
                        if time_range_hours <= 1:
                            period = "1h"
                        elif time_range_hours <= 4:
                            period = "4h"
                        elif time_range_hours <= 6:
                            period = "6h"
                        elif time_range_hours <= 12:
                            period = "12h"
                        elif time_range_hours <= 24:
                            period = "24h"
                        elif time_range_hours <= 25:
                            period = "25h"
                        elif time_range_hours <= 48:
                            period = "48h"
                        elif time_range_hours <= 168:  # 7 days
                            period = "8d"
                        elif time_range_hours <= 744:  # 30 days
                            period = "35d"
                        else:
                            period = "400d"
                        
                        request = HistoricalDataRequest(
                            host_name=host_name,
                            service_name=service_description,
                            period=period,
                            metric_name=metric_id,
                            source="scraper"
                        )
                        
                        result = await self.historical_service.get_historical_data(request)
                        
                        if result.success:
                            historical_data = result.data
                            metrics_data = []
                            
                            # Process data points from scraper
                            if historical_data and historical_data.data_points:
                                # Group data points by metric name
                                metrics_by_name = {}
                                for dp in historical_data.data_points:
                                    metric_name = dp.metric_name
                                    if metric_name not in metrics_by_name:
                                        metrics_by_name[metric_name] = {
                                            "name": metric_name,
                                            "unit": dp.unit or "",
                                            "data_points": []
                                        }
                                    # Store as timestamp, value tuples
                                    timestamp = dp.timestamp.isoformat() if hasattr(dp.timestamp, 'isoformat') else str(dp.timestamp)
                                    metrics_by_name[metric_name]["data_points"].append([timestamp, dp.value])
                                
                                # Convert to response format
                                for metric_name, metric_data in metrics_by_name.items():
                                    # More flexible metric matching - check if metric_id is contained in metric_name or vice versa
                                    if metric_id:
                                        metric_id_lower = metric_id.lower()
                                        metric_name_lower = metric_name.lower()
                                        
                                        # Skip if specific metric requested and there's no match
                                        if (metric_id_lower not in metric_name_lower and 
                                            metric_name_lower not in metric_id_lower and
                                            metric_id_lower != metric_name_lower):
                                            continue
                                    
                                    metric_info = {
                                        "title": metric_name,
                                        "color": "#1f77b4",  # Default color
                                        "line_type": "area",  # Default line type
                                        "data_points": metric_data["data_points"],
                                        "data_points_count": len(metric_data["data_points"]),
                                    }
                                    metrics_data.append(metric_info)
                            
                            response = {
                                "success": True,
                                "data_source": "scraper",
                                "time_range": period,
                                "step": 60,  # Default step for scraper data
                                "metrics": metrics_data,
                                "metric_id": metric_id,
                            }
                            
                            # Include summary stats if available
                            if historical_data and historical_data.summary_stats:
                                response["summary_stats"] = historical_data.summary_stats
                            
                            # Include metadata
                            if historical_data and historical_data.metadata:
                                response["metadata"] = {
                                    "host": historical_data.metadata.get("host_name", host_name),
                                    "service": historical_data.metadata.get("service_name", service_description),
                                    "period": historical_data.metadata.get("time_range", period),
                                    "data_points_parsed": historical_data.metadata.get("parsed_data_points", 0),
                                    "execution_time_ms": historical_data.metadata.get("execution_time_ms", 0),
                                }
                            
                            return response
                        else:
                            return {
                                "success": False,
                                "error": result.error or "Historical data retrieval failed",
                                "data_source": "scraper"
                            }
                            
                    except ImportError as e:
                        return {
                            "success": False,
                            "error": f"Historical service model import failed: {e}",
                            "data_source": "scraper"
                        }
                    except Exception as e:
                        logger.exception(f"Error using scraper data source for {host_name}/{service_description}/{metric_id}")
                        return {
                            "success": False,
                            "error": f"Scraper data source error: {sanitize_error(e)}",
                            "data_source": "scraper"
                        }
                        
                else:  # effective_source == "rest_api" or fallback
                    # Use existing REST API logic
                    if not self.metrics_service:
                        return {
                            "success": False,
                            "error": "Metrics service not available"
                        }
                        
                    result = await self.metrics_service.get_metric_history(
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