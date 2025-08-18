# Project Structure

## Root Directory Organization

### Entry Points
- `mcp_checkmk_server.py` - **Primary MCP server entry point** (47 tools)
- `checkmk_cli_mcp.py` - MCP-based CLI client
- `checkmk_scraper.py` - Web scraping utilities
- `mcp_checkmk_server.py` - Standalone MCP server

### Configuration Files
- `config.yaml` - Main application configuration
- `config.yaml.example` - Configuration template
- `.env` - Environment variables (not committed)
- `.env.example` - Environment template
- `requirements.txt` - Python dependencies
- `setup.py` - Package installation configuration
- `pytest.ini` - Test configuration

### Documentation
- `README.md` - Comprehensive project documentation
- `docs/` - Extended documentation and guides
- `examples/` - Configuration examples and usage samples
- `specs/` - Feature specifications and implementation plans

## Core Package Structure (`checkmk_agent/`)

### Main Modules
```
checkmk_agent/
├── __init__.py              # Package initialization
├── api_client.py            # Synchronous CheckMK REST API client
├── async_api_client.py      # Asynchronous API wrapper
├── config.py                # Configuration management
├── cli.py                   # Direct CLI interface (legacy)
├── cli_mcp.py              # MCP-based CLI interface
├── common.py               # Shared utilities
├── host_operations.py      # Host management operations
├── service_operations.py   # Service management operations
├── service_parameters.py   # Parameter management
├── service_status.py       # Status monitoring
├── llm_client.py          # LLM integration
├── mcp_client.py          # MCP client implementation
└── logging_utils.py       # Logging configuration
```

### Service Layer (`services/`)
**Architecture**: Service-oriented with base classes and mixins
```
services/
├── __init__.py             # Service exports
├── base.py                 # BaseService with error handling
├── host_service.py         # Host operations service
├── service_service.py      # Service operations service
├── status_service.py       # Status monitoring service
├── parameter_service.py    # Parameter management service
├── event_service.py        # Event console service
├── metrics_service.py      # Metrics and performance service
├── bi_service.py          # Business Intelligence service
├── historical_service.py   # Historical data service
├── streaming.py           # Streaming capabilities (mixin)
├── cache.py               # Caching layer (mixin)
├── batch.py               # Batch operations (mixin)
├── metrics.py             # Performance monitoring (mixin)
├── recovery.py            # Error recovery (mixin)
└── handlers/              # Specialized parameter handlers
    ├── base.py            # Base parameter handler
    ├── temperature.py     # Temperature monitoring
    ├── database.py        # Database monitoring
    ├── network.py         # Network service monitoring
    ├── custom_checks.py   # Custom check parameters
    └── registry.py        # Handler registration
```

### MCP Integration (`mcp_server/`)
```
mcp_server/
├── __init__.py            # MCP server exports
├── server.py              # Unified MCP server (47 tools)
└── README.md              # MCP server documentation
```

### Data Models (`services/models/`)
**Pattern**: Pydantic models for type safety
```
models/
├── __init__.py            # Model exports
├── hosts.py               # Host-related models
├── services.py            # Service-related models
├── status.py              # Status monitoring models
└── parameters.py          # Parameter management models
```

### Interactive Interface (`interactive/`)
```
interactive/
├── __init__.py            # Interactive exports
├── mcp_session.py         # MCP session management
├── ui_manager.py          # User interface management
├── command_parser.py      # Command parsing
├── tab_completer.py       # Tab completion
├── readline_handler.py    # Readline integration
├── help_system.py         # Help and documentation
└── color_manager.py       # Color theme management
```

### Utilities (`utils/`, `middleware/`)
```
utils/
├── __init__.py            # Utility exports
└── request_context.py     # Request ID tracking

middleware/
├── __init__.py            # Middleware exports
└── request_tracking.py    # Request tracking middleware

formatters/
├── __init__.py            # Formatter exports
├── base_formatter.py      # Base formatting
└── cli_formatter.py       # CLI output formatting
```

## Testing Structure (`tests/`)

### Test Organization
```
tests/
├── __init__.py            # Test package
├── conftest.py            # Pytest configuration and fixtures
├── test_api_client.py     # API client tests
├── test_services.py       # Service layer tests
├── test_mcp_*.py         # MCP integration tests
├── test_streaming.py      # Streaming functionality tests
├── test_cache.py         # Caching tests
├── test_batch.py         # Batch operations tests
├── test_integration.py    # End-to-end integration tests
└── test_performance.py    # Performance benchmarks
```

### Test Categories (pytest markers)
- `unit` - Fast unit tests
- `integration` - Integration tests requiring external services
- `asyncio` - Async operation tests
- `slow` - Long-running tests
- `api` - Tests that interact with APIs

## Configuration Structure (`examples/configs/`)

### Environment-Specific Configs
```
examples/configs/
├── development.yaml       # Development environment
├── production.yaml        # Production environment
├── testing.yaml          # Testing environment
└── ui-themes.yaml        # UI customization themes
```

## Documentation Structure (`docs/`)

### Documentation Categories
```
docs/
├── ADVANCED_FEATURES.md   # Advanced functionality guide
├── USAGE_EXAMPLES.md      # Usage examples and tutorials
├── PARAMETER_MANAGEMENT_GUIDE.md  # Parameter management
├── SERVICE_PARAMETERS_ARCHITECTURE.md  # Architecture details
├── PROJECT_COMPLETION.md  # Project status and completion
└── conversations/         # Development conversation logs
```

## Naming Conventions

### Files and Modules
- **Snake case**: `service_operations.py`, `mcp_client.py`
- **Descriptive names**: Clear indication of functionality
- **Consistent suffixes**: `_service.py`, `_client.py`, `_operations.py`

### Classes
- **PascalCase**: `BaseService`, `HostService`, `AsyncCheckmkClient`
- **Descriptive names**: `TemperatureParameterHandler`, `StreamingHostService`
- **Pattern suffixes**: `Service`, `Client`, `Handler`, `Mixin`

### Functions and Methods
- **Snake case**: `list_hosts()`, `get_service_status()`
- **Async prefix**: `async def` for all async operations
- **Action verbs**: `create_`, `update_`, `delete_`, `list_`, `get_`

### Constants and Configuration
- **UPPER_SNAKE_CASE**: `DEFAULT_TIMEOUT`, `MAX_RETRIES`
- **Environment variables**: `CHECKMK_SERVER_URL`, `OPENAI_API_KEY`