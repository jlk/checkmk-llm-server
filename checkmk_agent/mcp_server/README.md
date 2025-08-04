# Checkmk MCP Server Documentation

## Overview

The Checkmk MCP (Model Context Protocol) Server provides a comprehensive interface for AI assistants to interact with Checkmk monitoring systems. This server exposes 40+ tools covering all aspects of Checkmk operations.

## Key Concepts

### Current Host Operations

The MCP server provides host management capabilities through the underlying Checkmk REST API. Current operations focus on basic host configuration and status monitoring.

## Host Operations

### Getting Host Details

The `get_host` tool retrieves basic host information:

```json
{
  "name": "get_host",
  "arguments": {
    "name": "server01",
    "include_status": true
  }
}
```

This returns:
- Basic host attributes (IP address, alias, etc.)
- Monitoring status (if include_status=true)
- Directly configured host attributes
- Folder location and basic configuration

### Current Limitations

**Note**: The `effective_attributes` parameter is not currently supported in the MCP server implementation. While the underlying API client supports this feature, it has not been exposed through the MCP tools yet.

### Example: Getting Host Configuration

To get basic host information:

```json
{
  "tool": "get_host",
  "arguments": {
    "name": "webserver01",
    "include_status": true
  }
}
```

## Service Parameter Management

### Understanding Service Parameters

Service parameters control how services are monitored, including:
- Warning and critical thresholds
- Check intervals
- Notification settings
- Service-specific configurations

### Getting Effective Parameters

Use the `get_effective_parameters` tool to retrieve all parameters affecting a service:

```json
{
  "tool": "get_effective_parameters",
  "arguments": {
    "host_name": "server01",
    "service_name": "CPU load"
  }
}
```

This returns:
- Parameters directly set for this service
- Parameters inherited from host rules
- Parameters inherited from folder rules
- Global default parameters

### Parameter Inheritance Hierarchy

Parameters are applied in this order (later overrides earlier):
1. Global defaults
2. Folder rules (from parent to child)
3. Host-specific rules
4. Service-specific rules

## Best Practices

### 1. Host Configuration Analysis

When troubleshooting or analyzing a host, use the available tools to gather information:

```json
{
  "tool": "get_host",
  "arguments": {
    "name": "problematic-host",
    "include_status": true
  }
}
```

### 2. Understanding Service Parameters

When analyzing service parameters, use `get_effective_parameters` to understand current parameter configuration:

```json
{
  "tool": "get_effective_parameters",
  "arguments": {
    "host_name": "db-server",
    "service_name": "MySQL Connections"
  }
}
```

### 3. Modifying Parameters

To modify parameters:
- Use `set_service_parameters` for service-specific changes
- Use rule management tools for broader changes affecting multiple hosts/services
- Always verify changes by re-checking parameters after modifications

## Common Use Cases

### 1. Troubleshooting Service Alerts

When a service is alerting, check its effective parameters:

```json
{
  "tool": "get_effective_parameters",
  "arguments": {
    "host_name": "app-server",
    "service_name": "Memory"
  }
}
```

### 2. Analyzing Host Configuration

For host analysis with current capabilities:

```json
{
  "tool": "get_host",
  "arguments": {
    "name": "critical-server",
    "include_status": true
  }
}
```

### 3. Bulk Parameter Updates

To update parameters for multiple hosts, create a rule:

```json
{
  "tool": "create_rule",
  "arguments": {
    "ruleset": "checkparameters:memory",
    "folder": "/production/web",
    "value_raw": {
      "levels": [80.0, 90.0]
    },
    "properties": {
      "description": "Memory thresholds for web servers"
    }
  }
}
```

## Tool Reference

### Host Management Tools

- `list_hosts`: List all hosts with basic configuration
- `get_host`: Get detailed information about a specific host (basic attributes only)
- `list_host_services`: Shows services with their current monitoring state

### Parameter Management Tools

- `get_effective_parameters`: Get current parameters affecting a service
- `set_service_parameters`: Modify service-specific parameters
- `get_ruleset_info`: Understand available parameter rulesets
- `discover_rulesets`: Find rulesets affecting specific services

## Integration Tips for AI Assistants

1. **Use available host tools** to gather basic host configuration and status
2. **Check current parameters** when troubleshooting monitoring behavior
3. **Document parameter sources** when making changes
4. **Use rule management tools** for changes affecting multiple hosts
5. **Verify changes** by re-checking parameters after modifications

## Current Implementation Status

### Working Features
- Basic host management (create, get, update, delete, list)
- Service parameter management through `get_effective_parameters` and `set_service_parameters`
- Service status monitoring and problem management
- Rule management for configuration
- Comprehensive service operations

### Planned Enhancements
- **Effective Attributes Support**: The `effective_attributes` parameter for host operations is planned for future implementation
- **Enhanced Parameter Inheritance**: More detailed parameter source tracking
- **Advanced Configuration Analysis**: Tools for understanding complete inherited configuration

### Error Handling

When operations fail, common causes include:
- The host or service doesn't exist
- Insufficient permissions for the operation
- Invalid parameter values or configuration
- Network connectivity issues

Always handle these cases gracefully and provide clear error messages to users.