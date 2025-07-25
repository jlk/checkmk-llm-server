#!/usr/bin/env python3
"""
Checkmk MCP Server Entry Point

This script starts the Checkmk MCP (Model Context Protocol) server,
providing LLM tools for comprehensive infrastructure monitoring and management.

Usage:
    python mcp_checkmk_server.py [--config CONFIG_FILE] [--log-level LEVEL]

The server will run on stdio by default for MCP client integration.
"""

import sys
import asyncio
import logging
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from checkmk_agent.config import load_config
from checkmk_agent.mcp_server import CheckmkMCPServer


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)  # Use stderr to avoid interfering with stdio MCP transport
        ]
    )


async def main():
    """Main entry point for the Checkmk MCP server."""
    parser = argparse.ArgumentParser(description="Checkmk MCP Server")
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file"
    )
    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level"
    )
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio"],
        default="stdio",
        help="Transport type for MCP server"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        logger.info("Starting Checkmk MCP Server...")
        logger.info(f"Checkmk URL: {config.checkmk.server_url}")
        logger.info(f"Transport: {args.transport}")
        
        # Create and initialize the server
        server = CheckmkMCPServer(config)
        await server.initialize()
        
        logger.info("MCP Server initialized, starting transport...")
        
        # Run the server
        await server.run(transport_type=args.transport)
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.exception("Fatal error in MCP server")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())