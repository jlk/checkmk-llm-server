# Checkmk LLM Agent Usage Examples

This guide provides comprehensive examples of using the Checkmk LLM Agent with the new features introduced in Checkmk 2.4.

## Table of Contents
- [Event Console Examples](#event-console-examples)
- [Metrics and Performance Data Examples](#metrics-and-performance-data-examples)
- [Business Intelligence Examples](#business-intelligence-examples)
- [Enhanced Acknowledgment Examples](#enhanced-acknowledgment-examples)
- [System Information Examples](#system-information-examples)

## Event Console Examples

The Event Console provides access to service event history and log management.

### View Service Event History

```bash
# CLI command
python -m checkmk_agent.cli services events server01 "CPU utilization"

# Natural language in interactive mode
"Show me the event history for CPU utilization on server01"
"What events occurred for the disk space service on server01?"
```

### List All Events for a Host

```bash
# CLI command
python -m checkmk_agent.cli events list --host server01

# Natural language
"Show me all events for server01"
"What happened on server01 in the last 24 hours?"
```

### Get Recent Critical Events

```bash
# CLI command
python -m checkmk_agent.cli events critical --limit 20

# Natural language
"Show me the recent critical events"
"What critical issues occurred recently?"
```

### Acknowledge Events

```bash
# CLI command
python -m checkmk_agent.cli events acknowledge EVENT123 "Working on it"

# Natural language
"Acknowledge event EVENT123 with comment 'Working on it'"
```

### Search Events

```bash
# CLI command
python -m checkmk_agent.cli events search "disk full" --state critical

# Natural language
"Search for critical events containing 'disk full'"
"Find all events about disk space issues"
```

## Metrics and Performance Data Examples

Access performance graphs and historical metric data.

### Get Service Metrics

```bash
# CLI command
python -m checkmk_agent.cli services metrics server01 "CPU utilization" --hours 24

# Natural language
"Show me CPU metrics for server01 over the last 24 hours"
"Get performance graphs for memory usage on server01"
```

### Retrieve Specific Metric History

```bash
# CLI command - requires metric ID from Checkmk UI
python -m checkmk_agent.cli metrics history server01 "CPU utilization" cpu_user --hours 168

# Natural language
"Show me the CPU user metric history for server01 for the past week"
```

### Performance Data Reduction Options

```bash
# Get maximum values (useful for capacity planning)
python -m checkmk_agent.cli services metrics server01 "Interface eth0" --hours 24 --reduce max

# Get minimum values
python -m checkmk_agent.cli services metrics server01 "Temperature" --hours 24 --reduce min

# Natural language
"Show me the peak network usage on server01 eth0 today"
"What was the lowest temperature on server01 in the last 24 hours?"
```

## Business Intelligence Examples

Monitor business-level service aggregations and high-level status.

### Get Business Status Summary

```bash
# CLI command
python -m checkmk_agent.cli bi status

# Filter by business groups
python -m checkmk_agent.cli bi status --groups "Web Services,Database"

# Natural language
"Show me the business service status"
"How are the web services performing?"
"Give me a business-level overview"
```

### List Critical Business Services

```bash
# CLI command
python -m checkmk_agent.cli bi critical

# Natural language
"What business services are critical right now?"
"Show me failing business aggregations"
```

### Business Intelligence Dashboard

```python
# Python API example
from checkmk_agent.services.bi_service import BIService

# Get business summary
bi_service = BIService(client, config)
summary = await bi_service.get_business_status_summary()

print(f"Total Business Services: {summary.data['total_aggregations']}")
print(f"Critical: {summary.data['states']['crit']}")
print(f"Warning: {summary.data['states']['warn']}")
print(f"OK: {summary.data['states']['ok']}")

# List critical services with details
for critical in summary.data['critical_aggregations']:
    print(f"- {critical['id']}: {critical['output']}")
```

## Enhanced Acknowledgment Examples

Use the new expiration feature for acknowledgments.

### Acknowledge with Expiration

```bash
# CLI command - expires in 4 hours
python -m checkmk_agent.cli services acknowledge server01 "CPU load" \
  --comment "Known batch job, will complete soon" \
  --expire "2024-01-20T18:00:00"

# Natural language
"Acknowledge CPU load on server01 for 4 hours with comment 'batch job running'"
"Create a temporary acknowledgment for disk space on server01 until 6 PM"
```

### Acknowledgment Options

```bash
# Non-sticky acknowledgment (clears when service recovers)
python -m checkmk_agent.cli services acknowledge server01 "Memory" \
  --comment "Restarting service" --no-sticky

# Persistent acknowledgment (survives Checkmk restart)
python -m checkmk_agent.cli services acknowledge server01 "Disk" \
  --comment "Ordered new disk" --persistent

# With expiration and no notification
python -m checkmk_agent.cli services acknowledge server01 "CPU" \
  --comment "Maintenance window" --expire "2024-01-20T22:00:00" --no-notify
```

## System Information Examples

Get Checkmk system and version information.

### Get System Info

```bash
# CLI command
python -m checkmk_agent.cli system info

# Natural language
"What version of Checkmk is running?"
"Show me the system information"
```

### Example Output

```json
{
  "checkmk_version": "2.4.0p1",
  "edition": "Enterprise",
  "site": "production",
  "python_version": "3.11.5",
  "apache_version": "2.4.54"
}
```

## Advanced Usage Patterns

### Combining Features for Incident Response

```bash
# 1. Check business impact
python -m checkmk_agent.cli bi status

# 2. Find affected services
python -m checkmk_agent.cli status critical

# 3. Check event history for root cause
python -m checkmk_agent.cli events list --host problem-server --state critical

# 4. Review performance metrics
python -m checkmk_agent.cli services metrics problem-server "CPU utilization" --hours 6

# 5. Acknowledge with expiration
python -m checkmk_agent.cli services acknowledge problem-server "CPU load" \
  --comment "Investigating high load, ETA 2 hours" \
  --expire "$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:%S')"
```

### Natural Language Workflow

In interactive mode or via Claude/LLM:

```
User: "Show me what's wrong with the web services"
Agent: [Shows BI aggregation status for web services]

User: "Which specific servers are affected?"
Agent: [Lists critical services on web servers]

User: "Show me the CPU history for web-server-01"
Agent: [Displays CPU metrics graph for last 24 hours]

User: "Check for any disk-related events on that server"
Agent: [Shows Event Console entries for disk events]

User: "Acknowledge the CPU issue for 2 hours while we investigate"
Agent: [Creates acknowledgment with 2-hour expiration]
```

## MCP Tool Reference

When using the MCP server with Claude or other LLMs, these tools are available:

### Event Console Tools
- `list_service_events` - Get event history for a specific service
- `list_host_events` - Get all events for a host
- `get_recent_critical_events` - List recent critical events
- `acknowledge_event` - Acknowledge an event
- `search_events` - Search events by text

### Metrics Tools
- `get_service_metrics` - Get performance graphs for a service
- `get_metric_history` - Get historical data for a specific metric

### Business Intelligence Tools
- `get_business_status_summary` - Get business-level status overview
- `get_critical_business_services` - List critical business services

### System Tools
- `get_system_info` - Get Checkmk version and system information

All tools support natural language queries when used through an LLM interface.