"""Performance monitoring and metrics collection."""

import asyncio
import time
import logging
import statistics
from typing import Dict, Any, List, Optional, Callable, TypeVar
from datetime import datetime, timedelta
from collections import defaultdict, deque
from functools import wraps
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field


F = TypeVar("F", bound=Callable[..., Any])


class PerformanceMetric(BaseModel):
    """A single performance metric measurement."""

    name: str
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=datetime.now)
    tags: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimingStats(BaseModel):
    """Statistics for timing measurements."""

    count: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    avg_time: float = 0.0
    recent_times: List[float] = Field(default_factory=list, max_length=100)

    def add_measurement(self, duration: float):
        """Add a timing measurement."""
        self.count += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.avg_time = self.total_time / self.count

        # Keep only recent measurements
        self.recent_times.append(duration)
        if len(self.recent_times) > 100:
            self.recent_times.pop(0)

    @property
    def recent_avg(self) -> float:
        """Get average of recent measurements."""
        return statistics.mean(self.recent_times) if self.recent_times else 0.0

    @property
    def p95(self) -> float:
        """Get 95th percentile of recent measurements."""
        if len(self.recent_times) < 2:
            return 0.0
        return statistics.quantiles(self.recent_times, n=20)[18]  # 95th percentile

    @property
    def p99(self) -> float:
        """Get 99th percentile of recent measurements."""
        if len(self.recent_times) < 2:
            return 0.0
        return statistics.quantiles(self.recent_times, n=100)[98]  # 99th percentile


class MetricsCollector:
    """Centralized metrics collection system."""

    def __init__(self, retention_hours: int = 24):
        """
        Initialize metrics collector.

        Args:
            retention_hours: How long to keep metrics in memory
        """
        self.retention_hours = retention_hours
        self.metrics: deque = deque()
        self.timing_stats: Dict[str, TimingStats] = defaultdict(TimingStats)
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "count",
        tags: Optional[Dict[str, str]] = None,
        **metadata,
    ):
        """Record a metric."""
        metric = PerformanceMetric(
            name=name, value=value, unit=unit, tags=tags or {}, metadata=metadata
        )

        async with self._lock:
            self.metrics.append(metric)

    async def record_timing(self, name: str, duration: float, **tags):
        """Record a timing measurement."""
        async with self._lock:
            self.timing_stats[name].add_measurement(duration)

        await self.record_metric(
            name=f"{name}.duration", value=duration, unit="seconds", tags=tags
        )

    async def increment_counter(self, name: str, value: int = 1, **tags):
        """Increment a counter."""
        async with self._lock:
            self.counters[name] += value

        await self.record_metric(
            name=f"{name}.count", value=value, unit="count", tags=tags
        )

    async def set_gauge(self, name: str, value: float, **tags):
        """Set a gauge value."""
        async with self._lock:
            self.gauges[name] = value

        await self.record_metric(
            name=f"{name}.gauge", value=value, unit="gauge", tags=tags
        )

    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive metrics statistics."""
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(hours=1)  # Last hour

            # Get recent metrics
            recent_metrics = [m for m in self.metrics if m.timestamp >= cutoff]

            # Calculate request rate
            request_rate = (
                len([m for m in recent_metrics if m.name.endswith(".duration")]) / 3600
            )  # per second

            return {
                "total_metrics": len(self.metrics),
                "recent_metrics_1h": len(recent_metrics),
                "request_rate_per_second": request_rate,
                "timing_stats": {
                    name: {
                        "count": stats.count,
                        "avg_ms": stats.avg_time * 1000,
                        "min_ms": stats.min_time * 1000,
                        "max_ms": stats.max_time * 1000,
                        "recent_avg_ms": stats.recent_avg * 1000,
                        "p95_ms": stats.p95 * 1000,
                        "p99_ms": stats.p99 * 1000,
                    }
                    for name, stats in self.timing_stats.items()
                },
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "memory_usage": {
                    "metrics_count": len(self.metrics),
                    "timing_stats_count": len(self.timing_stats),
                    "counters_count": len(self.counters),
                    "gauges_count": len(self.gauges),
                },
            }

    async def get_timing_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get timing statistics for a specific metric."""
        async with self._lock:
            stats = self.timing_stats.get(name)
            if not stats:
                return None

            return {
                "name": name,
                "count": stats.count,
                "total_time": stats.total_time,
                "avg_time": stats.avg_time,
                "min_time": stats.min_time,
                "max_time": stats.max_time,
                "recent_avg": stats.recent_avg,
                "p95": stats.p95,
                "p99": stats.p99,
            }

    async def _cleanup_loop(self):
        """Background task to clean up old metrics."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_old_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in metrics cleanup: {e}")

    async def _cleanup_old_metrics(self):
        """Remove old metrics beyond retention period."""
        cutoff = datetime.now() - timedelta(hours=self.retention_hours)

        async with self._lock:
            # Remove old metrics
            while self.metrics and self.metrics[0].timestamp < cutoff:
                self.metrics.popleft()

            self.logger.debug(f"Cleaned up metrics, {len(self.metrics)} remaining")

    def __del__(self):
        """Cleanup on destruction."""
        if hasattr(self, "_cleanup_task"):
            self._cleanup_task.cancel()


# Global metrics collector instance (lazy initialization)
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def timed(metric_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """
    Decorator to automatically time function execution.

    Args:
        metric_name: Name for the metric (defaults to function name)
        tags: Additional tags for the metric
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                await get_metrics_collector().record_timing(
                    name, duration, **(tags or {})
                )
                await get_metrics_collector().increment_counter(f"{name}.success")
                return result

            except Exception as e:
                duration = time.time() - start_time
                await get_metrics_collector().record_timing(
                    f"{name}.error", duration, **(tags or {})
                )
                await get_metrics_collector().increment_counter(f"{name}.error")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                # For sync functions, we can't easily record metrics without making them async
                # Could use a background thread, but keeping it simple for now
                return result

            except Exception as e:
                duration = time.time() - start_time
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@asynccontextmanager
async def timed_context(metric_name: str, tags: Optional[Dict[str, str]] = None):
    """
    Context manager for timing code blocks.

    Usage:
        async with timed_context("my_operation"):
            # code to time
            pass
    """
    start_time = time.time()
    try:
        yield
        duration = time.time() - start_time
        await get_metrics_collector().record_timing(
            metric_name, duration, **(tags or {})
        )
        await get_metrics_collector().increment_counter(f"{metric_name}.success")

    except Exception as e:
        duration = time.time() - start_time
        await get_metrics_collector().record_timing(
            f"{metric_name}.error", duration, **(tags or {})
        )
        await get_metrics_collector().increment_counter(f"{metric_name}.error")
        raise


class MetricsMixin:
    """Mixin to add metrics capabilities to services."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = get_metrics_collector()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def record_operation(
        self, operation: str, duration: float, success: bool = True, **tags
    ):
        """Record an operation metric."""
        await self.metrics.record_timing(
            f"{self.__class__.__name__}.{operation}", duration, **tags
        )

        if success:
            await self.metrics.increment_counter(
                f"{self.__class__.__name__}.{operation}.success", **tags
            )
        else:
            await self.metrics.increment_counter(
                f"{self.__class__.__name__}.{operation}.error", **tags
            )

    async def record_api_call(
        self, endpoint: str, duration: float, status_code: int = 200
    ):
        """Record API call metrics."""
        await self.metrics.record_timing(f"api.{endpoint}", duration)
        await self.metrics.increment_counter(f"api.{endpoint}.calls")

        if 200 <= status_code < 300:
            await self.metrics.increment_counter(f"api.{endpoint}.success")
        elif 400 <= status_code < 500:
            await self.metrics.increment_counter(f"api.{endpoint}.client_error")
        elif 500 <= status_code < 600:
            await self.metrics.increment_counter(f"api.{endpoint}.server_error")

    async def record_cache_hit(self, cache_key: str):
        """Record cache hit."""
        await self.metrics.increment_counter("cache.hits", cache_key=cache_key)

    async def record_cache_miss(self, cache_key: str):
        """Record cache miss."""
        await self.metrics.increment_counter("cache.misses", cache_key=cache_key)

    async def set_active_connections(self, count: int):
        """Set number of active connections."""
        await self.metrics.set_gauge("connections.active", count)

    async def set_queue_size(self, queue_name: str, size: int):
        """Set queue size."""
        await self.metrics.set_gauge(f"queue.{queue_name}.size", size)

    async def get_service_metrics(self) -> Dict[str, Any]:
        """Get metrics specific to this service."""
        all_stats = await self.metrics.get_stats()
        service_name = self.__class__.__name__

        # Filter metrics for this service
        service_timing = {
            k: v
            for k, v in all_stats["timing_stats"].items()
            if k.startswith(service_name)
        }

        service_counters = {
            k: v for k, v in all_stats["counters"].items() if k.startswith(service_name)
        }

        return {
            "service": service_name,
            "timing_stats": service_timing,
            "counters": service_counters,
            "total_operations": sum(v["count"] for v in service_timing.values()),
            "avg_response_time": (
                statistics.mean([v["avg_ms"] for v in service_timing.values()])
                if service_timing
                else 0
            ),
        }
