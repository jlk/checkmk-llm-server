"""Performance benchmarks and tests."""

import pytest
import asyncio
import time
import statistics
from unittest.mock import AsyncMock, Mock

from checkmk_agent.services.streaming import StreamingHostService
from checkmk_agent.services.cache import LRUCache, CachedHostService
from checkmk_agent.services.batch import BatchProcessor
from checkmk_agent.services.metrics import get_metrics_collector
from checkmk_agent.config import AppConfig


@pytest.fixture
def mock_config():
    """Mock configuration for benchmarks."""
    return Mock(spec=AppConfig)


class TestCachePerformance:
    """Performance tests for caching functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_read_performance(self):
        """Test cache read performance."""
        cache = LRUCache(max_size=1000, default_ttl=300)
        
        # Pre-populate cache
        for i in range(500):
            await cache.set(f"key_{i}", f"value_{i}")
        
        # Benchmark read performance
        start_time = time.time()
        
        for i in range(1000):
            key = f"key_{i % 500}"  # Mix of hits and misses
            await cache.get(key)
        
        duration = time.time() - start_time
        ops_per_second = 1000 / duration
        
        # Should handle at least 10,000 ops/second
        assert ops_per_second > 10000
        print(f"Cache read performance: {ops_per_second:.0f} ops/second")
    
    @pytest.mark.asyncio
    async def test_cache_write_performance(self):
        """Test cache write performance."""
        cache = LRUCache(max_size=1000, default_ttl=300)
        
        start_time = time.time()
        
        for i in range(1000):
            await cache.set(f"key_{i}", f"value_{i}")
        
        duration = time.time() - start_time
        ops_per_second = 1000 / duration
        
        # Should handle at least 5,000 write ops/second
        assert ops_per_second > 5000
        print(f"Cache write performance: {ops_per_second:.0f} ops/second")
    
    @pytest.mark.asyncio
    async def test_cache_concurrent_access(self):
        """Test cache performance under concurrent load."""
        cache = LRUCache(max_size=1000, default_ttl=300)
        
        # Pre-populate
        for i in range(100):
            await cache.set(f"key_{i}", f"value_{i}")
        
        async def concurrent_operations():
            for i in range(100):
                # Mix of reads and writes
                if i % 3 == 0:
                    await cache.set(f"new_key_{i}", f"new_value_{i}")
                else:
                    await cache.get(f"key_{i % 100}")
        
        # Run concurrent operations
        start_time = time.time()
        
        await asyncio.gather(*[concurrent_operations() for _ in range(10)])
        
        duration = time.time() - start_time
        total_ops = 10 * 100
        ops_per_second = total_ops / duration
        
        # Should handle concurrent access efficiently
        assert ops_per_second > 5000
        print(f"Concurrent cache performance: {ops_per_second:.0f} ops/second")


class TestStreamingPerformance:
    """Performance tests for streaming functionality."""
    
    @pytest.fixture
    def streaming_service(self, mock_config):
        """Create streaming service for benchmarks."""
        mock_client = AsyncMock()
        return StreamingHostService(mock_client, mock_config)
    
    @pytest.mark.asyncio
    async def test_streaming_throughput(self, streaming_service):
        """Test streaming throughput with large datasets."""
        # Mock large dataset
        total_items = 10000
        batch_size = 100
        
        def create_batch_data(offset, limit):
            return {
                'value': [
                    {'id': f'host_{i}', 'folder': '/', 'attributes': {}}
                    for i in range(offset, min(offset + limit, total_items))
                ],
                'total_count': total_items
            }
        
        # Mock API responses
        call_count = 0
        async def mock_list_hosts(limit=None, offset=0, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)  # Simulate small API delay
            return create_batch_data(offset, limit)
        
        streaming_service.checkmk.list_hosts = mock_list_hosts
        
        # Benchmark streaming
        start_time = time.time()
        
        processed_items = 0
        async for batch in streaming_service.list_hosts_streamed(batch_size=batch_size):
            processed_items += len(batch.items)
            if processed_items >= 5000:  # Process 5000 items for benchmark
                break
        
        duration = time.time() - start_time
        items_per_second = processed_items / duration
        
        print(f"Streaming throughput: {items_per_second:.0f} items/second")
        print(f"Processed {processed_items} items in {duration:.2f} seconds")
        
        # Should process at least 500 items/second (conservative estimate)
        assert items_per_second > 500
    
    @pytest.mark.asyncio
    async def test_streaming_memory_efficiency(self, streaming_service):
        """Test streaming memory efficiency."""
        try:
            import psutil
            import os
        except ImportError:
            pytest.skip("psutil not installed - skipping memory efficiency test")
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Mock large dataset that would consume significant memory if loaded all at once
        total_items = 50000
        
        def create_batch_data(offset, limit):
            return {
                'value': [
                    {
                        'id': f'host_{i}',
                        'folder': f'/folder/{i % 10}',
                        'attributes': {
                            'alias': f'Host {i}',
                            'description': f'This is host number {i} with lots of data' * 10
                        }
                    }
                    for i in range(offset, min(offset + limit, total_items))
                ],
                'total_count': total_items
            }
        
        async def mock_list_hosts(limit=None, offset=0, **kwargs):
            await asyncio.sleep(0.001)
            return create_batch_data(offset, limit)
        
        streaming_service.checkmk.list_hosts = mock_list_hosts
        
        # Process stream and track memory
        max_memory = initial_memory
        processed_items = 0
        
        async for batch in streaming_service.list_hosts_streamed(batch_size=1000):
            processed_items += len(batch.items)
            
            # Check memory usage
            current_memory = process.memory_info().rss / 1024 / 1024
            max_memory = max(max_memory, current_memory)
            
            if processed_items >= 10000:  # Process 10k items
                break
        
        memory_increase = max_memory - initial_memory
        
        print(f"Memory usage - Initial: {initial_memory:.1f}MB, Max: {max_memory:.1f}MB")
        print(f"Memory increase: {memory_increase:.1f}MB for {processed_items} items")
        
        # Memory increase should be reasonable (less than 100MB for 10k items)
        assert memory_increase < 100


class TestBatchPerformance:
    """Performance tests for batch operations."""
    
    @pytest.mark.asyncio
    async def test_batch_processing_throughput(self):
        """Test batch processing throughput."""
        processor = BatchProcessor(max_concurrent=10, max_retries=1)
        
        # Create test items
        items = [f"item_{i}" for i in range(1000)]
        
        async def fast_operation(item):
            await asyncio.sleep(0.001)  # Fast operation
            return f"processed_{item}"
        
        start_time = time.time()
        
        result = await processor.process_batch(
            items=items,
            operation=fast_operation,
            batch_id="throughput_test"
        )
        
        duration = time.time() - start_time
        items_per_second = len(items) / duration
        
        print(f"Batch processing throughput: {items_per_second:.0f} items/second")
        print(f"Processed {len(items)} items in {duration:.2f} seconds")
        
        assert result.progress.success == 1000
        # Should process at least 500 items/second with concurrency
        assert items_per_second > 500
    
    @pytest.mark.asyncio
    async def test_batch_scaling_with_concurrency(self):
        """Test how batch processing scales with concurrency."""
        items = [f"item_{i}" for i in range(500)]
        
        async def simulated_operation(item):
            await asyncio.sleep(0.01)  # Simulate I/O bound operation
            return f"processed_{item}"
        
        # Test different concurrency levels
        concurrency_levels = [1, 5, 10, 20]
        results = {}
        
        for concurrency in concurrency_levels:
            processor = BatchProcessor(max_concurrent=concurrency)
            
            start_time = time.time()
            
            result = await processor.process_batch(
                items=items,
                operation=simulated_operation,
                batch_id=f"scaling_test_{concurrency}"
            )
            
            duration = time.time() - start_time
            items_per_second = len(items) / duration
            
            results[concurrency] = {
                'duration': duration,
                'throughput': items_per_second,
                'success_count': result.progress.success
            }
            
            print(f"Concurrency {concurrency}: {items_per_second:.0f} items/second")
        
        # Higher concurrency should improve throughput for I/O bound operations
        assert results[10]['throughput'] > results[1]['throughput']
        assert results[20]['throughput'] > results[5]['throughput']


class TestMetricsPerformance:
    """Performance tests for metrics collection."""
    
    @pytest.mark.asyncio
    async def test_metrics_collection_overhead(self):
        """Test overhead of metrics collection."""
        collector = get_metrics_collector()
        
        # Benchmark without metrics
        start_time = time.time()
        
        for i in range(1000):
            await asyncio.sleep(0.0001)  # Simulate small operation
        
        baseline_duration = time.time() - start_time
        
        # Benchmark with metrics
        start_time = time.time()
        
        for i in range(1000):
            await asyncio.sleep(0.0001)
            await collector.record_timing(f"operation_{i % 10}", 0.0001)
            await collector.increment_counter(f"counter_{i % 5}")
        
        metrics_duration = time.time() - start_time
        
        overhead = (metrics_duration - baseline_duration) / baseline_duration * 100
        
        print(f"Metrics overhead: {overhead:.1f}%")
        print(f"Baseline: {baseline_duration:.3f}s, With metrics: {metrics_duration:.3f}s")
        
        # Metrics overhead should be reasonable (less than 50%)
        assert overhead < 50
    
    @pytest.mark.asyncio
    async def test_metrics_storage_efficiency(self):
        """Test metrics storage efficiency."""
        collector = get_metrics_collector()
        
        # Clear any existing metrics
        await collector._cleanup_old_metrics()
        
        # Record many metrics
        start_time = time.time()
        
        for i in range(10000):
            await collector.record_timing(f"operation_{i % 100}", 0.001 * i)
            await collector.increment_counter(f"counter_{i % 50}")
            await collector.set_gauge(f"gauge_{i % 20}", float(i))
        
        duration = time.time() - start_time
        
        # Get statistics
        stats = await collector.get_stats()
        
        print(f"Recorded 10,000 metrics in {duration:.2f} seconds")
        print(f"Metrics per second: {10000/duration:.0f}")
        print(f"Total stored metrics: {stats['total_metrics']}")
        
        # Should be able to record at least 5000 metrics/second
        assert (10000 / duration) > 5000
        
        # Should have all metrics stored
        assert stats['total_metrics'] >= 10000


class TestIntegratedPerformance:
    """Integrated performance tests combining multiple features."""
    
    @pytest.mark.asyncio
    async def test_cached_streaming_performance(self, mock_config):
        """Test performance of cached streaming operations."""
        # Create cached streaming service
        mock_client = AsyncMock()
        cached_service = CachedHostService(mock_client, mock_config)
        
        # Mock API response
        async def mock_list_hosts(**kwargs):
            await asyncio.sleep(0.01)  # Simulate API delay
            return {
                'value': [
                    {'id': f'host_{i}', 'folder': '/', 'attributes': {}}
                    for i in range(100)
                ],
                'total_count': 100
            }
        
        cached_service.checkmk.list_hosts = mock_list_hosts
        
        # First call (cache miss)
        start_time = time.time()
        result1 = await cached_service.list_hosts(search="test")
        first_call_duration = time.time() - start_time
        
        # Second call (cache hit)
        start_time = time.time()
        result2 = await cached_service.list_hosts(search="test")
        second_call_duration = time.time() - start_time
        
        # Cache should provide significant speedup
        speedup = first_call_duration / second_call_duration
        
        print(f"First call: {first_call_duration:.3f}s")
        print(f"Second call: {second_call_duration:.3f}s")
        print(f"Speedup: {speedup:.1f}x")
        
        # Should get at least 5x speedup from cache
        assert speedup > 5
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_end_to_end_performance(self):
        """Test end-to-end performance of a complete workflow."""
        # Simulate complete workflow: streaming + caching + batch processing + metrics
        
        # Setup components
        cache = LRUCache(max_size=1000, default_ttl=300)
        processor = BatchProcessor(max_concurrent=5)
        collector = get_metrics_collector()
        
        # Simulate workflow
        start_time = time.time()
        
        # 1. Stream data
        items = []
        for batch_num in range(10):
            batch_items = [f"item_{batch_num}_{i}" for i in range(50)]
            items.extend(batch_items)
            await asyncio.sleep(0.001)  # Simulate streaming delay
        
        # 2. Cache frequently accessed items
        for i in range(0, len(items), 10):
            await cache.set(f"cached_{i}", items[i])
        
        # 3. Batch process items
        async def process_item(item):
            # Check cache first
            # Extract index from item name for cache lookup
            item_parts = item.split('_')
            if len(item_parts) >= 3:
                batch_num = item_parts[1]
                item_idx = item_parts[2]
                cache_key = f"cached_{int(batch_num) * 50 + int(item_idx)}"
                cached = await cache.get(cache_key)
            else:
                cached = None
                
            if cached:
                await collector.increment_counter("cache_hits")
            else:
                await collector.increment_counter("cache_misses")
            
            await asyncio.sleep(0.002)  # Simulate processing
            await collector.record_timing("item_processing", 0.002)
            return f"processed_{item}"
        
        result = await processor.process_batch(
            items=items[:100],  # Process subset for benchmark
            operation=process_item,
            batch_id="end_to_end_test"
        )
        
        total_duration = time.time() - start_time
        
        # Get final statistics
        stats = await collector.get_stats()
        cache_stats = cache.get_stats()
        
        print(f"End-to-end workflow completed in {total_duration:.2f} seconds")
        print(f"Processed {result.progress.success} items")
        print(f"Cache hit rate: {cache_stats.hit_rate:.1%}")
        print(f"Total metrics recorded: {stats['total_metrics']}")
        
        # Workflow should complete efficiently
        assert total_duration < 5.0  # Should complete within 5 seconds
        assert result.progress.success == 100
        assert cache_stats.hits > 0  # Should have some cache hits


@pytest.mark.asyncio
async def test_memory_leak_detection():
    """Test for memory leaks in long-running operations."""
    try:
        import psutil
        import os
    except ImportError:
        pytest.skip("psutil not installed - skipping memory leak test")
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Run operations that could potentially leak memory
    cache = LRUCache(max_size=100, default_ttl=60)
    processor = BatchProcessor(max_concurrent=5)
    collector = get_metrics_collector()
    
    for iteration in range(10):
        # Cache operations
        for i in range(100):
            await cache.set(f"key_{iteration}_{i}", f"value_{iteration}_{i}")
            await cache.get(f"key_{iteration}_{i}")
        
        # Batch operations
        items = [f"item_{iteration}_{i}" for i in range(50)]
        
        async def simple_op(item):
            await asyncio.sleep(0.001)
            return f"processed_{item}"
        
        await processor.process_batch(items, simple_op)
        
        # Metrics operations
        for i in range(100):
            await collector.record_timing(f"op_{iteration}", 0.001)
            await collector.increment_counter(f"counter_{iteration}")
        
        # Clear cache to prevent legitimate growth
        await cache.clear()
        
        # Check memory periodically
        if iteration % 3 == 0:
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory
            
            print(f"Iteration {iteration}: Memory usage {current_memory:.1f}MB (+{memory_growth:.1f}MB)")
            
            # Memory growth should be reasonable (less than 50MB over 10 iterations)
            assert memory_growth < 50


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s"])