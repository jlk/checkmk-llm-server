"""Performance validation tests for request ID tracing system."""

import pytest
import asyncio
import time
import threading
import concurrent.futures
import psutil
import os
from typing import List, Tuple
from unittest.mock import Mock, patch

from checkmk_mcp_server.utils.request_context import (
    generate_request_id,
    set_request_id,
    get_request_id,
    with_request_id,
    ensure_request_id,
    REQUEST_ID_CONTEXT,
)
from checkmk_mcp_server.middleware.request_tracking import (
    track_request,
    RequestTrackingMiddleware,
    with_request_tracking,
)
from checkmk_mcp_server.logging_utils import setup_logging, RequestIDFormatter


class PerformanceMetrics:
    """Helper class to collect and analyze performance metrics."""

    def __init__(self):
        self.measurements: List[Tuple[str, float]] = []
        self.process = psutil.Process(os.getpid())

    def measure_time(self, name: str, operation):
        """Measure execution time of an operation."""
        start_time = time.perf_counter()
        result = operation()
        end_time = time.perf_counter()

        duration = end_time - start_time
        self.measurements.append((name, duration))
        return result, duration

    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024

    def get_summary(self) -> dict:
        """Get performance summary."""
        if not self.measurements:
            return {}

        durations = [d for _, d in self.measurements]
        return {
            "total_operations": len(durations),
            "total_time": sum(durations),
            "average_time": sum(durations) / len(durations),
            "min_time": min(durations),
            "max_time": max(durations),
            "operations_per_second": (
                len(durations) / sum(durations) if sum(durations) > 0 else 0
            ),
        }


class TestRequestIDGenerationPerformance:
    """Test performance characteristics of request ID generation."""

    def test_request_id_generation_speed(self):
        """Test request ID generation speed."""
        metrics = PerformanceMetrics()

        def generate_batch():
            return [generate_request_id() for _ in range(10000)]

        ids, duration = metrics.measure_time("generate_10k_ids", generate_batch)

        # Should generate 10,000 IDs in under 100ms
        assert duration < 0.1, f"ID generation too slow: {duration:.3f}s for 10,000 IDs"

        # All IDs should be unique
        assert len(set(ids)) == 10000, "Generated IDs are not unique"

        # All IDs should have correct format
        for req_id in ids:
            assert req_id.startswith("req_")
            assert len(req_id) == 9

    def test_request_id_generation_memory_usage(self):
        """Test memory usage of request ID generation."""
        metrics = PerformanceMetrics()

        initial_memory = metrics.get_memory_usage()

        # Generate a large number of IDs
        ids = [generate_request_id() for _ in range(100000)]

        final_memory = metrics.get_memory_usage()
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 50MB for 100k IDs)
        assert memory_increase < 50, f"Memory usage too high: {memory_increase:.2f}MB"

        # Verify IDs are still valid
        assert len(ids) == 100000
        assert all(id.startswith("req_") for id in ids[:100])  # Sample check

    def test_context_operations_performance(self):
        """Test performance of context get/set operations."""
        metrics = PerformanceMetrics()

        def context_operations():
            for i in range(10000):
                test_id = f"req_test{i:06d}"
                set_request_id(test_id)
                retrieved_id = get_request_id()
                assert retrieved_id == test_id

        _, duration = metrics.measure_time("10k_context_ops", context_operations)

        # Should complete 10,000 operations in under 50ms
        assert duration < 0.05, f"Context operations too slow: {duration:.3f}s"


class TestDecoratorPerformance:
    """Test performance impact of request tracking decorators."""

    def test_track_request_decorator_overhead(self):
        """Test overhead of @track_request decorator."""
        metrics = PerformanceMetrics()

        def plain_function(x):
            return x * 2

        @track_request()
        def decorated_function(x):
            return x * 2

        # Measure plain function performance
        def run_plain():
            return [plain_function(i) for i in range(10000)]

        _, plain_duration = metrics.measure_time("plain_10k", run_plain)

        # Measure decorated function performance
        def run_decorated():
            return [decorated_function(i) for i in range(10000)]

        _, decorated_duration = metrics.measure_time("decorated_10k", run_decorated)

        # Overhead should be reasonable (less than 3x slower)
        overhead_ratio = (
            decorated_duration / plain_duration if plain_duration > 0 else 1
        )
        assert (
            overhead_ratio < 3.0
        ), f"Decorator overhead too high: {overhead_ratio:.2f}x"

    @pytest.mark.asyncio
    async def test_async_decorator_performance(self):
        """Test performance of async decorators."""
        metrics = PerformanceMetrics()

        async def plain_async_function(x):
            await asyncio.sleep(0.0001)  # Minimal async work
            return x * 2

        @track_request()
        async def decorated_async_function(x):
            await asyncio.sleep(0.0001)  # Same minimal async work
            return x * 2

        # Measure plain async performance
        async def run_plain_async():
            tasks = [plain_async_function(i) for i in range(1000)]
            return await asyncio.gather(*tasks)

        start_time = time.perf_counter()
        await run_plain_async()
        plain_duration = time.perf_counter() - start_time

        # Measure decorated async performance
        async def run_decorated_async():
            tasks = [decorated_async_function(i) for i in range(1000)]
            return await asyncio.gather(*tasks)

        start_time = time.perf_counter()
        await run_decorated_async()
        decorated_duration = time.perf_counter() - start_time

        # Overhead should be reasonable for async operations
        overhead_ratio = (
            decorated_duration / plain_duration if plain_duration > 0 else 1
        )
        assert (
            overhead_ratio < 2.0
        ), f"Async decorator overhead too high: {overhead_ratio:.2f}x"


class TestConcurrencyPerformance:
    """Test performance under concurrent load."""

    def test_concurrent_request_id_generation(self):
        """Test concurrent request ID generation performance."""

        def worker():
            return [generate_request_id() for _ in range(1000)]

        start_time = time.perf_counter()

        # Run 10 concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        duration = time.perf_counter() - start_time

        # Should complete 10,000 total operations in under 1 second
        assert duration < 1.0, f"Concurrent generation too slow: {duration:.3f}s"

        # Collect all IDs and verify uniqueness
        all_ids = []
        for result in results:
            all_ids.extend(result)

        assert len(all_ids) == 10000
        assert len(set(all_ids)) == 10000, "Concurrent generation produced duplicates"

    def test_context_isolation_performance(self):
        """Test performance of context isolation across threads."""
        results_queue = []

        def worker(thread_id):
            test_id = f"req_thread{thread_id:03d}"
            measurements = []

            for i in range(1000):
                start = time.perf_counter()
                set_request_id(f"{test_id}_{i:03d}")
                retrieved = get_request_id()
                end = time.perf_counter()

                measurements.append(end - start)
                assert retrieved == f"{test_id}_{i:03d}"

            results_queue.append((thread_id, measurements))

        start_time = time.perf_counter()

        # Run 5 concurrent threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        total_duration = time.perf_counter() - start_time

        # Should complete all operations in under 1 second
        assert (
            total_duration < 1.0
        ), f"Context isolation too slow: {total_duration:.3f}s"

        # Verify all threads completed successfully
        assert len(results_queue) == 5

        # Calculate average operation time
        all_measurements = []
        for _, measurements in results_queue:
            all_measurements.extend(measurements)

        avg_operation_time = sum(all_measurements) / len(all_measurements)

        # Average operation should be very fast (under 1ms)
        assert (
            avg_operation_time < 0.001
        ), f"Average operation too slow: {avg_operation_time:.6f}s"

    @pytest.mark.asyncio
    async def test_async_concurrency_performance(self):
        """Test async concurrency performance."""

        async def async_worker(worker_id):
            results = []
            for i in range(100):
                test_id = generate_request_id()
                set_request_id(test_id)

                # Simulate async work
                await asyncio.sleep(0.001)

                retrieved = get_request_id()
                results.append((test_id, retrieved))

            return results

        start_time = time.perf_counter()

        # Run 20 concurrent async workers
        tasks = [async_worker(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time

        # Should complete in reasonable time (under 5 seconds with sleeps)
        assert duration < 5.0, f"Async concurrency too slow: {duration:.3f}s"

        # Verify all operations completed correctly
        total_operations = sum(len(result) for result in results)
        assert total_operations == 2000  # 20 workers × 100 operations

        # Verify context isolation worked
        for worker_results in results:
            for test_id, retrieved_id in worker_results:
                assert test_id == retrieved_id, "Context isolation failed"


class TestMiddlewarePerformance:
    """Test performance of request tracking middleware."""

    def test_middleware_processing_performance(self):
        """Test middleware request processing performance."""
        middleware = RequestTrackingMiddleware(
            auto_generate=True,
            log_requests=False,  # Disable logging for pure processing test
            include_timing=False,
        )

        start_time = time.perf_counter()

        # Process 10,000 requests
        for i in range(10000):
            request_context = {}
            request_id = middleware.process_request(request_context, f"operation_{i}")
            middleware.complete_request(request_id, request_context, success=True)

        duration = time.perf_counter() - start_time

        # Should complete 10,000 operations in under 1 second
        assert duration < 1.0, f"Middleware processing too slow: {duration:.3f}s"

        # Calculate operations per second
        ops_per_second = 10000 / duration
        assert (
            ops_per_second > 10000
        ), f"Middleware throughput too low: {ops_per_second:.0f} ops/sec"

    def test_middleware_with_logging_performance(self):
        """Test middleware performance with logging enabled."""
        # Use a null handler to avoid actual I/O overhead
        import logging

        logger = logging.getLogger("performance_test")
        logger.addHandler(logging.NullHandler())
        logger.setLevel(logging.DEBUG)

        middleware = RequestTrackingMiddleware(
            auto_generate=True, log_requests=True, include_timing=True
        )

        start_time = time.perf_counter()

        # Process 1,000 requests with logging
        for i in range(1000):
            request_context = {}
            request_id = middleware.process_request(
                request_context, f"logged_operation_{i}"
            )
            middleware.complete_request(request_id, request_context, success=True)

        duration = time.perf_counter() - start_time

        # Should complete even with logging overhead (under 0.5 seconds)
        assert duration < 0.5, f"Middleware with logging too slow: {duration:.3f}s"


class TestLoggingPerformance:
    """Test performance of request ID logging integration."""

    def test_logging_formatter_performance(self):
        """Test performance impact of RequestIDFormatter."""
        import logging
        import io

        # Create loggers with different formatters
        plain_logger = logging.getLogger("plain_performance")
        plain_handler = logging.StreamHandler(io.StringIO())
        plain_handler.setFormatter(logging.Formatter("%(message)s"))
        plain_logger.addHandler(plain_handler)
        plain_logger.setLevel(logging.INFO)

        request_logger = logging.getLogger("request_performance")
        request_handler = logging.StreamHandler(io.StringIO())
        request_handler.setFormatter(RequestIDFormatter())
        request_logger.addHandler(request_handler)
        request_logger.setLevel(logging.INFO)

        # Set a request ID
        set_request_id("req_perf_test")

        # Measure plain logging
        start_time = time.perf_counter()
        for i in range(10000):
            plain_logger.info(f"Plain log message {i}")
        plain_duration = time.perf_counter() - start_time

        # Measure request ID logging
        start_time = time.perf_counter()
        for i in range(10000):
            request_logger.info(f"Request log message {i}")
        request_duration = time.perf_counter() - start_time

        # Request ID logging should not be significantly slower
        overhead_ratio = request_duration / plain_duration if plain_duration > 0 else 1
        assert (
            overhead_ratio < 2.0
        ), f"Logging formatter overhead too high: {overhead_ratio:.2f}x"

        # Clean up
        plain_logger.removeHandler(plain_handler)
        request_logger.removeHandler(request_handler)


class TestMemoryUsagePerformance:
    """Test memory usage characteristics of request tracking."""

    def test_long_running_memory_stability(self):
        """Test memory stability over long-running operations."""
        import gc

        metrics = PerformanceMetrics()
        initial_memory = metrics.get_memory_usage()

        # Simulate long-running operations
        for batch in range(100):
            # Generate many request IDs
            ids = [generate_request_id() for _ in range(1000)]

            # Use context operations
            for i, req_id in enumerate(
                ids[:100]
            ):  # Use subset to avoid excessive operations
                set_request_id(req_id)
                retrieved = get_request_id()
                assert retrieved == req_id

            # Clear references
            del ids

            # Force garbage collection every 10 batches
            if batch % 10 == 0:
                gc.collect()
                current_memory = metrics.get_memory_usage()
                memory_growth = current_memory - initial_memory

                # Memory growth should be bounded (less than 100MB)
                assert (
                    memory_growth < 100
                ), f"Memory leak detected: {memory_growth:.2f}MB growth"

        # Final memory check
        gc.collect()
        final_memory = metrics.get_memory_usage()
        total_growth = final_memory - initial_memory

        # Total memory growth should be reasonable
        assert total_growth < 50, f"Excessive memory usage: {total_growth:.2f}MB growth"

    def test_context_variable_cleanup(self):
        """Test that context variables don't accumulate indefinitely."""
        import weakref
        import gc

        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024

        # Create many request contexts
        weak_refs = []

        for i in range(10000):
            req_id = generate_request_id()
            set_request_id(req_id)

            # Create weak reference to track cleanup
            if i % 1000 == 0:
                weak_refs.append(weakref.ref(req_id))

        # Clear current context
        REQUEST_ID_CONTEXT.set(None)

        # Force garbage collection
        gc.collect()

        # Check memory usage
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory

        # Memory increase should be minimal (context variables should be cleaned up)
        assert (
            memory_increase < 20
        ), f"Context variables not properly cleaned up: {memory_increase:.2f}MB"


class TestRealWorldScenarioPerformance:
    """Test performance under realistic usage scenarios."""

    @pytest.mark.asyncio
    async def test_mcp_server_tool_performance(self):
        """Test performance of MCP server tool calls with request tracking."""

        @with_request_tracking("MCP Tool")
        async def mock_mcp_tool(**kwargs):
            # Simulate tool work
            await asyncio.sleep(0.001)
            return {
                "result": "success",
                "request_id": get_request_id(),
                "arguments": kwargs,
            }

        # Measure performance of many tool calls
        start_time = time.perf_counter()

        tasks = []
        for i in range(100):
            task = mock_mcp_tool(param1=f"value_{i}", param2=i)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        duration = time.perf_counter() - start_time

        # Should complete 100 tool calls in reasonable time (under 2 seconds)
        assert duration < 2.0, f"MCP tool calls too slow: {duration:.3f}s"

        # Verify all results have unique request IDs
        request_ids = [result["request_id"] for result in results]
        assert len(set(request_ids)) == 100, "Request IDs not unique"

    def test_cli_command_performance(self):
        """Test performance of CLI commands with request tracking."""

        @track_request(operation_name="CLI Command")
        def mock_cli_command(command_args):
            # Simulate CLI work
            return {
                "success": True,
                "request_id": get_request_id(),
                "output": f"Processed {len(command_args)} arguments",
            }

        # Measure performance of many CLI commands
        start_time = time.perf_counter()

        results = []
        for i in range(1000):
            result = mock_cli_command([f"arg_{j}" for j in range(5)])
            results.append(result)

        duration = time.perf_counter() - start_time

        # Should complete 1000 CLI commands in under 1 second
        assert duration < 1.0, f"CLI commands too slow: {duration:.3f}s"

        # Verify all commands succeeded
        assert all(result["success"] for result in results)

        # Verify unique request IDs
        request_ids = [result["request_id"] for result in results]
        assert len(set(request_ids)) == 1000, "CLI request IDs not unique"


class TestBenchmarkSuite:
    """Comprehensive benchmark suite for request tracking system."""

    def test_benchmark_complete_system(self):
        """Comprehensive benchmark of the complete request tracking system."""
        metrics = PerformanceMetrics()

        # Test various components
        components = [
            ("ID Generation", lambda: [generate_request_id() for _ in range(1000)]),
            ("Context Operations", self._benchmark_context_operations),
            ("Decorator Overhead", self._benchmark_decorator_overhead),
            ("Middleware Processing", self._benchmark_middleware_processing),
        ]

        results = {}
        for name, operation in components:
            _, duration = metrics.measure_time(name, operation)
            results[name] = duration

        # Print benchmark results
        print("\n--- Request Tracking System Benchmark ---")
        for name, duration in results.items():
            print(f"{name:20s}: {duration:.6f}s")

        # Assert performance requirements
        assert results["ID Generation"] < 0.1, "ID generation too slow"
        assert results["Context Operations"] < 0.1, "Context operations too slow"
        assert results["Decorator Overhead"] < 0.5, "Decorator overhead too high"
        assert results["Middleware Processing"] < 0.5, "Middleware processing too slow"

    def _benchmark_context_operations(self):
        for i in range(1000):
            set_request_id(f"req_bench{i:06d}")
            get_request_id()

    def _benchmark_decorator_overhead(self):
        @track_request()
        def decorated_func(x):
            return x * 2

        return [decorated_func(i) for i in range(1000)]

    def _benchmark_middleware_processing(self):
        middleware = RequestTrackingMiddleware(log_requests=False)

        for i in range(1000):
            request_context = {}
            request_id = middleware.process_request(request_context, f"benchmark_{i}")
            middleware.complete_request(request_id, request_context, success=True)
