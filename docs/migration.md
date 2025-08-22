# Migration Guide: Checkmk 2.0 to 2.4

This guide helps migrate from older Checkmk versions (2.0/2.1/2.2/2.3) to Checkmk 2.4+, which is required for the Checkmk MCP Server.

## Why Upgrade to Checkmk 2.4?

Checkmk 2.4 introduces several new features that the LLM Agent leverages:

- **Event Console API**: Access service event history and logs
- **Metrics API**: Retrieve performance graphs and historical data  
- **Business Intelligence API**: Monitor business-level service aggregations
- **Enhanced Acknowledgments**: Set time-based acknowledgment expiry
- **Improved Query Methods**: More efficient host/service listing

## Breaking Changes in Checkmk 2.4

### 1. Host and Service Listing Methods Changed

**Old API (2.0-2.3)**: Used GET requests with query parameters
```bash
GET /domain-types/host/collections/all?query={"op":"=","left":"name","right":"server01"}
```

**New API (2.4+)**: Uses POST requests with query in request body
```bash
POST /domain-types/host/collections/all
Body: {"query": {"op": "=", "left": "name", "right": "server01"}}
```

**Impact**: The Checkmk MCP Server automatically handles this conversion, so no changes needed on your part.

### 2. Query Expression Format

- **Old**: Query expressions passed as JSON strings in URL parameters
- **New**: Query expressions passed as objects in request body
- **Impact**: Transparent to users - the agent handles conversion automatically

### 3. New API Endpoints Available

Checkmk 2.4 adds several new API endpoints that the agent can now use:

- `/domain-types/event_console/` - Event Console operations
- `/domain-types/metric/` - Performance metrics and graphs
- `/domain-types/bi_aggregation/` - Business Intelligence aggregations
- Enhanced acknowledgment options with expiration times

## Pre-Migration Checklist

### 1. Backup Current Environment

**Checkmk Configuration**:
```bash
# Backup Checkmk site
sudo -u mysite omd backup /path/to/backup/
```

**Agent Configuration**:
```bash
cp config.yaml config.yaml.backup
cp -r examples/ examples.backup/
```

### 2. Document Current Setup

Record your current:
- Checkmk version: `omd version`
- Configured hosts and services
- Custom rules and parameters
- Notification configurations
- Agent configuration settings

### 3. Test Environment

If possible, set up a test Checkmk 2.4 environment to validate migration before production.

## Migration Steps

### Step 1: Upgrade Checkmk Server

**Note**: This guide covers agent migration only. For Checkmk server upgrade procedures, consult the [official Checkmk documentation](https://docs.checkmk.com/latest/en/update.html).

After upgrading Checkmk to 2.4+:

1. **Verify API is enabled**:
```bash
curl -k https://your-checkmk-server/check_mk/api/1.0/version
```

2. **Test new endpoints**:
```bash
# Event Console API
curl -k -u "user:password" \
  https://your-server/check_mk/api/1.0/domain-types/event_console/collections/events

# Metrics API  
curl -k -u "user:password" \
  https://your-server/check_mk/api/1.0/domain-types/metric/collections/all
```

### Step 2: Update the Checkmk MCP Server

1. **Backup current agent**:
```bash
cd checkmk_llm_agent
git stash  # Save any local changes
```

2. **Pull latest version**:
```bash
git pull origin main
```

3. **Update dependencies**:
```bash
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

### Step 3: Test Agent Connection

1. **Test basic connectivity**:
```bash
python -c "
from checkmk_mcp_server.config import load_config
from checkmk_mcp_server.api_client import CheckmkAPIClient

config = load_config('config.yaml')
client = CheckmkAPIClient(config)
version = client.get_version()
print(f'Connected to Checkmk {version}')
"
```

2. **Test new features**:
```bash
# Test Event Console
python checkmk_cli_mcp.py services events server01 "CPU utilization"

# Test Metrics API
python checkmk_cli_mcp.py services metrics server01 "CPU utilization" --hours 24

# Test Business Intelligence
python checkmk_cli_mcp.py bi status
```

### Step 4: Update AI Client Configurations

If you're using Claude Desktop or other MCP clients, no configuration changes are needed - the existing setup will automatically use the new features.

### Step 5: Validate All Features

Run through your typical monitoring workflows to ensure everything works:

1. **Host Management**:
```bash
python checkmk_cli_mcp.py hosts list --limit 5
python checkmk_cli_mcp.py hosts create test-host --ip 192.168.1.100 --folder /test
python checkmk_cli_mcp.py hosts delete test-host
```

2. **Service Operations**:
```bash
python checkmk_cli_mcp.py services list server01
python checkmk_cli_mcp.py services acknowledge server01 "CPU load" --comment "Test ack"
```

3. **New Features**:
```bash
python checkmk_cli_mcp.py services events server01 "CPU utilization"
python checkmk_cli_mcp.py services metrics server01 "Memory" --hours 24
python checkmk_cli_mcp.py bi status
```

## New Features Available After Migration

### Event Console Integration

**View service event history**:
> "Show me the event history for CPU utilization on server01"

**Search for specific events**:
> "Find all events related to disk space issues in the last 24 hours"

### Performance Metrics API

**Get historical metrics**:
> "Show me CPU performance for server01 over the last week"

**Analyze trends**:
> "What's the memory usage trend for database servers this month?"

### Business Intelligence Monitoring

**Business service status**:
> "What's the current status of our business services?"

**Critical business impact**:
> "Which business services are currently failing and what's the impact?"

### Enhanced Acknowledgments

**Time-based acknowledgments**:
> "Acknowledge CPU load on server01 for 4 hours with comment 'investigating batch job'"

**Acknowledgment expiration**:
```bash
python checkmk_cli_mcp.py services acknowledge server01 "CPU load" \
  --comment "Maintenance window" \
  --expire "2024-12-31T23:59:59"
```

## Troubleshooting Migration Issues

### API Endpoint Not Found

**Error**: `HTTP 404` when trying to use new features

**Cause**: Checkmk version still < 2.4 or API endpoint not enabled

**Solution**: 
- Verify Checkmk version: `omd version`
- Check API documentation in Checkmk Web UI
- Ensure all required packages are installed

### Authentication Issues

**Error**: `HTTP 401` or `HTTP 403` after migration

**Cause**: User permissions may have changed

**Solution**:
- Verify automation user still exists
- Check user permissions for new API endpoints
- Recreate automation user if necessary

### Performance Issues

**Symptom**: Slower response times after migration

**Cause**: New API methods may have different performance characteristics

**Solution**:
```yaml
# Adjust performance settings
advanced_features:
  caching:
    max_size: 5000      # Increase cache
    default_ttl: 600    # Longer cache TTL
  
  batch_processing:
    max_concurrent: 5   # Reduce if needed
    rate_limit: 25      # Adjust rate limiting
```

### Feature Detection Issues

**Error**: Agent tries to use features not available in your Checkmk version

**Solution**: The agent includes automatic feature detection, but you can manually disable features:

```yaml
# Disable features not available in your version
features:
  event_console: false
  metrics_api: false
  business_intelligence: false
```

## Rollback Procedure

If you need to revert to Checkmk 2.0 compatibility:

### Step 1: Use Legacy Agent Branch

```bash
# Switch to legacy branch (if available)
git checkout legacy-2.0-support

# Or revert to previous version
git log --oneline  # Find previous commit
git checkout <commit-hash>
```

### Step 2: Restore Configuration

```bash
cp config.yaml.backup config.yaml
```

### Step 3: Downgrade Dependencies

```bash
pip install -r requirements-legacy.txt
```

### Step 4: Test Legacy Functionality

```bash
# Test basic operations work
python -m checkmk_mcp_server.cli hosts list
python -m checkmk_mcp_server.cli status overview
```

## Reporting Migration Issues

If you encounter issues during migration:

1. **Check existing issues**: [GitHub Issues](../../issues)

2. **Create a detailed issue** including:
   - Source Checkmk version
   - Target Checkmk version  
   - Specific error messages
   - Steps to reproduce
   - Migration step where issue occurred

3. **Include diagnostic information**:
```bash
# Checkmk version
curl -k https://your-server/check_mk/api/1.0/version

# Agent version
git rev-parse HEAD

# Configuration (sanitized)
cat config.yaml | sed 's/password:.*/password: [REDACTED]/'
```

## Post-Migration Best Practices

### 1. Update Monitoring Procedures

Take advantage of new Checkmk 2.4 features:
- Use Event Console for root cause analysis
- Leverage Business Intelligence for high-level monitoring
- Set up time-based acknowledgments for planned maintenance

### 2. Performance Optimization

```yaml
# Optimize for Checkmk 2.4
advanced_features:
  caching:
    max_size: 10000      # Larger cache for better performance
    default_ttl: 900     # 15-minute cache TTL
  
  streaming:
    default_batch_size: 200  # Larger batches for 2.4 efficiency
  
  metrics:
    retention_hours: 48  # Longer metrics retention
```

### 3. User Training

Update your team on new capabilities:
- Natural language queries for event investigation
- Business service monitoring workflows
- Enhanced acknowledgment procedures

### 4. Documentation Updates

Update your internal documentation to reflect:
- New natural language capabilities
- Business Intelligence monitoring procedures
- Enhanced event investigation workflows

The migration to Checkmk 2.4 unlocks significant new capabilities for your monitoring workflows. The Checkmk MCP Server is designed to make the most of these new features while maintaining backward compatibility where possible.

## Related Documentation

- **[Getting Started Guide](getting-started.md)** - Post-migration setup verification
- **[Usage Examples](USAGE_EXAMPLES.md)** - New feature examples and workflows
- **[Troubleshooting](troubleshooting.md)** - Migration-specific troubleshooting
- **[Advanced Features](ADVANCED_FEATURES.md)** - New capabilities available in 2.4+