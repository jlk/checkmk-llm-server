# Common Tasks - Checkmk MCP Server

This document contains step-by-step instructions for common repetitive tasks in the Checkmk MCP Server project.

## Add New Parameter Handler

**Last performed:** 2025-08-03
**Purpose:** Add support for a new service type with specialized parameter handling

**Files to modify:**
- `/checkmk_mcp_server/services/handlers/new_handler.py` - Create new handler file
- `/checkmk_mcp_server/services/handlers/__init__.py` - Register the handler
- `/checkmk_mcp_server/services/parameter_service.py` - Update handler registry
- `/tests/test_handlers/test_new_handler.py` - Add test coverage
- `/docs/handlers.md` - Document the new handler

**Steps:**
1. Create new handler class inheriting from BaseHandler
   ```python
   class NewServiceHandler(BaseHandler):
       def can_handle(self, ruleset_name: str) -> bool:
           return 'new_service' in ruleset_name.lower()
       
       def get_default_parameters(self) -> Dict:
           return {"threshold": 80.0, "enabled": True}
       
       def validate_parameters(self, params: Dict) -> Tuple[bool, str]:
           # Validation logic
           return True, "Valid"
   ```
2. Register handler in `__init__.py`
3. Add to HANDLER_REGISTRY in parameter_service.py
4. Write comprehensive tests
5. Test with actual Checkmk API
6. Update documentation

**Important notes:**
- Always ensure parameters are the correct type (float vs int)
- Test with actual API calls before committing
- Consider edge cases and null values

## Add New MCP Tool

**Last performed:** 2025-08-07
**Purpose:** Expose new functionality through MCP protocol

**Files to modify:**
- `/checkmk_mcp_server/mcp_server/server.py` - Add tool definition and handler
- `/tests/test_mcp_server.py` - Add test for new tool
- `/README.md` - Update tool count and documentation

**Steps:**
1. Define tool in TOOLS list:
   ```python
   {
       "name": "new_tool_name",
       "description": "Clear description of what the tool does",
       "inputSchema": {
           "type": "object",
           "properties": {
               "param1": {"type": "string", "description": "Parameter description"},
               "param2": {"type": "number", "description": "Parameter description"}
           },
           "required": ["param1"]
       }
   }
   ```
2. Implement handler function:
   ```python
   async def handle_new_tool(arguments: Dict[str, Any]) -> CallToolResult:
       request_id = generate_request_id()
       logger.info(f"[{request_id}] Executing new_tool with args: {arguments}")
       
       try:
           # Implementation logic
           result = await service.execute_operation(arguments)
           return CallToolResult(content=[TextContent(text=json.dumps(result))])
       except Exception as e:
           logger.error(f"[{request_id}] Error: {str(e)}")
           return CallToolResult(content=[TextContent(text=f"Error: {str(e)}")])
   ```
3. Add to tool_handlers dictionary in call_tool()
4. Write unit and integration tests
5. Test with Claude Desktop
6. Update README tool count (currently 47)

**Important notes:**
- Use proper MCP SDK decorators (@server.list_tools(), @server.call_tool())
- Always include request ID in logs
- Handle datetime serialization properly
- Return CallToolResult with TextContent

## Debug MCP Server Issues

**Last performed:** 2025-07-25
**Purpose:** Troubleshoot MCP server when tools aren't working

**Files to check:**
- `/mcp_checkmk_server.py` - Entry point
- `/checkmk_mcp_server/mcp_server/server.py` - Tool implementations
- `/logs/mcp_server.log` - Server logs
- `~/.claude/claude_desktop_config.json` - Claude configuration

**Steps:**
1. Enable debug logging:
   ```bash
   export LOG_LEVEL=DEBUG
   ```
2. Run server directly to see output:
   ```bash
   python mcp_checkmk_server.py
   ```
3. Check for import errors or missing dependencies
4. Verify tool registration:
   ```python
   # In server.py, add debug print
   @server.list_tools()
   async def list_tools():
       print(f"Listing {len(TOOLS)} tools")
       return TOOLS
   ```
5. Monitor logs during Claude interaction:
   ```bash
   tail -f logs/mcp_server.log
   ```
6. Check Claude Desktop config for correct path and environment variables
7. Test with simple tool first (e.g., list_hosts)

**Common issues:**
- MCP SDK v1.12.0 CallToolResult construction bug (use workaround)
- Missing environment variables
- Incorrect file paths in Claude config
- Datetime serialization errors (use custom JSON encoder)

## Run Test Suite

**Last performed:** Daily
**Purpose:** Ensure all functionality works correctly

**Files involved:**
- `/tests/*` - All test files
- `/pytest.ini` - Test configuration
- `/conftest.py` - Test fixtures

**Steps:**
1. Run all tests:
   ```bash
   pytest
   ```
2. Run with coverage:
   ```bash
   pytest --cov=checkmk_mcp_server --cov-report=html
   ```
3. Run specific test file:
   ```bash
   pytest tests/test_api_client.py
   ```
4. Run with verbose output:
   ```bash
   pytest -v
   ```
5. Run only failed tests:
   ```bash
   pytest --lf
   ```

**Test categories:**
- Unit tests: Individual component testing
- Integration tests: API interaction testing  
- MCP tests: Tool functionality
- Performance tests: Load and stress testing

## Add Service Operation

**Last performed:** 2025-07-24
**Purpose:** Add new service management functionality

**Files to modify:**
- `/checkmk_mcp_server/api_client.py` - API method
- `/checkmk_mcp_server/service_operations.py` - Business logic
- `/checkmk_mcp_server/cli.py` - CLI command
- `/checkmk_mcp_server/mcp_server/server.py` - MCP tool
- `/tests/test_service_operations.py` - Tests

**Steps:**
1. Add API client method:
   ```python
   def new_service_operation(self, host_name: str, service_name: str, **kwargs):
       endpoint = f"/domain-types/service/actions/new_operation/invoke"
       return self._request("POST", endpoint, json={...})
   ```
2. Add service operation handler
3. Create CLI command in services group
4. Expose as MCP tool
5. Write comprehensive tests
6. Test with real Checkmk instance

**Important notes:**
- Use monitoring endpoints for status
- Use setup endpoints for configuration
- Handle service name encoding properly

## Performance Optimization

**Last performed:** Ongoing
**Purpose:** Improve response times and resource usage

**Files to monitor:**
- `/checkmk_mcp_server/services/cache_service.py` - Caching logic
- `/checkmk_mcp_server/services/batch_service.py` - Batch operations
- `/checkmk_mcp_server/services/streaming_service.py` - Large datasets

**Steps:**
1. Profile code to find bottlenecks:
   ```bash
   python -m cProfile -o profile.stats mcp_checkmk_server.py
   python -m pstats profile.stats
   ```
2. Enable caching for read operations:
   ```python
   @lru_cache(maxsize=1000)
   def get_cached_data(key: str):
       return fetch_from_api(key)
   ```
3. Use batch operations for multiple items:
   ```python
   async def batch_process(items: List, batch_size=50):
       for batch in chunks(items, batch_size):
           await process_batch(batch)
   ```
4. Implement streaming for large results:
   ```python
   async def stream_results():
       async for chunk in api_client.stream_data():
           yield process_chunk(chunk)
   ```
5. Monitor metrics and adjust

**Performance targets:**
- Sub-second response for common operations
- Handle 50,000+ hosts
- 10,000+ cache operations/second

## Handle Checkmk API Changes

**Last performed:** As needed
**Purpose:** Adapt to new Checkmk API versions

**Files to check:**
- `/checkmk-rest-openapi.yaml` - API specification
- `/checkmk_mcp_server/api_client.py` - API methods
- All test files

**Steps:**
1. Download latest OpenAPI spec:
   ```bash
   curl https://monitoring.example.com/site/check_mk/api/1.0/openapi.json > checkmk-rest-openapi.yaml
   ```
2. Compare with existing spec for changes
3. Update affected API methods
4. Adjust parameter validation
5. Update tests for new behavior
6. Test thoroughly with new version
7. Update documentation

**Important notes:**
- Maintain backward compatibility when possible
- Document breaking changes clearly
- Update version requirements

## Troubleshoot Authentication

**Last performed:** As needed
**Purpose:** Fix authentication issues with Checkmk

**Files to check:**
- `/.env` - Credentials
- `/checkmk_mcp_server/api_client.py` - Auth implementation
- Server logs

**Steps:**
1. Verify credentials are correct:
   ```bash
   curl -H "Authorization: Bearer $CHECKMK_PASSWORD" \
     https://monitoring.example.com/site/check_mk/api/1.0/version
   ```
2. Check user permissions in Checkmk
3. Verify site name is correct
4. Test with automation user vs regular user
5. Check for expired tokens
6. Review authentication logs

**Common issues:**
- Wrong site name in URL
- Insufficient permissions
- Special characters in password
- Token vs password confusion