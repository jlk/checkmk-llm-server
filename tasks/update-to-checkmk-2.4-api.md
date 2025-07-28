# Update to Checkmk 2.4 API

## Overview
Upgrade the Checkmk LLM Agent to use the new Checkmk 2.4 REST API, which is significantly larger (48,927 lines vs 21,353 lines) and includes critical breaking changes to existing endpoints.

## Critical Breaking Changes Found

### 1. **Host Listing API Changed from GET to POST**
- **2.0**: `GET /domain-types/host/collections/all` with query parameters
- **2.4**: `POST /domain-types/host/collections/all` with JSON body
- **Impact**: All host listing operations need to be rewritten
- **Parameters moved from query string to JSON body**

### 2. **Service Listing API Changed from GET to POST**
- **2.0**: `GET /domain-types/service/collections/all` with query parameters
- **2.4**: `POST /domain-types/service/collections/all` with JSON body
- **Impact**: All service listing operations need to be rewritten
- **Parameters moved from query string to JSON body**

### 3. **New Acknowledgement Parameter**
- **2.4 adds**: `expire_on` field for acknowledgements
- **Impact**: Optional enhancement, backward compatible

### 4. **Downtime Duration Type Changed**
- **2.0**: `duration` as integer (seconds)
- **2.4**: `duration` appears to be in minutes (60 vs 3600)
- **Impact**: Need to verify and adjust duration calculations

### 5. **Deprecated Endpoints**
- **2.4**: GET versions of host/service listing marked as deprecated with Werk references
- Must use POST versions to avoid future breakage

## Breaking Changes Checklist
- [ ] Update host listing from GET to POST
- [ ] Update service listing from GET to POST  
- [ ] Migrate query parameters to JSON body
- [ ] Test duration parameter changes
- [ ] Add expire_on support for acknowledgements
- [ ] Update host service listing endpoint (also changed to POST)
- [ ] Verify all query expressions still work with new format

## Implementation Checklist

### Phase 1: Critical API Compatibility Fixes
- [ ] Update OpenAPI spec reference from `checkmk-rest-openapi.yaml` to `checkmk-rest-openapi-2.4.yaml`
- [ ] Update `api_client.py` methods:
  - [ ] `list_hosts()` - change from GET to POST
  - [ ] `list_host_services()` - change from GET to POST  
  - [ ] `list_all_services()` - change from GET to POST
  - [ ] `list_host_services_with_monitoring_data()` - change from GET to POST
  - [ ] `list_all_services_with_monitoring_data()` - change from GET to POST
- [ ] Update `async_api_client.py` wrapper methods
- [ ] Add Content-Type headers for POST requests
- [ ] Move query parameters to JSON request body
- [ ] Test all MCP tools with new API

### Phase 2: Event Console Integration
- [ ] Create `checkmk_agent/services/event_service.py`
- [ ] Implement Event Console methods:
  - [ ] `list_events(query, host, application, state, phase)`
  - [ ] `get_event(event_id, site_id)`
  - [ ] `change_event_state(event_id, new_state)`
  - [ ] `acknowledge_event(event_id, comment, contact)`
  - [ ] `delete_events(query, method, site_id)`
- [ ] Add Event Console MCP tools:
  - [ ] `list_service_events` - Show event history for a service
  - [ ] `list_host_events` - Show event history for a host  
  - [ ] `get_recent_critical_events` - Show recent critical events
  - [ ] `acknowledge_event` - Acknowledge specific events
  - [ ] `search_events` - Search events by query expression

### Phase 3: Metrics and Performance Data
- [ ] Create `checkmk_agent/services/metrics_service.py`
- [ ] Implement graph/metrics retrieval
- [ ] Add Metrics MCP tools:
  - [ ] `get_service_metrics` - Get performance metrics/graphs
  - [ ] `get_metric_history` - Get historical metric data

### Phase 4: Enhanced Features
- [ ] Update acknowledgement to support `expire_on` field
- [ ] Add support for new BI (Business Intelligence) endpoints
- [ ] Explore other new endpoints in 2.4 API

## Testing Checklist
- [ ] Set up Checkmk 2.4 test instance
- [ ] Test all 14 basic MCP tools
- [ ] Test all 18 enhanced MCP tools
- [ ] Verify host listing with new POST endpoint
- [ ] Verify service listing with new POST endpoint
- [ ] Test query expressions in new format
- [ ] Test acknowledgements with expire_on
- [ ] Test downtime duration handling
- [ ] Test Event Console integration
- [ ] Performance testing with larger API
- [ ] Error handling for new response formats

## Documentation Updates
- [ ] Update README with Checkmk 2.4 requirements
- [ ] Document breaking changes for users
- [ ] Add Event Console usage examples
- [ ] Add Metrics usage examples
- [ ] Update API examples in documentation
- [ ] Create migration guide from 2.0 to 2.4

## Migration Guide Elements
1. **Pre-Migration Checklist**
   - Backup current configuration
   - Note current Checkmk version
   - List active integrations

2. **Breaking Changes for Users**
   - Minimum Checkmk version now 2.4
   - API authentication remains the same
   - New features available (Event Console, Metrics)

3. **Rollback Plan**
   - Keep copy of old OpenAPI spec
   - Document version pinning options
   - Provide downgrade instructions

## Code Examples for Key Changes

### Host Listing Migration
```python
# OLD (2.0) - GET request
def list_hosts(self, query=None, columns=None):
    params = {}
    if query:
        params['query'] = json.dumps(query)
    if columns:
        params['columns'] = columns
    return self._request('GET', '/domain-types/host/collections/all', params=params)

# NEW (2.4) - POST request
def list_hosts(self, query=None, columns=None, sites=None):
    data = {}
    if query:
        data['query'] = query  # Already a dict, not JSON string
    if columns:
        data['columns'] = columns
    if sites:
        data['sites'] = sites
    return self._request('POST', '/domain-types/host/collections/all', json=data)
```

### Service Listing Migration
```python
# OLD (2.0) - GET request
def list_all_services(self, host_name=None, query=None, columns=None):
    params = {}
    if host_name:
        params['host_name'] = host_name
    if query:
        params['query'] = json.dumps(query)
    if columns:
        params['columns'] = columns
    return self._request('GET', '/domain-types/service/collections/all', params=params)

# NEW (2.4) - POST request  
def list_all_services(self, host_name=None, query=None, columns=None, sites=None):
    data = {}
    if host_name:
        data['host_name'] = host_name
    if query:
        data['query'] = query  # Already a dict, not JSON string
    if columns:
        data['columns'] = columns
    if sites:
        data['sites'] = sites
    return self._request('POST', '/domain-types/service/collections/all', json=data)
```

## Timeline Estimate
- Phase 1 (Critical Fixes): 2-3 days
- Phase 2 (Event Console): 2-3 days
- Phase 3 (Metrics): 1-2 days
- Phase 4 (Testing & Docs): 2-3 days
- **Total**: 7-11 days

## Success Criteria
- All existing MCP tools work with Checkmk 2.4
- Event Console integration provides service history
- No regression in current functionality
- Performance remains acceptable with larger API
- Clear migration path for users