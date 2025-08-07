# Implement Comprehensive Service Parameter Management

## Goal
Ensure the MCP server can read and write ALL service parameters for any service type, including temperature sensors, custom checks, and any other monitoring parameters managed by Checkmk.

## Current State Analysis

### Existing Capabilities
1. **MCP Tools Available**:
   - `get_effective_parameters`: Retrieves effective parameters for a service
   - `set_service_parameters`: Sets parameters for a service by creating rules

2. **Service Types Supported**:
   - Basic types: CPU, Memory, Filesystem, Network, Load
   - Limited parameter templates for common services
   - Basic ruleset discovery based on service name patterns

3. **Limitations**:
   - Only covers common service types explicitly
   - No support for temperature sensors, custom checks, or specialized services
   - No dynamic parameter schema discovery
   - Cannot update existing rules (only create new ones)
   - No bulk parameter operations
   - Limited validation capabilities

### API Capabilities (Checkmk 2.4)
1. **Rule Management**: `/domain-types/rule/collections/all`
   - Create, list, get, delete, move rules
   - Rules contain parameter values in `value_raw` field

2. **Ruleset Management**: `/domain-types/ruleset/collections/all`
   - List all available rulesets
   - Get ruleset details and schemas

3. **Limitations**:
   - No direct "get effective parameters" endpoint
   - Parameters are managed through rules, not directly
   - Need to understand ruleset naming conventions

## Implementation Plan

### Phase 1: Enhance Ruleset Discovery and Mapping

1. **Create Comprehensive Ruleset Mapping**:
   ```python
   # Extend PARAMETER_RULESETS in parameter_service.py
   PARAMETER_RULESETS = {
       # Environmental monitoring
       'temperature': 'checkgroup_parameters:temperature',
       'humidity': 'checkgroup_parameters:humidity',
       'power': 'checkgroup_parameters:ups_power',
       'voltage': 'checkgroup_parameters:voltage',
       'airflow': 'checkgroup_parameters:airflow',
       
       # Database monitoring
       'oracle_tablespace': 'checkgroup_parameters:oracle_tablespaces',
       'mssql_counters': 'checkgroup_parameters:mssql_counters',
       'mysql_connections': 'checkgroup_parameters:mysql_connections',
       
       # Application monitoring
       'jvm_memory': 'checkgroup_parameters:jvm_memory',
       'apache_status': 'checkgroup_parameters:apache_status',
       'nginx_status': 'checkgroup_parameters:nginx_status',
       
       # Hardware monitoring
       'smart': 'checkgroup_parameters:disk_smart',
       'raid': 'checkgroup_parameters:raid',
       'ipmi': 'checkgroup_parameters:ipmi_sensors',
       
       # Network monitoring
       'tcp_connections': 'checkgroup_parameters:tcp_connections',
       'http': 'checkgroup_parameters:http',
       'https': 'checkgroup_parameters:https',
       
       # Custom/local checks
       'custom': 'checkgroup_parameters:custom_checks',
       'local': 'checkgroup_parameters:local',
       
       # Add wildcard pattern matching
       '*': 'checkgroup_parameters:*'  # For dynamic discovery
   }
   ```

2. **Implement Dynamic Ruleset Discovery**:
   ```python
   async def discover_service_ruleset_dynamic(self, service_name: str) -> str:
       """Dynamically discover ruleset for any service type."""
       # 1. Try exact mapping first
       # 2. Try pattern matching
       # 3. Query API for all rulesets and fuzzy match
       # 4. Use service check plugin name if available
   ```

### Phase 2: Enhance Parameter Schema Discovery

1. **Add Schema Retrieval**:
   ```python
   async def get_parameter_schema(self, ruleset_name: str) -> Dict[str, Any]:
       """Get parameter schema for validation and UI generation."""
       # Get ruleset info from API
       # Extract parameter definitions
       # Return structured schema
   ```

2. **Implement Parameter Validation**:
   ```python
   async def validate_parameters(self, ruleset: str, parameters: Dict) -> ValidationResult:
       """Validate parameters against ruleset schema."""
       # Get schema
       # Validate types, ranges, required fields
       # Return detailed validation result
   ```

### Phase 3: Implement Advanced Rule Management

1. **Rule Update Capability**:
   ```python
   async def update_service_parameters(self, rule_id: str, parameters: Dict) -> ServiceResult:
       """Update existing rule parameters."""
       # Get existing rule
       # Preserve conditions and properties
       # Update only parameter values
       # Handle rule versioning/etag
   ```

2. **Rule Search and Filtering**:
   ```python
   async def find_parameter_rules(self, filters: RuleFilters) -> List[ParameterRule]:
       """Find rules matching complex criteria."""
       # Support filtering by:
       # - Host patterns
       # - Service patterns
       # - Parameter values
       # - Rule properties
   ```

3. **Bulk Operations**:
   ```python
   async def set_bulk_parameters(self, operations: List[BulkOperation]) -> BulkResult:
       """Set parameters for multiple services in one operation."""
       # Validate all operations
       # Create rules in batch
       # Return detailed results
   ```

### Phase 4: Add MCP Tools for Complete Coverage

1. **New MCP Tools to Add**:
   - `discover_service_ruleset`: Find appropriate ruleset for any service
   - `get_parameter_schema`: Get parameter schema for a ruleset
   - `validate_service_parameters`: Validate parameters before setting
   - `update_parameter_rule`: Update existing parameter rule
   - `list_parameter_rules`: List rules with advanced filtering
   - `bulk_set_parameters`: Set parameters for multiple services
   - `get_all_rulesets`: List all available parameter rulesets
   - `search_parameter_rules`: Search rules by various criteria

2. **Enhanced Existing Tools**:
   - `get_effective_parameters`: Add ruleset auto-discovery
   - `set_service_parameters`: Add schema validation, support all service types

### Phase 5: Add Specialized Parameter Handlers

1. **Temperature Sensor Handler**:
   ```python
   class TemperatureParameterHandler:
       """Specialized handler for temperature monitoring parameters."""
       def get_default_thresholds(self, sensor_type: str) -> Dict:
           # Return appropriate defaults for CPU, ambient, disk temps
       
       def validate_temperature_params(self, params: Dict) -> bool:
           # Validate temperature-specific parameters
   ```

2. **Custom Check Handler**:
   ```python
   class CustomCheckParameterHandler:
       """Handler for custom/local check parameters."""
       def parse_custom_parameters(self, check_output: str) -> Dict:
           # Parse parameters from check output
       
       def generate_parameter_rule(self, check_name: str, params: Dict) -> Dict:
           # Generate appropriate rule structure
   ```

### Phase 6: Testing and Documentation

1. **Comprehensive Test Suite**:
   - Test all common service types
   - Test specialized services (temperature, custom checks)
   - Test edge cases and error handling
   - Test bulk operations
   - Performance testing for large environments

2. **Documentation Updates**:
   - Document all new MCP tools
   - Add examples for various service types
   - Create parameter management guide
   - Update README with new capabilities

## Implementation Priority

1. **High Priority** (Week 1):
   - Enhance ruleset discovery to support all service types
   - Add temperature sensor support specifically
   - Implement dynamic ruleset discovery
   - Add `discover_service_ruleset` MCP tool

2. **Medium Priority** (Week 2):
   - Add parameter schema discovery
   - Implement validation framework
   - Add rule update capability
   - Add specialized handlers for common cases

3. **Lower Priority** (Week 3):
   - Bulk operations
   - Advanced search capabilities
   - Performance optimizations
   - Comprehensive documentation

## Success Criteria

1. **Functional Requirements**:
   - ✅ Can read parameters for ANY service type
   - ✅ Can write parameters for ANY service type
   - ✅ Supports temperature sensors explicitly
   - ✅ Supports custom/local checks
   - ✅ Validates parameters before setting
   - ✅ Can update existing rules
   - ✅ Supports bulk operations

2. **Performance Requirements**:
   - Parameter retrieval < 1 second
   - Bulk operations handle 100+ services
   - Efficient caching of ruleset information

3. **Usability Requirements**:
   - Clear error messages for invalid parameters
   - Helpful suggestions for parameter values
   - Easy discovery of appropriate rulesets

## Example Usage

```python
# Temperature sensor example
result = await mcp_client.call_tool(
    "set_service_parameters",
    {
        "host_name": "server01",
        "service_name": "Temperature CPU Core 0",
        "parameters": {
            "levels": (75.0, 85.0),  # Warning at 75°C, Critical at 85°C
            "levels_lower": (5.0, 0.0),  # Warning below 5°C, Critical below 0°C
            "device_levels_handling": "worst",
            "trend_compute": {
                "period": 30,
                "levels": (5.0, 10.0)  # Temperature rise per period
            }
        }
    }
)

# Custom check example
result = await mcp_client.call_tool(
    "set_service_parameters",
    {
        "host_name": "server01", 
        "service_name": "Custom Database Lock Check",
        "parameters": {
            "levels": (100, 200),  # Warning/critical thresholds
            "perfdata": True,
            "inventory": "always",
            "check_interval": 300
        }
    }
)
```

## Notes

- The Checkmk API manages parameters through rules, not direct parameter assignment
- Multiple rules can affect a single service; precedence matters
- Some parameters are check-specific and require understanding the check plugin
- Temperature parameters vary by sensor type (CPU, ambient, disk, etc.)
- Custom checks may have completely arbitrary parameter structures