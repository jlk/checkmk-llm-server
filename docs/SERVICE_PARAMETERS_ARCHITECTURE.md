# Checkmk Service Parameters Architecture

This document explains how service parameters actually work in Checkmk and how our implementation correctly handles them.

## The Fundamental Understanding

### What We Initially Got Wrong

Our original implementation attempted to:
1. Manually evaluate rules to compute "effective parameters"
2. Treat service parameters as direct properties of services
3. Use rule evaluation logic that didn't match Checkmk's internal engine

**This approach was fundamentally flawed** because:
- Checkmk's rule engine is complex and proprietary
- Service parameters are computed during discovery/configuration time
- Manual rule evaluation cannot replicate Checkmk's internal logic

### How Checkmk Actually Works

Checkmk uses a **rule-based configuration system** where:

1. **Rules Define Parameters**: Parameters are defined in rules within rulesets
2. **Checkmk Evaluates Rules**: Checkmk's internal engine evaluates all applicable rules
3. **Discovery Contains Results**: Service discovery data contains the computed effective parameters
4. **No Direct Parameter API**: There are no direct "get/set service parameters" endpoints

## Correct API Architecture

### For Reading Service Parameters (Effective Parameters)

#### Primary Method: Service Discovery
```python
# Correct approach - use service discovery data
result = client.get_service_effective_parameters(host_name, service_name)
```

**Endpoint**: `/objects/service_discovery/{host_name}`

**Why This Works**:
- Service discovery contains services with their effective parameters
- Parameters are pre-computed by Checkmk's rule engine
- Includes check plugin information and current configuration

**Response Structure**:
```json
{
  "host_name": "server01",
  "service_name": "Temperature Sensor 1",
  "parameters": {
    "levels": [70.0, 80.0],
    "levels_lower": [5.0, 0.0],
    "output_unit": "c"
  },
  "check_plugin": "temperature",
  "discovery_phase": "monitored",
  "status": "success",
  "source": "service_discovery"
}
```

#### Fallback Method: Service Monitoring
If service is not in discovery data, we fall back to monitoring endpoints:

**Endpoint**: `/domain-types/service/collections/all`

This provides monitoring data but limited parameter information.

### For Writing Service Parameters (Rule Management)

#### Create Parameter Rules
```python
# Correct approach - create rules that define parameters
rule = client.create_service_parameter_rule(
    ruleset_name="checkgroup_parameters:temperature",
    folder="/",
    parameters={"levels": (75.0, 85.0)},
    host_name="server01",
    service_pattern="Temperature.*",
    description="Temperature thresholds for server01"
)
```

**Endpoint**: `/domain-types/rule/collections/all`

#### Update Existing Rules
```python
updated_rule = client.update_service_parameter_rule(
    rule_id="rule_123",
    parameters={"levels": (80.0, 90.0)},
    description="Updated temperature thresholds"
)
```

**Endpoint**: `/objects/rule/{rule_id}`

#### Find Applicable Rules
```python
rules = client.find_service_parameter_rules(
    host_name="server01",
    service_name="Temperature Sensor 1"
)
```

This searches relevant rulesets to find rules affecting the service.

## Ruleset Mapping

Our implementation includes intelligent ruleset mapping:

### Temperature Services
- **Pattern**: `temp`, `temperature`, `thermal`
- **Rulesets**: 
  - `checkgroup_parameters:temperature`
  - `checkgroup_parameters:hw_temperature`
  - `checkgroup_parameters:ipmi_sensors`

### Filesystem Services
- **Pattern**: `filesystem`, `disk`, `mount`, `df`
- **Ruleset**: `checkgroup_parameters:filesystem`

### CPU Services
- **Pattern**: `cpu`, `load`, `processor`
- **Rulesets**:
  - `checkgroup_parameters:cpu_utilization`
  - `checkgroup_parameters:cpu_load`

### Memory Services
- **Pattern**: `memory`, `ram`, `mem`
- **Ruleset**: `checkgroup_parameters:memory_linux`

### Network Services
- **Pattern**: `interface`, `network`, `if`, `eth`, `nic`
- **Ruleset**: `checkgroup_parameters:if`

## Implementation Details

### API Client Methods

#### New Correct Methods
```python
class CheckmkClient:
    def get_service_effective_parameters(self, host_name: str, service_name: str) -> Dict[str, Any]:
        """Get effective parameters from service discovery data."""
        
    def create_service_parameter_rule(self, ruleset_name: str, folder: str, 
                                    parameters: Dict[str, Any], ...) -> Dict[str, Any]:
        """Create a rule to set service parameters."""
        
    def update_service_parameter_rule(self, rule_id: str, 
                                    parameters: Dict[str, Any], ...) -> Dict[str, Any]:
        """Update an existing parameter rule."""
        
    def find_service_parameter_rules(self, host_name: str, service_name: str, 
                                   ruleset_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find existing rules affecting a service."""
```

#### Legacy Method (Backward Compatibility)
```python
def get_effective_parameters(self, host_name: str, service_name: str, 
                           ruleset: Optional[str] = None) -> Dict[str, Any]:
    """Legacy method - delegates to get_service_effective_parameters."""
```

### Parameter Service Updates

The `ParameterService` class has been updated to:

1. **Use correct API methods** for getting effective parameters
2. **Create rules properly** when setting parameters
3. **Handle response formats** from service discovery
4. **Provide better error handling** for missing services/parameters

## Error Handling

### Service Not Found
When a service doesn't exist or isn't discoverable:
```json
{
  "status": "not_found",
  "message": "Service 'Unknown Service' not found on host 'server01'"
}
```

### Parameters Not Available
When parameters aren't in discovery data:
```json
{
  "status": "partial",
  "parameters": {"note": "Parameters not available in discovery data"},
  "source": "service_monitoring"
}
```

### Ruleset Not Found
When we can't determine the appropriate ruleset:
```json
{
  "status": "error",
  "message": "Cannot determine parameter ruleset for service: Unknown Service"
}
```

## Best Practices

### 1. Always Use Service Discovery for Reading
- Service discovery contains the most accurate parameter information
- It reflects what Checkmk actually uses for monitoring
- Includes check plugin and configuration details

### 2. Create Specific Rules for Writing
- Use specific host and service patterns when possible
- Choose appropriate rulesets based on service type
- Include descriptive comments for maintainability

### 3. Understand Rule Precedence
- Checkmk evaluates rules in specific order
- More specific rules (lower in folders) take precedence
- Rule order within a ruleset matters

### 4. Test Parameter Changes
- Always verify effective parameters after creating rules
- Use discovery to confirm changes took effect
- Consider Checkmk configuration activation requirements

## Migration Guide

### From Old Implementation
```python
# OLD - Manual rule evaluation (incorrect)
result = client.get_effective_parameters(host, service, ruleset)
parameters = result["parameters"]

# NEW - Service discovery approach (correct)
result = client.get_service_effective_parameters(host, service)
parameters = result["parameters"]
```

### For Parameter Setting
```python
# OLD - Direct parameter setting (didn't exist properly)
# This was never correctly implemented

# NEW - Rule-based parameter setting (correct)
rule = client.create_service_parameter_rule(
    ruleset_name="checkgroup_parameters:temperature",
    folder="/",
    parameters={"levels": (75.0, 85.0)},
    host_name=host,
    service_pattern=service
)
```

## Testing

Use the provided test script to validate the implementation:

```bash
python test_corrected_parameters.py --host your-host --service your-service
```

This script demonstrates:
1. Getting effective parameters correctly
2. Finding existing parameter rules
3. Creating new parameter rules (when uncommented)

## Conclusion

The corrected implementation now properly aligns with Checkmk's architecture:

- **Parameters come from service discovery** (computed by Checkmk)
- **Parameter changes use rule management** (the correct way)
- **Rule evaluation is left to Checkmk** (not manually implemented)
- **Error handling covers edge cases** (missing services, unknown rulesets)

This approach is more reliable, maintainable, and follows Checkmk's intended API usage patterns.