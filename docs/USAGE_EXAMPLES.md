# Usage Examples and Common Workflows

This guide provides practical examples of using the Checkmk MCP Server for real-world monitoring scenarios. Examples show both natural language queries (for AI clients) and CLI commands.

## Quick Reference

| Scenario | Natural Language Query | CLI Command |
|----------|----------------------|-------------|
| Check system health | "Show me overall infrastructure health" | `status overview` |
| Find critical problems | "What critical issues do I have?" | `status critical` |
| Host information | "List hosts matching 'web*'" | `hosts list --search web*` |
| Service status | "Show services for server01" | `services list server01` |
| Acknowledge problem | "Ack CPU load on server01 for 2 hours" | `services acknowledge server01 "CPU load" --hours 2` |
| Schedule maintenance | "Create 4-hour downtime for DB maintenance" | `services downtime prod-db "MySQL" --hours 4` |

## Common Monitoring Scenarios

### Daily Health Check

**Scenario**: Start your day by checking infrastructure health

**Natural Language**: 
> "Give me a health summary of my infrastructure"

**CLI Command**:
```bash
python checkmk_cli_mcp.py status overview
```

**What you get**:
- Overall system status
- Count of hosts/services by state
- Recent critical/warning issues
- Business service impact

### Incident Response

**Scenario**: Alerts are firing, need to understand scope and impact

**Step 1 - Assess Impact**:
> "Show me all critical problems and their business impact"

**Step 2 - Identify Affected Systems**:
> "List all hosts with critical services"

**Step 3 - Check Event History**:
> "Show me events for server01 in the last 2 hours"

**Step 4 - Acknowledge Issues**:
> "Acknowledge all critical issues with comment 'Incident #12345 - investigating'"

### Performance Investigation

**Scenario**: Users report slow application performance

**Check Web Servers**:
> "Show me CPU and memory metrics for all web servers over the last 4 hours"

**Check Database Performance**:
> "What's the database connection and response time trend for the last 24 hours?"

**Check Network**:
> "Show me network utilization for the web farm"

### Maintenance Window Planning

**Scenario**: Planning maintenance for database cluster

**Step 1 - Check Dependencies**:
> "What services depend on the database servers?"

**Step 2 - Create Downtime**:
> "Create a 4-hour maintenance window for all database services starting at 2 AM"

**Step 3 - Verify Downtime**:
> "Show me scheduled downtimes for tomorrow"

## Metrics and Performance Data Examples

Access performance graphs and historical metric data.

### Get Service Metrics

```bash
# CLI command
python -m checkmk_mcp_server.cli services metrics server01 "CPU utilization" --hours 24

# Natural language
"Show me CPU metrics for server01 over the last 24 hours"
"Get performance graphs for memory usage on server01"
```

### Retrieve Specific Metric History

```bash
# CLI command - requires metric ID from Checkmk UI
python -m checkmk_mcp_server.cli metrics history server01 "CPU utilization" cpu_user --hours 168

# Natural language
"Show me the CPU user metric history for server01 for the past week"
```

### Performance Data Reduction Options

```bash
# Get maximum values (useful for capacity planning)
python -m checkmk_mcp_server.cli services metrics server01 "Interface eth0" --hours 24 --reduce max

# Get minimum values
python -m checkmk_mcp_server.cli services metrics server01 "Temperature" --hours 24 --reduce min

# Natural language
"Show me the peak network usage on server01 eth0 today"
"What was the lowest temperature on server01 in the last 24 hours?"
```

## Business Intelligence Examples

Monitor business-level service aggregations and high-level status.

### Get Business Status Summary

```bash
# CLI command
python -m checkmk_mcp_server.cli bi status

# Filter by business groups
python -m checkmk_mcp_server.cli bi status --groups "Web Services,Database"

# Natural language
"Show me the business service status"
"How are the web services performing?"
"Give me a business-level overview"
```

### List Critical Business Services

```bash
# CLI command
python -m checkmk_mcp_server.cli bi critical

# Natural language
"What business services are critical right now?"
"Show me failing business aggregations"
```

### Business Intelligence Dashboard

```python
# Python API example
from checkmk_mcp_server.services.bi_service import BIService

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
python -m checkmk_mcp_server.cli services acknowledge server01 "CPU load" \
  --comment "Known batch job, will complete soon" \
  --expire "2024-01-20T18:00:00"

# Natural language
"Acknowledge CPU load on server01 for 4 hours with comment 'batch job running'"
"Create a temporary acknowledgment for disk space on server01 until 6 PM"
```

### Acknowledgment Options

```bash
# Non-sticky acknowledgment (clears when service recovers)
python -m checkmk_mcp_server.cli services acknowledge server01 "Memory" \
  --comment "Restarting service" --no-sticky

# Persistent acknowledgment (survives Checkmk restart)
python -m checkmk_mcp_server.cli services acknowledge server01 "Disk" \
  --comment "Ordered new disk" --persistent

# With expiration and no notification
python -m checkmk_mcp_server.cli services acknowledge server01 "CPU" \
  --comment "Maintenance window" --expire "2024-01-20T22:00:00" --no-notify
```

## System Information Examples

Get Checkmk system and version information.

### Get System Info

```bash
# CLI command
python -m checkmk_mcp_server.cli system info

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

## Tips for Effective Usage

### Natural Language Best Practices

**Be Specific**:
- Good: "Show CPU metrics for web-server-01 for the last 4 hours"
- Less effective: "Show me some metrics"

**Use Context**:
- "Check disk space on database servers" (uses logical grouping)
- "Find all critical problems related to storage" (uses problem correlation)

**Combine Operations**:
- "Show critical problems, then acknowledge them with comment 'Investigating'"
- "Create maintenance window and notify team about scheduled downtime"

### CLI Usage Tips

**Use Aliases**:
```bash
# Create helpful aliases
alias cmk-status='python checkmk_cli_mcp.py status overview'
alias cmk-critical='python checkmk_cli_mcp.py status critical'
alias cmk-hosts='python checkmk_cli_mcp.py hosts list'
```

**Batch Scripts**:
```bash
#!/bin/bash
# Daily health check script
echo "Infrastructure Health Report - $(date)"
python checkmk_cli_mcp.py status overview
python checkmk_cli_mcp.py status problems --limit 10
```

**Use Configuration Files**:
```bash
# Different environments
python checkmk_cli_mcp.py --config prod.yaml hosts list
python checkmk_cli_mcp.py --config test.yaml hosts list
```

### Performance Optimization

**Use Filtering**:
- "Show only critical problems" (reduces data processing)
- "List hosts matching 'web*'" (targeted queries)

**Leverage Caching**:
- Repeated queries are automatically cached
- Use "refresh" keyword to bypass cache when needed

**Batch Operations**:
- "Acknowledge all warnings on web servers" (single operation vs. multiple)

For detailed setup instructions, see the [Getting Started Guide](getting-started.md).  
For architecture details, see the [Architecture Guide](architecture.md).  
For troubleshooting, see the [Troubleshooting Guide](troubleshooting.md).

## Need More Help?

- **[Getting Started Guide](getting-started.md)** - Complete setup walkthrough
- **[Architecture Guide](architecture.md)** - Technical implementation details  
- **[Advanced Features](ADVANCED_FEATURES.md)** - Streaming, caching, batch operations
- **[Troubleshooting Guide](troubleshooting.md)** - Common issues and solutions

For questions not covered in the documentation, check the [GitHub issues](../../issues) or create a new issue.