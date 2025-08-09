# Technology Stack - Checkmk LLM Agent

## Core Technologies

### Programming Language
- **Python 3.8+**: Primary implementation language
  - Type hints throughout codebase
  - Async/await support for concurrent operations
  - Context variables for thread-safe request tracking
  - Dataclasses for clean data structures

### Key Python Libraries

#### API & Web
- **requests 2.31+**: Synchronous HTTP client for Checkmk API
- **httpx 0.24+**: Modern async HTTP client with HTTP/2 support
- **aiohttp 3.8+**: Async HTTP client/server framework
- **urllib3**: HTTP connection pooling

#### Data Validation & Serialization
- **pydantic 2.0+**: Data validation using Python type annotations
  - Request/response models
  - Configuration management
  - Schema validation
- **python-dateutil**: Date/time parsing and manipulation
- **pyyaml 6.0+**: YAML configuration file support
- **python-json-logger**: Structured JSON logging

#### LLM Integration
- **openai 1.0+**: OpenAI GPT-4 integration
- **anthropic 0.18+**: Claude API integration
- **langchain 0.1+**: LLM framework for chaining operations
- **tiktoken**: Token counting for LLM context management

#### MCP (Model Context Protocol)
- **mcp 1.12.0**: MCP SDK for tool exposure
  - Server implementation
  - Tool registration
  - Async operation support
- **fastmcp**: Alternative MCP implementation (optional)

#### CLI & User Interface
- **typer 0.9+**: Modern CLI framework
  - Command groups
  - Auto-completion
  - Rich help text
- **rich 13.0+**: Terminal formatting and colors
  - Tables and panels
  - Progress bars
  - Syntax highlighting
- **click 8.1+**: Command line interface creation kit
- **prompt_toolkit 3.0+**: Interactive command line applications

#### Testing
- **pytest 7.4+**: Testing framework
  - Fixtures for test setup
  - Parametrized tests
  - Async test support
- **pytest-asyncio 0.21+**: Async test execution
- **pytest-cov**: Code coverage reporting
- **pytest-mock**: Mock object framework
- **responses**: Mock HTTP responses for testing

#### Development Tools
- **black**: Code formatter
- **flake8**: Linting tool
- **mypy**: Static type checker
- **isort**: Import statement organizer
- **pre-commit**: Git hook framework

## External Dependencies

### Checkmk REST API
- **Version**: v2.4+ required
- **Protocol**: REST over HTTPS
- **Authentication**: Bearer token or session-based
- **OpenAPI Spec**: 21,000+ lines defining all endpoints

### LLM Providers
- **OpenAI API** (optional): GPT-4, GPT-4-turbo
- **Anthropic API**: Claude 4 Opus, Sonnet, Haiku
- **Ollama** (optional): Local LLM hosting
- **Azure OpenAI** (optional): Enterprise deployment

## Development Setup

### Environment Setup
```bash
# Clone repository
git clone https://github.com/your-org/checkmk_llm_agent.git
cd checkmk_llm_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Configuration Files

#### `.env` (Environment Variables)
```bash
# Checkmk Configuration
CHECKMK_URL=https://monitoring.example.com
CHECKMK_USERNAME=automation
CHECKMK_PASSWORD=secure_token
CHECKMK_SITE=production

# LLM Configuration
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=gpt-4-turbo-preview
LLM_TEMPERATURE=0.7

# MCP Configuration
MCP_SERVER_PORT=3000
MCP_SERVER_HOST=localhost

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

#### `config.yaml` (Application Configuration)
```yaml
checkmk:
  api_version: "1.0"
  timeout: 30
  retry_attempts: 3
  rate_limit: 100  # requests per minute

llm:
  provider: "openai"  # or "anthropic", "ollama"
  model: "gpt-4"
  max_tokens: 4000
  temperature: 0.7

cache:
  enabled: true
  ttl: 300  # seconds
  max_size: 10000

monitoring:
  enable_metrics: true
  metrics_port: 9090
```

### Project Structure
```
checkmk_llm_agent/
├── .env.example              # Environment template
├── .gitignore               # Git ignore rules
├── .pre-commit-config.yaml  # Pre-commit hooks
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
├── setup.py                 # Package setup
├── pyproject.toml          # Modern Python packaging
├── Makefile                # Build automation
├── Dockerfile              # Container definition
├── docker-compose.yml      # Local development stack
│
├── checkmk_agent/          # Main package
│   ├── __init__.py
│   ├── __main__.py        # Entry point
│   ├── api_client.py      # API communication
│   ├── cli.py             # CLI interface
│   ├── config.py          # Configuration management
│   ├── context_vars.py    # Request ID tracking
│   ├── logging_utils.py   # Logging configuration
│   │
│   ├── services/          # Service layer
│   │   ├── __init__.py
│   │   ├── base.py        # Base service class
│   │   └── ...            # Service implementations
│   │
│   ├── handlers/          # Parameter handlers
│   │   ├── __init__.py
│   │   ├── base.py        # Base handler
│   │   └── ...            # Handler implementations
│   │
│   └── mcp_server/        # MCP integration
│       ├── __init__.py
│       └── server.py      # MCP server implementation
│
├── tests/                 # Test suite
│   ├── conftest.py       # Pytest configuration
│   ├── fixtures/         # Test fixtures
│   └── ...               # Test files
│
├── docs/                 # Documentation
│   ├── api/             # API documentation
│   ├── guides/          # User guides
│   └── development/     # Developer docs
│
└── examples/            # Usage examples
    ├── configs/        # Configuration examples
    └── scripts/        # Example scripts
```

## Build & Deployment

### Local Development
```bash
# Run in development mode
python -m checkmk_agent

# Run MCP server
python mcp_checkmk_server.py

# Run tests
pytest

# Run with coverage
pytest --cov=checkmk_agent --cov-report=html

# Format code
black checkmk_agent tests
isort checkmk_agent tests

# Type checking
mypy checkmk_agent
```

#### Claude Desktop Integration
```json
{
  "mcpServers": {
    "checkmk": {
      "command": "python",
      "args": [
        "/path/to/mcp_checkmk_server.py"
      ],
      "env": {
        "CHECKMK_URL": "https://monitoring.example.com",
        "CHECKMK_USERNAME": "automation",
        "CHECKMK_PASSWORD": "secure_token",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Performance Considerations

### Caching Strategy
- **LRU Cache**: In-memory caching with size limits
- **TTL**: Time-based cache expiration
- **Redis** (optional): Distributed caching for scale
- **Cache Keys**: Operation + parameters hash

### Connection Management
- **Connection Pooling**: Reuse HTTP connections
- **Keep-Alive**: Persistent connections
- **Timeout Configuration**: Configurable per operation
- **Circuit Breaker**: Fail fast on errors

### Async Operations
- **Async/Await**: Non-blocking I/O operations
- **Concurrency Limits**: Prevent overwhelming Checkmk
- **Task Queues**: Background job processing
- **Streaming**: Memory-efficient large datasets

## Security Best Practices

### Credential Management
- **Environment Variables**: Never hardcode credentials
- **Secrets Management**: Use vault systems in production
- **Token Rotation**: Regular credential updates
- **Least Privilege**: Minimal required permissions

### Input Validation
- **Pydantic Models**: Type-safe validation
- **Sanitization**: Clean user inputs
- **SQL Injection Prevention**: Parameterized queries
- **Command Injection Prevention**: No shell execution

### Network Security
- **HTTPS Only**: Encrypted API communication
- **Certificate Validation**: Verify SSL certificates
- **Rate Limiting**: Prevent abuse
- **IP Whitelisting**: Restrict access

## Monitoring & Observability

### Logging
- **Structured Logging**: JSON format for parsing
- **Request ID Tracking**: End-to-end tracing
- **Log Levels**: Configurable verbosity
- **Log Rotation**: Automatic file management

### Metrics
- **Prometheus Format**: Standard metrics exposition
- **Custom Metrics**: Operation-specific tracking
- **Performance Metrics**: Latency, throughput
- **Error Metrics**: Failure rates and types

### Health Checks
- **Liveness Probe**: Service availability
- **Readiness Probe**: Service readiness
- **Dependency Checks**: Verify external services
- **Performance Checks**: Response time monitoring

## Development Workflow

### Git Workflow
```bash
# Feature branch
git checkout -b feature/new-handler

# Make changes
git add .
git commit -m "feat: add new parameter handler"

# Run tests
pytest

# Push and create PR
git push origin feature/new-handler
```

### Testing Strategy
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: API interaction testing
3. **End-to-End Tests**: Full workflow validation
4. **Performance Tests**: Load and stress testing

### CI/CD Pipeline
```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.8'
    - run: pip install -r requirements.txt
    - run: pip install -r requirements-dev.txt
    - run: pytest --cov
    - run: black --check .
    - run: mypy checkmk_agent
```

## Troubleshooting

### Common Issues

#### MCP Server Not Starting
```bash
# Check logs
tail -f logs/mcp_server.log

# Verify environment
python -c "import mcp; print(mcp.__version__)"

# Test connection
curl http://localhost:3000/health
```

#### API Authentication Failures
```bash
# Test credentials
curl -H "Authorization: Bearer $TOKEN" \
  https://monitoring.example.com/api/1.0/version

# Check token expiration
python -c "import jwt; print(jwt.decode('$TOKEN', options={'verify_signature': False}))"
```

#### Performance Issues
```bash
# Profile code
python -m cProfile -o profile.stats mcp_checkmk_server.py

# Analyze profile
python -m pstats profile.stats

# Monitor memory
python -m memory_profiler mcp_checkmk_server.py
```

## Resources

### Documentation
- [Checkmk REST API Docs](https://docs.checkmk.com/latest/en/rest_api.html)
- [MCP Protocol Spec](https://github.com/modelcontextprotocol/spec)
- [Python Async Best Practices](https://docs.python.org/3/library/asyncio.html)

### Community
- GitHub Issues: Bug reports and features
- Discord: Real-time support
- Stack Overflow: Q&A with `checkmk-llm` tag

### Training Materials
- Video tutorials on YouTube
- Workshop materials in `/docs/workshops/`
- Example notebooks in `/examples/notebooks/`