# Key Components and Entry Points

## Primary Entry Points

### 1. MCP Server (Main Interface)
- **File**: `mcp_checkmk_server.py`
- **Purpose**: Primary interface for LLM integration
- **Features**: 40 tools for comprehensive monitoring operations
- **Usage**: `python mcp_checkmk_server.py --config config.yaml`

### 2. MCP-Based CLI
- **File**: `checkmk_cli_mcp.py`
- **Purpose**: Command-line interface using MCP backend
- **Usage**: `python checkmk_cli_mcp.py interactive`

### 3. Direct CLI (Legacy)
- **File**: `checkmk_agent/cli.py`
- **Purpose**: Direct API access without MCP layer
- **Usage**: `python -m checkmk_agent.cli interactive`

## Core Components

### API Client (`checkmk_agent/api_client.py`)
- **Class**: `CheckmkClient`
- **Purpose**: Comprehensive Checkmk REST API integration
- **Features**: Host/service management, monitoring, parameters, events, metrics
- **Key Methods**: `list_hosts()`, `list_all_services()`, `get_service_status()`

### Service Layer (`checkmk_agent/services/`)
- **Parameter Service**: Universal parameter management with specialized handlers
- **Status Service**: Health monitoring and dashboard functionality  
- **Host Service**: Host lifecycle management
- **Streaming Service**: Memory-efficient large dataset processing
- **Cache Service**: LRU caching with TTL for performance

### MCP Server (`checkmk_agent/mcp_server/server.py`)
- **Class**: `CheckmkMCPServer`
- **Purpose**: Unified MCP server exposing all functionality
- **Tools**: 40 comprehensive monitoring tools
- **Features**: JSON serialization, error handling, streaming support

### Specialized Parameter Handlers (`checkmk_agent/services/handlers/`)
- **Temperature Handler**: CPU, GPU, ambient, storage temperature monitoring
- **Database Handler**: Oracle, MySQL, PostgreSQL, MongoDB, Redis parameters
- **Network Handler**: HTTP/HTTPS, TCP/UDP, DNS, SSH monitoring
- **Custom Checks Handler**: MRPE, local checks, Nagios plugins

## Configuration Management

### Primary Config (`config.yaml`)
```yaml
checkmk:
  server_url: "https://your-checkmk-server.com"
  username: "automation_user"
  password: "your_secure_password"
  site: "mysite"

llm:
  openai_api_key: "sk-your-key"
  default_model: "gpt-3.5-turbo"
```

### Environment Variables
- `CHECKMK_SERVER_URL`, `CHECKMK_USERNAME`, `CHECKMK_PASSWORD`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

## Interactive Mode (`checkmk_agent/interactive/`)
- **Natural language processing** for commands
- **Tab completion** and command history
- **Color themes** and rich formatting
- **Contextual help** system
- **MCP session management**

## Testing Infrastructure (`tests/`)
- **100% pass rate** maintained
- **Comprehensive coverage**: unit, integration, performance tests
- **Async testing** support with pytest-asyncio
- **Mock testing** with requests-mock
- **Special focus**: parameter management and MCP tools

## Key Validation Scripts
- `validate_parameter_system.py` - Comprehensive parameter system validation
- `test_new_features.py` - New feature testing
- `benchmark_parameter_operations.py` - Performance benchmarking