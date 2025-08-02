# Codebase Structure

## Root Directory
- `mcp_checkmk_server.py` - **Main MCP server entry point** (40 tools)
- `checkmk_cli_mcp.py` - MCP-based CLI entry point
- `requirements.txt` - All dependencies including MCP SDK
- `setup.py` - Package configuration
- `pytest.ini` - Test configuration

## Core Package: `checkmk_agent/`

### API Layer
- `api_client.py` - **Main Checkmk REST API client** (CheckmkClient class)
- `async_api_client.py` - Async wrapper for API operations
- `config.py` - Configuration management (YAML/TOML/ENV support)

### CLI Interfaces
- `cli.py` - **Direct CLI interface** (legacy)
- `cli_mcp.py` - **MCP-based CLI interface** (recommended)

### MCP Integration
- `mcp_server/server.py` - **Unified MCP server** with 40 tools
- `mcp_client.py` - MCP client implementation

### Service Layer (`services/`)
- `base.py` - Base service class with error handling
- `host_service.py` - Host management operations
- `status_service.py` - Health monitoring and dashboards
- `service_service.py` - Service operations and discovery
- `parameter_service.py` - **Parameter management with specialized handlers**
- `streaming.py` - Memory-efficient large dataset processing
- `cache.py` - LRU caching with TTL
- `batch.py` - Concurrent bulk operations
- `metrics.py` - Performance monitoring
- `recovery.py` - Circuit breakers and retry policies

### Specialized Handlers (`services/handlers/`)
- `base.py` - Base handler class and registry
- `temperature.py` - Temperature monitoring handler
- `database.py` - Database service handler
- `network.py` - Network service handler
- `custom_checks.py` - Custom check handler

### Interactive Mode (`interactive/`)
- `mcp_session.py` - Interactive MCP session management
- `command_parser.py` - Natural language command parsing
- `ui_manager.py` - Rich UI formatting
- `color_manager.py` - Color theme management
- `tab_completer.py` - Tab completion
- `help_system.py` - Contextual help

### Data Models (`services/models/`)
- `hosts.py` - Host-related data models
- `services.py` - Service-related data models
- `status.py` - Status and monitoring data models

## Testing (`tests/`)
- Comprehensive test suite with 100% pass rate
- Integration, unit, performance, and streaming tests
- Special focus on parameter management and MCP tools

## Documentation (`docs/`)
- Complete API documentation and usage examples
- Architecture guides and implementation summaries
- Conversation history for project decisions