# Effective Attributes Parameter Implementation Plan (REVISED)

## Overview
The LLM currently doesn't realize it can pass the `effective_attributes` parameter to get comprehensive host details including inherited folder attributes and computed parameters. This plan outlines how to make this capability discoverable and usable.

## Problem Statement
- The Checkmk API supports `effective_attributes` parameter for host queries
- The API client (`api_client.py`) already supports this parameter
- However, the host service layer doesn't expose this parameter
- The MCP server tools don't advertise this capability
- LLMs using the system are unaware they can request inherited attributes

## Critical Issues Identified (Must Fix First)

### 1. **Async/Sync Architecture Mismatch** (Priority: HIGH)
**Status**: Blocking Implementation

**Issue**: The host service layer calls `await self.checkmk.get_host()` but the API client's `get_host()` method is synchronous. This causes runtime failures.

**Files to fix**:
- `checkmk_agent/api_client.py:281` - Make `get_host()` method async
- `checkmk_agent/api_client.py:308` - Make `list_hosts()` method async 

**Fix Required**:
```python
# api_client.py
async def get_host(self, host_name: str, effective_attributes: bool = False) -> Dict[str, Any]:
    # Convert to use async HTTP calls
```

### 2. **Documentation Inaccuracy** (Priority: HIGH)
**Status**: Critical

**Issue**: The MCP README created incorrectly claims `effective_attributes` is already working with examples that will fail.

**Files to fix**:
- `checkmk_agent/mcp_server/README.md` - Remove incorrect examples and mark feature as planned

### 3. **Missing Implementation Scope** (Priority: HIGH)
**Status**: Gap in plan

**Issue**: Both `get_host` AND `list_hosts` need updating, but the plan only focuses on `get_host`.

## Revised Implementation Tasks

### Phase 0: Fix Blockers (NEW - Must Complete First)

#### Task 1: Fix Async/Sync Mismatch
- Make `api_client.get_host()` async
- Make `api_client.list_hosts()` async  
- Ensure all HTTP calls use async patterns
- Update any affected service layer methods

#### Task 2: Correct Documentation
- Fix MCP README to remove false claims
- Mark `effective_attributes` as "planned enhancement"
- Remove non-working examples

### Phase 1: Core Implementation

#### Task 3: Update Host Service Layer
**Files to modify**:
- `checkmk_agent/services/host_service.py`

**Changes**:
1. Update `get_host()` method signature:
   ```python
   async def get_host(self, name: str, include_status: bool = True, 
                      effective_attributes: bool = False) -> ServiceResult[HostInfo]:
   ```

2. Update `list_hosts()` method signature:
   ```python
   async def list_hosts(self, search=None, folder=None, limit=None, offset=0, 
                        include_status=False, effective_attributes=False) -> ServiceResult[HostListResult]:
   ```

3. Pass `effective_attributes` parameter to API client calls

#### Task 4: Update MCP Server Tool Definitions
**Files to modify**:
- `checkmk_agent/mcp_server/server.py`

**Changes**:
1. Update `get_host` tool schema to include:
   ```python
   "effective_attributes": {
       "type": "boolean", 
       "description": "Include inherited folder attributes and computed parameters (permissions enforced by Checkmk server)",
       "default": False
   }
   ```

2. Update `list_hosts` tool schema similarly

3. Update tool handlers to pass the parameter through:
   ```python
   async def get_host(name, include_status=True, effective_attributes=False):
       result = await self.host_service.get_host(
           name=name, 
           include_status=include_status,
           effective_attributes=effective_attributes
       )
   ```

### Phase 2: CLI Enhancement

#### Task 5: Update CLI Interface
**Files to modify**:
- `checkmk_agent/cli.py`

**Changes**:
- Add `--effective-attributes` flag for host commands
- Update help text to explain the feature

### Phase 3: Testing & Documentation

#### Task 6: Add Tests
**Test coverage needed**:
- Unit tests for host service with effective_attributes
- Integration tests verifying inherited attributes  
- MCP server tests for new parameter
- CLI tests for new flags

#### Task 7: Update Documentation
**Documentation updates**:
1. **MCP Server README** - Replace incorrect content with accurate planned features
2. **API Documentation** - Document parameter usage
3. **CLI Help** - Add examples using effective attributes
4. **CLAUDE.md** - Add notes about using effective attributes
5. **Permission Model Documentation** - Clarify that Checkmk server enforces all permissions

## Security & Permission Model

### Permission Enforcement
**Important**: All security and permission checks are handled by the Checkmk server itself. The agent implementation relies on:

1. **Checkmk Server Authentication**: User credentials are validated by Checkmk
2. **Checkmk Permission Model**: Access to effective attributes is controlled by Checkmk's built-in permission system
3. **API-Level Filtering**: The Checkmk REST API automatically filters results based on user permissions
4. **No Additional Security Layer**: The agent does not implement additional permission checking beyond what Checkmk provides

### Implementation Assumption
When `effective_attributes=true` is requested:
- The agent passes the parameter directly to the Checkmk API
- If the user lacks permissions, Checkmk will return appropriate error responses
- The agent forwards these responses without modification
- No sensitive data filtering is performed at the agent level

## Implementation Order

1. **Phase 0: Fix Blockers (MUST COMPLETE FIRST)**
   - Fix async/sync mismatch in API client
   - Correct MCP documentation inaccuracies

2. **Phase 1: Core Implementation**
   - Update host service to accept effective_attributes
   - Update MCP server tool definitions  
   - Update tool handlers

3. **Phase 2: CLI Enhancement**
   - Add CLI flags and options
   - Update help documentation

4. **Phase 3: Testing & Documentation**
   - Write comprehensive tests
   - Update all documentation
   - Add usage examples

## Code Examples

### Host Service Update
```python
async def get_host(self, name: str, include_status: bool = True, 
                   effective_attributes: bool = False) -> ServiceResult[HostInfo]:
    """
    Get detailed information about a specific host.
    
    Args:
        name: Host name
        include_status: Whether to include status information
        effective_attributes: Include all inherited folder attributes (permissions enforced by Checkmk)
        
    Returns:
        ServiceResult containing HostInfo with complete configuration
    """
    # Implementation passes effective_attributes to API client
    # Checkmk server enforces all permission checks
```

### MCP Tool Usage Example (After Implementation)
```json
{
  "tool": "get_host",
  "arguments": {
    "name": "webserver01",
    "include_status": true,
    "effective_attributes": true
  }
}
```

### Expected Benefits
1. LLMs can access complete host configuration
2. Troubleshooting becomes more effective with full parameter visibility
3. Understanding of parameter inheritance improves
4. Reduced confusion about where settings come from

## Success Criteria
- [ ] Async/sync mismatch resolved in API client
- [ ] MCP documentation corrected to reflect current status
- [ ] Host service accepts and uses effective_attributes parameter for both get_host and list_hosts
- [ ] MCP tools expose the parameter in their schemas
- [ ] CLI supports the new parameter
- [ ] Tests pass with >90% coverage
- [ ] Documentation clearly explains the feature and permission model
- [ ] LLMs can successfully use the parameter

## Risk Mitigation
- **Backward Compatibility**: Default to false to maintain existing behavior
- **Performance**: Document that effective_attributes may increase response time significantly
- **Permission Model**: Document that Checkmk server handles all security and permission enforcement
- **Error Handling**: Properly forward Checkmk permission errors to users

## Revised Timeline Estimate
**Phase 0 (Blockers)**: 4-6 hours
- Fix async/sync issues: 3-4 hours
- Correct documentation: 1-2 hours

**Phase 1 (Core Implementation)**: 3-4 hours
- Host service updates: 2-3 hours
- MCP server updates: 1-2 hours

**Phase 2 (CLI Enhancement)**: 1-2 hours
**Phase 3 (Testing & Documentation)**: 2-3 hours

**Total Revised Estimate**: 10-15 hours

## Next Steps
1. **MANDATORY**: Complete Phase 0 blockers before any feature implementation
2. Review and approve this revised plan
3. Create feature branch
4. Implement changes following the phases
5. Submit PR with comprehensive testing