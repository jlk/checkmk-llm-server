# Project Overview

## Purpose
The **Checkmk LLM Agent** is a comprehensive Python application that integrates Large Language Models with Checkmk monitoring systems through the Model Context Protocol (MCP). It enables natural language interactions for infrastructure monitoring and management.

## Key Features
- **MCP-First Architecture**: 40 tools for comprehensive monitoring operations
- **Natural Language Processing**: Convert user queries to Checkmk API calls
- **Service Parameter Management**: Universal parameter read/write for ALL service types
- **Specialized Parameter Handlers**: Temperature, database, network, and custom check handlers
- **Advanced Features**: Streaming, caching, batch processing, performance metrics
- **Multiple Interfaces**: CLI, MCP server, interactive mode
- **Enterprise-Grade**: Production-ready with comprehensive error handling

## Current Status
- ✅ **FULLY OPERATIONAL** with Checkmk 2.4+ support
- ✅ **Production Ready** with 100% test pass rate
- ✅ **Complete MCP Integration** - 40 tools exposed
- ✅ **Comprehensive Service Parameter Management** recently completed
- ✅ **Enhanced Error Handling** with syntax error detection

## Tech Stack
- **Python 3.8+** with modern async/await patterns
- **Pydantic v2** for data validation and serialization
- **Click** for CLI interface
- **Requests** for HTTP API client
- **MCP SDK** for Model Context Protocol integration
- **PyYAML/TOML** for configuration management
- **OpenAI/Anthropic** for LLM integration
- **pytest** for comprehensive testing

## Architecture
- **Service Layer**: Business logic with specialized handlers
- **API Client**: Comprehensive Checkmk REST API integration
- **MCP Server**: Unified server exposing all functionality
- **CLI Interfaces**: Both direct and MCP-based CLIs
- **Interactive Mode**: Rich CLI with natural language processing