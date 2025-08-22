# Service Parameter Management

The Checkmk MCP Server now supports comprehensive service parameter management, allowing you to view default service rules, modify service parameters, and override default settings for specific hosts and services.

## Overview

Service parameter management enables you to:

- **View Default Parameters**: See default thresholds for service types (CPU, memory, disk, network)
- **Override Service Parameters**: Set custom warning/critical thresholds for specific hosts
- **Manage Parameter Rules**: Create, list, and delete parameter rules
- **Discover Rulesets**: Find the appropriate ruleset for any service
- **Natural Language Interface**: Use conversational commands for all operations

## Quick Start

### View Default Parameters

```bash
# CLI commands
checkmk-mcp-server services params defaults cpu
checkmk-mcp-server services params defaults memory
checkmk-mcp-server services params defaults filesystem

# Natural language (interactive mode)
> "show default CPU parameters"
> "what are the default memory thresholds?"
> "show filesystem defaults"
```

### Override Service Parameters

```bash
# CLI commands
checkmk-mcp-server services params set server01 "CPU utilization" --warning 85 --critical 95
checkmk-mcp-server services params set server01 "Filesystem /" --warning 90 --critical 95

# Natural language (interactive mode)  
> "set CPU warning to 85% for server01"
> "override disk critical to 95% for server01"
> "set memory warning to 80% and critical to 90% for database-01"
```

### View Effective Parameters

```bash
# CLI commands
checkmk-mcp-server services params show server01 "CPU utilization"
checkmk-mcp-server services params show server01 "Filesystem /"

# Natural language (interactive mode)
> "what are the CPU parameters for server01?"
> "show disk space thresholds for server01"
> "show all rules affecting server01"
```

## CLI Reference

### Service Parameters Command Group

All service parameter commands are under the `services params` group:

```bash
checkmk-mcp-server services params --help
```

#### Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `defaults [TYPE]` | View default parameters for service type | `defaults cpu` |
| `show HOST SERVICE` | View effective parameters for a service | `show server01 "CPU utilization"` |
| `set HOST SERVICE` | Set/override parameters for a service | `set server01 "CPU utilization" --warning 85` |
| `rules [--ruleset NAME]` | List parameter rules | `rules --ruleset cpu_utilization_linux` |
| `discover [HOST] SERVICE` | Discover appropriate ruleset | `discover server01 "CPU utilization"` |

#### Command Options

**`services params set` options:**
- `--warning FLOAT`: Set warning threshold percentage
- `--critical FLOAT`: Set critical threshold percentage  
- `--comment TEXT`: Add comment to the rule

**`services params rules` options:**
- `--ruleset NAME`: Show rules for specific ruleset

## Natural Language Interface

The natural language interface supports conversational commands for all parameter operations.

### Supported Command Patterns

#### Viewing Parameters
- `"show default CPU parameters"`
- `"what are the memory thresholds for server01?"`
- `"show filesystem parameters for database-01"`
- `"what are the effective parameters for CPU on server01?"`

#### Setting Parameters
- `"set CPU warning to 85% for server01"`
- `"override disk critical to 95% for database-01"`
- `"set memory warning to 80% and critical to 90% for web-server"`
- `"change filesystem thresholds to 85/95 for server01"`

#### Rule Management
- `"show all parameter rules"`
- `"list CPU rules"`
- `"show rules for filesystems ruleset"`
- `"what rules affect server01?"`

#### Discovery
- `"what ruleset controls CPU on server01?"`
- `"find ruleset for memory utilization"`
- `"discover ruleset for Filesystem /var"`

## Understanding Rulesets

Checkmk uses rulesets to manage service parameters. Each service type has associated rulesets:

### Common Service Rulesets

| Service Type | Ruleset Name | Description |
|--------------|--------------|-------------|
| CPU (Linux) | `cpu_utilization_linux` | CPU utilization on Linux/Unix systems |
| CPU (Windows) | `cpu_utilization_simple` | CPU utilization for simple devices |
| Memory (Linux) | `memory_linux` | Memory levels for Linux systems |
| Memory (Windows) | `memory_level_windows` | Memory levels for Windows systems |
| Filesystems | `filesystems` | Filesystem usage and growth monitoring |
| Network | `interfaces` | Network interface utilization |

### Rule Precedence

Rules are applied in order of precedence (highest to lowest):

1. **Host-specific rules with exact service match**
2. **Host-specific rules with service patterns**  
3. **Host tag/label-based rules**
4. **Folder-based rules**
5. **Global default rules**

## Parameter Formats

### CPU Parameters

```python
{
    "levels": (80.0, 90.0),      # Warning, Critical percentages
    "average": 15,                # Averaging period in minutes
    "horizon": 90                 # Time horizon for averaging
}
```

### Memory Parameters

```python
{
    "levels": (80.0, 90.0),      # Warning, Critical percentages
    "average": 3,                 # Averaging period in minutes
    "handle_zero": True           # Handle zero-usage scenarios
}
```

### Filesystem Parameters

```python
{
    "levels": (80.0, 90.0),      # Warning, Critical percentages
    "magic_normsize": 20,         # Normalization reference size (GB)
    "magic": 0.8,                 # Magic factor for large filesystems
    "trend_range": 24             # Trend analysis period (hours)
}
```

## Step-by-Step Workflows

### Override CPU Thresholds for a Host

1. **Discover the service and ruleset:**
   ```bash
   checkmk-mcp-server services params discover server01 "CPU utilization"
   ```

2. **View current parameters:**
   ```bash
   checkmk-mcp-server services params show server01 "CPU utilization"
   ```

3. **Create override rule:**
   ```bash
   checkmk-mcp-server services params set server01 "CPU utilization" \
     --warning 85 --critical 95 \
     --comment "Production server needs higher thresholds"
   ```

4. **Verify new parameters:**
   ```bash
   checkmk-mcp-server services params show server01 "CPU utilization"
   ```

### Bulk Parameter Management

1. **List all available rulesets:**
   ```bash
   checkmk-mcp-server services params rules
   ```

2. **Review existing rules for a ruleset:**
   ```bash
   checkmk-mcp-server services params rules --ruleset cpu_utilization_linux
   ```

3. **Apply consistent thresholds to multiple hosts:**
   ```bash
   # Script to apply same thresholds to multiple hosts
   for host in server01 server02 server03; do
     checkmk-mcp-server services params set $host "CPU utilization" \
       --warning 85 --critical 95 \
       --comment "Production CPU thresholds"
   done
   ```

## Best Practices

### Threshold Setting Guidelines

1. **Start Conservative**: Begin with lower thresholds and adjust based on experience
2. **Warning vs Critical**: Keep warning thresholds 5-10% below critical thresholds
3. **Service-Specific**: Consider the normal operating range for each service type
4. **Environment-Specific**: Use different thresholds for dev/test/prod environments

### Rule Management

1. **Descriptive Comments**: Always include meaningful comments explaining the rule purpose
2. **Specific Targeting**: Use specific host and service conditions to avoid conflicts
3. **Rule Review**: Periodically review and clean up obsolete rules
4. **Documentation**: Document custom thresholds and their reasoning

### Recommended Thresholds by Environment

#### Production Environment
- **CPU**: Warning 80%, Critical 90%
- **Memory**: Warning 80%, Critical 90%  
- **Filesystems**: Warning 80%, Critical 90%

#### Development Environment
- **CPU**: Warning 90%, Critical 95%
- **Memory**: Warning 85%, Critical 92%
- **Filesystems**: Warning 85%, Critical 95%

#### Database Servers
- **CPU**: Warning 80%, Critical 95%
- **Memory**: Warning 85%, Critical 92%
- **Data Filesystems**: Warning 90%, Critical 95%

## Templates and Presets

The agent includes predefined templates for common scenarios. See `examples/service_parameter_templates.yaml` for:

- **Environment Templates**: Production, development, testing
- **Role Templates**: Web servers, database servers, application servers
- **Service Templates**: Conservative, aggressive, and specialized thresholds
- **Quick Overrides**: Common threshold adjustments

## Troubleshooting

### Common Issues

#### False Positive Alerts
**Problem**: Too many unnecessary alerts
**Solution**: 
- Increase warning/critical percentages
- Extend averaging periods for volatile metrics
- Use magic factor for filesystem growth prediction

#### Missed Real Issues  
**Problem**: Thresholds too relaxed, missing actual problems
**Solution**:
- Lower warning/critical percentages
- Reduce averaging periods for quicker detection
- Add trend monitoring for early warning

#### Rule Conflicts
**Problem**: Multiple rules affecting the same service
**Solution**:
- Review rule precedence and conditions
- Use more specific host/service matching  
- Consolidate overlapping rules

### Debugging Commands

```bash
# Check what rules affect a specific service
checkmk-mcp-server services params show server01 "CPU utilization"

# List all rules in a ruleset
checkmk-mcp-server services params rules --ruleset cpu_utilization_linux

# Discover the correct ruleset for a service
checkmk-mcp-server services params discover server01 "CPU utilization"

# View default parameters for comparison
checkmk-mcp-server services params defaults cpu
```

## API Integration

The service parameter functionality integrates with Checkmk's REST API:

### Key Endpoints Used
- `GET /domain-types/ruleset/collections/all` - List available rulesets
- `POST /domain-types/rule/collections/all` - Create parameter rules
- `GET /domain-types/rule/collections/all` - List existing rules
- `DELETE /objects/rule/{rule_id}` - Delete rules

### Authentication
Uses the same authentication as other Checkmk operations (automation user tokens).

### Permissions Required
- `wato.rulesets` - Access to ruleset management
- `wato.edit` - Edit configuration
- `wato.use_git` - Configuration versioning (if enabled)
- `wato.all_folders` - Access to all folders (for global rules)

## Advanced Usage

### Custom Rule Creation

For advanced scenarios, you can create custom rules with complex conditions:

```python
# Example: Create rule for all hosts with specific tags
{
    "ruleset": "cpu_utilization_linux",
    "folder": "/production",
    "value_raw": '{"levels": (85.0, 95.0)}',
    "conditions": {
        "host_tags": {"criticality": "critical", "environment": "production"},
        "service_description": ["CPU utilization"]
    },
    "properties": {
        "description": "Critical production server CPU thresholds"
    }
}
```

### Regex Patterns

Use regex patterns for flexible service matching:

```python
# Match all filesystem services
"service_description": ["~Filesystem.*"]

# Match multiple hosts
"host_name": ["~server.*", "~db.*"]
```

### Integration with Configuration Management

Parameter rules can be managed through configuration management tools:

```yaml
# Ansible example
- name: Set CPU thresholds for web servers
  shell: |
    checkmk-mcp-server services params set {{ inventory_hostname }} "CPU utilization" \
      --warning 85 --critical 95 \
      --comment "Web server CPU thresholds"
  when: "'webservers' in group_names"
```

## Examples Repository

See the `examples/` directory for:

- `service_parameter_templates.yaml` - Comprehensive template library
- `service_examples.yaml` - Basic service operation examples
- Configuration examples for different environments and roles

## Next Steps

1. **Test in Development**: Start by testing parameter overrides in a development environment
2. **Monitor Effectiveness**: Track alert frequency and accuracy after threshold changes  
3. **Document Changes**: Keep records of threshold modifications and their reasons
4. **Automate Common Tasks**: Script repetitive parameter management tasks
5. **Review Regularly**: Periodically review and update thresholds based on changing requirements