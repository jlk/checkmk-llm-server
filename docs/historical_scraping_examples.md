# Historical Data Scraping Usage Examples

This document provides examples of using the historical data scraping functionality in the Checkmk LLM Agent. The scraper provides enhanced data parsing capabilities and dual data source support for historical metrics and events.

## Table of Contents

- [Configuration](#configuration)
- [Basic Usage Examples](#basic-usage-examples)
- [Advanced Scraping Features](#advanced-scraping-features)
- [MCP Tool Integration](#mcp-tool-integration)
- [Performance Optimization](#performance-optimization)
- [Error Handling](#error-handling)
- [Natural Language Interactions](#natural-language-interactions)
- [Troubleshooting](#troubleshooting)

## Configuration

### Basic Configuration

Add the historical data configuration to your `config.yaml`:

```yaml
# Historical data configuration
historical_data:
  source: "scraper"           # Default data source: "rest_api" or "scraper"
  cache_ttl: 60              # Cache TTL in seconds (default: 60)
  scraper_timeout: 30        # Request timeout in seconds
```

### Environment-Specific Configurations

**Development (examples/configs/development.yaml):**
```yaml
historical_data:
  source: "scraper"
  cache_ttl: 30              # Shorter cache for development
  scraper_timeout: 15        # Faster timeout for development
```

**Production (examples/configs/production.yaml):**
```yaml
historical_data:
  source: "rest_api"         # Use REST API for production stability
  cache_ttl: 300             # Longer cache for production
  scraper_timeout: 60        # Longer timeout for production
```

**Testing (examples/configs/testing.yaml):**
```yaml
historical_data:
  source: "scraper"
  cache_ttl: 5               # Very short cache for testing
  scraper_timeout: 10        # Short timeout for testing
```

## Basic Usage Examples

### 1. Getting Historical Metrics

#### Using Default Configuration
```python
# Uses configured default data source
result = await get_metric_history(
    host_name="server01",
    service_description="CPU load",
    metric_id="load1",
    time_range_hours=24
)

print(f"Success: {result['success']}")
print(f"Data source: {result['data_source']}")
print(f"Data points: {result['metrics'][0]['data_points_count']}")
```

#### Overriding Data Source
```python
# Override to use scraper regardless of configuration
result = await get_metric_history(
    host_name="server01",
    service_description="Temperature CPU",
    metric_id="temp_cpu",
    time_range_hours=168,       # 1 week
    data_source="scraper"       # Explicit override
)

if result["success"]:
    # Access enhanced scraper features
    summary_stats = result["unified_data"]["summary_stats"]
    print(f"Average temperature: {summary_stats.get('avg', 'N/A')}°C")
    print(f"Maximum temperature: {summary_stats.get('max', 'N/A')}°C")
    print(f"Minimum temperature: {summary_stats.get('min', 'N/A')}°C")
```

### 2. Listing Service Events

#### Event Console (REST API)
```python
# Use Event Console for official events
events = await list_service_events(
    host_name="server01",
    service_name="Disk space /",
    limit=20,
    data_source="rest_api"
)

if events["success"]:
    for event in events["events"]:
        print(f"Event: {event['text']}")
        print(f"State: {event['state']}")
        print(f"Time: {event['first_time']}")
```

#### Synthetic Events from Metrics (Scraper)
```python
# Generate synthetic events from metric changes
events = await list_service_events(
    host_name="server01",
    service_name="Memory usage",
    limit=50,
    data_source="scraper"
)

if events["success"]:
    print(f"Found {events['count']} metric change events")
    for event in events["events"]:
        print(f"Change detected: {event['text']}")
        print(f"Time: {event['first_time']}")
```

## Advanced Scraping Features

### 1. Multiple Service Types

#### Temperature Monitoring
```python
# Temperature data with unit extraction
result = await get_metric_history(
    host_name="server01",
    service_description="Temperature CPU",
    metric_id="temp_cpu",
    time_range_hours=48,
    data_source="scraper"
)

if result["success"]:
    # Scraper automatically extracts numeric values from "75.5°C"
    data_points = result["unified_data"]["metrics"][0]["data_points"]
    for point in data_points[:5]:  # Show first 5 points
        print(f"{point['timestamp']}: {point['value']}°C")
```

#### Memory Usage with Percentages
```python
# Memory usage with percentage extraction
result = await get_metric_history(
    host_name="server01",
    service_description="Memory usage",
    metric_id="mem_used_percent",
    time_range_hours=24,
    data_source="scraper"
)

if result["success"]:
    # Scraper extracts numeric values from "85.5%" strings
    stats = result["unified_data"]["summary_stats"]
    print(f"Average memory usage: {stats.get('avg', 0):.1f}%")
    print(f"Peak memory usage: {stats.get('max', 0):.1f}%")
```

#### Network Interfaces with Bandwidth Units
```python
# Network interface with bandwidth unit parsing
result = await get_metric_history(
    host_name="switch01",
    service_description="Interface eth0",
    metric_id="if_in_octets",
    time_range_hours=12,
    data_source="scraper"
)

if result["success"]:
    # Scraper handles "125.4 Mbit/s" format
    metrics = result["unified_data"]["metrics"][0]
    print(f"Interface: {metrics['name']}")
    print(f"Unit: {metrics.get('unit', 'unknown')}")
    
    data_points = metrics["data_points"]
    latest = data_points[-1] if data_points else None
    if latest:
        print(f"Latest bandwidth: {latest['value']} Mbit/s")
```

### 2. Data Parsing Capabilities

#### Mixed Data Types
```python
# Service with mixed string and numeric values
result = await get_metric_history(
    host_name="server01",
    service_description="Disk usage /var",
    metric_id="disk_used",
    time_range_hours=168,
    data_source="scraper"
)

if result["success"]:
    # Scraper handles "45.2 GB", 46.8, "48.1GB" formats
    data_points = result["unified_data"]["metrics"][0]["data_points"]
    
    print("Parsed disk usage values:")
    for i, point in enumerate(data_points[-5:]):  # Last 5 points
        print(f"  {i+1}. {point['timestamp']}: {point['value']} GB")
```

#### Non-Numeric Status Data
```python
# Service returning text status values
result = await get_metric_history(
    host_name="server01",
    service_description="Service Status",
    metric_id="status",
    time_range_hours=24,
    data_source="scraper"
)

if result["success"]:
    # Scraper preserves text values like "OK", "WARNING", "CRITICAL"
    data_points = result["unified_data"]["metrics"][0]["data_points"]
    
    # Count status occurrences
    status_counts = {}
    for point in data_points:
        status = point["value"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("Status distribution:")
    for status, count in status_counts.items():
        print(f"  {status}: {count} occurrences")
```

## MCP Tool Integration

### 1. Claude Desktop Integration

Configure Claude Desktop to use the MCP server:

```json
{
  "mcpServers": {
    "checkmk": {
      "command": "python",
      "args": ["mcp_checkmk_server.py", "--config", "config.yaml"]
    }
  }
}
```

Then use natural language with Claude:

```
User: "Show me the CPU temperature history for server01 over the last week using the scraper"

Claude will call:
get_metric_history(
    host_name="server01",
    service_description="Temperature CPU", 
    metric_id="temp_cpu",
    time_range_hours=168,
    data_source="scraper"
)
```

### 2. VS Code MCP Extension

With the MCP extension, you can use historical data tools directly in VS Code:

```python
# In VS Code with MCP extension
# Use Command Palette: "MCP: Get Metric History"
# Tool will suggest parameters and show results inline
```

### 3. Programmatic MCP Client

```python
from mcp_client import MCPClient

async def main():
    client = MCPClient("checkmk")
    await client.connect()
    
    # Use the historical tools
    result = await client.call_tool("get_metric_history", {
        "host_name": "server01",
        "service_description": "CPU load",
        "metric_id": "load1",
        "time_range_hours": 24,
        "data_source": "scraper"
    })
    
    print(f"Tool result: {result}")
    await client.disconnect()

# Run with asyncio.run(main())
```

## Performance Optimization

### 1. Caching Strategies

#### Optimal Cache TTL
```python
# Configure cache TTL based on data update frequency
historical_data:
  cache_ttl: 60      # 1 minute for frequently changing metrics
  # cache_ttl: 300   # 5 minutes for slow-changing metrics
  # cache_ttl: 900   # 15 minutes for historical analysis
```

#### Cache Hit Rate Monitoring
```python
# Monitor cache performance
historical_service = server.historical_service
stats = historical_service.get_cache_stats()

print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hits'] / (stats['hits'] + stats['misses']):.1%}")
print(f"Cache size: {stats['size']} entries")
```

### 2. Concurrent Requests

#### Batch Processing
```python
import asyncio

async def get_multiple_metrics():
    # Process multiple metrics concurrently
    tasks = [
        get_metric_history("server01", "CPU load", "load1", data_source="scraper"),
        get_metric_history("server01", "Memory usage", "mem_used", data_source="scraper"),
        get_metric_history("server01", "Disk space /", "disk_used", data_source="scraper"),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Task {i} failed: {result}")
        else:
            print(f"Task {i} succeeded: {result['metrics'][0]['data_points_count']} points")

# Run with asyncio.run(get_multiple_metrics())
```

### 3. Memory Management

#### Large Dataset Handling
```python
# For large datasets, consider time range limits
result = await get_metric_history(
    host_name="server01",
    service_description="High-frequency metric",
    metric_id="high_freq_metric",
    time_range_hours=24,        # Limit time range for memory efficiency
    reduce="average",           # Use data reduction
    data_source="scraper"
)

if result["success"]:
    execution_time = result["unified_data"]["execution_time_ms"]
    data_count = result["unified_data"]["parsed_data_points"]
    print(f"Processed {data_count} points in {execution_time:.1f}ms")
```

## Error Handling

### 1. Network Issues

```python
async def robust_metric_retrieval(host_name, service_name, metric_id):
    """Robust metric retrieval with fallback strategies."""
    
    # Try scraper first
    try:
        result = await get_metric_history(
            host_name=host_name,
            service_description=service_name,
            metric_id=metric_id,
            data_source="scraper"
        )
        
        if result["success"]:
            return result
        else:
            print(f"Scraper failed: {result['error']}")
            
    except Exception as e:
        print(f"Scraper exception: {e}")
    
    # Fallback to REST API
    try:
        result = await get_metric_history(
            host_name=host_name,
            service_description=service_name,
            metric_id=metric_id,
            data_source="rest_api"
        )
        
        if result["success"]:
            print("Fallback to REST API successful")
            return result
        else:
            print(f"REST API also failed: {result['error']}")
            
    except Exception as e:
        print(f"REST API exception: {e}")
    
    return {"success": False, "error": "All data sources failed"}
```

### 2. Authentication Errors

```python
async def handle_auth_errors():
    """Handle authentication-related errors."""
    
    result = await get_metric_history(
        host_name="server01",
        service_description="CPU load",
        metric_id="load1",
        data_source="scraper"
    )
    
    if not result["success"]:
        error = result["error"]
        
        if "401" in error or "Unauthorized" in error:
            print("Authentication failed. Please check credentials.")
            print("Update config.yaml with valid username/password")
            
        elif "403" in error or "Forbidden" in error:
            print("Access denied. User may lack required permissions.")
            print("Ensure user has access to historical data endpoints")
            
        elif "timeout" in error.lower():
            print("Request timed out. Consider increasing scraper_timeout")
            
        else:
            print(f"Unexpected error: {error}")
```

### 3. Data Validation

```python
def validate_scraper_result(result):
    """Validate scraper result data."""
    
    if not result["success"]:
        return False, f"Request failed: {result['error']}"
    
    if not result.get("metrics"):
        return False, "No metrics data returned"
    
    unified_data = result.get("unified_data", {})
    
    # Check for parsing errors
    parse_errors = unified_data.get("parse_errors", [])
    if parse_errors:
        error_count = len(parse_errors)
        total_count = unified_data.get("raw_data_count", 0)
        error_rate = error_count / total_count if total_count > 0 else 0
        
        if error_rate > 0.5:  # More than 50% errors
            return False, f"High error rate: {error_rate:.1%} ({error_count}/{total_count})"
    
    # Check data completeness
    data_points = unified_data.get("parsed_data_points", 0)
    if data_points == 0:
        return False, "No valid data points parsed"
    
    return True, "Data validation passed"

# Usage
result = await get_metric_history(
    host_name="server01",
    service_description="CPU load", 
    metric_id="load1",
    data_source="scraper"
)

is_valid, message = validate_scraper_result(result)
print(f"Validation: {message}")
```

## Natural Language Interactions

### 1. Claude Desktop Examples

```
User: "Show me the temperature trend for server01 over the past 3 days using the web scraper"

Claude: I'll get the temperature data for server01 using the web scraper for enhanced parsing capabilities.

[Calls get_metric_history with data_source="scraper"]

The temperature data shows:
- Average: 76.9°C
- Maximum: 78.1°C  
- Minimum: 75.5°C
- Data points: 144 (every 30 minutes)
- Temperature range is within normal limits
```

```
User: "Find any unusual events in the memory usage for database servers"

Claude: I'll analyze memory usage events by using the scraper to detect metric changes.

[Calls list_service_events with data_source="scraper"]

Found 3 significant memory events:
1. Memory usage jumped from 65% to 89% on db01 at 2025-01-15 14:30
2. Memory usage spiked to 95% on db02 at 2025-01-15 16:45  
3. Memory returned to normal (72%) on db01 at 2025-01-15 18:00
```

### 2. Interactive CLI Examples

```bash
# Start interactive mode
python checkmk_agent_cli.py interactive

# Natural language commands
>>> "Get CPU temperature history for server01 using scraper"
[Executing: get_metric_history(host_name="server01", service_description="Temperature CPU", data_source="scraper")]

>>> "Show network interface events for the last 24 hours"
[Executing: list_service_events with scraper analysis]

>>> "Compare memory usage between servers using enhanced parsing"
[Executing: Multiple get_metric_history calls with scraper data source]
```

## Troubleshooting

### 1. Common Issues

#### Scraper Import Errors
```
Error: "No module named 'checkmk_agent.services.web_scraping'"

Solution:
1. Ensure web scraping services are properly installed
2. Check that the checkmk_agent package is complete
3. Fall back to REST API: data_source="rest_api"
```

#### Configuration Issues
```
Error: "Invalid configuration"

Solution:
1. Verify config.yaml syntax
2. Check historical_data section exists
3. Validate source value: "scraper" or "rest_api"
```

#### Network Timeouts
```
Error: "Request timeout after 30 seconds"

Solution:
1. Increase scraper_timeout in config
2. Check network connectivity to Checkmk server
3. Verify server is responding to web requests
```

### 2. Performance Issues

#### Slow Response Times
```python
# Diagnose performance issues
result = await get_metric_history(
    host_name="server01",
    service_description="CPU load",
    metric_id="load1",
    data_source="scraper"
)

if result["success"]:
    execution_time = result["unified_data"]["execution_time_ms"]
    
    if execution_time > 5000:  # > 5 seconds
        print(f"Slow response: {execution_time:.1f}ms")
        print("Consider:")
        print("- Reducing time_range_hours")
        print("- Checking network latency")
        print("- Using REST API for this metric")
```

#### High Memory Usage
```python
# Monitor memory usage patterns
import psutil
import gc

def check_memory_usage():
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"Memory usage: {memory_mb:.1f} MB")
    
    # Force garbage collection
    gc.collect()
    
    return memory_mb

# Before large operation
before_memory = check_memory_usage()

# Perform operation
result = await get_metric_history(...)

# After operation
after_memory = check_memory_usage()
print(f"Memory delta: {after_memory - before_memory:.1f} MB")
```

### 3. Data Quality Issues

#### Parsing Errors
```python
def analyze_parsing_errors(result):
    """Analyze parsing errors in scraper results."""
    
    if not result["success"]:
        return
    
    unified_data = result.get("unified_data", {})
    parse_errors = unified_data.get("parse_errors", [])
    
    if parse_errors:
        print(f"Found {len(parse_errors)} parsing errors:")
        for i, error in enumerate(parse_errors[:5]):  # Show first 5
            print(f"  {i+1}. {error}")
        
        if len(parse_errors) > 5:
            print(f"  ... and {len(parse_errors) - 5} more")
        
        # Suggest solutions
        print("\nSuggestions:")
        print("- Check if service returns expected data format")
        print("- Consider using REST API for this metric")
        print("- Report parsing issues to development team")
```

#### Missing Data
```python
def check_data_completeness(result, expected_hours):
    """Check if scraped data is complete for the requested time range."""
    
    if not result["success"]:
        return False
    
    data_points = result["unified_data"]["parsed_data_points"]
    
    # Estimate expected data points (assuming 5-minute intervals)
    expected_points = expected_hours * 12  # 12 points per hour
    completeness = data_points / expected_points if expected_points > 0 else 0
    
    print(f"Data completeness: {completeness:.1%}")
    print(f"Got {data_points} points, expected ~{expected_points}")
    
    if completeness < 0.8:  # Less than 80% complete
        print("Warning: Data may be incomplete")
        print("Consider:")
        print("- Checking service monitoring frequency")
        print("- Verifying time range is valid")
        print("- Using shorter time range")
    
    return completeness >= 0.8

# Usage
result = await get_metric_history(
    host_name="server01",
    service_description="CPU load",
    metric_id="load1", 
    time_range_hours=24,
    data_source="scraper"
)

is_complete = check_data_completeness(result, 24)
```

This guide covers all aspects of using the historical data scraping functionality, from basic configuration to advanced troubleshooting techniques. The examples demonstrate both programmatic usage and natural language interactions through MCP integration.