# Add Host Check Configuration Prompts

## Goal
Add three new MCP prompts that allow users to configure host check behavior:
1. **Maximum Check Attempts** - Adjust how many failed checks trigger a DOWN state
2. **Retry Check Interval** - Configure time between retry attempts when host is in soft state
3. **Check Timeout** - Set maximum time to wait for check response

These address the need to tune host check sensitivity based on network quality and reliability requirements.

## Background

### Use Case
Users need to adjust host check attempts when:
- Network connections are unreliable (increase attempts to reduce false positives)
- Network is stable and fast detection is needed (decrease attempts for quicker alerts)
- Different hosts require different sensitivity levels based on their importance or network location

### Technical Context
In Checkmk, host checks (typically ICMP ping) use several parameters to control behavior:

1. **`max_check_attempts`** - Number of consecutive failed checks before host enters hard DOWN state
   - Attribute: `host_max_check_attempts` in monitoring data
   - Ruleset: `extra_host_conf:max_check_attempts`
   
2. **`retry_interval`** - Time between checks when host is in soft problem state
   - Attribute: `host_retry_interval` (in interval units)
   - Ruleset: `extra_host_conf:retry_interval`
   
3. **`check_timeout`** - Maximum time to wait for check response
   - For SNMP: `snmp_timing` ruleset with timeout/retries
   - For active checks: `active_checks:icmp` or check command timeout

## Implementation Design

### Prompt Definitions

#### 1. Adjust Host Check Attempts
```python
"adjust_host_check_attempts": Prompt(
    name="adjust_host_check_attempts",
    description="Configure host check sensitivity by adjusting maximum check attempts",
    arguments=[
        {
            "name": "host_name",
            "description": "Name of the host to configure (or 'all' for global rule)",
            "required": True,
        },
        {
            "name": "max_attempts", 
            "description": "Maximum number of check attempts before host is considered down (1-10)",
            "required": True,
        },
        {
            "name": "reason",
            "description": "Reason for adjustment (e.g., 'unreliable network', 'critical host')",
            "required": False,
        }
    ],
)
```

#### 2. Adjust Host Retry Interval
```python
"adjust_host_retry_interval": Prompt(
    name="adjust_host_retry_interval",
    description="Configure retry interval for host checks when in soft problem state",
    arguments=[
        {
            "name": "host_name",
            "description": "Name of the host to configure (or 'all' for global rule)",
            "required": True,
        },
        {
            "name": "retry_interval", 
            "description": "Retry interval in minutes (0.1-60)",
            "required": True,
        },
        {
            "name": "reason",
            "description": "Reason for adjustment (e.g., 'reduce load', 'faster recovery detection')",
            "required": False,
        }
    ],
)
```

#### 3. Adjust Host Check Timeout
```python
"adjust_host_check_timeout": Prompt(
    name="adjust_host_check_timeout",
    description="Configure timeout for host check commands",
    arguments=[
        {
            "name": "host_name",
            "description": "Name of the host to configure (or 'all' for global rule)",
            "required": True,
        },
        {
            "name": "timeout_seconds", 
            "description": "Timeout in seconds (1-60)",
            "required": True,
        },
        {
            "name": "check_type",
            "description": "Type of check: 'icmp', 'snmp', or 'all' (default: 'icmp')",
            "required": False,
        },
        {
            "name": "reason",
            "description": "Reason for adjustment (e.g., 'slow network', 'distant location')",
            "required": False,
        }
    ],
)
```

### Prompt Handler Implementation
Each handler should:
1. Validate input parameters (within valid ranges)
2. Retrieve current host configuration and monitoring data
3. Determine appropriate ruleset based on prompt type
4. Check for existing rules and handle conflicts
5. Create or update the rule
6. Generate comprehensive prompt text with analysis

### Expected Prompt Outputs

#### 1. Check Attempts Output
```
Configure host check sensitivity for '{host_name}'

CURRENT CONFIGURATION:
- Host: {host_name}
- Current max check attempts: {current_attempts}
- Current retry interval: {retry_interval} minutes
- Check interval: {check_interval} minutes
- Current sensitivity: {high/medium/low based on attempts}

PROPOSED CHANGE:
- New max check attempts: {new_attempts}
- Reason: {reason or 'Not specified'}
- Impact: Host must fail {new_attempts} consecutive checks before DOWN state

ANALYSIS:
1. Detection timing:
   - Current: DOWN state after {current_time} ({current_attempts} × {check_interval} min)
   - Proposed: DOWN state after {new_time} ({new_attempts} × {check_interval} min)

2. Recommendations:
   - Stable networks: 1-2 attempts (fast detection)
   - Normal networks: 3-4 attempts (balanced)
   - Unreliable networks: 5-10 attempts (reduce false alerts)

CONFIGURATION:
Creating rule in folder '{folder}' with ruleset 'extra_host_conf:max_check_attempts'
```

#### 2. Retry Interval Output
```
Configure host retry interval for '{host_name}'

CURRENT CONFIGURATION:
- Host: {host_name}
- Normal check interval: {check_interval} minutes
- Current retry interval: {current_retry} minutes
- Max check attempts: {max_attempts}

PROPOSED CHANGE:
- New retry interval: {new_retry} minutes
- Reason: {reason or 'Not specified'}

IMPACT ANALYSIS:
1. Soft state behavior:
   - When host enters soft DOWN state, checks will run every {new_retry} minutes
   - Total time to hard state: {new_retry} × ({max_attempts} - 1) = {total_time} minutes
   
2. Resource impact:
   - More frequent retries: Higher load but faster recovery detection
   - Less frequent retries: Lower load but slower recovery detection

3. Best practices:
   - Fast recovery needed: 0.5-1 minute
   - Balanced approach: 1-5 minutes  
   - Resource constrained: 5-10 minutes

CONFIGURATION:
Creating rule in folder '{folder}' with ruleset 'extra_host_conf:retry_interval'
```

#### 3. Check Timeout Output
```
Configure host check timeout for '{host_name}'

CURRENT CONFIGURATION:
- Host: {host_name}
- Check type: {icmp/snmp/tcp}
- Current timeout: {current_timeout} seconds
- Network latency: {estimated based on location/tags}

PROPOSED CHANGE:
- New timeout: {new_timeout} seconds
- Check type affected: {check_type}
- Reason: {reason or 'Not specified'}

ANALYSIS:
1. Timeout implications:
   - Too short: False DOWN states due to network delays
   - Too long: Delayed detection of actual problems
   
2. Recommendations by network type:
   - LAN/Ethernet: 1-5 seconds
   - Good WiFi (5GHz): 3-8 seconds
   - Normal WiFi (2.4GHz): 5-12 seconds
   - Poor WiFi/Congested: 10-20 seconds
   - WAN/Internet: 5-15 seconds
   - Slow Internet (DSL/Cable): 15-25 seconds
   - Mobile/Cellular: 20-35 seconds
   - Satellite/Distant: 25-45 seconds
   - Very high-latency: 45-60 seconds

3. Performance impact:
   - Longer timeouts may delay check scheduling
   - Consider network RTT: timeout should be > 3×RTT

CONFIGURATION:
{For ICMP}: Creating rule 'active_checks:icmp' with timeout parameter
{For SNMP}: Creating rule 'snmp_timing' with timeout and retry settings
```

## Technical Requirements

### 1. API Integration
- Use existing rule management endpoints (`/domain-types/rule/collections/all`)
- **⚠️ CRITICAL**: Validate exact ruleset names against Checkmk 2.4 API before implementation:
  - Max attempts: `extra_host_conf:max_check_attempts` (verify in API docs)
  - Retry interval: `extra_host_conf:retry_interval` (verify in API docs)
  - ICMP timeout: `active_checks:icmp` (verify parameter structure)
  - SNMP timeout: `snmp_timing` (verify parameter structure)
- **Rule Conflict Resolution**: Implement strategy for handling existing rules:
  - Priority-based updates (higher priority wins)
  - Rule merging for compatible configurations
  - Explicit user confirmation for conflicts
- **Folder Hierarchy**: Follow existing folder structure patterns
- **Transaction Safety**: Use atomic operations where possible

### 2. Parameter Validation & Data Integrity
- **Max attempts**: Integer 1-10 with business logic validation:
  - Warn if attempts > 5 (may delay detection)
  - Error if attempts < 1 (invalid configuration)
  - Consider network reliability context
- **Retry interval**: Float 0.1-60 (minutes) with constraints:
  - Must be positive and non-zero
  - Validate against check_interval (retry should be ≤ normal interval)
  - Convert to appropriate Checkmk interval units
- **Timeout**: Integer 1-60 (seconds) with network-aware validation:
  - Minimum based on estimated RTT (timeout > 3×RTT recommended)
  - Maximum reasonable for check type (SNMP vs ICMP)
  - Validate against overall check budget
- **Host Validation**: Multi-tier validation strategy:
  - Check host existence in Checkmk
  - Validate host accessibility and check configuration
  - Handle wildcard patterns safely ('*' matching)
- **Permission Validation**: Pre-flight permission checks
- **Unit Conversion Safety**: Implement precise floating-point conversions with validation

### 3. Integration Points & Architecture
- **MCP Integration**: Follow existing prompt registration patterns in `CheckmkMCPServer`:
  - Add to `_prompts` dictionary with proper Prompt objects
  - Implement handlers in `get_prompt()` switch statement
  - Maintain consistent error handling with other prompts
- **Service Layer Integration**:
  - Use `api_client.create_rule()` and `update_rule()` methods
  - Leverage `host_service` for current host configuration
  - Utilize `parameter_service` for rule conflict detection
- **Data Flow Architecture**:
  ```
  User Request → Prompt Handler → Validation Layer → 
  API Client → Checkmk REST API → Response Formatter
  ```
- **Consistent Error Propagation**: Follow existing error handling patterns
- **Logging Strategy**: Implement structured logging for rule operations

## Architectural Considerations

### 1. Error Recovery & Resilience
- **Transactional Operations**: Implement rollback capability for failed rule updates
- **Graceful Degradation**: Provide degraded functionality if some API calls fail
- **Idempotency**: Ensure operations can be safely retried
- **Circuit Breaker Pattern**: Protect against cascading API failures

### 2. Performance & Scalability
- **Batch Operations**: Consider bulk rule updates for efficiency
- **Caching Strategy**: Cache rule lookups and host validation results
- **Rate Limiting**: Respect Checkmk API rate limits
- **Async Processing**: Use async patterns for I/O-heavy operations

### 3. Security & Compliance
- **Input Sanitization**: Validate all user inputs for security
- **Audit Logging**: Log all rule changes for compliance
- **Permission Enforcement**: Validate user permissions before operations
- **Data Validation**: Use Pydantic models for type safety

### 4. Maintainability & Extensibility
- **Code Reuse**: Leverage existing rule management utilities
- **Pattern Consistency**: Follow established MCP prompt patterns
- **Test Coverage**: Implement comprehensive unit and integration tests
- **Documentation**: Maintain in-line documentation and examples

### 5. Monitoring & Observability
- **Operation Metrics**: Track rule creation success/failure rates
- **Performance Monitoring**: Monitor response times and API usage
- **Health Checks**: Validate rule effectiveness over time
- **Error Analysis**: Categorize and analyze common failure patterns

## Implementation Checklist

### Phase 1: Research and Validation
- [ ] Confirm exact ruleset names work with Checkmk 2.4 API:
  - [ ] `extra_host_conf:max_check_attempts` 
  - [ ] `extra_host_conf:retry_interval`
  - [ ] `active_checks:icmp` for ICMP timeout
  - [ ] `snmp_timing` for SNMP timeout
- [ ] Test rule creation with each ruleset
- [ ] Verify parameter formats and value_raw encoding
- [ ] Test retrieval of current host monitoring attributes
- [ ] Document interval unit conversions

### Phase 2: Core Implementation - Check Attempts
- [ ] Add `adjust_host_check_attempts` to `_prompts` dictionary
- [ ] Implement handler with:
  - [ ] Host validation (exists or 'all')
  - [ ] Current config retrieval via monitoring API
  - [ ] Rule creation with proper conditions
  - [ ] Comprehensive prompt text generation
- [ ] Add parameter validation (1-10 range)
- [ ] Handle existing rules and priorities

### Phase 3: Core Implementation - Retry Interval
- [ ] Add `adjust_host_retry_interval` to `_prompts` dictionary
- [ ] Implement handler with:
  - [ ] Retry interval validation (0.1-60 minutes)
  - [ ] Unit conversion (minutes to interval units)
  - [ ] Impact calculation based on max_attempts
  - [ ] Resource usage analysis in prompt
- [ ] Test with various interval values

### Phase 4: Core Implementation - Check Timeout
- [ ] Add `adjust_host_check_timeout` to `_prompts` dictionary
- [ ] Implement handler with:
  - [ ] Check type detection (ICMP vs SNMP)
  - [ ] Appropriate ruleset selection
  - [ ] Network latency estimation
  - [ ] Different timeout handling for check types
- [ ] Handle both ICMP and SNMP timeout rules

### Phase 5: Error Handling & Resilience
- [ ] **Host Validation Errors**:
  - [ ] Non-existent hosts with suggestions for similar names
  - [ ] Invalid wildcard patterns with usage examples
  - [ ] Hosts with no check configuration
- [ ] **API Communication Errors**:
  - [ ] Network connectivity failures with retry strategy
  - [ ] API rate limiting with backoff implementation
  - [ ] Malformed API responses with fallback handling
- [ ] **Rule Management Errors**:
  - [ ] Ruleset availability validation with alternatives
  - [ ] Rule conflict detection with resolution options
  - [ ] Invalid rule parameters with correction suggestions
- [ ] **Transaction Safety**:
  - [ ] Atomic operations with rollback capability
  - [ ] Partial failure recovery with state consistency
  - [ ] Operation tracking for audit and debugging

### Phase 6: Testing & Validation
- [ ] **Unit Testing**:
  - [ ] Parameter validation logic with boundary conditions
  - [ ] Rule creation logic with mock API responses
  - [ ] Error handling paths with exception scenarios
  - [ ] Data conversion utilities with precision validation
- [ ] **Integration Testing**:
  - [ ] End-to-end prompt execution with real API
  - [ ] Rule conflict resolution in live environment
  - [ ] Permission validation with different user roles
  - [ ] Multi-step operations with state verification
- [ ] **Functional Testing**:
  - [ ] Single host configuration scenarios
  - [ ] Global rules with 'all' pattern matching
  - [ ] Parameter boundary testing (min/max values)
  - [ ] Complex rule combinations and interactions
- [ ] **Error Scenario Testing**:
  - [ ] Invalid host names and pattern matching
  - [ ] Out-of-range parameters with validation messages
  - [ ] Permission denied scenarios with clear messaging
  - [ ] API failures with recovery and retry logic
- [ ] **Performance Testing**:
  - [ ] Concurrent rule operations under load
  - [ ] Large-scale host pattern matching
  - [ ] API rate limiting and backoff behavior
- [ ] **Security Testing**:
  - [ ] Input injection attempts and sanitization
  - [ ] Authorization bypass testing
  - [ ] Data leakage prevention validation

### Phase 7: Documentation
- [ ] Update README.md with all three prompts
- [ ] Add comprehensive examples to USAGE_EXAMPLES.md
- [ ] Document in MCP prompts section
- [ ] Update prompt count (add 3 to current count)
- [ ] Add troubleshooting guide
- [ ] Document best practices for each parameter

## Usage Examples

### Check Attempts Examples
```
# Example 1: Increase attempts for unreliable host
User: "The network connection to remote-office-01 is unreliable"
Assistant uses: adjust_host_check_attempts(
    host_name="remote-office-01",
    max_attempts=6,
    reason="unreliable network connection"
)

# Example 2: Decrease attempts for critical host
User: "I need faster alerting for the main database server"
Assistant uses: adjust_host_check_attempts(
    host_name="prod-db-01", 
    max_attempts=1,
    reason="critical host requiring fast detection"
)
```

### Retry Interval Examples
```
# Example 1: Faster recovery detection
User: "I want quicker recovery detection for web servers"
Assistant uses: adjust_host_retry_interval(
    host_name="web-server-01",
    retry_interval=0.5,
    reason="fast recovery detection needed"
)

# Example 2: Reduce monitoring load
User: "The monitoring is causing too much load during problems"
Assistant uses: adjust_host_retry_interval(
    host_name="all",
    retry_interval=10,
    reason="reduce monitoring load during outages"
)
```

### Check Timeout Examples
```
# Example 1: Satellite connection
User: "Our satellite office has high latency"
Assistant uses: adjust_host_check_timeout(
    host_name="satellite-office-01",
    timeout_seconds=30,
    check_type="icmp",
    reason="satellite connection with high latency"
)

# Example 2: SNMP timeout for slow devices
User: "The old switches take forever to respond to SNMP"
Assistant uses: adjust_host_check_timeout(
    host_name="old-switch-*",
    timeout_seconds=15,
    check_type="snmp",
    reason="legacy hardware with slow SNMP response"
)

# Example 3: WiFi-connected devices
User: "The warehouse scanners are on WiFi and sometimes have delays"
Assistant uses: adjust_host_check_timeout(
    host_name="warehouse-scanner-*",
    timeout_seconds=10,
    check_type="icmp",
    reason="WiFi-connected devices with variable latency"
)

# Example 4: Poor WiFi connection
User: "The guest network access points have terrible WiFi signal"
Assistant uses: adjust_host_check_timeout(
    host_name="guest-ap-*",
    timeout_seconds=20,
    check_type="icmp",
    reason="poor WiFi signal causing packet loss and retransmissions"
)

# Example 5: Slow internet connection
User: "Our branch office has only a 1Mbps DSL connection"
Assistant uses: adjust_host_check_timeout(
    host_name="branch-office-router",
    timeout_seconds=25,
    check_type="icmp",
    reason="slow DSL internet connection with limited bandwidth"
)

# Example 6: Mobile hotspot devices
User: "Field technicians use mobile hotspots that can be unreliable"
Assistant uses: adjust_host_check_timeout(
    host_name="field-hotspot-*",
    timeout_seconds=35,
    check_type="icmp",
    reason="mobile cellular connection with variable signal strength"
)

# Example 7: IoT devices on congested WiFi
User: "The IoT sensors are on a congested 2.4GHz network"
Assistant uses: adjust_host_check_timeout(
    host_name="iot-sensor-*",
    timeout_seconds=15,
    check_type="icmp",
    reason="congested 2.4GHz WiFi with many competing devices"
)
```

### Combined Configuration Example
```
User: "Configure the remote site for unreliable WAN connection"
Assistant would use all three prompts:
1. adjust_host_check_attempts(host_name="remote-site-01", max_attempts=5)
2. adjust_host_retry_interval(host_name="remote-site-01", retry_interval=2)
3. adjust_host_check_timeout(host_name="remote-site-01", timeout_seconds=15)
```

## Critical Technical Validation Required

### **🔴 HIGH PRIORITY - Must Resolve Before Implementation**

1. **API Compatibility Verification**:
   - **Action Required**: Test ruleset names against Checkmk 2.4 API:
     - `extra_host_conf:max_check_attempts` - validate parameter format
     - `extra_host_conf:retry_interval` - verify unit expectations (seconds/minutes/intervals)
     - `active_checks:icmp` - confirm timeout parameter structure
     - `snmp_timing` - validate timeout and retry parameter schema
   - **Risk**: Implementation failure if rulesets don't exist or have different schemas
   - **Mitigation**: Create API validation test suite before development

2. **Rule Conflict Strategy**:
   - **Decision Required**: Conflict resolution approach:
     - Option A: Update existing rules with user confirmation
     - Option B: Create higher-priority rules (recommended for safety)
     - Option C: Merge compatible configurations
   - **Implementation**: Design user experience for conflict scenarios
   - **Rollback**: Ensure all changes can be undone safely

3. **Unit Conversion Precision**:
   - **Investigation Needed**: Checkmk interval unit expectations:
     - retry_interval: minutes → interval units conversion factor
     - Data type requirements (float vs integer)
     - Precision requirements and rounding behavior
   - **Testing Required**: Validate conversions with edge cases

### **🟡 MEDIUM PRIORITY - Design Decisions**

4. **Timeout Configuration Scope**:
   - **Research Required**: ICMP timeout configuration capabilities:
     - Per-host vs global timeout settings
     - Multiple check types per host handling
     - Service-level vs host-level timeout precedence
   - **Architecture Impact**: May require multiple prompt handlers

5. **Feature Scope Expansion**:
   - **Future Consideration**: Additional monitoring parameters:
     - Normal check_interval configuration
     - Flap detection threshold management
     - Check time period (business hours) configuration
   - **Recommendation**: Implement core features first, expand based on usage

### **🟢 LOW PRIORITY - Enhancement Opportunities**

6. **Intelligent Defaults**:
   - **Enhancement**: Network-aware parameter suggestions
   - **Implementation**: Host tag-based recommendations
   - **Value**: Improved user experience and configuration quality

## Risk Assessment Matrix

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| API Schema Mismatch | Medium | High | Pre-implementation API testing |
| Rule Conflicts | High | Medium | Robust conflict detection |
| Unit Conversion Errors | Low | High | Comprehensive conversion testing |
| Permission Issues | Medium | Medium | Permission validation framework |
| Performance Degradation | Low | Medium | Load testing and optimization |

## Success Criteria

1. **Functionality**:
   - All three prompts work correctly for individual hosts
   - Global rules ('all' hosts) apply properly
   - Parameters are validated and converted correctly
   - Rules are created in appropriate rulesets

2. **User Experience**:
   - Natural language requests trigger appropriate prompts
   - Clear explanation of current vs proposed configuration
   - Impact analysis helps users make informed decisions
   - Best practices guidance included

3. **Integration**:
   - Seamless integration with existing MCP prompt system
   - No disruption to existing monitoring setup
   - Proper error handling and recovery
   - Consistent with other prompt patterns

4. **Documentation**:
   - All prompts documented in README
   - Usage examples cover common scenarios
   - Troubleshooting guide available

## Future Enhancements

1. **Bulk Configuration**:
   - Configure multiple hosts with pattern matching
   - Apply different settings based on host tags/labels
   - Import/export configuration templates

2. **Intelligent Recommendations**:
   - Analyze historical check results to suggest optimal settings
   - Detect network quality patterns
   - Auto-adjust based on time of day/week

3. **Advanced Parameters**:
   - Normal check intervals
   - Flap detection thresholds
   - Check time periods (business hours vs off-hours)
   - Notification delays

4. **Service-Level Configuration**:
   - Similar prompts for service checks
   - Service-specific retry and timeout settings
   - Custom check command parameters

5. **Monitoring Integration**:
   - Show impact of changes on monitoring performance
   - Track rule effectiveness over time
   - Alert on configuration drift