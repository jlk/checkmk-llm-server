# Code Style and Conventions

## Python Standards
- **Python 3.8+** minimum requirement
- **Type hints** extensively used throughout codebase
- **Pydantic v2** for all data models and validation
- **Async/await** patterns for performance-critical operations

## Code Style
- **Black** formatting (line length 88 characters)
- **flake8** linting for code quality
- **mypy** for static type checking
- **pytest** for all testing with async support

## Naming Conventions
- **Classes**: PascalCase (e.g., `CheckmkClient`, `ParameterService`)
- **Functions/Methods**: snake_case (e.g., `list_hosts`, `get_service_status`)
- **Variables**: snake_case (e.g., `service_name`, `host_data`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `STATUS_COLUMNS`, `API_VERSION`)
- **Private methods**: Leading underscore (e.g., `_make_request`, `_validate_data`)

## Documentation Standards
- **Docstrings**: Google style for all public methods and classes
- **Type annotations**: Required for all function parameters and return values
- **Error handling**: Comprehensive with specific exception types
- **Logging**: Structured logging with appropriate levels

## Architecture Patterns
- **Service Layer Pattern**: Business logic separated from API client
- **Repository Pattern**: Data access abstraction
- **Factory Pattern**: For creating specialized handlers
- **Mixin Pattern**: For shared functionality (streaming, caching, etc.)
- **Strategy Pattern**: For different parameter handlers

## Error Handling
- **Custom exceptions**: Specific error types (e.g., `CheckmkAPIError`)
- **Graceful degradation**: Fallback mechanisms for failed operations
- **Retry logic**: Exponential backoff with circuit breakers
- **Validation**: Pydantic models for all API data

## Testing Conventions
- **Test organization**: Separate files for each major component
- **Markers**: `@pytest.mark.integration`, `@pytest.mark.slow`, etc.
- **Async testing**: `pytest-asyncio` for async operations
- **Mock usage**: `requests-mock` for API testing
- **Coverage**: Aim for high test coverage with meaningful tests

## Configuration Management
- **Multiple formats**: YAML, TOML, JSON, and environment variables
- **Hierarchical loading**: Environment-specific overrides
- **Validation**: Pydantic models for configuration validation
- **Security**: Environment variables for sensitive data