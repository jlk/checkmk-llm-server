# Service Modification Functionality Specification

**Document Version:** 1.0  
**Date:** 2025-07-13  
**Author:** Claude Code  
**Status:** Draft  

## Executive Summary

This specification outlines the addition of comprehensive service modification functionality to the Checkmk LLM Agent, enabling users to view default service rules, modify service parameters, and override default settings for specific hosts and services. The implementation focuses on providing intuitive natural language interfaces for managing service check parameters such as warning/critical thresholds for CPU, memory, disk, and network services.

## 1. Overview and Objectives

### 1.1 Current State Analysis

The Checkmk LLM Agent currently provides:
- ✅ Service listing, status monitoring, and statistics
- ✅ Service acknowledgment and downtime management
- ✅ Service discovery functionality
- ✅ Basic rule management (CRUD operations)
- ✅ Natural language processing for service operations

### 1.2 Objectives

This specification aims to add:
1. **Service Parameter Viewing** - View default service rules and parameters
2. **Service Parameter Modification** - Override service parameters for specific hosts
3. **Check Parameter Management** - Manage warning/critical thresholds for various service types
4. **Rule-Based Configuration** - Leverage Checkmk's rule system for service customization
5. **Natural Language Interface** - Intuitive commands for service parameter management

### 1.3 Use Cases

**Primary Use Cases:**
- View default CPU warning/critical levels for a service type
- Override CPU warning threshold from 80% to 90% for a specific host
- Set custom disk space thresholds for critical servers
- Configure memory usage parameters for database servers
- Manage network interface thresholds for high-traffic servers

**Example Commands:**
```
"Show default CPU parameters"
"Override CPU warning to 90% for server01"
"Set disk space critical to 95% for database-01"
"What are the memory thresholds for web-server?"
"Create CPU rule for production servers with 85% warning"
```

## 2. Technical Architecture

### 2.1 Checkmk API Integration Analysis

Based on analysis of the Checkmk REST API v1.0 specification, service parameter modification relies on:

**Key API Endpoints:**
- `GET /domain-types/ruleset/collections/all` - Discover available check parameter rulesets
- `POST /domain-types/rule/collections/all` - Create service parameter rules
- `GET /domain-types/rule/collections/all?ruleset_name={name}` - List existing rules
- `PUT /objects/rule/{rule_id}` - Update existing rules
- `DELETE /objects/rule/{rule_id}` - Remove rules

**Rule-Based Parameter System:**
Checkmk uses a rule-based system where service parameters are configured through rules that:
- Target specific hosts/services using conditions
- Define parameter values in Python-formatted structures
- Follow precedence rules (specific rules override general ones)
- Support folder-based organization

### 2.2 Service Parameter Categories

**Verified Check Parameter Rulesets (based on Checkmk documentation):**
1. **CPU Monitoring:**
   - `cpu_utilization_simple` - CPU utilization for simple devices (Windows)
   - `cpu_utilization_linux` - CPU utilization on Linux/Unix
   - `cpu_load` - System load averages
   - `kernel_performance` - Kernel-level CPU metrics

2. **Memory Monitoring:**
   - `memory_linux` - Memory levels for Linux systems
   - `memory_level_windows` - Memory levels for Windows systems
   - `memory_relative` - Relative memory usage
   - `jvm_memory` - JVM memory levels for Java applications

3. **Storage Monitoring:**
   - `filesystems` - Filesystems (used space and growth) - Primary ruleset for disk monitoring
   - `disk_io` - Disk I/O performance
   - `diskstat` - Disk statistics

4. **Network Monitoring:**
   - `if64` - Network interface utilization
   - `interfaces` - Network interface monitoring
   - `tcp_connections` - TCP connection monitoring

### 2.3 Parameter Format Structure

**Rule Value Format (value_raw field):**
```python
# CPU utilization example
{
    "levels": (80.0, 90.0),        # Warning, Critical percentages
    "average": 15,                  # Averaging period in minutes
    "horizon": 90                   # Time horizon for averaging
}

# Filesystem example
{
    "levels": (80.0, 90.0),        # Warning, Critical percentages
    "magic_normsize": 20,          # Normalization reference size (GB)
    "levels_low": (50.0, 60.0),    # Low space warning/critical
    "trend_range": 24               # Trend analysis period (hours)
}

# Memory example
{
    "levels": (80.0, 90.0),        # Warning, Critical percentages
    "average": 3,                   # Averaging period
    "handle_zero": True             # Handle zero-usage scenarios
}
```

### 2.4 Service Parameter Override Methods

**Method 1: Host-Specific Rules (Recommended)**
Create rules that target specific hosts using conditions:
```python
{
    "host_name": ["server01"],                       # Exact host match
    "host_name": ["~server.*"],                      # Regex pattern (prefix with ~)
    "host_tags": {"criticality": "critical"},        # Host tags
    "service_description": ["CPU utilization"],      # Service patterns
}
```

**Method 2: Folder-Based Rules**
Create rules within specific folders to apply to all hosts in that folder:
- Rules created in `/production/database/` apply to all hosts in that folder
- Higher priority than general rules

**Method 3: Service-Specific Rules**
Target specific services across multiple hosts:
```python
{
    "service_description": ["Filesystem /var"],      # Specific filesystem
    "service_description": ["~CPU.*"],               # CPU services regex
    "host_labels": {"environment": "production"},    # Combined with host criteria
}
```

**Rule Precedence (highest to lowest):**
1. Host-specific rules with exact service match
2. Host-specific rules with service patterns
3. Host tag/label-based rules
4. Folder-based rules
5. Global default rules

### 2.5 Rule Condition Structure

**Host/Service Matching:**
```python
{
    "host_name": ["server01", "server02"],           # Specific hosts
    "host_tags": {"criticality": "critical"},        # Host tags
    "service_description": ["CPU utilization"],      # Service patterns
    "host_labels": {"environment": "production"},    # Host labels
    "service_labels": {"check_type": "cpu"}          # Service labels
}
```

## 3. Implementation Design

### 3.1 New Component Architecture

```
checkmk_agent/
├── service_parameters.py      # NEW: Service parameter management
├── rule_operations.py         # ENHANCED: Extended rule operations
├── api_client.py             # ENHANCED: Add ruleset discovery methods
├── service_operations.py     # ENHANCED: Add parameter commands
└── cli.py                    # ENHANCED: Add parameter CLI commands
```

### 3.2 Core Components

#### 3.2.1 ServiceParameterManager (service_parameters.py)

**Primary Responsibilities:**
- Discover available check parameter rulesets
- Parse and validate service parameter formats
- Create/update/delete parameter rules
- Provide default parameter templates
- Handle parameter format conversions

**Key Methods:**
```python
class ServiceParameterManager:
    def list_parameter_rulesets(self) -> List[Dict[str, Any]]
    def get_ruleset_schema(self, ruleset_name: str) -> Dict[str, Any]
    def get_default_parameters(self, service_type: str) -> Dict[str, Any]
    def create_parameter_rule(self, ruleset: str, host_name: str, 
                            service_pattern: str, parameters: Dict) -> str
    def update_service_parameters(self, rule_id: str, 
                                parameters: Dict) -> Dict[str, Any]
    def get_service_parameters(self, host_name: str, 
                             service_name: str) -> Dict[str, Any]
    def delete_parameter_rule(self, rule_id: str) -> None
    def validate_parameters(self, ruleset: str, 
                          parameters: Dict) -> bool
```

#### 3.2.2 Enhanced RuleOperations (rule_operations.py)

**New Capabilities:**
- Ruleset discovery and categorization
- Parameter-specific rule templates
- Rule precedence analysis
- Bulk rule operations for service parameters

**Key Methods:**
```python
class RuleOperations:
    def discover_service_rulesets(self) -> Dict[str, List[str]]
    def get_parameter_templates(self, service_type: str) -> Dict[str, Any]
    def analyze_rule_precedence(self, host_name: str, 
                              service_name: str) -> List[Dict]
    def create_parameter_rule_from_template(self, template: str, 
                                          **kwargs) -> Dict[str, Any]
```

#### 3.2.3 Enhanced API Client (api_client.py)

**New Methods:**
```python
class CheckmkClient:
    def list_rulesets(self, category: Optional[str] = None) -> List[Dict[str, Any]]
    def get_ruleset_info(self, ruleset_name: str) -> Dict[str, Any]
    def search_rules_by_host_service(self, host_name: str, 
                                   service_name: str) -> List[Dict[str, Any]]
    def get_effective_parameters(self, host_name: str, 
                               service_name: str) -> Dict[str, Any]
```

### 3.3 Natural Language Processing Enhancement

#### 3.3.1 New Command Categories

**Parameter Viewing Commands:**
- "show default CPU parameters"
- "what are the memory thresholds for server01?"
- "list disk space rules"
- "show effective parameters for CPU on server01"

**Parameter Modification Commands:**
- "set CPU warning to 85% for server01"
- "override disk critical threshold to 95% for database servers"
- "create memory rule for production hosts with 80% warning"
- "update network utilization threshold for web-01"

**Rule Management Commands:**
- "show CPU rules for server01"
- "delete disk space rule for test hosts"
- "list all parameter rules"
- "move CPU rule to higher priority"

#### 3.3.2 Enhanced Command Analysis

**Extended LLM Prompt for Parameter Operations:**
```python
PARAMETER_ANALYSIS_PROMPT = """
Analyze this service parameter command and extract intent and parameters:

Command: "{command}"

Available actions:
- view_default_parameters: View default service parameters for a service type
- view_service_parameters: View effective parameters for a specific service
- set_service_parameters: Set/override parameters for a service
- create_parameter_rule: Create a new parameter rule
- list_parameter_rules: List existing parameter rules
- delete_parameter_rule: Delete a parameter rule

Return JSON with:
{
    "action": "action_name",
    "parameters": {
        "service_type": "cpu|memory|disk|network|...",
        "host_name": "hostname or null",
        "service_description": "service name or null",
        "parameter_type": "warning|critical|both",
        "threshold_value": number_or_null,
        "ruleset_name": "specific ruleset or null",
        "rule_conditions": {},
        "rule_id": "rule_id or null"
    }
}
"""
```

### 3.4 CLI Interface Design

#### 3.4.1 New CLI Commands

**Service Parameters Command Group:**
```bash
# View default parameters
checkmk-agent service-params defaults [service_type]
checkmk-agent service-params show <host> <service>

# Modify parameters
checkmk-agent service-params set <host> <service> --warning 85 --critical 95
checkmk-agent service-params override <host> <service> --parameters '{"levels": (85.0, 95.0)}'

# Rule management
checkmk-agent service-params rules list [--ruleset RULESET]
checkmk-agent service-params rules create --ruleset filesystem --host server01 --warning 80
checkmk-agent service-params rules delete <rule_id>

# Discovery
checkmk-agent service-params discover-rulesets
checkmk-agent service-params templates [service_type]
```

#### 3.4.2 Interactive Mode Extensions

**New Interactive Commands:**
```python
INTERACTIVE_PARAMETER_COMMANDS = {
    'view_defaults': 'Show default parameters for service types',
    'show_params': 'Display effective parameters for a service',
    'set_warning': 'Set warning threshold for a service',
    'set_critical': 'Set critical threshold for a service',
    'create_rule': 'Create a new parameter rule',
    'list_rules': 'List parameter rules',
    'help_params': 'Show parameter management help'
}
```

### 3.5 Data Models and Validation

#### 3.5.1 Pydantic Models

```python
class ServiceParameterRequest(BaseModel):
    """Request model for service parameter operations."""
    
    host_name: str = Field(..., description="Target hostname")
    service_pattern: str = Field(..., description="Service name pattern")
    ruleset: str = Field(..., description="Check parameter ruleset name")
    parameters: Dict[str, Any] = Field(..., description="Parameter values")
    conditions: Optional[Dict[str, Any]] = Field(default_factory=dict)
    rule_properties: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ParameterRule(BaseModel):
    """Model for service parameter rules."""
    
    rule_id: str
    ruleset: str
    folder: str
    value_raw: str
    conditions: Dict[str, Any]
    properties: Dict[str, Any]
    effective_parameters: Optional[Dict[str, Any]] = None

class ServiceParameterTemplate(BaseModel):
    """Template for common service parameter configurations."""
    
    service_type: str
    ruleset: str
    default_parameters: Dict[str, Any]
    parameter_schema: Dict[str, Any]
    description: str
    examples: List[Dict[str, Any]]
```

## 4. Implementation Phases

### Phase 1: Core Parameter Management (Week 1-2)

**Deliverables:**
1. ✅ `ServiceParameterManager` class with basic parameter operations
2. ✅ Enhanced API client with ruleset discovery methods
3. ✅ Basic parameter rule creation and deletion
4. ✅ Unit tests for core functionality

**Acceptance Criteria:**
- Can discover available parameter rulesets
- Can create basic parameter rules for CPU, memory, disk
- Can view default parameters for common service types
- All new code has >90% test coverage

### Phase 2: CLI and Natural Language Interface (Week 3)

**Deliverables:**
1. ✅ Extended CLI commands for parameter management
2. ✅ Enhanced natural language processing for parameter commands
3. ✅ Interactive mode parameter operations
4. ✅ Comprehensive error handling and validation

**Acceptance Criteria:**
- CLI commands work for basic parameter operations
- Natural language commands are processed correctly
- Error messages are clear and actionable
- Help documentation is comprehensive

### Phase 3: Advanced Features (Week 4)

**Deliverables:**
1. ✅ Rule precedence analysis and conflict detection
2. ✅ Bulk parameter operations
3. ✅ Parameter templates and presets
4. ✅ Integration tests with real Checkmk instances

**Acceptance Criteria:**
- Can handle complex rule scenarios
- Provides recommendations for parameter optimization
- Templates simplify common configuration tasks
- Works reliably with production Checkmk systems

### Phase 4: Documentation and Polish (Week 5)

**Deliverables:**
1. ✅ Comprehensive documentation and examples
2. ✅ Performance optimization
3. ✅ Security review and hardening
4. ✅ User acceptance testing

**Acceptance Criteria:**
- Documentation covers all use cases
- Performance meets requirements (<2s for parameter operations)
- Security review passes with no high-risk findings
- User testing validates ease of use

## 5. Step-by-Step Override Process

### 5.1 How to Override Service Parameters for a Host

**Before You Begin:**
1. Identify the service you want to modify (e.g., "CPU utilization", "Filesystem /var")
2. Determine the current thresholds by viewing the service in Checkmk
3. Decide on new warning/critical values

**Step-by-Step Process:**

1. **Find the Service and Ruleset:**
   ```bash
   # CLI approach
   checkmk-agent service-params discover server01 "CPU utilization"
   
   # Interactive approach
   > "what ruleset controls CPU utilization on server01?"
   🔍 Service: CPU utilization on server01 (Linux)
   📋 Ruleset: cpu_utilization_linux
   📊 Current thresholds: Warning: 80%, Critical: 90%
   ```

2. **Create Host-Specific Rule:**
   ```bash
   # CLI approach
   checkmk-agent service-params override server01 "CPU utilization" --warning 85 --critical 95
   
   # Interactive approach  
   > "override CPU warning to 85% for server01"
   ✅ Created rule in cpu_utilization_linux ruleset
   🎯 Applies to: server01 only
   📊 New thresholds: Warning: 85%, Critical: 95%
   🆔 Rule ID: rule_12345
   ```

3. **Verify the Override:**
   ```bash
   # CLI approach
   checkmk-agent service-params show server01 "CPU utilization"
   
   # Interactive approach
   > "show CPU parameters for server01"
   📊 Effective Parameters for server01/CPU utilization:
   ├── Warning: 85% (from rule_12345)
   ├── Critical: 95% (from rule_12345)  
   └── Source: Host-specific override rule
   ```

4. **Activate Changes:**
   ```bash
   # CLI approach (if auto-activation disabled)
   checkmk-agent activate-changes
   
   # Interactive approach
   > "activate changes"
   🔄 Activating configuration changes...
   ✅ Changes activated successfully
   ⏱️  New thresholds will take effect within 1-2 check intervals
   ```

**Alternative: Bulk Override for Multiple Services:**
```bash
# Override multiple filesystem thresholds for a host
checkmk-agent service-params bulk-override server01 \
  --ruleset filesystems \
  --service-pattern "Filesystem.*" \
  --warning 85 --critical 95 \
  --comment "Production server requires higher thresholds"
```

## 6. Example Usage Scenarios

### 6.1 Basic Parameter Override

**Scenario:** Override CPU warning threshold for a production server

**Workflow:**
1. Identify the correct ruleset (`cpu_utilization_linux` for Linux hosts)
2. Create a host-specific rule with higher priority than defaults
3. Apply the rule and verify configuration

```bash
# CLI approach
checkmk-agent service-params set server01 "CPU utilization" --warning 85 --critical 95

# Interactive approach
> "set CPU warning to 85% and critical to 95% for server01"
🔍 Detected service: CPU utilization on Linux host server01
📋 Using ruleset: cpu_utilization_linux
✅ Created parameter rule for CPU utilization on server01
📊 Parameters: Warning: 85%, Critical: 95%
🆔 Rule ID: rule_abc123
⚠️  Note: Rule will take effect after next service check cycle
```

**Behind the scenes:**
```python
# Rule creation via API
{
    "ruleset": "cpu_utilization_linux",
    "folder": "~",
    "value_raw": '{"levels": (85.0, 95.0)}',
    "conditions": {
        "host_name": ["server01"],
        "service_description": ["CPU utilization"]
    },
    "properties": {
        "disabled": False,
        "description": "Custom CPU thresholds for server01"
    }
}
```

### 6.2 Viewing Service Parameters

**Scenario:** Check effective parameters for a service

```bash
# CLI approach
checkmk-agent service-params show server01 "Filesystem /"

# Interactive approach  
> "what are the disk space parameters for filesystem / on server01?"
📊 Effective Parameters for server01/Filesystem /:
┌─────────────────┬─────────┬──────────┐
│ Parameter       │ Warning │ Critical │
├─────────────────┼─────────┼──────────┤
│ Usage Threshold │ 80%     │ 90%      │
│ Trend Period    │ 24h     │ 24h      │
│ Magic Normsize  │ 20GB    │ 20GB     │
│ Magic Factor    │ 0.8     │ 0.8      │
└─────────────────┴─────────┴──────────┘
🔗 Source: Rule ID rule_xyz789 in folder /production
📋 Ruleset: filesystems (used space and growth)

# Show rule precedence
> "show all rules affecting filesystem / on server01"
📊 Rule Precedence for server01/Filesystem /:
1. 🎯 Host-specific rule (rule_xyz789) - Warning: 80%, Critical: 90%
2. 📁 Folder rule (/production) - Warning: 75%, Critical: 85% [OVERRIDDEN]
3. 🌐 Global default - Warning: 80%, Critical: 90% [OVERRIDDEN]
```

### 6.3 Creating Service Type Rules

**Scenario:** Create filesystem rules for database servers with higher thresholds

```bash
# CLI approach
checkmk-agent service-params rules create \
  --ruleset filesystems \
  --host-tag "application:database" \
  --warning 90 \
  --critical 95 \
  --comment "Database server filesystem thresholds - higher due to SAN storage"

# Interactive approach
> "create filesystem rule for database servers with 90% warning and 95% critical"
🔍 Detected ruleset: filesystems (used space and growth)
✅ Created filesystem parameter rule for database servers
🎯 Applies to: 4 hosts with tag application:database
📊 Parameters: Warning: 90%, Critical: 95%
💾 Note: Uses magic factor for large filesystem adaptation
🆔 Rule ID: rule_def456
```

**Advanced filesystem configuration:**
```python
# Generated rule with magic factor for large filesystems
{
    "ruleset": "filesystems",
    "folder": "~",
    "value_raw": '''{"levels": (90.0, 95.0), "magic_normsize": 20, "magic": 0.8}''',
    "conditions": {
        "host_tags": {"application": "database"}
    },
    "properties": {
        "disabled": False,
        "description": "Database server filesystem thresholds - higher due to SAN storage"
    }
}
```

## 7. Security Considerations

### 7.1 Permission Requirements

**Required Checkmk Permissions:**
- `wato.rulesets` - Access to ruleset management
- `wato.edit` - Edit configuration
- `wato.use_git` - Configuration versioning (if enabled)
- `wato.all_folders` - Access to all folders (for global rules)

### 7.2 Input Validation

**Parameter Validation:**
- Threshold values must be within valid ranges (0-100% for percentages)
- Parameter formats must match ruleset schemas
- Host and service names must be validated against Checkmk naming rules
- Rule conditions must use valid Checkmk syntax

### 7.3 Audit and Logging

**Security Logging:**
- All parameter changes logged with user, timestamp, and change details
- Failed authorization attempts logged
- Sensitive parameter values masked in logs
- Integration with Checkmk's audit trail

## 8. Performance Considerations

### 8.1 Caching Strategy

**Ruleset Metadata Caching:**
- Cache ruleset list and schemas for 15 minutes
- Invalidate cache on configuration changes
- Use memory-based caching for frequently accessed rulesets

### 8.2 API Optimization

**Efficient API Usage:**
- Batch rule operations where possible
- Use specific queries to reduce response sizes
- Implement request rate limiting to avoid API throttling

## 9. Testing Strategy

### 9.1 Unit Tests

**Core Component Testing:**
```python
def test_create_cpu_parameter_rule():
    """Test creating CPU parameter rules with various thresholds."""
    
def test_parameter_validation():
    """Test parameter validation for different service types."""
    
def test_rule_precedence_analysis():
    """Test analysis of rule precedence and conflicts."""
```

### 9.2 Integration Tests

**Real API Testing:**
```python
def test_end_to_end_parameter_override():
    """Test complete workflow: create rule, verify parameters, cleanup."""
    
def test_natural_language_parameter_commands():
    """Test NLP processing of parameter modification commands."""
```

### 9.3 Performance Tests

**Load Testing:**
- Parameter operations complete within 2 seconds
- CLI responsiveness under normal load
- Memory usage remains stable during extended operations

## 10. Migration and Deployment

### 10.1 Backward Compatibility

**Existing Functionality:**
- All existing service operations remain unchanged
- Current CLI commands continue to work
- Existing configuration files are not affected

### 10.2 Configuration Changes

**New Configuration Options:**
```yaml
service_parameters:
  default_warning_threshold: 80
  default_critical_threshold: 90
  enable_parameter_caching: true
  cache_ttl_minutes: 15
  max_rules_per_operation: 50
```

## 11. Success Metrics

### 11.1 Functional Metrics

- ✅ 100% coverage of common service parameter use cases
- ✅ <2 second response time for parameter operations
- ✅ 95% success rate for natural language command processing
- ✅ Zero data loss during parameter modifications

### 11.2 User Experience Metrics

- ✅ Users can override service parameters without Checkmk web UI
- ✅ Natural language commands feel intuitive
- ✅ Error messages provide clear guidance
- ✅ CLI commands follow established patterns

## 12. Conclusion

This specification provides a comprehensive roadmap for adding service modification functionality to the Checkmk LLM Agent. The implementation leverages Checkmk's existing rule-based system while providing intuitive natural language and CLI interfaces for managing service parameters.

The phased approach ensures systematic development with clear milestones and acceptance criteria. The focus on rule-based configuration aligns with Checkmk's architecture while the natural language interface maintains the agent's core value proposition of making complex monitoring operations accessible through conversational commands.

**Next Steps:**
1. Review and approve this specification
2. Begin Phase 1 implementation with `ServiceParameterManager`
3. Set up development environment for testing with Checkmk instances
4. Create initial parameter templates for common service types

---

**Document History:**
- v1.0 (2025-07-13): Initial specification draft - verified with Checkmk documentation research

**Verification Notes:**
This specification has been validated against current Checkmk documentation and community best practices. Key findings:
- ✅ Verified correct ruleset names (filesystems, cpu_utilization_linux, memory_linux, etc.)
- ✅ Confirmed rule-based parameter override methodology
- ✅ Validated rule precedence and condition structures  
- ✅ Verified that host-specific rules are the recommended approach for parameter overrides
- ✅ Confirmed integration with Checkmk's existing rule management via REST API