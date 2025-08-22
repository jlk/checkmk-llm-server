# Advanced Features Guide

This document provides comprehensive guidance on the advanced features implemented in Phase 4 of the Checkmk MCP Server project.

## Overview

The Checkmk MCP Server includes several advanced features designed for larger deployments:

- **Streaming Support** - Handle large datasets efficiently
- **Caching Layer** - Improve performance with intelligent caching
- **Batch Operations** - Process multiple operations efficiently
- **Advanced Error Recovery** - Circuit breakers, retries, and fallbacks
- **Specialized Parameter Handlers** - Intelligent parameter management for different service types

## Streaming Support

### Purpose
Streaming support allows the system to handle large Checkmk environments (thousands of hosts/services) without loading all data into memory simultaneously.

### Key Components

#### StreamingMixin
```python
from checkmk_mcp_server.services.streaming import StreamingMixin

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
from checkmk_mcp_server.services.cache import LRUCache

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
from checkmk_mcp_server.services.cache import CachingService

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
from checkmk_mcp_server.services.batch import BatchProcessor

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

## Advanced Error Recovery

### Purpose
Advanced error recovery patterns ensure system resilience in the face of network issues, API failures, and other transient problems.

### Key Components

#### Circuit Breaker
```python
from checkmk_mcp_server.services.recovery import CircuitBreaker

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
from checkmk_mcp_server.services.recovery import RetryPolicy

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
from checkmk_mcp_server.services.recovery import RecoveryMixin

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
The unified MCP server (`mcp_checkmk_server.py`) includes all advanced features with modular architecture:

```bash
# Start unified server with all advanced features
python mcp_checkmk_server.py --config config.yaml

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

## Specialized Parameter Handlers

### Purpose
Specialized parameter handlers provide intelligent, context-aware parameter generation and validation for different types of monitoring services. Each handler understands specific service characteristics and can provide optimized defaults, validate configurations, and suggest improvements.

### Key Components

#### Handler Registry
```python
from checkmk_mcp_server.services.handlers import get_handler_registry

# Get the global handler registry
registry = get_handler_registry()

# Find best handler for a service
handler = registry.get_best_handler(service_name="CPU Temperature")

# Get all handlers for a service type
handlers = registry.get_handlers_for_service("MySQL Connections")
```

#### Temperature Parameter Handler
```python
# Get optimized temperature parameters
result = await parameter_service.get_specialized_defaults("CPU Temperature")

# Context-aware parameters
production_context = {
    "environment": "production",
    "criticality": "high",
    "hardware_type": "server"
}

result = await parameter_service.get_specialized_defaults(
    "CPU Temperature", 
    production_context
)

# Result includes stricter thresholds for production
parameters = result.data["parameters"]
# {"levels": (70.0, 80.0), "output_unit": "c", ...}
```

#### Database Parameter Handler
```python
# MySQL connection parameters
mysql_result = await parameter_service.get_specialized_defaults("MySQL Connections")

# Oracle tablespace parameters
oracle_result = await parameter_service.get_specialized_defaults("Oracle Tablespace USERS")

# PostgreSQL lock parameters
postgres_result = await parameter_service.get_specialized_defaults("PostgreSQL Locks")
```

#### Network Service Parameter Handler
```python
# HTTPS monitoring parameters
https_result = await parameter_service.get_specialized_defaults("HTTPS API Health")

# Includes SSL certificate monitoring
parameters = https_result.data["parameters"]
# {
#   "response_time": (2.0, 5.0),
#   "ssl_cert_age": (30, 7),
#   "ssl_verify": True,
#   "timeout": 10
# }

# TCP port check parameters
tcp_result = await parameter_service.get_specialized_defaults("TCP Port 443")
```

#### Custom Check Parameter Handler
```python
# MRPE check parameters
mrpe_result = await parameter_service.get_specialized_defaults("MRPE check_disk")

# Nagios plugin parameters
nagios_result = await parameter_service.get_specialized_defaults("check_mysql")

# Local check parameters
local_result = await parameter_service.get_specialized_defaults("Local memory_check")
```

### Advanced Parameter Features

#### Parameter Validation
```python
# Validate parameters with specialized handlers
parameters = {
    "levels": (75.0, 85.0),
    "output_unit": "c",
    "device_levels_handling": "devdefault"
}

validation_result = await parameter_service.validate_specialized_parameters(
    parameters, 
    "CPU Temperature"
)

if validation_result.data["is_valid"]:
    print("Parameters are valid")
else:
    for error in validation_result.data["errors"]:
        print(f"Error: {error.message}")
```

#### Parameter Suggestions
```python
# Get optimization suggestions
current_params = {"levels": (60.0, 70.0)}

suggestions_result = await parameter_service.get_parameter_suggestions(
    "CPU Temperature",
    current_params
)

for suggestion in suggestions_result.data["suggestions"]:
    print(f"Parameter: {suggestion['parameter']}")
    print(f"Current: {suggestion['current_value']}")
    print(f"Suggested: {suggestion['suggested_value']}")
    print(f"Reason: {suggestion['reason']}")
```

#### Bulk Parameter Operations
```python
# Process multiple services efficiently
service_names = [
    "CPU Temperature",
    "GPU Temperature", 
    "MySQL Connections",
    "HTTP Health Check"
]

# Use MCP bulk operation tool
bulk_result = await mcp_server.call_tool("bulk_parameter_operations", {
    "service_names": service_names,
    "operation": "get_defaults",
    "context": {"environment": "production"}
})

# Process results
for service_result in bulk_result.data["results"]:
    service_name = service_result["service_name"]
    if service_result["success"]:
        handler_used = service_result["data"]["handler_used"]
        parameters = service_result["data"]["parameters"]
        print(f"{service_name}: {handler_used} handler used")
```

#### Rule Creation with Specialized Parameters
```python
# Create Checkmk rules with intelligent parameters
rule_data = {
    "ruleset": "checkgroup_parameters:temperature",
    "folder": "/servers/production",
    "conditions": {
        "host_name": ["web-*", "app-*"],
        "service_description": ["CPU Temperature"]
    },
    "properties": {
        "comment": "Production CPU temperature monitoring",
        "description": "Optimized thresholds for production servers"
    },
    "value": {
        "levels": (75.0, 85.0),
        "output_unit": "c"
    }
}

rule_result = await parameter_service.create_specialized_rule(
    "CPU Temperature",
    rule_data
)
```

### MCP Parameter Tools

The parameter management system exposes 12 specialized MCP tools:

1. **get_specialized_defaults** - Get intelligent default parameters
2. **validate_specialized_parameters** - Validate parameters using handlers
3. **get_parameter_suggestions** - Get optimization suggestions
4. **discover_parameter_handlers** - Find matching handlers for services
5. **get_handler_info** - Get detailed handler information
6. **bulk_parameter_operations** - Process multiple services efficiently
7. **create_specialized_rule** - Create rules with specialized parameters
8. **search_services_by_handler** - Find services matching handler types
9. **export_parameter_configuration** - Export parameter configurations
10. **import_parameter_configuration** - Import parameter configurations
11. **update_specialized_rule** - Update existing rules
12. **delete_specialized_rule** - Delete rules with validation

### Handler Performance

#### Benchmarks
- **Handler Selection**: 5,000+ operations/second
- **Parameter Generation**: 1,000+ operations/second  
- **Parameter Validation**: 500+ operations/second
- **Bulk Operations**: 2,000+ operations/second
- **Memory Usage**: <50MB for 10,000 services

#### Optimization Features
- **Handler Caching**: Instances cached after first use
- **Pattern Matching**: Optimized regex patterns for service detection
- **Concurrent Processing**: Thread-safe operations
- **Batch Processing**: Efficient bulk operations

### Configuration

```python
# config.yaml
parameter_handlers:
  temperature:
    enabled: true
    priority: 100
    profiles:
      cpu:
        levels: [75.0, 85.0]
        levels_lower: [5.0, 0.0]
      ambient:
        levels: [35.0, 40.0]
        levels_lower: [10.0, 5.0]
  
  database:
    enabled: true
    priority: 90
    connection_timeout: 30
    
  network_services:
    enabled: true
    priority: 80
    default_timeout: 10
    ssl_verification: true
    
  custom_checks:
    enabled: true
    priority: 70
    security_validation: true
    dangerous_commands:
      - "rm"
      - "del"
      - "format"
```

### Best Practices

#### Handler Usage
1. **Let the system choose handlers** - The registry automatically selects the best handler
2. **Provide context when available** - Context improves parameter quality
3. **Always validate parameters** - Use validation before creating rules
4. **Use bulk operations** - More efficient for multiple services

#### Performance Optimization
1. **Cache handler instances** - Handlers are automatically cached
2. **Use appropriate batch sizes** - Balance memory usage and throughput
3. **Leverage concurrent processing** - Use async operations where possible
4. **Monitor handler performance** - Track selection and generation times

#### Error Handling
1. **Handle handler failures gracefully** - Fall back to generic parameters
2. **Validate parameters before applying** - Prevent invalid rule creation
3. **Use try-except blocks** - Handle unexpected errors
4. **Log handler selection** - Debug issues with handler matching

This comprehensive advanced features guide provides the foundation for building highly scalable, performant, and resilient Checkmk integrations with intelligent parameter management.