# Request ID Tracing Implementation Spec

## Overview

Implement comprehensive request ID generation and tracking throughout the Checkmk MCP Server system to improve traceability, debugging, and troubleshooting capabilities.

## Objectives

- Generate unique request IDs for every LLM/client request
- Propagate request IDs through all system components
- Include request IDs in all log messages
- Provide request ID correlation across MCP tools
- Enable efficient log filtering and request tracing

## Request ID Requirements

### ID Generation
- **Format**: 6-digit hex string (e.g., `req_a1b2c3`)
- **Prefix**: All request IDs prefixed with `req_` for easy identification
- **Uniqueness**: High probability of uniqueness for typical request volumes (16.7M combinations)
- **Performance**: Very low overhead generation suitable for high-frequency operations
- **Readability**: Short, memorable IDs for easy log searching and troubleshooting

### ID Propagation
- Request ID must flow through all system layers:
  - MCP server entry points
  - Service layer operations
  - API client calls
  - Interactive CLI sessions
  - Batch and streaming operations

## Implementation Plan

### Phase 1: Core Infrastructure

#### 1.1 Request Context Manager
**File**: `checkmk_mcp_server/utils/request_tracking.py`
- [ ] Create request ID utilities using contextvars with robust fallback
- [ ] Implement lazy `generate_request_id()` function
- [ ] Create `@with_request_id` decorator for service methods
- [ ] Add context propagation support for async thread pool operations
- [ ] Implement ephemeral ID generation for orphaned operations

#### 1.2 Enhanced Logging Utilities
**File**: `checkmk_mcp_server/logging_utils.py`
- [ ] Modify existing logger configuration to include request ID
- [ ] Create custom log formatter with request ID field
- [ ] Add `get_logger_with_request_id()` function
- [ ] Ensure backward compatibility with existing logging

#### 1.3 Request ID Middleware
**File**: `checkmk_mcp_server/middleware/request_tracking.py`
- [ ] Create middleware decorator `@track_request()`
- [ ] Implement automatic request ID generation for entry points
- [ ] Add request ID to response headers/metadata where applicable

### Phase 2: MCP Server Integration

#### 2.1 MCP Tool Wrapper
**File**: `checkmk_mcp_server/mcp_server/server.py`
- [ ] Modify `@server.call_tool()` decorator to generate request IDs
- [ ] Update all 47 MCP tools to propagate request ID
- [ ] Add request ID to tool response metadata
- [ ] Ensure request ID flows through async operations

#### 2.2 MCP Session Management
**File**: `checkmk_mcp_server/interactive/mcp_session.py`
- [ ] Generate session-level request IDs for interactive mode
- [ ] Maintain request ID across multi-turn conversations
- [ ] Add request ID to MCP protocol messages

### Phase 3: Service Layer Integration

#### 3.1 Base Service Updates
**File**: `checkmk_mcp_server/services/base.py`
- [ ] Update `BaseService` to accept and propagate request ID
- [ ] Modify error handling to include request ID in exceptions
- [ ] Add request ID to service method signatures where needed

#### 3.2 API Client Integration
**File**: `checkmk_mcp_server/api_client.py`
- [ ] Add request ID to HTTP headers (`X-Request-ID`)
- [ ] Include request ID in API call logging
- [ ] Propagate request ID through retry mechanisms
- [ ] Add request ID to API response logging

#### 3.3 Service-Specific Updates
**Files**: All service classes in `checkmk_mcp_server/services/`
- [ ] `host_service.py` - Add request ID to host operations
- [ ] `status_service.py` - Include request ID in status checks
- [ ] `service_service.py` - Propagate through service operations
- [ ] `parameter_service.py` - Track parameter management requests
- [ ] `streaming.py` - Maintain parent request ID, generate sub-IDs for streaming batches
- [ ] `cache.py` - Include request ID in cache keys and logging
- [ ] `batch.py` - Generate sub-IDs for batch items, propagate through concurrent operations
- [ ] `metrics.py` - Add request ID to performance metrics

### Phase 4: CLI Integration

#### 4.1 Direct CLI Updates
**File**: `checkmk_mcp_server/cli.py`
- [ ] Generate request ID for each CLI command
- [ ] Add `--request-id` option to manually specify ID
- [ ] Include request ID in command output (optional verbose mode)

#### 4.2 MCP CLI Updates
**File**: `checkmk_mcp_server/cli_mcp.py`
- [ ] Integrate with MCP server request ID generation
- [ ] Display request ID in verbose mode
- [ ] Add request ID to error messages

#### 4.3 Interactive Mode Updates
**File**: `checkmk_mcp_server/interactive/command_parser.py`
- [ ] Generate request ID for each interactive command
- [ ] Maintain request ID context during command execution
- [ ] Display request ID in debug mode

### Phase 5: Specialized Components

#### 5.1 Parameter Handlers
**Files**: `checkmk_mcp_server/services/handlers/*.py`
- [ ] Update all parameter handlers to propagate request ID
- [ ] Include request ID in handler-specific logging
- [ ] Add request ID to validation error messages

#### 5.2 Async Operations
**Files**: Async components throughout codebase
- [ ] Ensure request ID propagation through asyncio tasks
- [ ] Update async context management
- [ ] Maintain request ID across awaited operations

## Technical Specifications

### Request ID Format
```python
import secrets
from typing import Optional

def generate_request_id() -> str:
    """Generate a unique 6-digit hex request ID with req_ prefix."""
    return f"req_{secrets.token_hex(3)}"  # 3 bytes = 6 hex chars

def generate_sub_request_id(parent_id: str, sequence: int) -> str:
    """Generate sub-request ID for batch operations."""
    return f"{parent_id}.{sequence:03d}"

def format_request_id(request_id: Optional[str]) -> str:
    """Format request ID for logging."""
    return request_id or "req_unknown"

def extract_parent_id(request_id: str) -> str:
    """Extract parent request ID from sub-request ID."""
    return request_id.split('.')[0] if '.' in request_id else request_id
```

### Context Variable Implementation
```python
from contextvars import ContextVar

# Global context variable for request ID
REQUEST_ID_CONTEXT: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
```

### Logging Format
```
2025-08-07 14:30:15.123 [req_a1b2c3] INFO checkmk_mcp_server.api_client: Fetching host list
2025-08-07 14:30:15.456 [req_a1b2c3] DEBUG checkmk_mcp_server.services.host_service: Processing 15 hosts
2025-08-07 14:30:15.789 [req_a1b2c3] ERROR checkmk_mcp_server.api_client: API call failed: Connection timeout
```

### HTTP Headers
```
X-Request-ID: req_a1b2c3
```

## Configuration

Request ID tracing is **always enabled** - no configuration required. This ensures consistent traceability across all deployments and eliminates configuration complexity.

### Optional HTTP Headers
```yaml
# Only configurable aspect - HTTP header inclusion (default: enabled)
api:
  include_request_id_in_headers: true  # Optional - defaults to true
```

## Testing Requirements

### Unit Tests
- [ ] Test request ID generation uniqueness
- [ ] Verify context propagation across function calls
- [ ] Test logging format with request IDs
- [ ] Validate middleware request ID injection

### Integration Tests
- [ ] End-to-end request ID flow through MCP tools
- [ ] API client request ID header propagation
- [ ] CLI command request ID generation
- [ ] Interactive mode request ID continuity

### Performance Tests
- [ ] Measure request ID generation overhead
- [ ] Validate no performance degradation in high-frequency operations
- [ ] Test concurrent request ID uniqueness

## Migration Strategy

### Backward Compatibility
- All existing APIs remain unchanged
- Request ID is optional in all contexts
- Graceful fallback when request ID is not available
- No breaking changes to existing log parsing tools

### Rollout Plan
1. **Phase 1**: Deploy core infrastructure and utilities
2. **Phase 2**: Enable request ID in MCP server (always on)
3. **Phase 3**: Enable in service layer components (always on)
4. **Phase 4**: Enable in CLI interfaces (always on)
5. **Phase 5**: Full deployment with specialized components (always on)

## Documentation Updates

### User Documentation
- [ ] Update README.md with request ID examples
- [ ] Add troubleshooting guide using request IDs
- [ ] Update configuration documentation

### Developer Documentation
- [ ] API documentation with request ID examples
- [ ] Logging best practices guide
- [ ] Request ID propagation patterns

## Success Criteria

### Functional Requirements
- [ ] Every LLM/client request generates unique request ID
- [ ] Request ID appears in all related log messages
- [ ] Request ID flows through all system components
- [ ] Easy log filtering by request ID
- [ ] No performance impact on existing operations

### Quality Requirements
- [ ] 100% test coverage for request ID functionality
- [ ] No breaking changes to existing APIs
- [ ] Comprehensive documentation
- [ ] Performance benchmarks within acceptable limits

## Files to Create/Modify

### New Files
- `checkmk_mcp_server/utils/request_context.py`
- `checkmk_mcp_server/middleware/request_tracking.py`
- `tests/test_request_tracking.py`
- `tests/test_request_context.py`

### Modified Files
- `checkmk_mcp_server/logging_utils.py`
- `checkmk_mcp_server/mcp_server/server.py`
- `checkmk_mcp_server/api_client.py`
- `checkmk_mcp_server/services/base.py`
- All service layer files
- All CLI interface files
- Configuration examples
- Documentation files

## Implementation Timeline

- **Phase 1-2**: Core infrastructure and MCP integration (2-3 days)
- **Phase 3**: Service layer integration (2-3 days)  
- **Phase 4**: CLI integration (1-2 days)
- **Phase 5**: Specialized components and testing (1-2 days)
- **Documentation and final validation**: 1 day

**Total Estimated Time**: 7-11 days

## Risk Mitigation

### Potential Issues
- Performance impact from hex ID generation (minimal - ~10-50ns per access)
- Context propagation in complex async operations
- Memory usage from additional context variables

### Mitigation Strategies
- Use lazy request ID generation to minimize overhead
- Implement efficient context variable patterns
- Monitor memory usage during testing
- Focus on robust fallback patterns rather than toggles