# Product Overview

## CheckMK LLM Agent

A Python agent that connects Large Language Models to CheckMK through the Model Context Protocol (MCP), enabling natural language interactions for infrastructure monitoring and management.

### Core Purpose
- Bridge between LLMs (Claude, ChatGPT) and CheckMK monitoring systems
- Enable natural language queries for infrastructure monitoring
- Provide programmatic access to CheckMK operations through standardized MCP protocol

### Key Features
- **MCP-First Architecture**: Primary interface through Model Context Protocol for universal LLM compatibility
- **Natural Language Operations**: Convert plain English to CheckMK API calls
- **Advanced Performance**: Streaming, caching, batch operations, and error recovery
- **Comprehensive Monitoring**: Host management, service monitoring, status dashboards, parameter management
- **Historical Data**: Event history, metrics, and performance analysis
- **Business Intelligence**: BI aggregations and business service monitoring

### Target Users
- System administrators managing CheckMK infrastructure
- DevOps teams needing programmatic monitoring access
- LLM applications requiring monitoring capabilities
- Automation workflows integrating with CheckMK

### Supported CheckMK Version
- Requires CheckMK 2.4.0+ due to API changes
- Uses REST API v1.0 with POST-based query methods
- Uses screen scraping to get historical data from web UI when not available via REST API