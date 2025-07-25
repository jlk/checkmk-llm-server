# Advanced Features Guide

This document provides comprehensive guidance on the advanced features implemented in Phase 4 of the Checkmk LLM Agent project.

## Overview

The Checkmk LLM Agent includes several advanced features designed for enterprise-scale deployments:

- **Streaming Support** - Handle large datasets efficiently
- **Caching Layer** - Improve performance with intelligent caching
- **Batch Operations** - Process multiple operations efficiently
- **Performance Monitoring** - Real-time metrics and monitoring
- **Advanced Error Recovery** - Circuit breakers, retries, and fallbacks

## Streaming Support

### Purpose
Streaming support allows the system to handle large Checkmk environments (thousands of hosts/services) without loading all data into memory simultaneously.

### Key Components

#### StreamingMixin
```python
from checkmk_agent.services.streaming import StreamingMixin

class MyService(StreamingMixin, BaseService):
    async def process_large_dataset(self):
        async for batch in self._stream_paginated_data(
            fetch_function=self.api_fetch,
            batch_size=100
        ):
            # Process batch.items
            for item in batch.items:
                await self.process_item(item)
```

#### StreamingHostService
```python
# Stream hosts in batches
async for batch in streaming_host_service.list_hosts_streamed(
    batch_size=100,
    search="web*"
):
    print(f"Processing batch {batch.batch_number} with {len(batch.items)} hosts")
    for host in batch.items:
        print(f"Host: {host.name}")
```

#### StreamingServiceService
```python
# Stream services across all hosts
async for batch in streaming_service_service.list_all_services_streamed(
    batch_size=200,
    state_filter=[ServiceState.CRITICAL, ServiceState.WARNING]
):
    print(f"Found {len(batch.items)} problematic services")
```

### Benefits
- **Memory Efficient**: Constant memory usage regardless of dataset size
- **Scalable**: Handle environments with 100k+ hosts/services
- **Responsive**: Progressive loading with real-time feedback
- **Resilient**: Automatic error handling and recovery

### Configuration
```python
# Customize batch sizes based on your environment
small_env = StreamingHostService(client, config)
# Default batch_size=100

large_env = StreamingHostService(client, config)
large_env.default_batch_size = 500  # Larger batches for better performance
```

## Caching Layer

### Purpose
The caching layer dramatically improves performance by storing frequently accessed data in memory with intelligent eviction policies.

### Key Components

#### LRUCache
```python
from checkmk_agent.services.cache import LRUCache

# Create cache with 1000 entries, 5-minute TTL
cache = LRUCache(max_size=1000, default_ttl=300)

# Store data
await cache.set("hosts:production", host_data, ttl=600)

# Retrieve data
cached_hosts = await cache.get("hosts:production")
if cached_hosts:
    print("Cache hit!")
else:
    print("Cache miss - fetch from API")
```

#### CachingService Mixin
```python
from checkmk_agent.services.cache import CachingService

class HostService(CachingService, BaseService):
    @cached(ttl=300, key_prefix="hosts")
    async def get_host_details(self, host_name: str):
        # This method result will be cached for 5 minutes
        return await self.api_client.get_host(host_name)
    
    async def update_host(self, host_name: str, **changes):
        result = await self.api_client.update_host(host_name, **changes)
        
        # Invalidate related cache entries
        await self.invalidate_cache_pattern(f"hosts:*{host_name}*")
        
        return result
```

#### CachedHostService
```python
# Drop-in replacement for HostService with caching
cached_service = CachedHostService(client, config)

# First call hits API
hosts1 = await cached_service.list_hosts(search="web*")

# Second call uses cache (much faster)
hosts2 = await cached_service.list_hosts(search="web*")
```

### Cache Strategies
- **LRU Eviction**: Least recently used items removed when cache is full
- **TTL Expiration**: Items automatically expire after specified time
- **Pattern Invalidation**: Invalidate multiple related entries with wildcards
- **Automatic Cleanup**: Background cleanup of expired entries

### Performance Benefits
- **5-50x speedup** for repeated queries
- **Reduced API load** on Checkmk server
- **Lower latency** for interactive operations
- **Configurable policies** for different use cases

## Batch Operations

### Purpose
Batch operations allow efficient processing of multiple items with concurrency control, retry logic, and progress tracking.

### Key Components

#### BatchProcessor
```python
from checkmk_agent.services.batch import BatchProcessor

processor = BatchProcessor(
    max_concurrent=10,    # Process 10 items simultaneously
    max_retries=3,        # Retry failed items up to 3 times
    retry_delay=1.0,      # Wait 1 second between retries
    rate_limit=50         # Maximum 50 operations per second
)

# Process batch of items
async def create_host(host_data):
    return await api_client.create_host(**host_data)

result = await processor.process_batch(
    items=host_data_list,
    operation=create_host,
    batch_id="host_creation_batch"
)

print(f"Success: {result.progress.success}")
print(f"Failed: {result.progress.failed}")
print(f"Duration: {result.progress.duration} seconds")
```

#### BatchOperationsMixin
```python
class HostService(BatchOperationsMixin, BaseService):
    async def bulk_create_hosts(self, hosts_data):
        return await self.batch_create(
            items=hosts_data,
            resource_type="host",
            create_function=self._create_single_host
        )
    
    async def bulk_update_hosts(self, updates):
        return await self.batch_update(
            updates=updates,
            resource_type="host", 
            update_function=self._update_single_host
        )
```

### Features
- **Concurrency Control**: Configurable parallel processing
- **Progress Tracking**: Real-time progress updates
- **Error Handling**: Per-item error tracking and retry logic
- **Rate Limiting**: Prevent API overwhelming
- **Validation**: Pre-process item validation
- **Statistics**: Detailed performance and success metrics

### Use Cases
- **Host Creation**: Create hundreds of hosts efficiently
- **Configuration Updates**: Update multiple items simultaneously
- **Data Migration**: Migrate large datasets between systems
- **Bulk Operations**: Any operation involving multiple items

## Performance Monitoring

### Purpose
Comprehensive performance monitoring provides visibility into system behavior, identifies bottlenecks, and enables data-driven optimization.

### Key Components

#### MetricsCollector
```python
from checkmk_agent.services.metrics import get_metrics_collector

collector = get_metrics_collector()

# Record timing
await collector.record_timing("api_call", 0.150)

# Count events
await collector.increment_counter("hosts_created")

# Set gauge values
await collector.set_gauge("active_connections", 25)

# Get statistics
stats = await collector.get_stats()
print(f"Request rate: {stats['request_rate_per_second']:.1f}/sec")
```

#### @timed Decorator
```python
from checkmk_agent.services.metrics import timed

class HostService:
    @timed(metric_name="host_operations.list")
    async def list_hosts(self, **kwargs):
        # Method execution time automatically recorded
        return await self.api_client.list_hosts(**kwargs)
```

#### Context Manager
```python
from checkmk_agent.services.metrics import timed_context

async def complex_operation():
    async with timed_context("data_processing"):
        # All code in this block is timed
        data = await fetch_data()
        processed = await process_data(data)
        return processed
```

#### MetricsMixin
```python
class MyService(MetricsMixin, BaseService):
    async def operation_with_metrics(self):
        start_time = time.time()
        try:
            result = await self.api_call()
            duration = time.time() - start_time
            await self.record_operation("api_call", duration, success=True)
            return result
        except Exception as e:
            duration = time.time() - start_time
            await self.record_operation("api_call", duration, success=False)
            raise
```

### Metrics Types
- **Timing**: Method execution times with percentiles
- **Counters**: Event counts (requests, errors, successes)
- **Gauges**: Current values (connections, queue sizes)
- **Statistics**: Hit rates, throughput, error rates

### Performance Insights
- **P95/P99 Response Times**: Identify slow operations
- **Error Rates**: Monitor system health
- **Throughput**: Measure system capacity
- **Cache Efficiency**: Optimize caching strategies

## Advanced Error Recovery

### Purpose
Advanced error recovery patterns ensure system resilience in the face of network issues, API failures, and other transient problems.

### Key Components

#### Circuit Breaker
```python
from checkmk_agent.services.recovery import CircuitBreaker

# Protect against cascading failures
breaker = CircuitBreaker(
    failure_threshold=5,    # Open after 5 failures
    recovery_timeout=60     # Try again after 60 seconds
)

async def protected_api_call():
    return await breaker.call(lambda: api_client.get_data())
```

#### Retry Policy
```python
from checkmk_agent.services.recovery import RetryPolicy

# Intelligent retry with backoff
retry_policy = RetryPolicy(
    max_retries=3,
    base_delay=1.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    jitter=True
)

result = await retry_policy.execute(
    lambda: api_client.unreliable_operation(),
    retryable_exceptions=(NetworkError, TimeoutError)
)
```

#### @resilient Decorator
```python
from checkmk_agent.services.recovery import RecoveryMixin

class HostService(RecoveryMixin, BaseService):
    @resilient(
        circuit_breaker=True,
        retry_policy=True,
        fallback=True
    )
    async def get_host_status(self, host_name):
        return await self.api_client.get_host_status(host_name)
```

#### Fallback Handler
```python
# Register fallback for critical operations
service.fallback_handler.register_fallback(
    "get_host_status",
    lambda host_name: {"status": "unknown", "message": "API unavailable"}
)
```

### Recovery Strategies
- **Circuit Breaker**: Prevent cascade failures
- **Retry with Backoff**: Handle transient errors
- **Fallback Operations**: Graceful degradation
- **Rate Limiting**: Prevent overwhelming services
- **Health Checks**: Monitor service availability

### Error Classification
- **Retryable**: Network timeouts, rate limits
- **Non-retryable**: Authentication, validation errors
- **Circuit Breaking**: High error rates, service unavailable

## MCP Server Integration

### Enhanced Server
The enhanced MCP server (`mcp_checkmk_enhanced_server.py`) includes all advanced features:

```bash
# Start enhanced server
python mcp_checkmk_enhanced_server.py --config config.yaml

# Advanced features available:
# - Streaming resources
# - Performance metrics
# - Cache management
# - Batch operations
```

### Advanced MCP Resources
- `checkmk://stream/hosts` - Streaming host data
- `checkmk://stream/services` - Streaming service data  
- `checkmk://metrics/server` - Server performance metrics
- `checkmk://cache/stats` - Cache statistics

### Advanced MCP Tools
- `stream_hosts` - Stream hosts in configurable batches
- `batch_create_hosts` - Efficient bulk host creation
- `get_server_metrics` - Comprehensive performance data
- `clear_cache` - Cache management operations

## Best Practices

### Performance Optimization
1. **Choose appropriate batch sizes** based on your environment
2. **Use caching** for frequently accessed, relatively static data
3. **Monitor metrics** to identify bottlenecks
4. **Implement circuit breakers** for external dependencies

### Error Handling
1. **Classify errors** appropriately (retryable vs. permanent)
2. **Use exponential backoff** with jitter for retries
3. **Implement fallbacks** for critical operations
4. **Monitor error rates** and circuit breaker states

### Scalability
1. **Use streaming** for large datasets
2. **Batch operations** where possible
3. **Configure concurrency** based on system capacity
4. **Implement rate limiting** to protect downstream services

### Monitoring
1. **Set up metrics collection** from day one
2. **Monitor key performance indicators**
3. **Set up alerting** on error rates and performance degradation
4. **Use cache statistics** to optimize cache policies

## Configuration Examples

### High-Performance Configuration
```python
# config.yaml
advanced_features:
  streaming:
    default_batch_size: 500
    max_concurrent_batches: 10
  
  caching:
    max_size: 10000
    default_ttl: 600
    cleanup_interval: 300
  
  batch_processing:
    max_concurrent: 20
    rate_limit: 100
  
  metrics:
    retention_hours: 48
    cleanup_interval: 3600
  
  recovery:
    circuit_breaker:
      failure_threshold: 10
      recovery_timeout: 30
    retry:
      max_retries: 5
      base_delay: 0.5
```

### Memory-Optimized Configuration
```python
advanced_features:
  streaming:
    default_batch_size: 50
    memory_limit_mb: 100
  
  caching:
    max_size: 1000
    default_ttl: 300
  
  batch_processing:
    max_concurrent: 5
  
  metrics:
    retention_hours: 24
```

This advanced features guide provides the foundation for building highly scalable, performant, and resilient Checkmk integrations.