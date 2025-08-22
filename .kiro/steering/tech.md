# Technology Stack

## Core Technologies

### Python Environment
- **Python Version**: 3.8+ (tested up to 3.12)
- **Package Manager**: pip with requirements.txt
- **Virtual Environment**: Standard venv recommended

### Key Dependencies
- **API Client**: `requests>=2.31.0` for HTTP operations
- **Data Validation**: `pydantic>=2.0.0` for type safety and validation
- **CLI Framework**: `click>=8.1.0` for command-line interface
- **Configuration**: `python-dotenv>=1.0.0`, `pyyaml>=6.0.0`, `tomli>=2.0.0`
- **MCP Integration**: `mcp>=1.0.0` (Model Context Protocol SDK)
- **Web Scraping**: `beautifulsoup4>=4.12.0`, `lxml>=4.9.0`, `html5lib>=1.1`

### LLM Integration
- **OpenAI**: `openai>=1.0.0`
- **Anthropic**: `anthropic>=0.18.0`
- **Optional**: `httpx>=0.24.0` for async HTTP operations

### Development Tools
- **Testing**: `pytest>=7.4.0`, `pytest-asyncio>=0.21.0`, `pytest-cov>=4.1.0`
- **Code Quality**: `black>=23.0.0`, `flake8>=6.0.0`, `mypy>=1.5.0`
- **Mocking**: `requests-mock>=1.11.0`
- **CLI Enhancement**: `rich>=13.0.0`, `typer>=0.9.0`

## Architecture Patterns

### Service Layer Architecture
- **Base Service**: All services inherit from `BaseService` class
- **Async Operations**: Extensive use of `async/await` patterns
- **Type Safety**: Pydantic models for all data structures
- **Error Handling**: Centralized error handling with custom exceptions

### Design Patterns
- **Factory Pattern**: Service creation and dependency injection
- **Mixin Pattern**: Streaming, caching, metrics, recovery capabilities
- **Repository Pattern**: Data access abstraction
- **Command Pattern**: CLI command structure

### Performance Features
- **Streaming**: Memory-efficient processing with `StreamingMixin`
- **Caching**: LRU caching with TTL via `CachingService`
- **Batch Operations**: Concurrent processing with `BatchProcessor`
- **Circuit Breaker**: Fault tolerance with `RecoveryMixin`

## Common Commands

### Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=checkmk_mcp_server

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests
pytest -m asyncio       # Async tests
pytest tests/test_*.py  # Specific test files
```

### Code Quality
```bash
# Format code
black checkmk_mcp_server/

# Lint code
flake8 checkmk_mcp_server/

# Type checking
mypy checkmk_mcp_server/

# Run all quality checks
black checkmk_mcp_server/ && flake8 checkmk_mcp_server/ && mypy checkmk_mcp_server/
```

### Running the Application
```bash
# MCP Server (primary interface)
python mcp_checkmk_server.py --config config.yaml

# MCP-based CLI
python checkmk_cli_mcp.py interactive
python checkmk_cli_mcp.py hosts list

# Direct API CLI (legacy)
python -m checkmk_mcp_server.cli interactive
python -m checkmk_mcp_server.cli hosts list

# Module-based CLI
python -m checkmk_mcp_server.cli_mcp interactive
```

### Configuration
```bash
# Copy example configuration
cp config.yaml.example config.yaml
cp examples/configs/development.yaml config.yaml

# Environment variables
cp .env.example .env
```

## Build System

### Package Management
- **Setup**: `setup.py` with setuptools
- **Entry Points**: Console scripts for CLI access
- **Dependencies**: Managed via `requirements.txt`
- **Optional Dependencies**: Extras for development, CLI enhancements

### Testing Configuration
- **pytest.ini**: Centralized test configuration
- **Async Support**: `asyncio_mode = auto`
- **Markers**: Custom test markers for categorization
- **Coverage**: Integrated coverage reporting