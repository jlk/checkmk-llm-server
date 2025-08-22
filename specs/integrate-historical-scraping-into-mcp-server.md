# Plan: Integrate Historical Data Scraping into MCP Server

## 1. Create Historical Scraping Service
- **New Service**: `checkmk_mcp_server/services/historical_service.py`
- **Purpose**: Wrapper around `CheckmkHistoricalScraper` following service layer patterns
- **Architecture**: Factory pattern for scraper instance management
- **Scraper Factory**: Creates fresh scraper instance per request (handles session timeouts)
- **Methods**: 
  - `scrape_service_history(host, service, period)` - Main scraping method
  - `get_temperature_history(host, service, period)` - Specialized for temperature data
  - `get_performance_history(host, service, period)` - Generic performance metrics
  - `get_unified_historical_data(host, service, period, source)` - Returns unified data model
  - `_parse_scraper_output(scraper_data)` - Convert scraper tuples to unified model

## 2. Configuration-Based Data Source Selection
- **Configuration Option**: `historical_data_source` in config.yaml
- **Options**: `"rest_api"` or `"scraper"` (no auto mode)
- **Default**: `"scraper"` (enabled by default)
- **Tool Parameter**: Optional `data_source` parameter to override config per single request
- **Parameter Behavior**: No fallback - caller must specify valid source, invalid values return error
- **Scope**: Applies to any service - universal scraping capability

## 3. Unified Data Model
- **New Data Classes**:
  ```python
  @dataclass
  class HistoricalDataPoint:
      timestamp: datetime
      value: Union[float, str]
      metric_name: str  # LLM can infer from context
      unit: Optional[str] = None  # LLM can infer from context

  @dataclass
  class HistoricalDataResult:
      data_points: List[HistoricalDataPoint]
      summary_stats: Dict[str, float]  # Preserve original names (min/avg/std/etc.)
      metadata: Dict[str, Any]  # source, time_range, etc.
      source: str  # "rest_api", "scraper", "event_console"
  ```
- **Purpose**: Standardize output format across all data sources
- **Data Processing**: LLM handles metric name/unit inference and summary stat name variations
- **Backward Compatibility**: Maintain existing formats while adding unified option

## 4. Enhanced MCP Tools
- **Target Tools**: `get_metric_history`, `list_service_events`
- **Enhancement Strategy**: Integrate scraper into existing tools (no new tools created)
- **Implementation**: Use configuration-based source selection within existing tools
- **Parameters**: Add optional `data_source` parameter to existing tools to override config

## 5. Data Processing Logic
- **Scraper Output Parsing**: Handle mixed array of time-series and summary data
- **Input Format**: `List[Tuple[str, Union[float, str]]]` from scraper
- **Processing Logic**:
  ```python
  def _parse_scraper_output(scraper_data):
      data_points = []
      summary_stats = {}
      
      for key, value in scraper_data:
          if _is_timestamp(key):  # e.g., "2025-01-15T10:30:00"
              data_points.append(HistoricalDataPoint(...))
          elif _is_summary_stat(key):  # e.g., "min", "max", "avg"
              summary_stats[key] = float(value)
  ```
- **Detection Methods**: 
  - `_is_timestamp(key)` - Parse timestamp strings (ISO format, etc.)
  - `_is_summary_stat(key)` - Detect known summary stat names

## 6. Integration Points
- **Service Registration**: Add `HistoricalService` to MCP server initialization
- **Error Handling**: Return `ScrapingError` directly in MCP responses
- **Caching**: Apply existing cache service with 60-second TTL (configurable)
- **Configuration**: Load at startup, add historical data settings to config.yaml:
  ```yaml
  historical_data:
    source: "scraper"  # "rest_api" or "scraper" only
    cache_ttl: 60
    scraper_timeout: 30
  ```

## 7. Backward Compatibility
- **No Breaking Changes**: Existing tools maintain current behavior
- **Progressive Enhancement**: New unified data model available alongside existing formats
- **Graceful Migration**: Users can gradually adopt unified model

## 8. Implementation Phases

### Phase 1: Core Infrastructure
- **Create Unified Data Model**: Implement `HistoricalDataPoint` and `HistoricalDataResult` classes
- **Create Historical Service**: Implement `HistoricalService` with scraper factory pattern
- **Add Configuration Support**: Extend config loading for historical data settings
- **Implement Data Parser**: Create `_parse_scraper_output()` with timestamp/summary detection
- **Unit Tests**: Test data model, parser logic, and service initialization

### Phase 2: Service Integration
- **Register Historical Service**: Add to MCP server service registry
- **Implement Scraper Factory**: Create fresh instances per request with session handling
- **Add Caching Layer**: Integrate with existing cache service (60s TTL)
- **Error Handling**: Implement `ScrapingError` passthrough in service responses
- **Integration Tests**: Test service registration and basic scraping functionality

### Phase 3: MCP Tool Enhancement
- **Enhance `get_metric_history`**: Add `data_source` parameter and scraper integration
- **Enhance `list_service_events`**: Add `data_source` parameter and scraper integration  
- **Parameter Validation**: Ensure `data_source` values are validated (no fallback)
- **Response Formatting**: Return unified data model alongside existing formats
- **Tool Tests**: Test enhanced tools with both REST API and scraper sources

### Phase 4: Testing & Validation
- **End-to-End Testing**: Test complete flow from MCP client through to scraper
- **Service Coverage**: Test scraping with various service types beyond temperature
- **Error Scenarios**: Test handling of scraper failures, timeouts, authentication issues
- **Performance Testing**: Validate caching behavior and response times
- **Documentation**: Update tool descriptions and usage examples

## 9. Implementation To-Do List

### Phase 1 Tasks ✅ COMPLETED
- [x] Create `checkmk_mcp_server/services/models/historical.py` with `HistoricalDataPoint` and `HistoricalDataResult` classes
- [x] Create `checkmk_mcp_server/services/historical_service.py` with scraper factory pattern
- [x] Update `checkmk_mcp_server/config.py` to load `historical_data` configuration section
- [x] Implement `_parse_scraper_output()` method with timestamp and summary stat detection
- [x] Implement `_is_timestamp()` helper method for timestamp detection
- [x] Implement `_is_summary_stat()` helper method for summary stat detection
- [x] Create `tests/test_historical_service.py` with unit tests for data model and parser
- [x] Create `tests/test_historical_data_parsing.py` with scraper output parsing tests

**Phase 1 Completed**: ✅ All 8 tasks completed with 49 passing tests

### Phase 2 Tasks ✅ COMPLETED
- [x] Add `HistoricalService` to MCP server initialization in `mcp_server/server.py`
- [x] Implement scraper factory class that creates fresh `CheckmkHistoricalScraper` instances
- [x] Integrate historical service with existing cache service (60s TTL)
- [x] Implement error handling to pass through `ScrapingError` in service responses
- [x] Create `tests/test_historical_service_integration.py` for service registration tests
- [x] Add historical service to service registry in `_get_service()` method

**Phase 2 Completed**: ✅ All 6 tasks completed with 10 new integration tests passing

### Phase 3 Tasks ✅ COMPLETED
- [x] Add `data_source` parameter to `get_metric_history` tool definition
- [x] Add `data_source` parameter to `list_service_events` tool definition
- [x] Implement data source selection logic in `get_metric_history` handler
- [x] Implement data source selection logic in `list_service_events` handler
- [x] Add parameter validation for `data_source` values (no fallback on invalid)
- [x] Update tool response formatting to include unified data model
- [x] Create `tests/test_mcp_historical_tools.py` for enhanced tool testing

**Phase 3 Completed**: ✅ All 7 tasks completed with 16 new MCP tool tests passing

### Phase 4 Tasks ✅ COMPLETED
- [x] Create end-to-end test scenarios from MCP client to scraper
- [x] Test scraping with various service types (CPU, memory, network, etc.)
- [x] Test error handling scenarios (authentication failures, timeouts, network issues)
- [x] Test caching behavior and performance with repeated requests
- [x] Update MCP tool descriptions to document `data_source` parameter
- [x] Update README.md with historical data configuration examples
- [x] Create usage examples in `docs/` showing scraper integration

**Phase 4 Completed**: ✅ All 7 tasks completed with 54 new comprehensive tests across 4 test files

## Benefits
- **Fills Data Gaps**: Provides historical data when REST API/Event Console are limited
- **Enhanced User Experience**: Natural language queries like "show temperature history" get actual data
- **Maintains Architecture**: Follows existing service layer and MCP patterns
- **Graceful Degradation**: Falls back to REST API when scraping unavailable