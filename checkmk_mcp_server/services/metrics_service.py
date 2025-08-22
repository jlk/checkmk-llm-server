"""Metrics service - provides access to Checkmk metrics and performance data."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from .base import BaseService, ServiceResult
from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkAPIError
from ..config import AppConfig


def _create_time_range_object(start_time: datetime, end_time: datetime) -> List[int]:
    """
    Convert datetime objects to a time_range array for Checkmk metrics API.

    Based on the API validation errors, the Checkmk REST API expects a time_range
    as an array of two integer Unix timestamps: [start_timestamp, end_timestamp]

    Args:
        start_time: Start datetime
        end_time: End datetime

    Returns:
        List with start and end Unix timestamps as integers

    Raises:
        ValueError: If timestamps are invalid or in wrong order
    """
    if start_time >= end_time:
        raise ValueError("Start time must be before end time")

    # Validate reasonable timestamp range (not too far in past/future)
    current_time = datetime.now()
    if start_time > current_time + timedelta(days=1):  # More than 1 day in future
        raise ValueError("Start time cannot be more than 1 day in the future")
    if end_time > current_time + timedelta(days=1):  # More than 1 day in future
        raise ValueError("End time cannot be more than 1 day in the future")

    # Convert to Unix timestamps as integers (no fractional seconds)
    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(end_time.timestamp())

    return [start_timestamp, end_timestamp]


class MetricInfo:
    """Metric data information."""

    def __init__(self, metric_data: Dict[str, Any]):
        self.color = metric_data.get("color", "#000000")
        self.data_points = metric_data.get("data_points", [])
        self.line_type = metric_data.get("line_type", "line")
        self.title = metric_data.get("title", "")
        self.raw_data = metric_data


class GraphCollection:
    """Graph collection containing metrics data."""

    def __init__(self, graph_data: Dict[str, Any]):
        self.time_range = graph_data.get("time_range", {})
        self.step = graph_data.get("step", 60)
        self.metrics = []

        # Convert metrics data to MetricInfo objects
        for metric_data in graph_data.get("metrics", []):
            self.metrics.append(MetricInfo(metric_data))

        self.raw_data = graph_data


class MetricsService(BaseService):
    """Metrics service - provides access to performance metrics and graphs."""

    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        super().__init__(checkmk_client, config)
        self.logger = logging.getLogger(__name__)

    async def get_single_metric(
        self,
        host_name: str,
        service_description: str,
        metric_id: str,
        time_range_hours: int = 24,
        reduce: str = "average",
        site: Optional[str] = None,
    ) -> ServiceResult[GraphCollection]:
        """
        Get data for a single metric.

        Args:
            host_name: Host name
            service_description: Service description
            metric_id: Metric ID (activate "Show internal IDs" in Checkmk UI to see IDs)
            time_range_hours: Number of hours back to retrieve data (default: 24)
            reduce: Data reduction method - "min", "max", or "average" (default: "average")
            site: Optional site name for performance optimization

        Returns:
            ServiceResult containing GraphCollection with metric data
        """

        async def _get_single_metric_operation():
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_range_hours)

            # Build request data
            # Note: Checkmk REST API requires time_range object with datetime strings
            data = {
                "type": "single_metric",
                "host_name": host_name,
                "service_description": service_description,
                "metric_id": metric_id,
                "time_range": _create_time_range_object(start_time, end_time),
                "reduce": reduce,
            }

            if site:
                data["site"] = site

            # Make API request
            response = await self._make_api_request(
                "POST", "/domain-types/metric/actions/get/invoke", json=data
            )

            return GraphCollection(response)

        return await self._execute_with_error_handling(
            _get_single_metric_operation, f"get_single_metric_{host_name}_{metric_id}"
        )

    async def get_predefined_graph(
        self,
        host_name: str,
        service_description: str,
        graph_id: str,
        time_range_hours: int = 24,
        reduce: str = "average",
        site: Optional[str] = None,
    ) -> ServiceResult[GraphCollection]:
        """
        Get data for a predefined graph (containing multiple metrics).

        Args:
            host_name: Host name
            service_description: Service description
            graph_id: Graph ID (activate "Show internal IDs" in Checkmk UI to see IDs)
            time_range_hours: Number of hours back to retrieve data (default: 24)
            reduce: Data reduction method - "min", "max", or "average" (default: "average")
            site: Optional site name for performance optimization

        Returns:
            ServiceResult containing GraphCollection with graph data
        """

        async def _get_predefined_graph_operation():
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_range_hours)

            # Build request data
            # Note: Checkmk REST API requires time_range object with datetime strings
            data = {
                "type": "predefined_graph",
                "host_name": host_name,
                "service_description": service_description,
                "graph_id": graph_id,
                "time_range": _create_time_range_object(start_time, end_time),
                "reduce": reduce,
            }

            if site:
                data["site"] = site

            # Make API request
            response = await self._make_api_request(
                "POST", "/domain-types/metric/actions/get/invoke", json=data
            )

            return GraphCollection(response)

        return await self._execute_with_error_handling(
            _get_predefined_graph_operation,
            f"get_predefined_graph_{host_name}_{graph_id}",
        )

    async def get_service_metrics(
        self,
        host_name: str,
        service_description: str,
        time_range_hours: int = 24,
        reduce: str = "average",
        site: Optional[str] = None,
    ) -> ServiceResult[List[GraphCollection]]:
        """
        Get common metrics for a service. This method attempts to retrieve
        several common graph types that are typically available.

        Args:
            host_name: Host name
            service_description: Service description
            time_range_hours: Number of hours back to retrieve data (default: 24)
            reduce: Data reduction method - "min", "max", or "average" (default: "average")
            site: Optional site name for performance optimization

        Returns:
            ServiceResult containing list of GraphCollection objects
        """

        async def _get_service_metrics_operation():
            # Common graph IDs that might be available (this is service-dependent)
            common_graph_ids = [
                "cpu_time_by_phase",  # CPU graphs
                "check_execution_time",  # Check timing
                "memory_usage",  # Memory graphs
                "filesystem_usage",  # Disk usage
                "interface_traffic",  # Network interface
                "load_average",  # System load
                "disk_io",  # Disk I/O
                "temperature",  # Temperature monitoring
            ]

            results = []

            # Try to get predefined graphs for common metrics
            for graph_id in common_graph_ids:
                try:
                    result = await self.get_predefined_graph(
                        host_name,
                        service_description,
                        graph_id,
                        time_range_hours,
                        reduce,
                        site,
                    )
                    if result.success and result.data.metrics:
                        results.append(result.data)
                except Exception as e:
                    # Graph might not exist for this service - continue with others
                    self.logger.debug(
                        f"Graph {graph_id} not available for {service_description}: {e}"
                    )
                    continue

            return results

        return await self._execute_with_error_handling(
            _get_service_metrics_operation,
            f"get_service_metrics_{host_name}_{service_description}",
        )

    async def get_metric_history(
        self,
        host_name: str,
        service_description: str,
        metric_id: str,
        time_range_hours: int = 168,  # 1 week
        reduce: str = "average",
        site: Optional[str] = None,
    ) -> ServiceResult[GraphCollection]:
        """
        Get historical data for a specific metric over a longer time period.

        Args:
            host_name: Host name
            service_description: Service description
            metric_id: Metric ID
            time_range_hours: Number of hours back to retrieve data (default: 168 = 1 week)
            reduce: Data reduction method - "min", "max", or "average" (default: "average")
            site: Optional site name for performance optimization

        Returns:
            ServiceResult containing GraphCollection with historical metric data
        """
        # This is essentially the same as get_single_metric but with longer default time range
        return await self.get_single_metric(
            host_name, service_description, metric_id, time_range_hours, reduce, site
        )

    async def get_performance_summary(
        self, host_name: str, service_description: str, time_range_hours: int = 24
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get a performance summary for a service including key metrics.

        Args:
            host_name: Host name
            service_description: Service description
            time_range_hours: Number of hours back to analyze (default: 24)

        Returns:
            ServiceResult containing performance summary
        """

        async def _get_performance_summary_operation():
            summary = {
                "host_name": host_name,
                "service_description": service_description,
                "time_range_hours": time_range_hours,
                "metrics_found": 0,
                "graphs_found": 0,
                "performance_data": [],
            }

            # Try to get service metrics
            metrics_result = await self.get_service_metrics(
                host_name, service_description, time_range_hours
            )

            if metrics_result.success:
                summary["graphs_found"] = len(metrics_result.data)

                for graph in metrics_result.data:
                    summary["metrics_found"] += len(graph.metrics)

                    # Add summary data for each graph
                    for metric in graph.metrics:
                        if metric.data_points:
                            # Calculate basic statistics
                            data_points = [
                                float(x) for x in metric.data_points if x is not None
                            ]
                            if data_points:
                                performance_info = {
                                    "metric_title": metric.title,
                                    "line_type": metric.line_type,
                                    "data_points_count": len(data_points),
                                    "min_value": min(data_points),
                                    "max_value": max(data_points),
                                    "avg_value": sum(data_points) / len(data_points),
                                    "last_value": (
                                        data_points[-1] if data_points else None
                                    ),
                                }
                                summary["performance_data"].append(performance_info)

            return summary

        return await self._execute_with_error_handling(
            _get_performance_summary_operation,
            f"get_performance_summary_{host_name}_{service_description}",
        )

    async def _make_api_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """Make an API request using the underlying client."""
        try:
            # Use the sync client through the async wrapper
            sync_client = self.checkmk.sync_client
            return sync_client._make_request(method, endpoint, **kwargs)
        except Exception as e:
            self.logger.error(f"Metrics API request failed: {e}")
            raise CheckmkAPIError(f"Metrics API request failed: {e}")
