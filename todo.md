# Checkmk LLM Agent Implementation Plan

## Project Overview
Create a Python agent that connects LLMs (Claude/ChatGPT) to Checkmk for easier configuration management through natural language interactions. Initial focus on host operations: list, create, and delete.

## Phase 1: Core Infrastructure

### 1. Project Setup
- [x] Create todo.md file with implementation plan
- [x] Set up Python virtual environment
- [x] Create requirements.txt with dependencies:
  - requests (HTTP client for Checkmk API)
  - openai or anthropic (LLM integration)
  - pydantic (data validation)
  - click (CLI framework)
  - python-dotenv (environment management)
- [x] Create .env.example for configuration template
- [x] Create basic project structure

### 2. Checkmk API Client
- [x] Implement CheckmkClient class with authentication
- [x] Add configuration management for Checkmk server URL and credentials
- [x] Implement error handling and rate limiting
- [x] Add logging for API interactions

### 3. LLM Integration
- [x] Create LLMClient interface for Claude/ChatGPT
- [x] Implement natural language processing for host operations
- [x] Add response formatting for human-readable output

## Phase 2: Host Operations Implementation

### 4. Host List Functionality
- [x] Implement `GET /domain-types/host_config/collections/all` endpoint
- [x] Add filtering and search capabilities
- [x] Format output for both API and natural language responses

### 5. Host Create Functionality
- [x] Implement `POST /domain-types/host_config/collections/all` endpoint
- [x] Support basic host creation (folder + hostname)
- [x] Add validation for required fields
- [x] Support optional attributes (IP address, alias, tags)
- [x] Support bulk host creation

### 6. Host Delete Functionality
- [x] Implement `DELETE /objects/host_config/{host_name}` endpoint
- [x] Add confirmation prompts for safety
- [x] Support bulk deletion if needed

## Phase 3: Agent Logic & CLI

### 7. Command Processing
- [x] Create natural language command parser
- [x] Map user intents to API operations
- [x] Implement conversation flow management

### 8. CLI Interface
- [x] Create command-line interface using Click
- [x] Add interactive mode for conversations
- [x] Implement configuration commands

### 9. Testing & Documentation
- [x] Add unit tests for API client
- [x] Add unit tests for LLM client functionality  
- [x] Add unit tests for host operations manager
- [x] Add CLI tests
- [x] Create integration tests with mock Checkmk server
- [x] Add pytest configuration and test utilities
- [x] Write setup and usage documentation

## Key Files to Create

```
checkmk_llm_agent/
├── todo.md                           # This implementation plan
├── requirements.txt                  # Python dependencies
├── setup.py                         # Package configuration
├── .env.example                     # Environment variables template
├── checkmk_agent/
│   ├── __init__.py
│   ├── api_client.py                # Checkmk REST API client
│   ├── llm_client.py                # LLM integration
│   ├── host_operations.py           # Host CRUD operations
│   ├── cli.py                       # Command-line interface
│   ├── config.py                    # Configuration management
│   └── utils.py                     # Common utilities
└── tests/
    ├── __init__.py
    ├── test_api_client.py
    ├── test_host_operations.py
    └── test_cli.py
```

## API Endpoints Reference

### Host Operations
- **List Hosts**: `GET /domain-types/host_config/collections/all`
- **Create Host**: `POST /domain-types/host_config/collections/all`
- **Delete Host**: `DELETE /objects/host_config/{host_name}`
- **Get Host**: `GET /objects/host_config/{host_name}`

### Required Schemas
- **CreateHost**: `folder` (required), `host_name` (required), `attributes` (optional)
- **Host Response**: Complex nested structure with links, members, extensions
- **Authentication**: Bearer token format

## Configuration Requirements
- Checkmk server URL
- Authentication credentials (username/password or API key)
- LLM API credentials (OpenAI/Anthropic)
- Default folder for host creation
- Logging configuration

## Success Criteria
- [x] User can list all hosts via natural language
- [x] User can create a new host with minimal information
- [x] User can delete a host with confirmation
- [x] All operations provide clear feedback
- [x] Error handling works for common scenarios
- [x] Configuration is secure and flexible
- [x] Comprehensive test coverage (unit and integration tests)
- [x] Full CLI interface with both direct commands and interactive mode

## Next Steps
1. Start with project setup and requirements.txt
2. Implement basic Checkmk API client
3. Add simple host list functionality
4. Extend to create and delete operations
5. Add LLM integration for natural language processing