#!/usr/bin/env python3
"""
Parameter Operations Benchmarking Script

This script provides comprehensive benchmarking for parameter management operations
including handler performance, parameter generation, validation, and bulk operations.

Usage:
    python benchmark_parameter_operations.py --config config.yaml
    python benchmark_parameter_operations.py --config config.yaml --benchmark all --iterations 1000
    python benchmark_parameter_operations.py --config config.yaml --benchmark handler-selection --output results.json
"""

import asyncio
import argparse
import json
import time
import statistics
import psutil
import gc
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

from checkmk_mcp_server.services.parameter_service import ParameterService
from checkmk_mcp_server.services.handlers import get_handler_registry
from checkmk_mcp_server.api_client import CheckmkClient
from checkmk_mcp_server.config import Config
from checkmk_mcp_server.mcp_server.server import CheckmkMCPServer


class ParameterBenchmark:
    """Comprehensive benchmarking for parameter operations."""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = CheckmkClient(config.checkmk)
        self.parameter_service = ParameterService(self.client, config)
        self.mcp_server = CheckmkMCPServer(self.client, config)
        self.handler_registry = get_handler_registry()
        
        self.benchmark_results = {
            "system_info": self._get_system_info(),
            "benchmarks": {},
            "summary": {}
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for benchmark context."""
        return {
            "cpu_count": multiprocessing.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "python_version": f"{psutil.PYTHON}",
            "platform": psutil.PLATFORM
        }
    
    def _measure_performance(self, func, *args, iterations: int = 100, warmup: int = 10) -> Dict[str, Any]:
        """Measure performance of a synchronous function."""
        # Warmup
        for _ in range(warmup):
            func(*args)
        
        # Measure
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func(*args)
            end = time.perf_counter()
            times.append(end - start)
        
        return {
            "iterations": iterations,
            "total_time": sum(times),
            "mean_time": statistics.mean(times),
            "median_time": statistics.median(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "operations_per_second": iterations / sum(times),
            "times": times
        }
    
    async def _measure_async_performance(self, func, *args, iterations: int = 100, 
                                       warmup: int = 10, concurrent: int = 1) -> Dict[str, Any]:
        """Measure performance of an async function."""
        # Warmup
        for _ in range(warmup):
            await func(*args)
        
        # Measure sequential performance
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            await func(*args)
            end = time.perf_counter()
            times.append(end - start)
        
        sequential_stats = {
            "iterations": iterations,
            "total_time": sum(times),
            "mean_time": statistics.mean(times),
            "median_time": statistics.median(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "operations_per_second": iterations / sum(times)
        }
        
        # Measure concurrent performance if requested
        concurrent_stats = None
        if concurrent > 1:
            start = time.perf_counter()
            tasks = [func(*args) for _ in range(concurrent)]
            await asyncio.gather(*tasks)
            end = time.perf_counter()
            
            concurrent_stats = {
                "concurrent_operations": concurrent,
                "total_time": end - start,
                "operations_per_second": concurrent / (end - start)
            }
        
        return {
            "sequential": sequential_stats,
            "concurrent": concurrent_stats
        }
    
    def benchmark_handler_selection(self, iterations: int = 1000) -> Dict[str, Any]:
        """Benchmark handler selection performance."""
        print(f"⚡ Benchmarking handler selection ({iterations} iterations)...")
        
        test_services = [
            "CPU Temperature",
            "GPU Temperature", 
            "MySQL Connections",
            "Oracle Tablespace USERS",
            "PostgreSQL Locks",
            "HTTP Health Check",
            "HTTPS API Monitoring",
            "TCP Port 443",
            "DNS Lookup",
            "MRPE check_disk",
            "Local check_memory",
            "check_mysql"
        ]
        
        results = {}
        
        # Test individual handler selection
        for service_name in test_services:
            def select_handler():
                return self.handler_registry.get_best_handler(service_name=service_name)
            
            service_results = self._measure_performance(select_handler, iterations=iterations//len(test_services))
            results[service_name] = service_results
        
        # Test mixed handler selection (realistic usage)
        def select_mixed_handlers():
            for service_name in test_services:
                self.handler_registry.get_best_handler(service_name=service_name)
        
        mixed_results = self._measure_performance(select_mixed_handlers, iterations=iterations//len(test_services))
        results["mixed_selection"] = mixed_results
        
        # Test handler caching effectiveness
        def test_caching():
            # First access (cache miss)
            handler1 = self.handler_registry.get_handler("temperature")
            # Second access (cache hit)
            handler2 = self.handler_registry.get_handler("temperature")
            return handler1, handler2
        
        caching_results = self._measure_performance(test_caching, iterations=iterations)
        results["caching_performance"] = caching_results
        
        return results
    
    async def benchmark_parameter_generation(self, iterations: int = 500, concurrent: int = 10) -> Dict[str, Any]:
        """Benchmark parameter generation performance."""
        print(f"🔧 Benchmarking parameter generation ({iterations} iterations, {concurrent} concurrent)...")
        
        test_services = [
            "CPU Temperature",
            "GPU Temperature",
            "System Temperature", 
            "MySQL Connections",
            "MySQL InnoDB Buffer Pool",
            "Oracle Tablespace USERS",
            "PostgreSQL Connections",
            "MongoDB Memory Usage",
            "HTTP Health Check",
            "HTTPS API Monitoring",
            "TCP Port 443",
            "DNS Lookup",
            "MRPE check_disk",
            "Local check_memory",
            "check_mysql"
        ]
        
        results = {}
        
        # Test parameter generation for each service type
        for service_name in test_services:
            async def generate_params():
                return await self.parameter_service.get_specialized_defaults(service_name)
            
            service_results = await self._measure_async_performance(
                generate_params, 
                iterations=iterations//len(test_services),
                concurrent=min(concurrent, 5)  # Limit concurrency per service
            )
            results[service_name] = service_results
        
        # Test mixed parameter generation
        async def generate_mixed_params():
            tasks = []
            for service_name in test_services[:5]:  # Limit to 5 services for mixed test
                task = self.parameter_service.get_specialized_defaults(service_name)
                tasks.append(task)
            await asyncio.gather(*tasks)
        
        mixed_results = await self._measure_async_performance(
            generate_mixed_params,
            iterations=iterations//10,
            concurrent=min(concurrent//2, 5)
        )
        results["mixed_generation"] = mixed_results
        
        # Test context-aware parameter generation
        contexts = [
            {"environment": "production", "criticality": "high"},
            {"environment": "development", "criticality": "low"}, 
            {"environment": "testing", "criticality": "medium"}
        ]
        
        async def generate_context_params():
            for context in contexts:
                await self.parameter_service.get_specialized_defaults("CPU Temperature", context)
        
        context_results = await self._measure_async_performance(
            generate_context_params,
            iterations=iterations//5,
            concurrent=min(concurrent//3, 3)
        )
        results["context_aware_generation"] = context_results
        
        return results
    
    async def benchmark_parameter_validation(self, iterations: int = 500, concurrent: int = 10) -> Dict[str, Any]:
        """Benchmark parameter validation performance."""
        print(f"🔍 Benchmarking parameter validation ({iterations} iterations, {concurrent} concurrent)...")
        
        validation_test_cases = [
            {
                "service_name": "CPU Temperature",
                "parameters": {"levels": (75.0, 85.0), "output_unit": "c"}
            },
            {
                "service_name": "MySQL Connections", 
                "parameters": {"levels": (80.0, 90.0), "hostname": "db.example.com", "port": 3306}
            },
            {
                "service_name": "HTTPS API Health",
                "parameters": {"url": "https://api.example.com/health", "response_time": (2.0, 5.0)}
            },
            {
                "service_name": "MRPE check_disk",
                "parameters": {"command_line": "check_disk -w 80% -c 90%", "timeout": 30}
            }
        ]
        
        results = {}
        
        # Test validation for each parameter type
        for i, test_case in enumerate(validation_test_cases):
            async def validate_params():
                return await self.parameter_service.validate_specialized_parameters(
                    test_case["parameters"], test_case["service_name"]
                )
            
            case_results = await self._measure_async_performance(
                validate_params,
                iterations=iterations//len(validation_test_cases),
                concurrent=min(concurrent, 5)
            )
            results[f"case_{i}_{test_case['service_name']}"] = case_results
        
        # Test bulk validation
        async def bulk_validate():
            tasks = []
            for test_case in validation_test_cases:
                task = self.parameter_service.validate_specialized_parameters(
                    test_case["parameters"], test_case["service_name"]
                )
                tasks.append(task)
            await asyncio.gather(*tasks)
        
        bulk_results = await self._measure_async_performance(
            bulk_validate,
            iterations=iterations//5,
            concurrent=min(concurrent//2, 5)
        )
        results["bulk_validation"] = bulk_results
        
        return results
    
    async def benchmark_mcp_tools(self, iterations: int = 200, concurrent: int = 5) -> Dict[str, Any]:
        """Benchmark MCP tool performance."""
        print(f"🌐 Benchmarking MCP tools ({iterations} iterations, {concurrent} concurrent)...")
        
        mcp_test_cases = [
            {
                "tool_name": "get_specialized_defaults",
                "arguments": {"service_name": "CPU Temperature"}
            },
            {
                "tool_name": "validate_specialized_parameters",
                "arguments": {
                    "parameters": {"levels": (75.0, 85.0), "output_unit": "c"},
                    "service_name": "CPU Temperature"
                }
            },
            {
                "tool_name": "discover_parameter_handlers",
                "arguments": {"service_name": "MySQL Connections"}
            },
            {
                "tool_name": "get_handler_info",
                "arguments": {"handler_name": "temperature"}
            },
            {
                "tool_name": "bulk_parameter_operations",
                "arguments": {
                    "service_names": ["CPU Temperature", "MySQL Connections"],
                    "operation": "get_defaults"
                }
            }
        ]
        
        results = {}
        
        for test_case in mcp_test_cases:
            async def call_mcp_tool():
                return await self.mcp_server.call_tool(
                    test_case["tool_name"], 
                    test_case["arguments"]
                )
            
            tool_results = await self._measure_async_performance(
                call_mcp_tool,
                iterations=iterations//len(mcp_test_cases),
                concurrent=min(concurrent, 3)  # Lower concurrency for MCP tools
            )
            results[test_case["tool_name"]] = tool_results
        
        return results
    
    def benchmark_memory_usage(self, scale_factors: List[int] = [100, 500, 1000, 2000]) -> Dict[str, Any]:
        """Benchmark memory usage at different scales."""
        print(f"💾 Benchmarking memory usage at scales: {scale_factors}...")
        
        results = {}
        
        for scale in scale_factors:
            print(f"  Testing scale: {scale} services...")
            
            # Clear memory before test
            gc.collect()
            initial_memory = psutil.Process().memory_info().rss / (1024**2)  # MB
            
            # Generate many parameter sets
            services = [f"CPU {i} Temperature" for i in range(scale)]
            
            start_time = time.perf_counter()
            
            # Simulate parameter generation for many services
            parameter_sets = []
            for service_name in services:
                handler = self.handler_registry.get_best_handler(service_name=service_name)
                if handler:
                    # Simulate parameter generation (without actual API calls)
                    params = {
                        "levels": (75.0, 85.0),
                        "output_unit": "c",
                        "service_name": service_name
                    }
                    parameter_sets.append(params)
            
            end_time = time.perf_counter()
            
            # Measure memory after generation
            final_memory = psutil.Process().memory_info().rss / (1024**2)  # MB
            memory_delta = final_memory - initial_memory
            
            # Clean up
            del parameter_sets
            gc.collect()
            
            results[f"scale_{scale}"] = {
                "service_count": scale,
                "processing_time": end_time - start_time,
                "initial_memory_mb": initial_memory,
                "final_memory_mb": final_memory,
                "memory_delta_mb": memory_delta,
                "memory_per_service_kb": (memory_delta * 1024) / scale if scale > 0 else 0,
                "services_per_second": scale / (end_time - start_time)
            }
        
        return results
    
    def benchmark_concurrent_access(self, thread_counts: List[int] = [1, 2, 4, 8, 16], 
                                  operations_per_thread: int = 100) -> Dict[str, Any]:
        """Benchmark concurrent access to handler registry."""
        print(f"🧵 Benchmarking concurrent access with thread counts: {thread_counts}...")
        
        results = {}
        
        def worker_task(operations: int) -> List[float]:
            """Worker task for concurrent testing."""
            times = []
            services = ["CPU Temperature", "MySQL Connections", "HTTP Check"] * (operations // 3)
            
            for service_name in services[:operations]:
                start = time.perf_counter()
                handler = self.handler_registry.get_best_handler(service_name=service_name)
                end = time.perf_counter()
                times.append(end - start)
                assert handler is not None
            
            return times
        
        for thread_count in thread_counts:
            print(f"  Testing {thread_count} threads...")
            
            start_time = time.perf_counter()
            
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                futures = [
                    executor.submit(worker_task, operations_per_thread)
                    for _ in range(thread_count)
                ]
                
                all_times = []
                for future in futures:
                    times = future.result()
                    all_times.extend(times)
            
            end_time = time.perf_counter()
            
            total_operations = thread_count * operations_per_thread
            total_time = end_time - start_time
            
            results[f"threads_{thread_count}"] = {
                "thread_count": thread_count,
                "operations_per_thread": operations_per_thread,
                "total_operations": total_operations,
                "total_time": total_time,
                "operations_per_second": total_operations / total_time,
                "mean_operation_time": statistics.mean(all_times),
                "median_operation_time": statistics.median(all_times),
                "p95_operation_time": statistics.quantiles(all_times, n=20)[18] if len(all_times) > 20 else max(all_times)
            }
        
        return results
    
    async def run_benchmarks(self, benchmarks: List[str], iterations: int = 500, 
                           concurrent: int = 10) -> Dict[str, Any]:
        """Run specified benchmarks."""
        print("🚀 Starting Parameter Operations Benchmarking...\n")
        
        start_time = time.perf_counter()
        
        if "handler-selection" in benchmarks or "all" in benchmarks:
            self.benchmark_results["benchmarks"]["handler_selection"] = \
                self.benchmark_handler_selection(iterations)
        
        if "parameter-generation" in benchmarks or "all" in benchmarks:
            self.benchmark_results["benchmarks"]["parameter_generation"] = \
                await self.benchmark_parameter_generation(iterations, concurrent)
        
        if "parameter-validation" in benchmarks or "all" in benchmarks:
            self.benchmark_results["benchmarks"]["parameter_validation"] = \
                await self.benchmark_parameter_validation(iterations, concurrent)
        
        if "mcp-tools" in benchmarks or "all" in benchmarks:
            self.benchmark_results["benchmarks"]["mcp_tools"] = \
                await self.benchmark_mcp_tools(iterations//2, concurrent//2)
        
        if "memory-usage" in benchmarks or "all" in benchmarks:
            self.benchmark_results["benchmarks"]["memory_usage"] = \
                self.benchmark_memory_usage()
        
        if "concurrent-access" in benchmarks or "all" in benchmarks:
            self.benchmark_results["benchmarks"]["concurrent_access"] = \
                self.benchmark_concurrent_access()
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Generate summary
        self._generate_summary(total_time)
        
        return self.benchmark_results
    
    def _generate_summary(self, total_time: float):
        """Generate benchmark summary."""
        summary = {
            "total_benchmark_time": total_time,
            "benchmarks_run": list(self.benchmark_results["benchmarks"].keys()),
            "key_metrics": {}
        }
        
        # Extract key performance metrics
        benchmarks = self.benchmark_results["benchmarks"]
        
        if "handler_selection" in benchmarks:
            mixed_selection = benchmarks["handler_selection"].get("mixed_selection", {})
            summary["key_metrics"]["handler_selection_ops_per_sec"] = \
                mixed_selection.get("operations_per_second", 0)
        
        if "parameter_generation" in benchmarks:
            mixed_gen = benchmarks["parameter_generation"].get("mixed_generation", {})
            if "sequential" in mixed_gen:
                summary["key_metrics"]["parameter_generation_ops_per_sec"] = \
                    mixed_gen["sequential"].get("operations_per_second", 0)
        
        if "parameter_validation" in benchmarks:
            bulk_val = benchmarks["parameter_validation"].get("bulk_validation", {})
            if "sequential" in bulk_val:
                summary["key_metrics"]["parameter_validation_ops_per_sec"] = \
                    bulk_val["sequential"].get("operations_per_second", 0)
        
        if "memory_usage" in benchmarks:
            scale_1000 = benchmarks["memory_usage"].get("scale_1000", {})
            summary["key_metrics"]["memory_per_service_kb"] = \
                scale_1000.get("memory_per_service_kb", 0)
        
        if "concurrent_access" in benchmarks:
            threads_8 = benchmarks["concurrent_access"].get("threads_8", {})
            summary["key_metrics"]["concurrent_ops_per_sec"] = \
                threads_8.get("operations_per_second", 0)
        
        self.benchmark_results["summary"] = summary
    
    def print_summary(self):
        """Print benchmark summary."""
        summary = self.benchmark_results["summary"]
        
        print(f"\n📊 Benchmark Summary:")
        print(f"   - Total time: {summary['total_benchmark_time']:.2f}s")
        print(f"   - Benchmarks run: {', '.join(summary['benchmarks_run'])}")
        
        print(f"\n⚡ Key Performance Metrics:")
        metrics = summary["key_metrics"]
        
        if "handler_selection_ops_per_sec" in metrics:
            print(f"   - Handler Selection: {metrics['handler_selection_ops_per_sec']:.0f} ops/sec")
        
        if "parameter_generation_ops_per_sec" in metrics:
            print(f"   - Parameter Generation: {metrics['parameter_generation_ops_per_sec']:.0f} ops/sec")
        
        if "parameter_validation_ops_per_sec" in metrics:
            print(f"   - Parameter Validation: {metrics['parameter_validation_ops_per_sec']:.0f} ops/sec")
        
        if "memory_per_service_kb" in metrics:
            print(f"   - Memory per Service: {metrics['memory_per_service_kb']:.1f} KB")
        
        if "concurrent_ops_per_sec" in metrics:
            print(f"   - Concurrent Access (8 threads): {metrics['concurrent_ops_per_sec']:.0f} ops/sec")
        
        # Performance assessment
        print(f"\n✅ Performance Assessment:")
        
        if metrics.get("handler_selection_ops_per_sec", 0) > 5000:
            print("   - Handler Selection: Excellent (>5000 ops/sec)")
        elif metrics.get("handler_selection_ops_per_sec", 0) > 1000:
            print("   - Handler Selection: Good (>1000 ops/sec)")
        else:
            print("   - Handler Selection: Needs improvement (<1000 ops/sec)")
        
        if metrics.get("parameter_generation_ops_per_sec", 0) > 100:
            print("   - Parameter Generation: Good (>100 ops/sec)")
        elif metrics.get("parameter_generation_ops_per_sec", 0) > 50:
            print("   - Parameter Generation: Acceptable (>50 ops/sec)")
        else:
            print("   - Parameter Generation: Needs improvement (<50 ops/sec)")
        
        if metrics.get("memory_per_service_kb", 0) < 10:
            print("   - Memory Usage: Excellent (<10 KB per service)")
        elif metrics.get("memory_per_service_kb", 0) < 50:
            print("   - Memory Usage: Good (<50 KB per service)")
        else:
            print("   - Memory Usage: High (>50 KB per service)")


async def main():
    """Main benchmarking function."""
    parser = argparse.ArgumentParser(description="Parameter Operations Benchmarking")
    parser.add_argument("--config", required=True, help="Configuration file path")
    parser.add_argument("--benchmark", nargs="+", 
                       choices=["handler-selection", "parameter-generation", "parameter-validation", 
                               "mcp-tools", "memory-usage", "concurrent-access", "all"],
                       default=["all"], help="Benchmarks to run")
    parser.add_argument("--iterations", type=int, default=500, help="Number of iterations per benchmark")
    parser.add_argument("--concurrent", type=int, default=10, help="Concurrent operations for async benchmarks")
    parser.add_argument("--output", help="Output file for benchmark results")
    parser.add_argument("--output-format", default="json", choices=["json", "yaml"],
                       help="Output format")
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.from_file(args.config)
    
    # Initialize benchmark
    benchmark = ParameterBenchmark(config)
    
    try:
        # Run benchmarks
        results = await benchmark.run_benchmarks(
            args.benchmark, 
            args.iterations, 
            args.concurrent
        )
        
        # Print summary
        benchmark.print_summary()
        
        # Export results if requested
        if args.output:
            if args.output_format == "json":
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
            elif args.output_format == "yaml":
                import yaml
                with open(args.output, 'w') as f:
                    yaml.dump(results, f, default_flow_style=False)
            
            print(f"📁 Benchmark results saved to {args.output}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Benchmarking failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))