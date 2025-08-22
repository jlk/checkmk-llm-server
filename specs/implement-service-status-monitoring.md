# Task: Implement Service Status Monitoring

## Overview
Add comprehensive service status monitoring capabilities to the Checkmk MCP Server, enabling users to query, analyze, and monitor service health through natural language commands.

## Background
The Checkmk OpenAPI provides extensive service status endpoints that can retrieve detailed monitoring information including service states, performance data, acknowledgements, downtimes, and check results. This task will implement a complete service status system that integrates with the existing CLI and interactive modes.

## Goals
1. **Real-time Service Status Queries**: Enable users to check service health across hosts
2. **Problem Detection**: Automatically identify and report services with issues
3. **Status Dashboard**: Provide comprehensive service health overviews
4. **Natural Language Interface**: Support intuitive commands like "show problem services" or "what's wrong with server01"
5. **Rich Status Display**: Present status information with clear visual indicators and actionable insights

## Technical Requirements

### 1. API Client Extensions (`api_client.py`)

#### New Methods to Implement:
```python
def get_service_status(self, host_name: str, service_description: Optional[str] = None) -> Dict[str, Any]
def list_problem_services(self, host_filter: Optional[str] = None) -> List[Dict[str, Any]]
def get_service_health_summary(self) -> Dict[str, Any]
def get_services_by_state(self, state: int, host_filter: Optional[str] = None) -> List[Dict[str, Any]]
def get_acknowledged_services(self) -> List[Dict[str, Any]]
def get_services_in_downtime(self) -> List[Dict[str, Any]]
```

#### Required Columns for Status Queries:
```python
STATUS_COLUMNS = [
    "host_name", "description", "state", "state_type", 
    "acknowledged", "plugin_output", "last_check", 
    "scheduled_downtime_depth", "perf_data", "check_interval",
    "current_attempt", "max_check_attempts", "notifications_enabled"
]
```

#### Livestatus Query Builders:
- Problem services: `{"op": "!=", "left": "state", "right": "0"}`
- Critical services: `{"op": "=", "left": "state", "right": "2"}`
- Warning services: `{"op": "=", "left": "state", "right": "1"}`
- Acknowledged services: `{"op": "=", "left": "acknowledged", "right": "1"}`
- Services in downtime: `{"op": ">", "left": "scheduled_downtime_depth", "right": "0"}`

### 2. Service Status Manager (`service_status.py`)

#### Create New Module:
- **Location**: `checkmk_mcp_server/service_status.py`
- **Purpose**: High-level service status operations and analysis
- **Dependencies**: `api_client.py`, `config.py`

#### Core Functionality:
```python
class ServiceStatusManager:
    def get_service_health_dashboard(self) -> Dict[str, Any]
    def analyze_service_problems(self, host_filter: Optional[str] = None) -> Dict[str, Any]
    def get_service_status_details(self, host_name: str, service_description: str) -> Dict[str, Any]
    def generate_status_summary(self) -> Dict[str, Any]
    def find_services_by_criteria(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]
```

#### Status Analysis Features:
- Service state distribution (OK/WARN/CRIT/UNKNOWN counts)
- Problem service categorization
- Performance trend analysis
- Alert fatigue detection (frequently flapping services)
- Downtime and acknowledgement tracking

### 3. CLI Integration (`cli.py`)

#### New Command Group: `status`
```bash
checkmk-mcp-server status --help                    # Show status command help
checkmk-mcp-server status overview                  # Service health dashboard
checkmk-mcp-server status problems                  # List all problem services
checkmk-mcp-server status host <hostname>           # Status for specific host
checkmk-mcp-server status service <host> <service>  # Detailed service status
checkmk-mcp-server status critical                  # Show only critical services
checkmk-mcp-server status acknowledged              # Show acknowledged problems
checkmk-mcp-server status downtime                  # Show services in downtime
```

#### Command Implementation:
- Use Click command groups for organization
- Integrate with existing CLI patterns
- Support output formatting (table, JSON, detailed)
- Add filtering and sorting options

### 4. Interactive Mode Enhancement

#### Natural Language Commands:
```
"show service status"
"what services have problems?"
"check server01 status" 
"show critical services"
"what's wrong with database server?"
"show services in downtime"
"list acknowledged problems"
"service health dashboard"
```

#### Command Parser Updates (`command_parser.py`):
- Add status-related keywords: `status`, `health`, `problems`, `critical`, `warning`, `acknowledged`, `downtime`
- Enhance parameter extraction for status queries
- Route status commands to service status manager

### 5. UI and Display Enhancements (`ui_manager.py`)

#### Status Display Features:
- **Color-coded service states**: Green (OK), Yellow (WARNING), Red (CRITICAL), Gray (UNKNOWN)
- **Status icons**: ✅ OK, ⚠️ WARNING, ❌ CRITICAL, ❓ UNKNOWN, 🔕 ACKNOWLEDGED, ⏸️ DOWNTIME
- **Rich formatting**: Tables for service lists, detailed cards for individual services
- **Progress indicators**: Health percentages, problem counts
- **Timestamps**: Relative time display (e.g., "2 minutes ago")

#### Dashboard Layout:
```
📊 Service Health Dashboard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏥 Overall Health: 87% (⚠️ 3 problems need attention)
✅ OK: 245 services  ⚠️ WARNING: 2 services  ❌ CRITICAL: 1 service

🔥 Critical Issues:
├─ 🖥️  server01/Database Connection ❌ CRITICAL (2m ago)
└─ 💾 server02/Disk Space / ❌ CRITICAL (5m ago)

⚠️  Warning Issues:
├─ 🖥️  server03/CPU Load ⚠️ WARNING (1m ago)
└─ 🌐 server04/Network Interface eth0 ⚠️ WARNING (3m ago)
```

### 6. Testing Strategy

#### Unit Tests (`test_service_status.py`):
- API client method testing with mock responses
- Service status manager functionality
- Status analysis algorithms
- Query building and filtering

#### Integration Tests:
- End-to-end status queries
- CLI command execution
- Interactive mode status commands
- Error handling for API failures

#### Test Data:
- Mock service status responses
- Various service state scenarios
- Performance data examples
- Multi-host environments

### 7. Documentation and Examples

#### User Documentation:
- Service status command reference
- Natural language query examples
- Status interpretation guide
- Troubleshooting common issues

#### Code Documentation:
- API method docstrings
- Status manager class documentation
- Query pattern examples
- Configuration options

## Implementation Plan

### Phase 1: Core API Integration (2-3 hours)
1. **Extend API client** with service status methods
2. **Implement Livestatus query builders** for common status queries
3. **Add comprehensive error handling** for API failures
4. **Create unit tests** for API integration

### Phase 2: Service Status Manager (2-3 hours)
1. **Create service_status.py module** with core functionality
2. **Implement status analysis features** (health dashboard, problem detection)
3. **Add service state categorization** and filtering
4. **Build status summary generators**

### Phase 3: CLI Integration (1-2 hours)
1. **Add status command group** to CLI
2. **Implement individual status commands** (overview, problems, etc.)
3. **Add output formatting options** (table, JSON, detailed)
4. **Integrate with existing CLI patterns**

### Phase 4: Interactive Mode Enhancement (2-3 hours)
1. **Update command parser** with status keywords
2. **Add natural language status queries** to service operations
3. **Implement status command routing**
4. **Test natural language processing**

### Phase 5: UI and Display (2-3 hours)
1. **Enhance UI manager** with status display features
2. **Implement color-coded status indicators**
3. **Create dashboard layout and formatting**
4. **Add rich status detail views**

### Phase 6: Testing and Documentation (1-2 hours)
1. **Complete test coverage** for all new functionality
2. **Integration testing** with real Checkmk instances
3. **Update documentation** with new commands and features
4. **Create usage examples** and troubleshooting guides

## Acceptance Criteria

### Functional Requirements:
- [ ] Users can query service status for individual services, hosts, or globally
- [ ] System identifies and highlights problem services automatically
- [ ] Natural language commands work intuitively ("show problems", "check server01")
- [ ] Status information includes service state, last check time, and output details
- [ ] Dashboard provides clear overview of service health across infrastructure
- [ ] Color coding and icons make status information immediately understandable

### Technical Requirements:
- [ ] All new code follows project patterns and conventions
- [ ] Comprehensive error handling for API failures and edge cases
- [ ] Unit test coverage >85% for new functionality
- [ ] Integration tests validate end-to-end functionality
- [ ] Performance optimized for large numbers of services
- [ ] Memory usage remains reasonable for status queries

### User Experience Requirements:
- [ ] Commands respond quickly (<2 seconds for typical queries)
- [ ] Output is clear, well-formatted, and actionable
- [ ] Error messages are helpful and suggest corrective actions
- [ ] Help documentation is comprehensive and includes examples
- [ ] Interactive mode provides intuitive status checking experience

## Dependencies
- Existing `api_client.py` with working service operations
- Current CLI framework and command patterns
- Interactive mode command parser infrastructure
- UI manager with color and formatting capabilities
- Testing framework and mock response patterns

## Risks and Considerations
- **API Performance**: Large Checkmk installations may have thousands of services
- **Data Freshness**: Status information may be cached and not real-time
- **Permissions**: Users need appropriate Checkmk permissions for service access
- **Network Reliability**: API calls may fail or timeout
- **Display Scalability**: Large service lists need pagination or filtering

## Future Enhancements
- Real-time status updates with WebSocket connections
- Historical status trending and analysis
- Service dependency mapping and impact analysis
- Custom alerting rules based on status patterns
- Integration with external monitoring systems
- Mobile-optimized status display