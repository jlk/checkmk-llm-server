# Checkmk MCP Server Documentation

Welcome to the Checkmk MCP Server documentation. This directory contains all the guides and references you need to set up, use, and understand the agent.

## Getting Started

**New to the Checkmk MCP Server? Start here:**

- **[Getting Started Guide](getting-started.md)** - Complete setup walkthrough from installation to first use
- **[Usage Examples](USAGE_EXAMPLES.md)** - Practical examples and common workflows
- **[Troubleshooting](troubleshooting.md)** - Solutions to common issues

## Core Documentation

### User Guides
- **[Getting Started](getting-started.md)** - Step-by-step setup and configuration
- **[Usage Examples](USAGE_EXAMPLES.md)** - Real-world scenarios and workflows

### Technical Documentation
- **[Architecture Guide](architecture.md)** - Technical architecture and design decisions
- **[Advanced Features](ADVANCED_FEATURES.md)** - Streaming, caching, batch operations, parameter handlers
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

### Specialized Topics
- **[Parameter Management Guide](PARAMETER_MANAGEMENT_GUIDE.md)** - Service parameter configuration
- **[Historical Data Scraping](historical_scraping_examples.md)** - Advanced data extraction examples

## Quick Navigation

### By User Type

**System Administrators**:
1. [Getting Started](getting-started.md) - Setup and basic configuration
2. [Usage Examples](USAGE_EXAMPLES.md) - Daily monitoring workflows
3. [Troubleshooting](troubleshooting.md) - Issue resolution

**Developers**:
1. [Architecture Guide](architecture.md) - Technical implementation details
2. [Advanced Features](ADVANCED_FEATURES.md) - Extensibility and customization
3. [Parameter Management](PARAMETER_MANAGEMENT_GUIDE.md) - Custom parameter handlers

**DevOps/SRE Teams**:
1. [Usage Examples](USAGE_EXAMPLES.md) - Incident response workflows
2. [Advanced Features](ADVANCED_FEATURES.md) - Performance optimization

### By Topic

**Setup and Configuration**:
- [Getting Started Guide](getting-started.md)
- [Troubleshooting Setup Issues](troubleshooting.md#installation-issues)

**Daily Operations**:
- [Common Monitoring Scenarios](USAGE_EXAMPLES.md#common-monitoring-scenarios)
- [Infrastructure Management](USAGE_EXAMPLES.md#infrastructure-management-tasks)
- [Incident Response Workflows](USAGE_EXAMPLES.md)

**Advanced Usage**:
- [Streaming and Performance](ADVANCED_FEATURES.md#streaming-support)
- [Parameter Management](PARAMETER_MANAGEMENT_GUIDE.md)
- [Historical Data Analysis](historical_scraping_examples.md)

**Development and Extension**:
- [Service Layer Architecture](architecture.md#service-layer-architecture)
- [MCP Server Architecture](architecture.md#mcp-server-architecture)
- [Specialized Parameter Handlers](ADVANCED_FEATURES.md#specialized-parameter-handlers)

## Feature Overview

| Feature                         | User Guide                                                            | Technical Details                                                        | Examples                                                |
| ------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------- |
| **Natural Language Monitoring** | [Getting Started](getting-started.md#step-5-first-monitoring-queries) | [Architecture](architecture.md)                                          | [Usage Examples](USAGE_EXAMPLES.md)                     |
| **Host Management**             | [Usage Examples](USAGE_EXAMPLES.md#infrastructure-management-tasks)   | [Architecture](architecture.md#service-implementations)                  | [Getting Started](getting-started.md)                   |
| **Service Operations**          | [Usage Examples](USAGE_EXAMPLES.md#common-monitoring-scenarios)       | [Advanced Features](ADVANCED_FEATURES.md)                                | [Troubleshooting](troubleshooting.md)                   |
| **Parameter Management**        | [Parameter Guide](PARAMETER_MANAGEMENT_GUIDE.md)                      | [Advanced Features](ADVANCED_FEATURES.md#specialized-parameter-handlers) | [Usage Examples](USAGE_EXAMPLES.md)                     |
| **Historical Data**             | [Historical Examples](historical_scraping_examples.md)                | [Advanced Features](ADVANCED_FEATURES.md)                                | [Usage Examples](USAGE_EXAMPLES.md)                     |
| **Performance Features**        | [Advanced Features](ADVANCED_FEATURES.md)                             | [Architecture](architecture.md#performance-characteristics)              | [Troubleshooting](troubleshooting.md#high-memory-usage) |

## Documentation Standards

This documentation follows these principles:
- **User-focused**: Starts with why and how, not technical implementation
- **Grounded language**: Avoids marketing terms and overstated claims
- **Practical examples**: Shows real-world usage scenarios
- **Clear cross-references**: Easy navigation between related topics
- **Honest about limitations**: Documents known issues and constraints

## Archive

The following files contain historical project information and are kept for reference:
- `ARCHITECTURE_REFACTORING_COMPLETED.md` - MCP server refactoring details
- `PROJECT_COMPLETION.md` - Checkmk 2.4 upgrade completion report
- `SERVICE_PARAMETERS_ARCHITECTURE.md` - Parameter system design document
- `project-history.md` - Project development timeline
- `project-status.md` - Historical status updates

## Contributing to Documentation

When updating documentation:
1. Keep user needs first
2. Use clear, straightforward language
3. Include practical examples
4. Test all code examples
5. Update cross-references
6. Follow the established structure

For questions about the documentation or suggestions for improvement, please [create an issue](../../issues).

---

**Need help?** Check the [Troubleshooting Guide](troubleshooting.md) or [create an issue](../../issues) with your specific question.