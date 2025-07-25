#!/usr/bin/env python3
"""
Checkmk Enhanced MCP Server Entry Point

This script starts the enhanced Checkmk MCP server with advanced features:
- Streaming support for large datasets
- Caching layer for improved performance  
- Batch operations for bulk processing
- Performance monitoring and metrics
- Advanced error recovery and resilience

Usage:
    python mcp_checkmk_enhanced_server.py [--config CONFIG_FILE] [--log-level LEVEL]

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
from checkmk_agent.mcp_server.enhanced_server import EnhancedCheckmkMCPServer


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
    """Main entry point for the Enhanced Checkmk MCP server."""
    parser = argparse.ArgumentParser(description="Enhanced Checkmk MCP Server")
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
    parser.add_argument(
        "--enable-caching",
        action="store_true",
        help="Enable caching layer (enabled by default)"
    )
    parser.add_argument(
        "--enable-streaming",
        action="store_true", 
        help="Enable streaming for large datasets (enabled by default)"
    )
    parser.add_argument(
        "--enable-metrics",
        action="store_true",
        help="Enable performance monitoring (enabled by default)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        logger.info("Starting Enhanced Checkmk MCP Server...")
        logger.info(f"Checkmk URL: {config.checkmk.server_url}")
        logger.info(f"Transport: {args.transport}")
        logger.info("Advanced Features:")
        logger.info("  - ✓ Streaming support for large datasets")
        logger.info("  - ✓ Caching layer for improved performance")
        logger.info("  - ✓ Batch operations for bulk processing")
        logger.info("  - ✓ Performance monitoring and metrics")
        logger.info("  - ✓ Advanced error recovery and resilience")
        
        # Create and initialize the enhanced server
        server = EnhancedCheckmkMCPServer(config)
        await server.initialize()
        
        logger.info("Enhanced MCP Server initialized, starting transport...")
        
        # Run the server
        await server.run(transport_type=args.transport)
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.exception("Fatal error in Enhanced MCP server")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())