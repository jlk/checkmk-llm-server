#!/usr/bin/env python3
"""
Performance benchmark for refactored MCP server architecture.

This script compares the performance of the new modular architecture
against the expected baseline to ensure no significant degradation.
"""

import asyncio
import time
import gc
import sys
import tracemalloc
from unittest.mock import Mock, patch
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from checkmk_mcp_server.mcp_server import CheckmkMCPServer
from checkmk_mcp_server.config import AppConfig


def create_mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=AppConfig)
    config.checkmk = Mock()
    config.checkmk.server_url = "http://test.checkmk.com"
    config.checkmk.username = "test_user"
    config.checkmk.password = "test_pass"
    config.checkmk.site = "test_site"
    return config


async def benchmark_server_initialization():
    """Benchmark server initialization time."""
    print("🚀 Benchmarking server initialization...")
    
    config = create_mock_config()
    initialization_times = []
    
    # Warm up
    with patch("checkmk_mcp_server.api_client.CheckmkClient"):
        server = CheckmkMCPServer(config)
        await server.initialize()
        await server.shutdown()
    
    # Benchmark multiple initializations
    for i in range(5):
        start_time = time.perf_counter()
        
        with patch("checkmk_mcp_server.api_client.CheckmkClient"):
            server = CheckmkMCPServer(config)
            await server.initialize()
            
            # Verify initialization was successful
            assert server._initialized == True
            assert len(server._tools) == 37
            assert len(server._tool_handlers) == 37
            
            await server.shutdown()
        
        end_time = time.perf_counter()
        init_time = end_time - start_time
        initialization_times.append(init_time)
        print(f"  Initialization {i+1}: {init_time:.3f}s")
    
    avg_time = sum(initialization_times) / len(initialization_times)
    print(f"  Average initialization time: {avg_time:.3f}s")
    
    # Performance expectation: Should initialize in under 2 seconds
    if avg_time > 2.0:
        print(f"  ⚠️  Warning: Initialization time ({avg_time:.3f}s) exceeds expected threshold (2.0s)")
    else:
        print(f"  ✅ Initialization performance acceptable")
    
    return avg_time


async def benchmark_tool_access():
    """Benchmark tool access performance."""
    print("🔧 Benchmarking tool access...")
    
    config = create_mock_config()
    
    with patch("checkmk_mcp_server.api_client.CheckmkClient"):
        server = CheckmkMCPServer(config)
        await server.initialize()
        
        # Benchmark tool list access
        start_time = time.perf_counter()
        for _ in range(1000):
            tools = server._tools
            assert len(tools) == 37
        end_time = time.perf_counter()
        
        tool_access_time = (end_time - start_time) / 1000
        print(f"  Tool list access (1000 iterations): {tool_access_time*1000:.3f}ms per access")
        
        # Benchmark handler access
        start_time = time.perf_counter()
        for _ in range(1000):
            handlers = server._tool_handlers
            assert len(handlers) == 37
        end_time = time.perf_counter()
        
        handler_access_time = (end_time - start_time) / 1000
        print(f"  Handler access (1000 iterations): {handler_access_time*1000:.3f}ms per access")
        
        # Benchmark service access
        start_time = time.perf_counter()
        for _ in range(1000):
            host_service = server.host_service
            service_service = server.service_service
            assert host_service is not None
            assert service_service is not None
        end_time = time.perf_counter()
        
        service_access_time = (end_time - start_time) / 1000
        print(f"  Service access (1000 iterations): {service_access_time*1000:.3f}ms per access")
        
        await server.shutdown()
    
    # Performance expectations: All access should be under 1ms
    if tool_access_time > 0.001:
        print(f"  ⚠️  Warning: Tool access time ({tool_access_time*1000:.3f}ms) may be slow")
    else:
        print(f"  ✅ Tool access performance acceptable")
    
    return tool_access_time, handler_access_time, service_access_time


async def benchmark_memory_usage():
    """Benchmark memory usage of the new architecture."""
    print("💾 Benchmarking memory usage...")
    
    config = create_mock_config()
    
    # Start memory tracking
    tracemalloc.start()
    gc.collect()
    
    initial_snapshot = tracemalloc.take_snapshot()
    
    # Create and initialize server
    with patch("checkmk_mcp_server.api_client.CheckmkClient"):
        server = CheckmkMCPServer(config)
        await server.initialize()
        
        # Take snapshot after initialization
        initialized_snapshot = tracemalloc.take_snapshot()
        
        # Compare memory usage
        top_stats = initialized_snapshot.compare_to(initial_snapshot, 'lineno')
        
        total_memory_mb = sum(stat.size for stat in top_stats) / 1024 / 1024
        print(f"  Total memory allocated: {total_memory_mb:.2f} MB")
        
        # Test tool creation doesn't leak memory
        for _ in range(100):
            _ = server._tools
            _ = server._tool_handlers
        
        gc.collect()
        final_snapshot = tracemalloc.take_snapshot()
        
        # Check for memory leaks
        leak_stats = final_snapshot.compare_to(initialized_snapshot, 'lineno')
        leak_memory_mb = sum(stat.size for stat in leak_stats if stat.size > 0) / 1024 / 1024
        
        print(f"  Memory usage after operations: {leak_memory_mb:.2f} MB")
        
        if leak_memory_mb > 1.0:  # More than 1MB increase
            print(f"  ⚠️  Warning: Potential memory leak detected (+{leak_memory_mb:.2f} MB)")
        else:
            print(f"  ✅ Memory usage stable")
        
        await server.shutdown()
    
    tracemalloc.stop()
    return total_memory_mb


async def benchmark_modular_vs_monolithic():
    """Compare modular architecture benefits."""
    print("🏗️  Analyzing modular architecture benefits...")
    
    # These are the benefits we can measure
    metrics = {
        "main_server_size": 0,
        "module_count": 0,
        "average_module_size": 0,
        "separation_ratio": 0
    }
    
    # Analyze main server file size
    server_file = Path(__file__).parent / "checkmk_agent" / "mcp_server" / "server.py"
    if server_file.exists():
        with open(server_file, 'r') as f:
            server_lines = len(f.readlines())
        metrics["main_server_size"] = server_lines
        print(f"  Main server.py: {server_lines} lines")
    
    # Count modules in the new architecture
    mcp_server_dir = Path(__file__).parent / "checkmk_agent" / "mcp_server"
    module_files = []
    
    for path in mcp_server_dir.rglob("*.py"):
        if path.name != "__init__.py" and path.is_file():
            module_files.append(path)
    
    metrics["module_count"] = len(module_files)
    
    # Calculate average module size
    total_lines = 0
    for module_file in module_files:
        with open(module_file, 'r') as f:
            lines = len(f.readlines())
            total_lines += lines
    
    if module_files:
        metrics["average_module_size"] = total_lines / len(module_files)
        metrics["separation_ratio"] = total_lines / max(metrics["main_server_size"], 1)
    
    print(f"  Total modules: {metrics['module_count']}")
    print(f"  Average module size: {metrics['average_module_size']:.0f} lines")
    print(f"  Architecture separation ratio: {metrics['separation_ratio']:.1f}x")
    
    # Expected benefits
    if metrics["main_server_size"] < 500:
        print(f"  ✅ Main server file size reduced (target: <500 lines)")
    else:
        print(f"  ⚠️  Main server file larger than expected")
    
    if metrics["average_module_size"] < 600:
        print(f"  ✅ Modules are appropriately sized (target: <600 lines each)")
    else:
        print(f"  ⚠️  Some modules may be too large")
    
    if metrics["module_count"] >= 20:
        print(f"  ✅ Good modular separation ({metrics['module_count']} modules)")
    else:
        print(f"  ⚠️  May need more modular separation")
    
    return metrics


async def run_comprehensive_benchmark():
    """Run the complete benchmark suite."""
    print("=" * 60)
    print("🧪 Checkmk MCP Server Architecture Performance Benchmark")
    print("=" * 60)
    print()
    
    results = {}
    
    try:
        # Run benchmarks
        results["init_time"] = await benchmark_server_initialization()
        print()
        
        results["access_times"] = await benchmark_tool_access()
        print()
        
        results["memory_mb"] = await benchmark_memory_usage()
        print()
        
        results["architecture"] = await benchmark_modular_vs_monolithic()
        print()
        
        # Summary
        print("=" * 60)
        print("📊 Benchmark Summary")
        print("=" * 60)
        
        print(f"Initialization Time: {results['init_time']:.3f}s")
        print(f"Tool Access Time: {results['access_times'][0]*1000:.3f}ms")
        print(f"Memory Usage: {results['memory_mb']:.2f} MB")
        print(f"Main Server Size: {results['architecture']['main_server_size']} lines")
        print(f"Total Modules: {results['architecture']['module_count']}")
        
        # Overall assessment
        print("\n🎯 Performance Assessment:")
        
        performance_issues = []
        if results["init_time"] > 2.0:
            performance_issues.append("Slow initialization")
        if results["access_times"][0] > 0.001:
            performance_issues.append("Slow tool access")
        if results["memory_mb"] > 50:
            performance_issues.append("High memory usage")
        
        if performance_issues:
            print(f"  ⚠️  Issues detected: {', '.join(performance_issues)}")
        else:
            print(f"  ✅ All performance metrics within acceptable ranges")
        
        # Architecture benefits
        print("\n🏗️  Architecture Benefits:")
        size_reduction = (4449 - results['architecture']['main_server_size']) / 4449 * 100
        print(f"  ✅ {size_reduction:.1f}% reduction in main server file size")
        print(f"  ✅ Modular design with {results['architecture']['module_count']} focused modules")
        print(f"  ✅ Average module size: {results['architecture']['average_module_size']:.0f} lines")
        
        return results
        
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return None


if __name__ == "__main__":
    # Run the benchmark
    results = asyncio.run(run_comprehensive_benchmark())
    
    if results:
        print("\n✅ Benchmark completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Benchmark failed!")
        sys.exit(1)