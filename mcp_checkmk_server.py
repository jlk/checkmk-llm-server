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
from checkmk_agent.mcp_server import CheckmkMCPServer


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration with request ID support."""
    # Import the proper logging setup function
    from checkmk_agent.logging_utils import setup_logging as proper_setup_logging
    
    # Use the proper setup with request ID support but output to stderr for MCP
    proper_setup_logging(log_level, include_request_id=True)
    
    # Ensure all handlers output to stderr to avoid interfering with stdio MCP transport
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if hasattr(handler, 'stream') and handler.stream != sys.stderr:
            handler.stream = sys.stderr


async def main():
    """Main entry point for the Enhanced Checkmk MCP server."""
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
    parser.add_argument(
        "--enable-caching",
        action="store_true",
        help="Enable caching layer for improved performance"
    )
    parser.add_argument(
        "--enable-streaming",
        action="store_true", 
        help="Enable streaming for large datasets"
    )
    parser.add_argument(
        "--enable-metrics",
        action="store_true",
        help="Enable performance monitoring and metrics collection"
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
        
        # Log core features (always available)
        logger.info("Core Features:")
        logger.info("  - ✓ Complete host and service management (28 tools)")
        logger.info("  - ✓ Event Console and metrics integration")
        logger.info("  - ✓ Business Intelligence and system info")
        
        # Log advanced features only if enabled
        advanced_features = []
        if args.enable_streaming:
            advanced_features.append("  - ✓ Streaming support for large datasets")
        if args.enable_caching:
            advanced_features.append("  - ✓ Caching layer for improved performance")
        if args.enable_metrics:
            advanced_features.append("  - ✓ Performance monitoring and metrics collection")
        
        if advanced_features:
            logger.info("Advanced Features Enabled:")
            for feature in advanced_features:
                logger.info(feature)
        else:
            logger.info("Advanced Features: Disabled (use --enable-* flags to enable)")
        
        # Always available features
        logger.info("  - ✓ Batch operations for bulk processing")
        logger.info("  - ✓ Advanced error recovery and resilience")
        
        # Create and initialize the server with feature flags
        server = CheckmkMCPServer(config)
        
        # Set advanced feature flags (server implementation can use these)
        server.enable_caching = args.enable_caching
        server.enable_streaming = args.enable_streaming  
        server.enable_metrics = args.enable_metrics
        
        await server.initialize()
        
        logger.info("MCP Server initialized, starting transport...")
        
        # Run the server
        await server.run(transport_type=args.transport)
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception:
        logger.exception("Fatal error in MCP server")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())