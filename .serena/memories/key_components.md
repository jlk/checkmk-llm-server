# Key Components and Entry Points (Updated 2025-08-22)

## Primary Entry Points

### 1. MCP Server (Main Interface) - REFACTORED
- **File**: `mcp_checkmk_server.py`
- **Purpose**: Primary interface for LLM integration with modular architecture
- **Features**: 37 tools across 8 categories with 93% size reduction
- **Usage**: `python mcp_checkmk_server.py --config config.yaml`
- **Architecture**: Clean orchestration with dependency injection

### 2. MCP-Based CLI
- **File**: `checkmk_cli_mcp.py`
- **Purpose**: Command-line interface using MCP backend
- **Usage**: `python checkmk_cli_mcp.py interactive`

### 3. Direct CLI (Legacy)
- **File**: `checkmk_agent/cli.py`
- **Purpose**: Direct API access without MCP layer
- **Usage**: `python -m checkmk_agent.cli interactive`

## Core Components (Refactored Architecture)

### Modular MCP Server (`checkmk_agent/mcp_server/`)

#### Main Server (`server.py`)
- **Class**: `CheckmkMCPServer`
- **Size**: 457 lines (93% reduction from 4,449 lines)
- **Purpose**: Orchestration-only with dependency injection
- **Features**: Clean tool routing, service container integration

#### Service Container (`container.py`)
- **Class**: `ServiceContainer`
- **Purpose**: Dependency injection managing 14 services
- **Features**: Lifecycle management, service resolution

#### Tool Categories (`tools/`)
- **Host Tools** (6): list_hosts, create_host, get_host, update_host, delete_host, list_host_services
- **Service Tools** (3): list_all_services, acknowledge_service_problem, create_service_downtime
- **Monitoring Tools** (3): get_health_dashboard, get_critical_problems, analyze_host_health
- **Parameter Tools** (11): get_effective_parameters, set_service_parameters, validate_service_parameters, etc.
- **Event Tools** (5): list_service_events, list_host_events, get_recent_critical_events, etc.
- **Metrics Tools** (2): get_service_metrics, get_metric_history
- **Business Tools** (2): get_business_status_summary, get_critical_business_services
- **Advanced Tools** (5): stream_hosts, batch_create_hosts, get_server_metrics, clear_cache, get_system_info

#### Core Handlers (`handlers/`)
- **Tool Registry** (`registry.py`): 15 methods for tool management
- **Protocol Handlers** (`protocol.py`): MCP resource and prompt serving

#### Prompt System (`prompts/`)
- **Definitions** (`definitions.py`): 7 prompts in 4 categories
- **Handlers** (`handlers.py`): Prompt execution with service integration
- **Validators** (`validators.py`): Argument validation

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
  # Option 1: OpenAI
  # openai_api_key: "sk-your-key"
  # default_model: "gpt-4"
  
  # Option 2: Anthropic (recommended)
  anthropic_api_key: "sk-ant-your-key"
  default_model: "claude-3-5-sonnet-20241022"
```

### Environment Variables
- `CHECKMK_SERVER_URL`, `CHECKMK_USERNAME`, `CHECKMK_PASSWORD`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

### Supported Models
- **OpenAI**: gpt-3.5-turbo, gpt-4, gpt-4-turbo
- **Anthropic**: claude-3-haiku-20240307, claude-3-5-sonnet-20241022, claude-3-opus-20240229

## Interactive Mode (`checkmk_agent/interactive/`)
- **Natural language processing** for commands
- **Tab completion** and command history
- **Color themes** and rich formatting
- **Contextual help** system
- **MCP session management**

## Testing Infrastructure (`tests/`)
- **Core tests passing** with backward compatibility
- **25 packages** discovered by setuptools
- **Comprehensive coverage**: unit, integration, performance tests
- **Async testing** support with pytest-asyncio
- **Mock testing** with requests-mock
- **Special focus**: parameter management and MCP tools

## Performance Metrics (Post-Refactoring)
- **Initialization**: 0.000s (excellent)
- **Tool Access**: 0.002ms per access (excellent)  
- **Memory Usage**: 0.14 MB (minimal)
- **File Organization**: 20 focused modules averaging 523 lines each

## Key Validation Scripts
- `validate_parameter_system.py` - Comprehensive parameter system validation
- `test_new_features.py` - New feature testing
- `benchmark_parameter_operations.py` - Performance benchmarking
- `benchmark_refactored_architecture.py` - Architecture performance validation (NEW)

## Backward Compatibility
- **100% maintained** - all existing imports work
- **Compatibility properties** added to server for legacy tests
- **Entry points functional** - all scripts work unchanged
- **Package installation** works with new structure