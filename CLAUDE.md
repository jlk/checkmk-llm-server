# CLAUDE.md

Follow these rules at all times @/Users/jlk/code-local/checkmk_llm_agent/RULES.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Checkmk LLM Agent** project designed to integrate with Checkmk's REST API using Large Language Models. The project enables natural language interactions with Checkmk monitoring systems through AI-powered automation.

## Current State

The project is a **FULLY OPERATIONAL** Checkmk LLM Agent implementation with:
- Complete Checkmk REST API OpenAPI specification (`checkmk-rest-openapi.yaml`)
- Host management operations (CRUD)
- Rule management operations (CRUD)
- **Service status and management operations**
- Natural language processing capabilities
- CLI interface with interactive mode
- **MCP Server Integration** - Both basic and enhanced servers fully functional with Claude
- **Robust error handling with syntax error detection**
- Test coverage for core functionality
- VS Code workspace configuration

## Current Focus

**MCP Server Integration Completed** - Recently completed comprehensive MCP server implementation and bug fixes:
- **Tool Registration**: Both basic and enhanced MCP servers now properly expose all tools (14 and 18 tools respectively)
- **Error Resolution**: Fixed all JSON serialization, parameter validation, and CallToolResult construction issues
- **Claude Integration**: Successfully tested with Claude - all tools functional and returning real infrastructure data
- **Missing Methods**: Implemented 6 missing StatusService methods for complete API coverage
- **Bug Workarounds**: Resolved MCP SDK v1.12.0 compatibility issues
- **Real-time Monitoring**: Verified through live log monitoring - zero errors in current session

**Previously Completed**:
- Enhanced host service status functionality with rich dashboards and problem categorization
- Advanced CLI filtering and natural language query support
- Comprehensive service operations and discovery capabilities

## API Architecture

The project centers around the comprehensive Checkmk REST API v1.0 specification:

### Core API Categories
- **Monitoring Operations**: Acknowledge problems, downtimes, host/service status
- **Setup & Configuration**: Host/service management, user management, rules/rulesets
- **Service Discovery**: Automated service detection and configuration
- **Service Management**: Service status monitoring, acknowledgments, downtime scheduling
- **Business Intelligence**: BI operations and analytics
- **Internal Operations**: Certificate management, activation, agent downloads

### Key Endpoints Structure
- Authentication via Checkmk's auth mechanisms
- Resource-oriented REST design
- Comprehensive permission model for each endpoint
- Stateless HTTP/1.1 protocol

## Development Commands

Currently no build system is configured. When implementing:

### Python Implementation (Recommended)
```bash
# Setup virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run agent
python checkmk_agent.py
```

## Architecture Considerations

### API Integration
- **Base URL**: Configure Checkmk server URL
- **Authentication**: Implement Checkmk auth (automation user tokens recommended)
- **Rate Limiting**: Implement throttling for API calls
- **Error Handling**: Robust handling of API errors and timeouts

### LLM Integration
- **Natural Language Processing**: Convert user queries to API calls
- **Response Formatting**: Convert API responses to human-readable format
- **Context Management**: Maintain conversation context for multi-step operations

### Security
- **Credential Management**: Secure storage of Checkmk credentials
- **Permission Validation**: Respect Checkmk's permission model
- **Data Sanitization**: Handle sensitive monitoring data appropriately

## File Structure

```
checkmk-rest-openapi.yaml     # Complete Checkmk REST API specification (21k+ lines)
checkmk_agent.code-workspace  # VS Code workspace configuration
.claude/settings.local.json   # Claude Code permissions

checkmk_agent/
├── __init__.py
├── api_client.py             # Core API client with service operations
├── cli.py                    # Enhanced CLI interface with interactive mode
├── config.py                 # Configuration management
├── host_operations.py        # Host management operations
├── service_operations.py     # Service management operations
├── service_parameters.py     # Service parameter management
├── llm_client.py            # LLM integration
├── logging_utils.py         # Logging utilities
├── utils.py                 # Utility functions
├── interactive/             # Enhanced interactive mode components
│   ├── __init__.py
│   ├── readline_handler.py   # Command history and readline integration
│   ├── command_parser.py     # Enhanced command parsing with fuzzy matching
│   ├── help_system.py        # Comprehensive contextual help system
│   ├── tab_completer.py      # Tab completion for commands and parameters
│   └── ui_manager.py         # Rich UI formatting and messaging
├── mcp_server/              # MCP Server Integration (FULLY FUNCTIONAL)
│   ├── __init__.py
│   ├── server.py             # Basic MCP server - 14 tools exposed
│   └── enhanced_server.py    # Enhanced MCP server - 18 tools exposed
└── services/                # Service Layer Architecture
    ├── __init__.py
    ├── status_service.py     # Status operations with all methods implemented
    ├── cache_service.py      # Caching and performance optimization
    ├── batch_service.py      # Batch processing capabilities
    └── streaming_service.py  # Real-time streaming operations

tests/
├── __init__.py
├── conftest.py
├── test_api_client.py
├── test_cli.py
├── test_host_operations.py
├── test_service_operations.py # Service operations tests
├── test_integration.py
├── test_llm_client.py
├── test_batch.py             # Batch processing tests
├── test_cache.py             # Caching functionality tests
├── test_performance.py       # Performance optimization tests
└── test_streaming.py         # Streaming operations tests

examples/
├── README.md
└── configs/
    ├── development.yaml
    ├── production.yaml
    └── testing.yaml
```

## Development Workflow

1. **API Client**: ✅ Checkmk REST API client with host/rule/service operations
2. **LLM Integration**: ✅ Natural language processing capabilities
3. **Agent Logic**: ✅ Conversation flow and command routing for hosts/rules/services
4. **MCP Server Integration**: ✅ Both basic and enhanced servers fully functional
5. **Testing**: ✅ Test coverage for core operations
6. **Documentation**: ✅ Setup and usage guides

## MCP Server Integration

The project includes comprehensive MCP (Model Context Protocol) server integration for seamless Claude AI integration:

### Basic MCP Server (`checkmk_agent/mcp_server/server.py`)
- **14 Tools Exposed**: Complete coverage of core Checkmk operations
- **Status**: ✅ Fully Functional - Successfully tested with Claude
- **Features**: Host operations, service management, status monitoring, problem analysis

### Enhanced MCP Server (`checkmk_agent/mcp_server/enhanced_server.py`) 
- **18 Tools Exposed**: All basic tools plus advanced features
- **Status**: ✅ Fully Functional - Advanced capabilities verified
- **Features**: Batch processing, streaming operations, caching, performance metrics

### Recent Fixes (2025-07-25)
- Fixed tool registration using proper MCP SDK decorators (`@server.list_tools()`, `@server.call_tool()`)
- Implemented 6 missing StatusService methods for complete API coverage
- Added custom JSON serialization handling for datetime objects
- Worked around MCP SDK v1.12.0 CallToolResult construction bug
- Verified zero errors through real-time log monitoring

## Service Operations Architecture

The service operations functionality is built around these key components:

### 1. API Client Integration (`api_client.py`)
- **Service Status Methods**: `list_host_services()`, `list_all_services()`
- **Service Management**: `acknowledge_service_problems()`, `create_service_downtime()`
- **Service Discovery**: `get_service_discovery_result()`, `start_service_discovery()`
- **Pydantic Models**: Type-safe validation for all service operations

### 2. Service Operations Manager (`service_operations.py`)
- **Natural Language Processing**: Analyzes user commands for service operations
- **Command Routing**: Routes commands to appropriate API methods
- **Response Formatting**: Converts API responses to human-readable format
- **Error Handling**: Robust error handling with meaningful messages

### 3. CLI Interface (`cli.py`)
- **Services Command Group**: Complete CLI interface for service operations
  - `services list [host_name]` - List services
  - `services status <host> <service>` - Get service status
  - `services acknowledge <host> <service>` - Acknowledge problems
  - `services downtime <host> <service>` - Create downtime
  - `services discover <host>` - Discover services
  - `services stats` - Show service statistics
- **Interactive Mode**: Natural language service commands in interactive mode

### 4. Supported Service Operations

#### Service Status and Monitoring
- **List Services**: View all services for a host or across all hosts
- **Service Status**: Get detailed status information for specific services
- **Service Statistics**: Overview of service states across the infrastructure

#### Service Problem Management
- **Acknowledge Problems**: Acknowledge service problems with comments
- **Create Downtime**: Schedule downtime periods for planned maintenance
- **Sticky/Persistent Options**: Control acknowledgment behavior

#### Service Discovery
- **Automated Discovery**: Discover new services on hosts
- **Discovery Modes**: Multiple discovery modes (refresh, new, remove, fixall)
- **Discovery Results**: Review discovered, vanished, and ignored services

### 5. Natural Language Examples

The system understands commands like:
- `"list services for server01"`
- `"show all services"`
- `"acknowledge CPU load on server01"`
- `"create 4 hour downtime for disk space on server01"`
- `"discover services on server01"`

### 6. Error Handling and Validation

- **API Error Handling**: Comprehensive error handling for all API operations
- **Input Validation**: Pydantic models ensure type safety
- **User-Friendly Messages**: Clear error messages and success confirmations
- **Retry Logic**: Built-in retry mechanism with exponential backoff

## Conversation Storage

Conversations with the AI assistant should be saved to preserve context, decisions, and progress. Each conversation must follow this standardized format:

```
TITLE: [Brief topic descriptor]
DATE: YYYY-MM-DD
PARTICIPANTS: [Comma-separated list]
SUMMARY: [Key points and decisions]

INITIAL PROMPT: [User's first substantive message only - exclude any system instructions or project context references]

KEY DECISIONS:
- [Decision point 1]
- [Decision point 2]

FILES CHANGED:
- [File 1] Summary of changes
- [File 2] Summary of changes
```

### Storage Guidelines
- Conversations should be stored in `docs/conversations/` organized by date (YYYY-MM/)
- File naming convention: `YYYY-MM-DD-HHMM-[brief-topic-slug].md` 
- **Timestamp Requirements**:
  - Use todays date and time
  - Use **UTC timezone** for all timestamps
  - Use **24-hour format** (HHMM) 
  - Timestamp should reflect **conversation start time** (when user sends first substantive message)
  - To determine UTC time: check current UTC time when conversation begins, or convert local time to UTC
  - Example: If conversation starts at 2:30 PM EST (UTC-5), use `1930` (7:30 PM UTC)
- Conversations that result in architecture decisions should be referenced in the relevant architecture docs
- Conversations that define features should be linked from the project documentation
- **IMPORTANT**: The INITIAL PROMPT must contain only the user's actual first message, not any system instructions about reading project context or role assignments

## Implementation Notes

- The OpenAPI spec is comprehensive (21,353 lines) - use code generation tools when possible
- Focus on core monitoring operations first (acknowledge, downtimes, status checks)
- Consider async operations for real-time monitoring capabilities
- Implement proper logging for debugging API interactions