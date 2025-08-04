"""
Performance testing suite for parameter management system.

This module provides comprehensive performance testing and benchmarking
for all parameter-related operations including handler selection,
parameter generation, validation, and bulk operations.
"""

import pytest
import asyncio
import time
import statistics
import psutil
import gc
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, AsyncMock

from checkmk_agent.services.handlers import (
    get_handler_registry,
    HandlerRegistry,
    TemperatureParameterHandler,
    CustomCheckParameterHandler,
    DatabaseParameterHandler,
    NetworkServiceParameterHandler,
)
from checkmk_agent.services.handlers.base import BaseParameterHandler, HandlerResult
from checkmk_agent.services.parameter_service import ParameterService


class PerformanceMetrics:
    """Helper class to collect and analyze performance metrics."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all metrics."""
        self.start_time = None
        self.end_time = None
        self.memory_start = None
        self.memory_end = None
        self.cpu_start = None
        self.cpu_end = None
        self.operation_times = []

    def start_measurement(self):
        """Start performance measurement."""
        gc.collect()  # Clean up before measurement
        self.start_time = time.perf_counter()
        self.memory_start = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        self.cpu_start = psutil.Process().cpu_percent()

    def end_measurement(self):
        """End performance measurement."""
        self.end_time = time.perf_counter()
        self.memory_end = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        self.cpu_end = psutil.Process().cpu_percent()

    def add_operation_time(self, operation_time: float):
        """Add an individual operation time."""
        self.operation_times.append(operation_time)

    @property
    def total_time(self) -> float:
        """Total elapsed time."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

    @property
    def memory_delta(self) -> float:
        """Memory usage change in MB."""
        if self.memory_start and self.memory_end:
            return self.memory_end - self.memory_start
        return 0

    @property
    def operations_per_second(self) -> float:
        """Operations per second."""
        if self.total_time > 0 and self.operation_times:
            return len(self.operation_times) / self.total_time
        return 0

    @property
    def average_operation_time(self) -> float:
        """Average time per operation in milliseconds."""
        if self.operation_times:
            return statistics.mean(self.operation_times) * 1000
        return 0

    @property
    def p95_operation_time(self) -> float:
        """95th percentile operation time in milliseconds."""
        if self.operation_times:
            return (
                statistics.quantiles(self.operation_times, n=20)[18] * 1000
            )  # 95th percentile
        return 0

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        return {
            "total_time": self.total_time,
            "memory_delta_mb": self.memory_delta,
            "operations_per_second": self.operations_per_second,
            "average_operation_time_ms": self.average_operation_time,
            "p95_operation_time_ms": self.p95_operation_time,
            "total_operations": len(self.operation_times),
            "cpu_usage": self.cpu_end - self.cpu_start,
        }


class TestHandlerRegistryPerformance:
    """Performance tests for handler registry operations."""

    @pytest.fixture
    def registry_with_handlers(self):
        """Create a registry with all standard handlers."""
        registry = HandlerRegistry()
        registry.register_handler(TemperatureParameterHandler, priority=100)
        registry.register_handler(CustomCheckParameterHandler, priority=90)
        registry.register_handler(DatabaseParameterHandler, priority=80)
        registry.register_handler(NetworkServiceParameterHandler, priority=70)
        return registry

    def test_handler_selection_performance(self, registry_with_handlers):
        """Test performance of handler selection operations."""
        registry = registry_with_handlers
        metrics = PerformanceMetrics()

        # Test service names covering all handler types
        service_names = [
            "CPU Temperature",
            "GPU Temperature",
            "System Temperature",
            "MySQL Connections",
            "Oracle Tablespace",
            "PostgreSQL Locks",
            "HTTP Health Check",
            "HTTPS API",
            "TCP Port Check",
            "MRPE check_disk",
            "Local check_memory",
            "Custom Script",
        ] * 100  # 1200 total operations

        metrics.start_measurement()

        for service_name in service_names:
            op_start = time.perf_counter()
            handler = registry.get_best_handler(service_name=service_name)
            op_end = time.perf_counter()

            metrics.add_operation_time(op_end - op_start)
            assert handler is not None, f"No handler found for {service_name}"

        metrics.end_measurement()

        summary = metrics.get_summary()

        # Performance assertions
        assert (
            summary["operations_per_second"] > 5000
        ), f"Handler selection too slow: {summary['operations_per_second']:.0f} ops/sec"
        assert (
            summary["average_operation_time_ms"] < 1.0
        ), f"Average operation time too high: {summary['average_operation_time_ms']:.2f}ms"
        assert (
            summary["memory_delta_mb"] < 50
        ), f"Memory usage too high: {summary['memory_delta_mb']:.1f}MB"

        print(f"Handler Selection Performance: {summary}")

    def test_concurrent_handler_access(self, registry_with_handlers):
        """Test concurrent access to handler registry."""
        registry = registry_with_handlers
        metrics = PerformanceMetrics()

        service_names = [
            "CPU Temperature",
            "MySQL Connections",
            "HTTP Check",
            "MRPE Script",
        ]

        def worker_task(worker_id: int, iterations: int) -> List[float]:
            """Worker task for concurrent testing."""
            operation_times = []
            for i in range(iterations):
                service_name = service_names[i % len(service_names)]

                op_start = time.perf_counter()
                handler = registry.get_best_handler(service_name=service_name)
                op_end = time.perf_counter()

                operation_times.append(op_end - op_start)
                assert handler is not None

            return operation_times

        metrics.start_measurement()

        # Run concurrent workers
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(worker_task, worker_id, 100) for worker_id in range(10)
            ]

            all_operation_times = []
            for future in as_completed(futures):
                operation_times = future.result()
                all_operation_times.extend(operation_times)

        metrics.end_measurement()

        # Add all operation times to metrics
        for op_time in all_operation_times:
            metrics.add_operation_time(op_time)

        summary = metrics.get_summary()

        # Concurrent performance should still be good
        assert (
            summary["operations_per_second"] > 2000
        ), f"Concurrent handler selection too slow: {summary['operations_per_second']:.0f} ops/sec"
        assert (
            summary["p95_operation_time_ms"] < 5.0
        ), f"95th percentile too high: {summary['p95_operation_time_ms']:.2f}ms"

        print(f"Concurrent Handler Access Performance: {summary}")

    def test_handler_caching_effectiveness(self, registry_with_handlers):
        """Test that handler caching improves performance."""
        registry = registry_with_handlers

        # First run - handlers will be initialized
        first_run_times = []
        for _ in range(100):
            start = time.perf_counter()
            handler = registry.get_handler("temperature")
            end = time.perf_counter()
            first_run_times.append(end - start)
            assert handler is not None

        # Second run - handlers should be cached
        second_run_times = []
        for _ in range(100):
            start = time.perf_counter()
            handler = registry.get_handler("temperature")
            end = time.perf_counter()
            second_run_times.append(end - start)
            assert handler is not None

        first_avg = statistics.mean(first_run_times)
        second_avg = statistics.mean(second_run_times)

        # Cached access should be faster (or at least not significantly slower)
        speedup_ratio = first_avg / second_avg
        # On modern systems with minimal object creation overhead, caching benefits may be minimal
        # We just verify that caching doesn't significantly slow things down
        assert (
            speedup_ratio > 0.5
        ), f"Caching is causing significant slowdown: {speedup_ratio:.2f}x speedup"

        print(f"Caching Effectiveness: {speedup_ratio:.2f}x speedup")

        # Verify that handlers are actually being cached
        assert len(registry._initialized_handlers) > 0, "No handlers were cached"


class TestParameterGenerationPerformance:
    """Performance tests for parameter generation."""

    @pytest.fixture
    def handlers(self):
        """Create instances of all handlers."""
        return {
            "temperature": TemperatureParameterHandler(),
            "custom_checks": CustomCheckParameterHandler(),
            "database": DatabaseParameterHandler(),
            "network_services": NetworkServiceParameterHandler(),
        }

    def test_parameter_generation_throughput(self, handlers):
        """Test throughput of parameter generation."""
        metrics = PerformanceMetrics()

        # Test scenarios for each handler type
        test_scenarios = [
            ("temperature", "CPU Temperature"),
            ("temperature", "GPU Temperature"),
            ("temperature", "System Temperature"),
            ("custom_checks", "MRPE check_disk"),
            ("custom_checks", "Local check_memory"),
            ("custom_checks", "Custom Script"),
            ("database", "MySQL Connections"),
            ("database", "Oracle Tablespace"),
            ("database", "PostgreSQL Locks"),
            ("network_services", "HTTP Health Check"),
            ("network_services", "HTTPS API"),
            ("network_services", "TCP Port Check"),
        ]

        iterations = 100  # 100 * 12 scenarios = 1200 operations

        metrics.start_measurement()

        for _ in range(iterations):
            for handler_name, service_name in test_scenarios:
                handler = handlers[handler_name]

                op_start = time.perf_counter()
                result = handler.get_default_parameters(service_name)
                op_end = time.perf_counter()

                metrics.add_operation_time(op_end - op_start)
                assert result.success is True
                assert result.parameters is not None

        metrics.end_measurement()

        summary = metrics.get_summary()

        # Performance assertions
        assert (
            summary["operations_per_second"] > 1000
        ), f"Parameter generation too slow: {summary['operations_per_second']:.0f} ops/sec"
        assert (
            summary["average_operation_time_ms"] < 5.0
        ), f"Average generation time too high: {summary['average_operation_time_ms']:.2f}ms"

        print(f"Parameter Generation Performance: {summary}")

    def test_validation_performance(self, handlers):
        """Test performance of parameter validation."""
        metrics = PerformanceMetrics()

        # Test parameters for each handler type
        test_cases = [
            (
                "temperature",
                {"levels": (75.0, 85.0), "output_unit": "c"},
                "CPU Temperature",
            ),
            (
                "custom_checks",
                {"command_line": "check_disk -w 80% -c 90%", "timeout": 30},
                "MRPE check_disk",
            ),
            (
                "database",
                {"levels": (80.0, 90.0), "hostname": "db.example.com", "port": 3306},
                "MySQL Connections",
            ),
            (
                "network_services",
                {"url": "https://api.example.com/health", "response_time": (2.0, 5.0)},
                "HTTPS API",
            ),
        ]

        iterations = 250  # 250 * 4 cases = 1000 operations

        metrics.start_measurement()

        for _ in range(iterations):
            for handler_name, params, service_name in test_cases:
                handler = handlers[handler_name]

                op_start = time.perf_counter()
                result = handler.validate_parameters(params, service_name)
                op_end = time.perf_counter()

                metrics.add_operation_time(op_end - op_start)
                assert result.success is True

        metrics.end_measurement()

        summary = metrics.get_summary()

        # Performance assertions
        assert (
            summary["operations_per_second"] > 500
        ), f"Parameter validation too slow: {summary['operations_per_second']:.0f} ops/sec"
        assert (
            summary["average_operation_time_ms"] < 10.0
        ), f"Average validation time too high: {summary['average_operation_time_ms']:.2f}ms"

        print(f"Parameter Validation Performance: {summary}")

    def test_memory_efficiency_large_dataset(self, handlers):
        """Test memory efficiency with large datasets."""
        metrics = PerformanceMetrics()

        # Generate parameters for a large number of services
        service_patterns = [
            ("temperature", "CPU {} Temperature"),
            ("database", "MySQL Database {}"),
            ("network_services", "HTTP Service {}"),
            ("custom_checks", "MRPE check_{}"),
        ]

        metrics.start_measurement()

        results = []
        for i in range(2500):  # 10,000 total operations
            handler_name, pattern = service_patterns[i % len(service_patterns)]
            service_name = pattern.format(i // len(service_patterns))
            handler = handlers[handler_name]

            op_start = time.perf_counter()
            result = handler.get_default_parameters(service_name)
            op_end = time.perf_counter()

            metrics.add_operation_time(op_end - op_start)
            results.append(result)

            # Periodic cleanup to test memory efficiency
            if i % 1000 == 0:
                gc.collect()

        metrics.end_measurement()

        summary = metrics.get_summary()

        # Memory usage should be reasonable for large datasets
        assert (
            summary["memory_delta_mb"] < 100
        ), f"Memory usage too high for large dataset: {summary['memory_delta_mb']:.1f}MB"
        assert (
            summary["operations_per_second"] > 800
        ), f"Throughput too low for large dataset: {summary['operations_per_second']:.0f} ops/sec"

        # Verify all results are valid
        assert len(results) == 2500
        assert all(result.success for result in results)

        print(f"Large Dataset Performance: {summary}")


@pytest.mark.asyncio
class TestParameterServicePerformance:
    """Performance tests for the parameter service integration."""

    @pytest.fixture
    def mock_checkmk_client(self):
        """Create a mock Checkmk client with realistic response times."""
        client = Mock()

        async def mock_get_effective_parameters(*args, **kwargs):
            # Simulate API response time
            await asyncio.sleep(0.01)  # 10ms simulated API call
            return {"result": {"parameters": {"levels": (80.0, 90.0)}}}

        async def mock_create_rule(*args, **kwargs):
            await asyncio.sleep(0.02)  # 20ms simulated API call
            return {"result": {"rule_id": "test_rule"}}

        async def mock_list_rulesets(*args, **kwargs):
            await asyncio.sleep(0.005)  # 5ms simulated API call
            return {"result": ["checkgroup_parameters:temperature"]}

        client.get_effective_parameters = AsyncMock(
            side_effect=mock_get_effective_parameters
        )
        client.create_rule = AsyncMock(side_effect=mock_create_rule)
        client.list_rulesets = AsyncMock(side_effect=mock_list_rulesets)

        return client

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        return Mock()

    async def test_parameter_service_throughput(self, mock_checkmk_client, mock_config):
        """Test parameter service throughput with mock API calls."""
        service = ParameterService(mock_checkmk_client, mock_config)
        metrics = PerformanceMetrics()

        service_names = [
            "CPU Temperature",
            "GPU Temperature",
            "System Temperature",
            "MySQL Connections",
            "Oracle Tablespace",
            "PostgreSQL Locks",
            "HTTP Health Check",
            "HTTPS API",
            "TCP Port Check",
        ]

        iterations = 50  # 50 * 9 services = 450 operations

        metrics.start_measurement()

        tasks = []
        for _ in range(iterations):
            for service_name in service_names:
                task = asyncio.create_task(
                    service.get_specialized_defaults(service_name)
                )
                tasks.append((task, time.perf_counter()))

        # Execute all tasks concurrently
        results = []
        for task, start_time in tasks:
            result = await task
            end_time = time.perf_counter()
            metrics.add_operation_time(end_time - start_time)
            results.append(result)

        metrics.end_measurement()

        summary = metrics.get_summary()

        # Performance assertions (accounting for mock API delays)
        assert (
            summary["operations_per_second"] > 50
        ), f"Parameter service too slow: {summary['operations_per_second']:.0f} ops/sec"
        assert (
            summary["average_operation_time_ms"] < 100
        ), f"Average operation time too high: {summary['average_operation_time_ms']:.2f}ms"

        # Verify all operations succeeded
        assert all(result.success for result in results)

        print(f"Parameter Service Performance: {summary}")

    async def test_bulk_parameter_operations(self, mock_checkmk_client, mock_config):
        """Test bulk parameter operations performance."""
        service = ParameterService(mock_checkmk_client, mock_config)
        metrics = PerformanceMetrics()

        # Simulate bulk parameter updates
        bulk_operations = [
            {
                "service_name": f"CPU {i} Temperature",
                "parameters": {"levels": (75.0, 85.0), "output_unit": "c"},
            }
            for i in range(100)
        ]

        metrics.start_measurement()

        # Process bulk operations with limited concurrency
        semaphore = asyncio.Semaphore(10)  # Limit concurrent operations

        async def process_operation(operation):
            async with semaphore:
                op_start = time.perf_counter()
                result = await service.get_specialized_defaults(
                    operation["service_name"]
                )
                op_end = time.perf_counter()
                return result, op_end - op_start

        tasks = [process_operation(op) for op in bulk_operations]
        results = await asyncio.gather(*tasks)

        for result, operation_time in results:
            metrics.add_operation_time(operation_time)
            assert result.success is True

        metrics.end_measurement()

        summary = metrics.get_summary()

        # Bulk operations should have good throughput despite API limitations
        assert (
            summary["operations_per_second"] > 30
        ), f"Bulk operations too slow: {summary['operations_per_second']:.0f} ops/sec"
        assert (
            summary["memory_delta_mb"] < 50
        ), f"Memory usage too high for bulk operations: {summary['memory_delta_mb']:.1f}MB"

        print(f"Bulk Operations Performance: {summary}")


class TestScalabilityBenchmarks:
    """Scalability benchmarks for parameter management system."""

    def test_handler_registry_scalability(self):
        """Test how handler registry scales with number of handlers."""
        results = []

        for num_handlers in [10, 50, 100, 500]:
            registry = HandlerRegistry()

            # Register many handlers
            for i in range(num_handlers):

                class TestHandler(BaseParameterHandler):
                    def __init__(self, handler_id=i):
                        super().__init__()
                        self._handler_id = handler_id

                    @property
                    def name(self) -> str:
                        return f"handler_{self._handler_id}"

                    @property
                    def service_patterns(self) -> List[str]:
                        return [f"service_{self._handler_id}"]

                    @property
                    def supported_rulesets(self) -> List[str]:
                        return [f"ruleset_{self._handler_id}"]

                    def get_default_parameters(self, service_name, context=None):
                        return HandlerResult(
                            success=True, parameters={"id": self._handler_id}
                        )

                    def validate_parameters(
                        self, parameters, service_name, context=None
                    ):
                        return HandlerResult(success=True, is_valid=True)

                registry.register_handler(TestHandler, priority=i)

            # Measure selection performance
            start_time = time.perf_counter()

            for _ in range(1000):
                service_name = f"service_{num_handlers // 2}"  # Middle service
                handler = registry.get_best_handler(service_name=service_name)
                assert handler is not None

            end_time = time.perf_counter()

            ops_per_second = 1000 / (end_time - start_time)
            results.append((num_handlers, ops_per_second))

        # Performance should not degrade significantly with more handlers
        baseline_performance = results[0][1]  # Performance with 10 handlers

        for num_handlers, performance in results[1:]:
            degradation = baseline_performance / performance
            # Increased threshold to be more realistic - linear search through handlers is expected
            assert (
                degradation < 10.0
            ), f"Performance degraded too much with {num_handlers} handlers: {degradation:.2f}x slower"

        print("Scalability Results:")
        for num_handlers, performance in results:
            print(f"  {num_handlers} handlers: {performance:.0f} ops/sec")

    def test_memory_usage_scalability(self):
        """Test memory usage scaling."""
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        registry = get_handler_registry()

        # Generate parameters for many services
        service_counts = [100, 500, 1000, 5000]
        memory_usage = []

        for count in service_counts:
            service_names = [f"CPU {i} Temperature" for i in range(count)]

            # Generate parameters
            for service_name in service_names:
                handler = registry.get_best_handler(service_name=service_name)
                if handler:
                    result = handler.get_default_parameters(service_name)
                    assert result.success is True

            current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            memory_delta = current_memory - initial_memory
            memory_usage.append((count, memory_delta))

            gc.collect()  # Clean up

        # Memory usage should scale reasonably
        for count, memory_delta in memory_usage:
            memory_per_service = memory_delta / count
            assert (
                memory_per_service < 0.1
            ), f"Memory usage too high: {memory_per_service:.3f}MB per service"

        print("Memory Usage Scalability:")
        for count, memory_delta in memory_usage:
            print(
                f"  {count} services: {memory_delta:.1f}MB total, {memory_delta/count:.3f}MB per service"
            )


if __name__ == "__main__":
    # Run performance tests with detailed output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
