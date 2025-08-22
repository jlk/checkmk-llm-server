# Checkmk MCP Server Documentation

## Overview

The Checkmk MCP (Model Context Protocol) Server provides a comprehensive interface for AI assistants to interact with Checkmk monitoring systems. The server has been completely refactored with a **modular architecture** that organizes 37 tools across 8 logical categories.

## Architecture

### New Modular Design (2025-08-20)

The MCP server has been refactored from a monolithic 4,449-line file into a clean, modular architecture:

```
checkmk_mcp_server/mcp_server/
├── server.py                    # Main orchestration (300 lines, 93% reduction)
├── container.py                 # Service dependency injection
├── tools/                       # Tool categories (8 categories, 37 tools)
│   ├── host/                   # Host operations (6 tools)
│   ├── service/                # Service operations (3 tools)  
│   ├── monitoring/             # Health monitoring (3 tools)
│   ├── parameters/             # Parameter management (11 tools)
│   ├── events/                 # Event management (5 tools)
│   ├── metrics/                # Metrics and performance (2 tools)
│   ├── business/               # Business intelligence (2 tools)
│   └── advanced/               # Advanced operations (5 tools)
├── handlers/                   # Core handlers
│   ├── registry.py             # Tool registration
│   ├── protocol.py             # MCP protocol handling
│   └── resource_handlers.py    # Resource management
├── prompts/                    # AI prompt system
│   ├── definitions.py          # Prompt definitions (7 prompts)
│   ├── handlers.py             # Prompt execution
│   └── validators.py           # Prompt validation
├── utils/                      # Utilities
│   ├── serialization.py        # JSON handling
│   └── errors.py               # Error sanitization
└── config/                     # Configuration
    └── tool_definitions.py     # Tool schemas
```

### Benefits of the New Architecture

- **Maintainability**: Each module has a single responsibility (200-500 lines each)
- **Testability**: Each tool category can be tested independently
- **Extensibility**: Easy to add new tools to appropriate categories
- **Code Quality**: 93% reduction in main server file, improved organization
- **Team Development**: Multiple developers can work on different categories
- **Historical Data**: Integrated modular web scraping (4,900-line monolith → 8 focused modules)

## Tool Categories

### 1. Host Tools (6 tools)
Host lifecycle management operations:
- `list_hosts`: List all hosts with filtering options
- `create_host`: Create new hosts
- `get_host`: Get detailed host information
- `update_host`: Update host configuration
- `delete_host`: Remove hosts
- `list_host_services`: List services for a specific host

### 2. Service Tools (3 tools)
Service management and problem handling:
- `list_all_services`: List all services across infrastructure
- `acknowledge_service_problem`: Acknowledge service problems
- `create_service_downtime`: Schedule service maintenance

### 3. Monitoring Tools (3 tools)
Infrastructure health oversight:
- `get_health_dashboard`: Comprehensive infrastructure health
- `get_critical_problems`: Critical problem identification
- `analyze_host_health`: Detailed host health analysis

### 4. Parameter Tools (11 tools)
Comprehensive parameter management with specialized handler support:
- `get_effective_parameters`: Get current parameters affecting a service
- `set_service_parameters`: Modify service-specific parameters
- `validate_service_parameters`: Validate parameter configurations
- `update_parameter_rule`: Update existing parameter rules
- `get_parameter_schema`: Get parameter schema definitions
- `get_parameter_suggestions`: Get intelligent parameter suggestions
- `get_specialized_defaults`: Get handler-specific defaults
- `discover_service_ruleset`: Find rulesets for services
- `list_parameter_handlers`: List available specialized handlers
- `get_service_handler_info`: Get handler information for services
- `validate_with_handler`: Validate parameters using specialized handlers

### 5. Event Tools (5 tools)
Event console operations:
- `list_service_events`: List service-related events
- `list_host_events`: List host-related events
- `get_recent_critical_events`: Get recent critical events
- `acknowledge_event`: Acknowledge events
- `search_events`: Advanced event search

### 6. Metrics Tools (2 tools)
Performance monitoring and historical data:
- `get_service_metrics`: Get current service metrics
- `get_metric_history`: Get historical metric data with modular web scraping architecture

**Enhanced Historical Data Features**:
- **Modular Web Scraping**: Refactored from monolithic 4,900-line scraper to modular system
- **Multiple Extraction Methods**: Graph parsing, table extraction, AJAX endpoint handling
- **Data Source Options**: REST API or web scraping via `data_source` parameter
- **Temperature Zone 0**: Specialized support for temperature monitoring data
- **Flexible Time Ranges**: 1h, 4h, 6h, 12h, 24h, 48h, 7d, 30d, 365d periods
- **Error Recovery**: Robust fallback mechanisms and retry logic

### 7. Business Tools (2 tools)
Business intelligence and reporting:
- `get_business_status_summary`: Business-level status overview
- `get_critical_business_services`: Critical business service monitoring

### 8. Advanced Tools (5 tools)
Advanced operations and utilities:
- `stream_hosts`: Real-time host streaming
- `batch_create_hosts`: Bulk host creation
- `get_server_metrics`: Server performance metrics
- `clear_cache`: Cache management
- `get_system_info`: System information

## Service Container

The new architecture uses dependency injection through a service container that manages:

- **API Client**: Checkmk REST API communication
- **Host Service**: Host management operations
- **Service Service**: Service monitoring operations
- **Status Service**: Status and health monitoring
- **Parameter Service**: Parameter management with specialized handlers
- **Client Service**: API client abstraction
- **Cache Service**: Performance optimization
- **Batch Service**: Bulk operations
- **Streaming Service**: Real-time operations
- **Historical Service**: Historical data access
- **Metrics Service**: Performance metrics
- **Business Service**: Business intelligence
- **Event Service**: Event console operations
- **Config Service**: Configuration management

## Prompt System

The server includes 7 AI prompts organized into 4 categories:

### Health Analysis
- `analyze_infrastructure_health`: Comprehensive infrastructure analysis

### Troubleshooting  
- `diagnose_service_problems`: Service problem diagnosis
- `suggest_performance_improvements`: Performance optimization suggestions

### Optimization
- `optimize_monitoring_configuration`: Monitoring configuration optimization

### Host Configuration
- `adjust_host_check_attempts`: Host check attempt configuration
- `adjust_host_retry_interval`: Host retry interval configuration
- `adjust_host_check_timeout`: Host check timeout configuration

## Usage Examples

### Getting Host Information
```json
{
  "tool": "get_host",
  "arguments": {
    "name": "server01",
    "include_status": true,
    "effective_attributes": true
  }
}
```

### Parameter Management
```json
{
  "tool": "get_effective_parameters",
  "arguments": {
    "host_name": "server01",
    "service_name": "CPU load"
  }
}
```

### Health Monitoring
```json
{
  "tool": "get_health_dashboard",
  "arguments": {
    "include_acknowledged": false,
    "max_problems": 20
  }
}
```

### AI-Powered Analysis
```json
{
  "prompt": "analyze_infrastructure_health",
  "arguments": {
    "focus_area": "performance",
    "include_trends": true
  }
}
```

## Backward Compatibility

The refactoring maintains 100% backward compatibility:

- All existing import paths continue to work
- Server interface remains identical
- Tool functionality preserved exactly
- No breaking changes introduced

```python
# These imports continue to work unchanged
from checkmk_mcp_server.mcp_server import CheckmkMCPServer
from checkmk_mcp_server.mcp_server.server import CheckmkMCPServer
```

## Development Guidelines

### Adding New Tools

1. **Choose Appropriate Category**: Place tools in the most logical category
2. **Follow Patterns**: Use existing tools as templates
3. **Service Integration**: Ensure proper service dependency injection
4. **Comprehensive Testing**: Add tests for the new tool
5. **Documentation**: Update this README with new tool information

### Extending Categories

1. **Create New Package**: Add new category under `tools/`
2. **Implement Interface**: Follow the standard ToolClass pattern
3. **Register Tools**: Add to tool registry configuration
4. **Integration**: Update main server orchestration
5. **Testing**: Add comprehensive test coverage

## Performance

The refactored architecture provides:

- **No Performance Degradation**: Identical performance to monolithic version
- **Better Memory Usage**: More efficient memory allocation
- **Faster Development**: Easier to locate and modify specific functionality
- **Improved Testing**: Faster test execution with isolated components

## Migration Notes

For developers working with the codebase:

1. **Tool Location**: Tools are now organized by category instead of in one file
2. **Service Access**: Services accessed through dependency injection container
3. **Testing**: Test files may need updates for new structure
4. **Documentation**: References to old structure should be updated

## Error Handling

The modular architecture provides consistent error handling:

- **Standardized Errors**: Consistent error format across all tools
- **Request Tracking**: Request ID tracking across all components
- **Graceful Degradation**: Fallback handling for missing services
- **Clear Messages**: User-friendly error messages

## Configuration

Tool definitions and configurations are centralized in:

- `config/tool_definitions.py`: Tool schema definitions
- `config/registry.py`: Tool and service registration
- `prompts/definitions.py`: Prompt definitions

This makes it easy to understand and modify tool configurations without searching through large files.

## Integration Tips for AI Assistants

1. **Use Tool Categories**: Choose tools from appropriate categories for your task
2. **Leverage Prompts**: Use AI prompts for complex analysis tasks
3. **Parameter Management**: Use specialized parameter tools for configuration
4. **Health Monitoring**: Use monitoring tools for infrastructure oversight
5. **Event Handling**: Use event tools for problem management
6. **Business Intelligence**: Use business tools for high-level reporting

The new modular architecture makes it easier to understand capabilities and choose the right tools for specific tasks.