#!/usr/bin/env python3
"""
Checkmk CLI - MCP Edition

This is the MCP-based version of the Checkmk CLI that uses the MCP server
as its backend instead of direct API calls.

Usage:
    checkmk_cli_mcp [OPTIONS] COMMAND [ARGS]...
    checkmk_cli_mcp interactive  # Start interactive mode
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from checkmk_mcp_server.cli_mcp import main


if __name__ == '__main__':
    main()