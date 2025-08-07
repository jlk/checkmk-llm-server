# Checkmk MCP Server Implementation (MCP-First Architecture)

## Overview
Transform the Checkmk LLM Agent into an MCP-first architecture where the MCP server becomes the primary interface, and the CLI becomes a specialized MCP client. This provides a unified service layer with multiple presentation formats: rich CLI interface and standardized MCP protocol.

## Architecture Vision: Service Layer + Multiple Clients

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Client    │    │  Claude Desktop │    │  Other MCP      │
│   (Rich UI)     │    │     Client      │    │   Clients       │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │              ┌───────┴──────────────────────┘
          │              │
          └──────────────┼──────────────────────────────────────┐
                         │                                      │
                ┌────────▼─────────┐                           │
                │   MCP Server     │                           │
                │  (Primary API)   │                           │
                └────────┬─────────┘                           │
                         │                                      │
                ┌────────▼─────────┐                           │
                │  Service Layer   │                           │
                │ (Business Logic) │                           │
                └────────┬─────────┘                           │
                         │                                      │
                ┌────────▼─────────┐                           │
                │  Checkmk API     │                           │
                │    Client        │                           │
                └──────────────────┘                           │
                                                               │
                ┌──────────────────────────────────────────────┘
                │
        ┌───────▼────────┐
        │ CLI Formatter  │
        │ (Rich Output)  │
        └────────────────┘
```

## Phase 0: Service Layer Refactoring (2-3 days)

### 0.1 Extract Business Logic from Presentation
Create a clean service layer that both MCP and CLI can consume:

```
checkmk_agent/
├── services/              # NEW: Core business services
│   ├── __init__.py
│   ├── base.py           # Base service with common patterns
│   ├── host_service.py   # Host operations business logic
│   ├── service_service.py # Service operations business logic
│   ├── status_service.py # Status monitoring business logic
│   ├── parameter_service.py # Parameter management logic
│   └── models/           # Structured response models
│       ├── __init__.py
│       ├── hosts.py
│       ├── services.py
│       └── status.py
├── formatters/           # NEW: Output formatters
│   ├── __init__.py
│   ├── cli_formatter.py  # Rich CLI formatting
│   └── base_formatter.py # Common formatting utilities
├── mcp_server/           # NEW: MCP server implementation
│   ├── __init__.py
│   ├── server.py         # Main MCP server
│   ├── tools/            # MCP tool definitions
│   ├── resources/        # MCP resource endpoints
│   └── prompts/          # MCP prompt templates
└── cli_client/           # NEW: CLI as MCP client
    ├── __init__.py
    ├── client.py         # MCP client for CLI
    └── interactive_ui.py # Interactive mode wrapper
```

### 0.2 Define Service Contracts
Create Pydantic models for all service responses:

```python
# checkmk_agent/services/models/hosts.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class HostInfo(BaseModel):
    name: str = Field(description="Host name")
    folder: str = Field(description="Checkmk folder path")
    ip_address: Optional[str] = Field(None, description="IP address")
    attributes: Dict[str, Any] = Field(default_factory=dict)
    status: Optional[str] = Field(None, description="Host status")

class HostListResult(BaseModel):
    hosts: List[HostInfo]
    total_count: int
    search_applied: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class HostCreateResult(BaseModel):
    host: HostInfo
    success: bool
    message: str
    warnings: List[str] = Field(default_factory=list)
```

## Phase 1: Core Service Implementation (2-3 days)

### 1.1 Update Dependencies
```text
# Add to requirements.txt
mcp>=1.0.0  # Official MCP Python SDK
asyncio-compat>=0.3.0  # For async compatibility
```

### 1.2 Implement Service Layer
```python
# checkmk_agent/services/host_service.py
from typing import Optional, Dict, Any
from ..api_client import CheckmkClient
from ..config import AppConfig
from .models.hosts import HostListResult, HostCreateResult, HostInfo

class HostService:
    """Core host operations service - presentation agnostic."""
    
    def __init__(self, checkmk_client: CheckmkClient, config: AppConfig):
        self.checkmk = checkmk_client
        self.config = config
    
    async def list_hosts(
        self, 
        search: Optional[str] = None,
        folder: Optional[str] = None,
        limit: Optional[int] = None
    ) -> HostListResult:
        """List hosts with optional filtering."""
        hosts_data = await self.checkmk.list_hosts()
        
        # Apply filtering logic
        filtered_hosts = self._apply_filters(hosts_data, search, folder)
        
        # Convert to structured models
        hosts = [HostInfo.model_validate(host) for host in filtered_hosts]
        
        return HostListResult(
            hosts=hosts[:limit] if limit else hosts,
            total_count=len(filtered_hosts),
            search_applied=search,
            metadata={
                "filtered_count": len(hosts),
                "original_count": len(hosts_data)
            }
        )
    
    async def create_host(
        self,
        name: str,
        folder: str = "/",
        ip_address: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> HostCreateResult:
        """Create a new host with validation."""
        # Business logic and validation
        result = await self.checkmk.create_host(name, folder, ip_address, attributes or {})
        
        return HostCreateResult(
            host=HostInfo.model_validate(result),
            success=True,
            message=f"Successfully created host {name}"
        )
```

## Phase 2: MCP Server Implementation (3-4 days)

### 2.1 Core MCP Server with Official SDK
```python
# checkmk_agent/mcp_server/server.py
import asyncio
from mcp import Server
from mcp.types import Tool, Resource, TextContent, ImageContent
from pydantic import Field
from typing import Optional, Dict, Any, List

from ..services.host_service import HostService
from ..services.status_service import StatusService
from ..services.service_service import ServiceService
from ..api_client import CheckmkClient
from ..config import load_config

class CheckmkMCPServer:
    """MCP Server for Checkmk operations."""
    
    def __init__(self):
        self.server = Server("checkmk-monitoring")
        self.config = load_config()
        self.checkmk_client = CheckmkClient(self.config.checkmk)
        
        # Initialize services
        self.host_service = HostService(self.checkmk_client, self.config)
        self.status_service = StatusService(self.checkmk_client, self.config)
        self.service_service = ServiceService(self.checkmk_client, self.config)
        
        self._register_tools()
        self._register_resources()
        self._register_prompts()
    
    def _register_tools(self):
        """Register all MCP tools."""
        
        @self.server.tool("list_hosts")
        async def list_hosts(
            search: Optional[str] = Field(None, description="Search pattern for host names"),
            folder: Optional[str] = Field(None, description="Filter by Checkmk folder"),
            limit: Optional[int] = Field(None, description="Maximum number of hosts to return")
        ) -> Dict[str, Any]:
            """List Checkmk hosts with optional filtering."""
            result = await self.host_service.list_hosts(search, folder, limit)
            return result.model_dump()
        
        @self.server.tool("create_host")
        async def create_host(
            name: str = Field(description="Unique host identifier"),
            folder: str = Field(default="/", description="Checkmk folder path"),
            ip_address: Optional[str] = Field(None, description="Host IP address"),
            attributes: Optional[Dict[str, str]] = Field(None, description="Additional host attributes")
        ) -> Dict[str, Any]:
            """Create a new host in Checkmk."""
            result = await self.host_service.create_host(name, folder, ip_address, attributes)
            return result.model_dump()
        
        @self.server.tool("get_health_dashboard")
        async def get_health_dashboard() -> Dict[str, Any]:
            """Get comprehensive service health dashboard."""
            result = await self.status_service.get_health_dashboard()
            return result.model_dump()
        
        @self.server.tool("list_service_problems")
        async def list_service_problems(
            severity: Optional[str] = Field(None, description="Filter by severity: critical, warning, unknown"),
            host_filter: Optional[str] = Field(None, description="Filter by host name pattern")
        ) -> Dict[str, Any]:
            """List services with problems."""
            result = await self.status_service.list_problems(severity, host_filter)
            return result.model_dump()
        
        @self.server.tool("acknowledge_service")
        async def acknowledge_service(
            host_name: str = Field(description="Host name"),
            service_name: str = Field(description="Service name"),
            comment: str = Field(default="Acknowledged via MCP", description="Acknowledgment comment"),
            sticky: bool = Field(default=True, description="Keep acknowledgment until service recovers")
        ) -> Dict[str, Any]:
            """Acknowledge a service problem."""
            result = await self.service_service.acknowledge_problem(host_name, service_name, comment, sticky)
            return result.model_dump()
    
    def _register_resources(self):
        """Register MCP resources for real-time data."""
        
        @self.server.resource("checkmk://hosts")
        async def hosts_inventory() -> TextContent:
            """Current host inventory with status summary."""
            result = await self.host_service.list_hosts()
            return TextContent(
                type="text",
                text=result.model_dump_json(indent=2)
            )
        
        @self.server.resource("checkmk://status/overview")
        async def status_overview() -> TextContent:
            """Overall system health metrics."""
            result = await self.status_service.get_health_dashboard()
            return TextContent(
                type="text", 
                text=result.model_dump_json(indent=2)
            )
        
        @self.server.resource("checkmk://services/{host_name}")
        async def host_services(host_name: str) -> TextContent:
            """All services for specified host."""
            result = await self.service_service.list_host_services(host_name)
            return TextContent(
                type="text",
                text=result.model_dump_json(indent=2)
            )
    
    def _register_prompts(self):
        """Register prompt templates for common workflows."""
        
        @self.server.prompt("system_health_analysis")
        async def system_health_analysis():
            """Comprehensive system health analysis workflow."""
            return """
You are a Checkmk monitoring expert. Analyze the current system health using these steps:

1. Get the health dashboard overview
2. Identify critical and warning services  
3. Categorize problems by type (performance, connectivity, etc.)
4. Provide prioritized recommendations for resolution
5. Suggest monitoring improvements if patterns emerge

Focus on actionable insights and business impact assessment.
"""
        
        @self.server.prompt("troubleshooting_guide")
        async def troubleshooting_guide():
            """Service problem troubleshooting workflow."""
            return """
You are troubleshooting a Checkmk service issue. Follow this systematic approach:

1. Gather service details and current status
2. Check related services on the same host
3. Review recent acknowledgments and downtimes
4. Analyze historical patterns if available
5. Provide step-by-step troubleshooting recommendations
6. Suggest preventive measures

Always consider the business impact and urgency level.
"""

async def main():
    """Run the MCP server."""
    server = CheckmkMCPServer()
    
    # Run with stdio transport (for Claude Desktop)
    from mcp.server.stdio import stdio_server
    async with stdio_server() as streams:
        await server.server.run(*streams)

if __name__ == "__main__":
    asyncio.run(main())
```

### 2.2 Enhanced Configuration
```yaml
# Extended config.yaml
checkmk:
  server_url: "https://your-checkmk-server.com"
  username: "automation_user"
  password: "your_secure_password"
  site: "mysite"

llm:
  openai_api_key: "sk-..."
  anthropic_api_key: "sk-ant-..."
  
mcp:
  server:
    name: "checkmk-monitoring"
    description: "Checkmk infrastructure monitoring and management"
    version: "1.0.0"
    transport: "stdio"  # or "http" for HTTP transport
    host: "localhost"   # for HTTP transport
    port: 8080         # for HTTP transport
  
  tools:
    enabled: ["host_*", "service_*", "status_*"]
    rate_limit: 20  # requests per minute
    timeout: 30     # seconds
    
  resources:
    cache_ttl: 300  # seconds
    streaming_threshold: 100  # switch to streaming for large responses
    max_batch_size: 1000
    
  auth:
    required: false  # Enable for production
    method: "api_key"
    api_key: "your-mcp-api-key"
```

## Phase 3: CLI as MCP Client (2-3 days)

### 3.1 CLI MCP Client Implementation
```python
# checkmk_agent/cli_client/client.py
import asyncio
from mcp import Client
from mcp.client.stdio import stdio_client
from typing import Any, Dict, Optional

class CheckmkCLIClient:
    """CLI client that connects to the MCP server."""
    
    def __init__(self):
        self.client = None
        self.connected = False
    
    async def connect(self):
        """Connect to the MCP server."""
        if not self.connected:
            # Connect to local MCP server
            self.client = await stdio_client()
            self.connected = True
    
    async def list_hosts(self, search: Optional[str] = None) -> Dict[str, Any]:
        """List hosts via MCP."""
        await self.connect()
        result = await self.client.call_tool("list_hosts", {"search": search})
        return result.content
    
    async def create_host(self, name: str, folder: str = "/", ip_address: Optional[str] = None) -> Dict[str, Any]:
        """Create host via MCP."""
        await self.connect()
        result = await self.client.call_tool("create_host", {
            "name": name,
            "folder": folder, 
            "ip_address": ip_address
        })
        return result.content
    
    async def get_health_dashboard(self) -> Dict[str, Any]:
        """Get health dashboard via MCP."""
        await self.connect()
        result = await self.client.call_tool("get_health_dashboard", {})
        return result.content
```

### 3.2 Enhanced CLI with Rich Formatting
```python
# checkmk_agent/cli_client/interactive_ui.py
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
from ..formatters.cli_formatter import CLIFormatter

class InteractiveCLI:
    """Enhanced CLI interface using MCP client."""
    
    def __init__(self):
        self.console = Console()
        self.mcp_client = CheckmkCLIClient()
        self.formatter = CLIFormatter()
    
    async def handle_list_hosts(self, search: Optional[str] = None):
        """Handle list hosts command with rich formatting."""
        with Progress() as progress:
            task = progress.add_task("Fetching hosts...", total=100)
            
            # Get data from MCP server
            data = await self.mcp_client.list_hosts(search)
            progress.update(task, advance=50)
            
            # Format for CLI display
            formatted_output = self.formatter.format_host_list(data)
            progress.update(task, advance=50)
        
        self.console.print(formatted_output)
    
    async def handle_health_dashboard(self):
        """Display health dashboard with rich formatting."""
        data = await self.mcp_client.get_health_dashboard()
        formatted_output = self.formatter.format_health_dashboard(data)
        self.console.print(formatted_output)
```

## Phase 4: Advanced Features (2-3 days)

### 4.1 Streaming Resources for Large Datasets
```python
@self.server.resource("checkmk://hosts/stream")
async def hosts_stream() -> TextContent:
    """Streaming host data for large environments."""
    async def generate_host_data():
        async for batch in self.host_service.list_hosts_streamed():
            yield batch.model_dump_json() + "\n"
    
    return TextContent(
        type="text",
        text="".join([chunk async for chunk in generate_host_data()])
    )
```

### 4.2 Enhanced Error Handling
```python
# checkmk_agent/services/base.py
from typing import TypeVar, Generic, Union
from pydantic import BaseModel

T = TypeVar('T')

class ServiceResult(BaseModel, Generic[T]):
    """Standard service result wrapper."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseService:
    """Base service with common error handling."""
    
    async def _execute_with_error_handling(self, operation) -> ServiceResult:
        """Execute operation with standardized error handling."""
        try:
            result = await operation()
            return ServiceResult(success=True, data=result)
        except CheckmkAPIError as e:
            return ServiceResult(success=False, error=f"Checkmk API error: {e}")
        except Exception as e:
            self.logger.exception("Unexpected error in service operation")
            return ServiceResult(success=False, error=f"Internal error: {e}")
```

## Phase 5: Integration & Testing (2-3 days)

### 5.1 Preserve and Extend Test Suite
```python
# tests/test_mcp_integration.py
import pytest
from checkmk_agent.mcp_server.server import CheckmkMCPServer
from checkmk_agent.cli_client.client import CheckmkCLIClient

@pytest.mark.asyncio
async def test_mcp_cli_integration():
    """Test that CLI commands work through MCP server."""
    # Start MCP server
    server = CheckmkMCPServer()
    
    # Connect CLI client
    cli_client = CheckmkCLIClient()
    
    # Test host operations
    result = await cli_client.list_hosts()
    assert result["success"] is True
    assert "hosts" in result
```

### 5.2 Claude Desktop Integration
```json
// examples/claude_desktop_config.json
{
  "mcpServers": {
    "checkmk-monitoring": {
      "command": "python",
      "args": ["-m", "checkmk_agent.mcp_server.server"],
      "cwd": "/path/to/checkmk_llm_agent",
      "env": {
        "CHECKMK_CONFIG_FILE": "/path/to/config.yaml"
      }
    }
  }
}
```

## Updated Timeline: 12-15 days

## Key Benefits of MCP-First Architecture

1. **Unified Service Layer**: Single source of truth for business logic
2. **Protocol Standardization**: MCP provides standardized interfaces
3. **Future-Proof**: Easy to add new clients (web UI, mobile, etc.)
4. **Better Testing**: Service layer can be tested independently
5. **Consistent Behavior**: All clients use the same underlying services
6. **Rich CLI Preserved**: CLI becomes even more powerful as an MCP client

## Success Criteria

- [ ] All existing CLI functionality works through MCP client
- [ ] MCP server provides comprehensive tool coverage
- [ ] Service layer successfully abstracts business logic
- [ ] Resources support real-time and streaming data
- [ ] Claude Desktop integration functional
- [ ] Performance meets or exceeds current CLI
- [ ] Test coverage maintained across all layers
- [ ] Documentation covers both development and usage

## Risk Mitigation

- Create feature branch for MCP implementation
- Service layer can be tested independently of presentation layers
- Gradual migration path preserves existing functionality
- Rollback plan: Service layer enhances rather than replaces current architecture