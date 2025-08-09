# System Architecture - Checkmk LLM Agent

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interfaces                        │
├───────────────┬──────────────────┬──────────────────────────┤
│  CLI Interface│  MCP Server      │  Direct API Integration  │
│  (Interactive)│  (47 Tools)      │  (Python SDK)            │
└───────┬───────┴────────┬─────────┴─────────┬────────────────┘
        │                │                   │
        └────────────────┼───────────────────┘
                         │
                    ┌────▼────┐
                    │  Core   │
                    │ Engine  │
                    └────┬────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐     ┌─────▼─────┐    ┌─────▼─────┐
   │  LLM    │     │  Service  │    │  Request  │
   │ Client  │     │   Layer   │    │  Tracing  │
   └────┬────┘     └─────┬─────┘    └─────┬─────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                  ┌──────▼──────┐
                  │ API Client  │
                  │ (Sync/Async)│
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │  Checkmk    │
                  │  REST API   │
                  └─────────────┘
```

## Core Components

### 1. API Client Layer (`checkmk_agent/api_client.py`)

**Purpose**: Low-level communication with Checkmk REST API

**Key Classes**:
- `CheckmkClient`: Synchronous API client
- `AsyncCheckmkClient`: Asynchronous API client
- `APIResponse`: Standardized response wrapper

**Features**:
- Authentication management
- Request/response logging
- Error handling and retries
- Rate limiting
- Connection pooling

### 2. Service Layer (`checkmk_agent/services/`)

**Purpose**: Business logic and domain-specific operations

**Core Services**:
```python
# Base Service Pattern
class BaseService:
    def __init__(self, api_client, request_id=None):
        self.api_client = api_client
        self.request_id = request_id or generate_request_id()
    
    def _create_result(self, success, data=None, error=None):
        return ServiceResult(success, data, error, self.request_id)
```

**Service Components**:
- `StatusService`: Service state monitoring
- `ParameterService`: Parameter management with handlers
- `CacheService`: Performance optimization
- `BatchService`: Bulk operations
- `StreamingService`: Large dataset handling

### 3. Parameter Handlers (`checkmk_agent/services/handlers/`)

**Purpose**: Domain-specific parameter intelligence

**Handler Registry**:
```python
HANDLER_REGISTRY = {
    'temperature': TemperatureHandler,
    'database': DatabaseHandler,
    'network': NetworkHandler,
    'custom': CustomCheckHandler
}
```

**Handler Interface**:
- `can_handle(ruleset_name)`: Check if handler applies
- `get_default_parameters()`: Provide defaults
- `validate_parameters()`: Validate input
- `optimize_parameters()`: Suggest improvements
- `get_parameter_hints()`: User guidance

### 4. MCP Server (`checkmk_agent/mcp_server/server.py`)

**Purpose**: Model Context Protocol integration for AI assistants

**Architecture**:
```python
@server.list_tools()
async def list_tools():
    return TOOLS  # 47 tool definitions

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    tool_handlers = {
        "get_host_status": handle_get_host_status,
        "set_service_parameters": handle_set_parameters,
        # ... 45 more handlers
    }
    return await tool_handlers[name](arguments)
```

**Tool Categories**:
1. **Host Management** (8 tools)
   - create_host, update_host, delete_host
   - get_host_status, list_hosts
   - bulk_create_hosts, move_host, rename_host

2. **Service Operations** (12 tools)
   - list_services, get_service_status
   - acknowledge_service_problems
   - create_service_downtime
   - discover_services
   - get_service_parameters, set_service_parameters
   - analyze_service_health
   - get_critical_problems
   - get_infrastructure_overview

3. **Rule Management** (7 tools)
   - create_rule, update_rule, delete_rule
   - list_rules, get_rule
   - move_rule, copy_rule

4. **Parameter Management** (12 tools)
   - list_available_rulesets
   - get_ruleset_info
   - get_all_service_parameters
   - set_service_parameters_advanced
   - optimize_service_parameters
   - validate_service_parameters
   - analyze_parameter_impact
   - export_parameters, import_parameters
   - get_parameter_recommendations
   - batch_update_parameters
   - get_parameter_history

5. **Advanced Operations** (5 tools)
   - batch_process_hosts
   - stream_large_dataset
   - get_performance_metrics
   - analyze_cache_efficiency
   - execute_custom_query

6. **Host Check Configuration** (3 tools)
   - adjust_host_check_attempts
   - adjust_host_retry_interval
   - adjust_host_check_timeout

### 5. CLI Interface (`checkmk_agent/cli.py`)

**Purpose**: Command-line interface for direct interaction

**Command Structure**:
```
checkmk-agent
├── hosts
│   ├── list
│   ├── create
│   ├── update
│   └── delete
├── services
│   ├── list
│   ├── status
│   ├── acknowledge
│   └── discover
├── rules
│   ├── list
│   ├── create
│   └── update
├── parameters
│   ├── get
│   ├── set
│   └── optimize
└── interactive (natural language mode)
```

### 6. Request ID Tracing (`checkmk_agent/context_vars.py`)

**Purpose**: End-to-end request tracking for debugging

**Implementation**:
```python
from contextvars import ContextVar

request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

def generate_request_id() -> str:
    """Generate 6-digit hex ID: req_xxxxxx"""
    return f"req_{secrets.token_hex(3)}"

class RequestContext:
    def __init__(self, request_id=None):
        self.request_id = request_id or generate_request_id()
        self.token = None
    
    def __enter__(self):
        self.token = request_id_var.set(self.request_id)
        return self.request_id
    
    def __exit__(self, *args):
        request_id_var.reset(self.token)
```

### 7. Logging System (`checkmk_agent/logging_utils.py`)

**Purpose**: Structured logging with request correlation

**Features**:
- RequestIDFormatter for consistent format
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Automatic request ID injection
- Performance metrics logging

## Data Flow

### 1. Natural Language Query Flow
```
User Input → LLM Client → Intent Analysis → Service Layer → API Client → Checkmk
     ↑                                                                        ↓
     └─────────────── Formatted Response ←── Result Processing ←────────────┘
```

### 2. MCP Tool Call Flow
```
Claude/AI → MCP Server → Tool Handler → Service Layer → API Client → Checkmk
     ↑                                                                    ↓
     └──────────── Tool Result ←── Response Formatting ←────────────────┘
```

### 3. CLI Command Flow
```
CLI Command → Command Parser → Operation Handler → API Client → Checkmk
      ↑                                                            ↓
      └────────── Rich Output ←── Response Formatter ←───────────┘
```

## Key Design Patterns

### 1. Service Result Pattern
```python
@dataclass
class ServiceResult:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Optional[Dict] = None
```

### 2. Handler Registry Pattern
```python
class HandlerRegistry:
    _handlers: Dict[str, BaseHandler] = {}
    
    @classmethod
    def register(cls, name: str, handler: BaseHandler):
        cls._handlers[name] = handler
    
    @classmethod
    def get_handler(cls, ruleset_name: str) -> Optional[BaseHandler]:
        # Fuzzy matching logic
        for pattern, handler in cls._handlers.items():
            if pattern in ruleset_name:
                return handler
        return None
```

### 3. Async Context Manager Pattern
```python
class AsyncAPIClient:
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        await self.session.close()
```

### 4. Caching Strategy Pattern
```python
class CacheStrategy:
    def should_cache(self, operation: str) -> bool
    def get_ttl(self, operation: str) -> int
    def generate_key(self, operation: str, params: dict) -> str
```

## Integration Points

### 1. Checkmk REST API
- Base URL: Configurable
- API Version: v1.0
- Authentication: Bearer token / Session
- Content-Type: application/json

### 2. LLM Providers
- OpenAI API (GPT-4)
- Anthropic API (Claude)
- Local LLMs via Ollama
- Custom providers via adapter pattern

### 3. MCP Clients
- Claude Desktop
- VS Code Claude extension
- Custom MCP implementations
- OpenAI Assistants (via adapter)

## Performance Optimizations

### 1. Caching Layer
- LRU cache with TTL
- 10,000+ operations/second
- Intelligent cache invalidation
- Memory-bounded caching

### 2. Connection Pooling
- Persistent HTTP connections
- Connection reuse
- Automatic retry with backoff
- Circuit breaker pattern

### 3. Batch Processing
- Concurrent operation execution
- Progress tracking
- Error aggregation
- Rate limiting

### 4. Streaming
- Constant memory usage
- 50,000+ items support
- Real-time progress updates
- Chunked processing

## Security Architecture

### 1. Authentication
- Secure credential storage
- Token rotation support
- Session management
- API key handling

### 2. Authorization
- Checkmk permission model
- Role-based access control
- Operation filtering
- Audit logging

### 3. Data Protection
- Sensitive data masking
- Secure configuration
- Encrypted storage
- Input validation

## Error Handling

### 1. Error Hierarchy
```python
CheckmkAgentError
├── APIError
│   ├── AuthenticationError
│   ├── RateLimitError
│   └── ValidationError
├── ServiceError
│   ├── ParameterError
│   └── HandlerError
└── ConfigurationError
```

### 2. Recovery Strategies
- Automatic retry with exponential backoff
- Circuit breaker for failing services
- Graceful degradation
- Fallback mechanisms

## Monitoring & Observability

### 1. Metrics Collection
- Operation latency
- Success/failure rates
- Cache hit ratios
- Resource utilization

### 2. Health Checks
- API connectivity
- Service availability
- Handler status
- Cache health

### 3. Debugging Support
- Request ID tracing
- Detailed logging
- Performance profiling
- Error aggregation

## Deployment Architecture

### 1. MCP Server Deployment
```yaml
# Claude Desktop config
{
  "mcpServers": {
    "checkmk": {
      "command": "python",
      "args": ["mcp_checkmk_server.py"],
      "env": {
        "CHECKMK_URL": "https://monitoring.example.com",
        "CHECKMK_USERNAME": "automation",
        "CHECKMK_PASSWORD": "secure_token"
      }
    }
  }
}
```

### 2. Docker Deployment
```dockerfile
FROM python:3.8-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "mcp_checkmk_server.py"]
```

### 3. Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkmk-llm-agent
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: agent
        image: checkmk-llm-agent:latest
        env:
        - name: CHECKMK_URL
          valueFrom:
            secretKeyRef:
              name: checkmk-creds
              key: url
```

## Future Architecture Considerations

### Phase 2 Enhancements
- WebSocket support for real-time updates
- GraphQL API layer
- Plugin architecture for custom handlers
- Distributed caching with Redis

### Phase 3 Evolution
- Microservices architecture
- Event-driven processing
- Machine learning pipeline
- Multi-tenant support