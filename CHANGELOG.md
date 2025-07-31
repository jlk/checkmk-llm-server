# Changelog

All notable changes to the Checkmk LLM Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2025-01-31

### Changed
- **BREAKING**: Consolidated MCP servers into single unified implementation
- Removed basic MCP server (`mcp_checkmk_server.py` with 24 tools)  
- Enhanced MCP server is now the single MCP server with all 28 tools (24 standard + 4 advanced)
- All users now automatically get advanced features (streaming, caching, batch operations, metrics)
- Simplified architecture and documentation
- Updated all references from dual servers to single server implementation

### Benefits
- Simpler deployment and maintenance
- No confusion about server choice  
- All users get performance optimizations automatically
- Single upgrade path for new features
- Reduced codebase complexity

## [2.0.0] - 2025-01-28

### Added
- Full support for Checkmk 2.4 REST API
- Event Console integration for service history and event management
  - 5 new MCP tools: `list_service_events`, `list_host_events`, `get_recent_critical_events`, `acknowledge_event`, `search_events`
- Metrics and Performance Data API
  - 2 new MCP tools: `get_service_metrics`, `get_metric_history`
  - Support for graphs and historical data retrieval
- Business Intelligence (BI) integration
  - 2 new MCP tools: `get_business_status_summary`, `get_critical_business_services`
  - Business-level service aggregation monitoring
- System information endpoint
  - 1 new MCP tool: `get_system_info`
- Acknowledgment expiration support (`expire_on` field)
- Comprehensive migration guide from Checkmk 2.0

### Changed
- **BREAKING**: Minimum Checkmk version requirement changed to 2.4.0
- **BREAKING**: Host and service listing endpoints changed from GET to POST
- Query expressions now passed as objects in request body instead of JSON strings
- Basic MCP server had 24 tools (increased from 17)
- Enhanced MCP server had 28 tools (increased from 22)
- **Now consolidated**: Single MCP server with all 28 tools

### Fixed
- Service state display showing "Unknown" instead of actual states
- Query expression handling for Checkmk 2.4 compatibility
- Parameter validation errors in MCP tools

### Documentation
- Added comprehensive usage examples for all new features
- Added migration guide for upgrading from Checkmk 2.0-2.3
- Updated README with new feature descriptions
- Added breaking changes documentation

## [1.0.0] - 2025-01-15

### Initial Release
- Core Checkmk REST API integration
- MCP server implementation (basic and enhanced)
- CLI interface with natural language processing
- Host management operations
- Service monitoring and management
- Rule and parameter management
- Status dashboards and problem analysis
- Service discovery operations
- Downtime scheduling
- Problem acknowledgment
- Async operations support
- Comprehensive error handling