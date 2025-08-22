# Checkmk MCP Server

Connect AI assistants like Claude to your Checkmk monitoring infrastructure using natural language. This MCP (Model Context Protocol) server enables conversational monitoring operations through any MCP-compatible client.

## Why Use This?

**Turn this:** "I need to check if any hosts in the web farm are having CPU issues and acknowledge any problems for the next 2 hours while we investigate."

**Into this:** Just ask your AI assistant - it handles the API calls, finds the problems, and manages acknowledgments automatically.

### What You Get

- **Natural Language Monitoring**: Talk to your infrastructure like you would a colleague
- **MCP Standard Integration**: Works with Claude Desktop, VS Code, and other MCP clients
- **Complete Checkmk Coverage**: Hosts, services, events, metrics, business intelligence
- **Production Ready**: Built for enterprise environments with caching, batching, and error recovery
- **Easy Setup**: Configure once, use everywhere

## Quick Examples

```bash
# Start the MCP server
python mcp_checkmk_server.py --config config.yaml
```

Then in Claude Desktop or other MCP client:
- "Show me all critical problems in the infrastructure"
- "List services for server01"
- "Create a 2-hour downtime for database maintenance on prod-db-01"
- "What's the CPU usage trend for web servers this week?"
- "Acknowledge all disk space warnings with note 'investigating'"

## Quick Start

### Requirements
- Python 3.8+
- Checkmk 2.4.0+ server with REST API enabled
- MCP-compatible client (Claude Desktop, VS Code, etc.)

### Setup

1. **Install**:
```bash
git clone https://github.com/jlk/checkmk_mcp_server
cd checkmk_mcp_server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure** (choose ONE method):
```bash
# Option A: YAML config (recommended for most users)
cp examples/configs/development.yaml config.yaml
# Edit config.yaml with your Checkmk server details

# Option B: Environment variables (better for production/containers)
cp .env.example .env
# Edit .env with your Checkmk server details
```

3. **Run MCP Server**:
```bash
# With YAML config
python mcp_checkmk_server.py --config config.yaml

# With environment variables
python mcp_checkmk_server.py
```

4. **Connect your AI client** (see detailed setup in [Getting Started Guide](docs/getting-started.md))

That's it! Your AI assistant can now monitor your infrastructure.

## Key Features

- **37 Monitoring Tools**: Complete Checkmk operations through MCP protocol
- **Natural Language Interface**: Conversational monitoring and management
- **Production Scale**: Handle thousands of hosts with streaming and caching
- **Smart Parameter Management**: Intelligent defaults for different service types
- **Historical Data Access**: Scrape and analyze performance trends
- **Event Management**: Track, acknowledge, and manage infrastructure events
- **Business Intelligence**: Monitor high-level service health and SLAs

## Client Setup

### Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "checkmk": {
      "command": "python",
      "args": ["/path/to/mcp_checkmk_server.py", "--config", "config.yaml"]
    }
  }
}
```

### Other MCP Clients
Supports any MCP-compatible client including VS Code Continue extension. See [Getting Started Guide](docs/getting-started.md) for detailed setup instructions.

## Documentation

- **[Getting Started Guide](docs/getting-started.md)** - Step-by-step setup and configuration
- **[Usage Examples](docs/USAGE_EXAMPLES.md)** - Practical examples and common workflows
- **[Architecture Guide](docs/architecture.md)** - Technical architecture and design decisions
- **[Advanced Features](docs/ADVANCED_FEATURES.md)** - Streaming, caching, batch operations
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions

## What Can You Do?

**Infrastructure Health**: "Show me all critical problems and their business impact"

**Service Management**: "Create a 4-hour maintenance window for the database cluster"

**Performance Analysis**: "What's the CPU trend for web servers over the last week?"

**Event Investigation**: "Show me all disk-related events on server01 today"

**Bulk Operations**: "Acknowledge all network warnings until the upgrade completes"

**Historical Analysis**: "Extract temperature data for the server room from yesterday"

## System Requirements

- **Checkmk Version**: 2.4.0+ (for Event Console, Metrics API, and Business Intelligence features)
- **Python**: 3.8 or higher
- **Memory**: Scales with infrastructure size (caching and streaming handle large environments efficiently)
- **Network**: Requires REST API access to Checkmk server

## Support

For questions or issues:
1. Check the [troubleshooting guide](docs/troubleshooting.md)
2. Review [existing issues](../../issues)
3. Create a new issue with detailed information

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

**Status**: Production ready with full Checkmk 2.4 support including Event Console, Metrics API, and Business Intelligence features.