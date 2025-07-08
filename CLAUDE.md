# CLAUDE.md

Follow these rules at all times @/Users/jlk/code-local/checkmk_llm_agent/RULES.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Checkmk LLM Agent** project designed to integrate with Checkmk's REST API using Large Language Models. The project enables natural language interactions with Checkmk monitoring systems through AI-powered automation.

## Current State

The project is in early development with:
- Complete Checkmk REST API OpenAPI specification (`checkmk-rest-openapi.yaml`)
- VS Code workspace configuration
- No implementation code yet

## API Architecture

The project centers around the comprehensive Checkmk REST API v1.0 specification:

### Core API Categories
- **Monitoring Operations**: Acknowledge problems, downtimes, host/service status
- **Setup & Configuration**: Host/service management, user management, rules/rulesets
- **Service Discovery**: Automated service detection and configuration
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
```

## Development Workflow

1. **API Client**: Build basic Checkmk REST API client
2. **LLM Integration**: Add natural language processing capabilities
3. **Agent Logic**: Implement conversation flow and command routing
4. **Testing**: Add comprehensive tests for API interactions
5. **Documentation**: Create setup and usage guides

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